"""`serve`, `status`, `stop` — the local server that makes a page writable, and
the tunnel that makes it readable from anywhere."""

from __future__ import annotations

import argparse
import subprocess

from .. import server
from ..paths import Archive, default_archive
from . import console


def add_parsers(subparsers: argparse._SubParsersAction) -> None:
    serve = subparsers.add_parser("serve", help="démarrer le serveur de commentaires")
    serve.add_argument("--port", type=int, default=server.DEFAULT_PORT)
    serve.add_argument(
        "--foreground",
        action="store_true",
        help="rester au premier plan (logs à l'écran) ; ne touche pas au tunnel",
    )
    serve.add_argument("--open", action="store_true", help="ouvrir la galerie servie")
    serve.set_defaults(handler=run_serve)

    status = subparsers.add_parser("status", help="état du serveur et du tunnel")
    status.set_defaults(handler=run_status)

    stop = subparsers.add_parser("stop", help="arrêter le serveur et le tunnel")
    stop.set_defaults(handler=run_stop)


def run_serve(args: argparse.Namespace) -> None:
    archive = default_archive()
    if args.foreground:
        serve_in_terminal(archive, args.port)
        return
    try:
        running = server.ensure_running(archive, args.port)
    except server.LaunchError as error:
        console.fail(str(error))
        return
    console.say(f"serveur : {running.url} (pid {running.pid})")
    if (tunnel := publish(archive)) is not None:
        console.say(f"public : {tunnel.url} (pid {tunnel.pid})")
    if args.open:
        subprocess.run(["open", running.url], check=False)


def serve_in_terminal(archive: Archive, port: int) -> None:
    """The foreground mode is a debugging one: it shows the server's own logs and
    owns nothing else. It leaves the tunnel exactly as it found it — one already up
    keeps publishing the port its ingress rule names, and one started here would
    outlive the terminal that reads the logs, or die with a Ctrl-C meant for the
    server. `serve` and `stop` are what own the pair."""
    import uvicorn

    console.say(f"serveur au premier plan sur http://{server.HOST}:{port}")
    uvicorn.run(server.create_app(archive), host=server.HOST, port=port)


def publish(archive: Archive) -> server.Tunnel | None:
    """Start the tunnel alongside the server, and hand it back to whoever prints
    an address — None when this machine publishes nothing.

    The remote side is a bonus: a machine without a cloudflared config gets no
    tunnel and no warning, and a tunnel that refuses to come up is a warning.
    Neither ever costs the local server — being unable to serve because Cloudflare
    is down would be the worse failure of the two.
    """
    try:
        return server.tunnel.ensure_running(archive)
    except server.LaunchError as error:
        console.warn(f"{error} — l'archive reste servie en local")
        return None


def run_status(args: argparse.Namespace) -> None:
    archive = default_archive()
    running = server.status(archive)
    if running is None:
        console.say("serveur arrêté")
    else:
        console.say(f"serveur : {running.url} (pid {running.pid}, depuis {running.started_at})")
    report_tunnel(archive)


def report_tunnel(archive: Archive) -> None:
    """A machine with no cloudflared config hears nothing about a tunnel — the
    remote side is opt-in, and its absence is not a state to report."""
    tunnel = server.tunnel.status(archive)
    if tunnel is not None:
        console.say(f"public : {tunnel.url} (pid {tunnel.pid}, depuis {tunnel.started_at})")
    elif server.tunnel.configured() is not None:
        console.say("tunnel arrêté — l'archive n'est joignable qu'en local")


def run_stop(args: argparse.Namespace) -> None:
    archive = default_archive()
    running = server.stop(archive)
    console.say("serveur arrêté" if running else "aucun serveur en cours")
    if server.tunnel.stop(archive) is not None:
        console.say("tunnel arrêté")
