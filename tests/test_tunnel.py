"""The two pieces of the tunnel that can be wrong without anything crashing:
what is read out of the cloudflared config, and the address a page ends up at."""

from __future__ import annotations

from pathlib import Path

import pytest

from visualreport.server import tunnel

FULL_CONFIG = """
tunnel: fdd51682-88d0-4a34-9da7-374e6664c8d8
credentials-file: /Users/someone/.cloudflared/fdd51682.json

ingress:
  - hostname: reports.example.test
    service: http://127.0.0.1:8787
  - service: http_status:404
"""


@pytest.fixture
def config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Point the reader at a fabricated config, and return a writer for it."""
    path = tmp_path / "config.yml"
    monkeypatch.setenv(tunnel.CONFIG_ENV, str(path))

    def write(text: str) -> Path:
        path.write_text(text, encoding="utf-8")
        return path

    return write


def test_reads_the_tunnel_and_its_hostname(config) -> None:
    config(FULL_CONFIG)
    ingress = tunnel.configured()
    assert ingress is not None
    assert ingress.tunnel == "fdd51682-88d0-4a34-9da7-374e6664c8d8"
    # The catch-all is a rule too, and naming no hostname it must not be read as
    # the archive's address.
    assert ingress.hostname == "reports.example.test"


def test_no_config_means_no_remote(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(tunnel.CONFIG_ENV, str(tmp_path / "absent.yml"))
    assert tunnel.configured() is None


def test_an_ingress_without_any_hostname_means_no_remote(config) -> None:
    config("tunnel: t-1\ningress:\n  - service: http_status:404\n")
    assert tunnel.configured() is None


def test_a_config_without_a_tunnel_means_no_remote(config) -> None:
    config("ingress:\n  - hostname: reports.example.test\n    service: http://127.0.0.1:8787\n")
    assert tunnel.configured() is None


def test_unreadable_yaml_means_no_remote(config) -> None:
    config("tunnel: [unclosed\n")
    assert tunnel.configured() is None


def test_a_page_is_published_under_the_configured_hostname() -> None:
    running = tunnel.Tunnel(
        pid=42, metrics_port=8788, hostname="reports.example.test", started_at="2026-08-10T10:00:00"
    )
    page = Path("/Users/someone/.claude/html-reports/report-gym-costs-2026-08-10.html")
    assert (
        running.page_url(page)
        == "https://reports.example.test/report-gym-costs-2026-08-10.html"
    )


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"status": 200, "readyConnections": 4}, True),
        ({"status": 200, "readyConnections": 0}, False),
        ({"status": 200}, False),
        ("nope", False),
    ],
)
def test_readiness_needs_a_connection_to_the_edge(payload: object, expected: bool) -> None:
    # cloudflared answers /ready with 200 while it is still dialing, so the count
    # is the only thing that says the hostname is actually served.
    assert tunnel.established(payload) is expected
