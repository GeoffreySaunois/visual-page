"""Running the server in the background, and finding it again.

The state file next to the archive records the pid and port of the running
instance, so `render --serve` reuses it instead of stacking servers, and `status`
and `stop` have something to act on. The mechanics of a detached process live in
`detached.py`; what is here is the server's own command line, state and health
check.
"""

from __future__ import annotations

import sys
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from ..paths import Archive
from .app import DEFAULT_PORT, HOST
from .detached import DetachedProcess, LaunchError

STARTUP_TIMEOUT_S = 8.0


@dataclass(frozen=True)
class Running:
    pid: int
    port: int
    started_at: str

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> Running:
        return cls(
            pid=int(state["pid"]),  # type: ignore[arg-type]
            port=int(state["port"]),  # type: ignore[arg-type]
            started_at=str(state["started_at"]),
        )

    @property
    def url(self) -> str:
        return f"http://{HOST}:{self.port}"

    def page_url(self, page: Path) -> str:
        return f"{self.url}/{page.name}"


def process(archive: Archive) -> DetachedProcess:
    return DetachedProcess(
        state_path=archive.server_state,
        log_path=archive.logs / "server.log",
        label="le serveur",
        timeout_s=STARTUP_TIMEOUT_S,
    )


def status(archive: Archive) -> Running | None:
    """The running instance, or None — a state file whose process died is ignored."""
    state = process(archive).recorded()
    if state is None:
        return None
    try:
        return Running.from_state(state)
    except (KeyError, TypeError, ValueError):
        return None


def ensure_running(archive: Archive, port: int) -> Running:
    running = status(archive)
    if running is not None:
        return running
    return start(archive, port)


def start(archive: Archive, port: int) -> Running:
    """Spawn a detached server and wait until it answers."""
    if (running := status(archive)) is not None:
        raise LaunchError(f"un serveur tourne déjà (pid {running.pid}, {running.url})")
    server = process(archive)
    state = server.launch(command(archive, port), port=port)
    running = Running.from_state(state)
    server.await_ready(running.pid, lambda: healthy(running))
    return running


def stop(archive: Archive) -> Running | None:
    running = status(archive)
    process(archive).halt()
    return running


def command(archive: Archive, port: int) -> list[str]:
    return [
        sys.executable,
        "-m",
        "visualreport.server",
        "--port",
        str(port),
        "--archive",
        str(archive.root),
    ]


def healthy(running: Running) -> bool:
    try:
        with urllib.request.urlopen(f"{running.url}/api/health", timeout=1) as response:
            return response.status == 200
    except (urllib.error.URLError, TimeoutError, ConnectionError):
        return False


def default_port() -> int:
    return DEFAULT_PORT
