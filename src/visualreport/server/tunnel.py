"""The archive's public address: the cloudflared tunnel that publishes it.

The local server binds loopback only, so a page is reachable from a phone through
a tunnel that dials it from the same machine. The remote side is **optional, and
its opt-in is the presence of a cloudflared config**: no file, no usable ingress
rule, or no `cloudflared` on the PATH means no tunnel at all — no error, and the
local behavior untouched. Nothing here is hard-coded about a particular domain.

`~/.cloudflared/config.yml` (moved by `VISUAL_REPORT_CLOUDFLARED_CONFIG`) is the
single source of truth: the tunnel to run and the hostname the archive answers on
are both read from it, so the engine and cloudflared can never disagree about
either. The tunnel's own state lives beside the server's, and its readiness is
read from cloudflared's metrics endpoint — the exact analogue of `/api/health`.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import yaml

from ..paths import Archive
from .detached import DetachedProcess, LaunchError

CLOUDFLARED = "cloudflared"
CONFIG_ENV = "VISUAL_REPORT_CLOUDFLARED_CONFIG"
DEFAULT_CONFIG = Path.home() / ".cloudflared" / "config.yml"
METRICS_HOST = "127.0.0.1"
METRICS_PORT = 8788
# Four QUIC connections to the edge take a few seconds on a cold start, and a
# flaky uplink retries; the server's 8s would call a healthy tunnel a failure.
STARTUP_TIMEOUT_S = 25.0


@dataclass(frozen=True)
class Ingress:
    """What the engine keeps of the cloudflared config: which tunnel to run, and
    the hostname it publishes the archive under."""

    tunnel: str
    hostname: str


@dataclass(frozen=True)
class Tunnel:
    pid: int
    metrics_port: int
    hostname: str
    started_at: str

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> Tunnel:
        return cls(
            pid=int(state["pid"]),  # type: ignore[arg-type]
            metrics_port=int(state["metrics_port"]),  # type: ignore[arg-type]
            hostname=str(state["hostname"]),
            started_at=str(state["started_at"]),
        )

    @property
    def url(self) -> str:
        return f"https://{self.hostname}"

    def page_url(self, page: Path) -> str:
        return f"{self.url}/{page.name}"


def config_path() -> Path:
    """Where the cloudflared config is read from. `VISUAL_REPORT_CLOUDFLARED_CONFIG`
    moves it — the way the tests point at a fabricated one."""
    override = os.environ.get(CONFIG_ENV)
    return Path(override).expanduser() if override else DEFAULT_CONFIG


def configured() -> Ingress | None:
    """The archive's ingress rule, or None when the remote side is not installed.

    A missing file, unreadable YAML, a config without a tunnel, and one whose
    ingress carries no hostname (a lone `http_status:404` catch-all) all mean the
    same thing: this machine serves locally only.
    """
    path = config_path()
    if not path.is_file():
        return None
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (yaml.YAMLError, OSError):
        return None
    if not isinstance(document, dict):
        return None
    name = str(document.get("tunnel") or "").strip()
    hostname = first_hostname(document.get("ingress"))
    if not name or not hostname:
        return None
    return Ingress(tunnel=name, hostname=hostname)


def first_hostname(ingress: object) -> str | None:
    """The hostname of the first ingress rule that carries one. Rules without a
    hostname — the catch-all every cloudflared config ends with — match anything
    and name nothing, so they are skipped rather than read as an address."""
    if not isinstance(ingress, list):
        return None
    for rule in ingress:
        if isinstance(rule, dict) and str(rule.get("hostname") or "").strip():
            return str(rule["hostname"]).strip()
    return None


def process(archive: Archive) -> DetachedProcess:
    return DetachedProcess(
        state_path=archive.tunnel_state,
        log_path=archive.logs / "tunnel.log",
        label="le tunnel",
        timeout_s=STARTUP_TIMEOUT_S,
    )


def status(archive: Archive) -> Tunnel | None:
    """The running tunnel, or None — a state file whose process died is ignored."""
    state = process(archive).recorded()
    if state is None:
        return None
    try:
        return Tunnel.from_state(state)
    except (KeyError, TypeError, ValueError):
        return None


def ensure_running(archive: Archive) -> Tunnel | None:
    """The tunnel publishing the archive, started if needed, or None when this
    machine has no remote side configured."""
    running = status(archive)
    if running is not None:
        return running
    return start(archive)


def start(archive: Archive) -> Tunnel | None:
    """Spawn a detached cloudflared and wait until it holds the edge. A machine
    with no config, or without the binary, publishes nothing and says so with a
    None rather than an error — that is the whole opt-in."""
    ingress = configured()
    if ingress is None or shutil.which(CLOUDFLARED) is None:
        return None
    if metrics_port_taken():
        raise LaunchError(
            f"un processus occupe déjà {METRICS_HOST}:{METRICS_PORT} — arrêter le "
            'cloudflared lancé hors du moteur (pkill -f "cloudflared tunnel run") '
            "puis relancer"
        )
    tunnel_process = process(archive)
    state = tunnel_process.launch(
        command(ingress),
        metrics_port=METRICS_PORT,
        hostname=ingress.hostname,
    )
    tunnel = Tunnel.from_state(state)
    try:
        tunnel_process.await_ready(tunnel.pid, lambda: ready(tunnel))
    except LaunchError:
        # A cloudflared that never reached the edge is not left behind: `status`
        # reads the state file, and a lingering pid would have it announce a
        # public address that answers 502.
        tunnel_process.halt()
        raise
    return tunnel


def stop(archive: Archive) -> Tunnel | None:
    running = status(archive)
    process(archive).halt()
    return running


def command(ingress: Ingress) -> list[str]:
    # `--metrics` is an option of the `tunnel` command, not of its `run`
    # subcommand: after `run`, cloudflared refuses the whole line. Pinning the
    # address is what makes the readiness probe findable — left alone,
    # cloudflared picks the first free port out of a list of five.
    return [
        CLOUDFLARED,
        "tunnel",
        "--metrics",
        f"{METRICS_HOST}:{METRICS_PORT}",
        "run",
        ingress.tunnel,
    ]


def metrics_port_taken() -> bool:
    """Whether something already listens on the metrics port.

    cloudflared exits when it cannot bind it, and the `/ready` answer would then
    come from that other process — a tunnel the engine neither started nor owns,
    reported as its own. Refusing to launch is the honest outcome.
    """
    with socket.socket() as probe:
        probe.settimeout(0.5)
        return probe.connect_ex((METRICS_HOST, METRICS_PORT)) == 0


def ready(tunnel: Tunnel) -> bool:
    """Whether cloudflared holds at least one connection to the edge — until then
    the hostname resolves but answers 502."""
    url = f"http://{METRICS_HOST}:{tunnel.metrics_port}/ready"
    try:
        with urllib.request.urlopen(url, timeout=1) as response:
            if response.status != 200:
                return False
            payload = json.loads(response.read())
    except (urllib.error.URLError, TimeoutError, ConnectionError, json.JSONDecodeError):
        return False
    return established(payload)


def established(payload: object) -> bool:
    """cloudflared answers `/ready` while it is still dialing the edge, with zero
    ready connections; only a positive count means the hostname is served."""
    if not isinstance(payload, dict):
        return False
    try:
        return int(payload.get("readyConnections") or 0) >= 1
    except (TypeError, ValueError):
        return False
