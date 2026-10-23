"""Explicit local preview server controls; hosted publication uses render --serve."""

from __future__ import annotations

import argparse
import subprocess

from .. import server
from ..paths import Archive, default_archive
from . import console


def add_parsers(subparsers: argparse._SubParsersAction) -> None:
    serve = subparsers.add_parser("serve", help="démarrer un aperçu local explicite")
    serve.add_argument("--port", type=int, default=server.DEFAULT_PORT)
    serve.add_argument(
        "--foreground",
        action="store_true",
        help="rester au premier plan (logs à l'écran)",
    )
    serve.add_argument("--open", action="store_true", help="ouvrir la galerie servie")
    serve.set_defaults(handler=run_serve)

    status = subparsers.add_parser("status", help="état du serveur local")
    status.set_defaults(handler=run_status)

    stop = subparsers.add_parser("stop", help="arrêter le serveur local")
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
    if args.open:
        subprocess.run(["open", running.url], check=False)


def serve_in_terminal(archive: Archive, port: int) -> None:
    """Run an explicit loopback preview in the terminal."""
    import uvicorn

    console.say(f"serveur au premier plan sur http://{server.HOST}:{port}")
    uvicorn.run(server.create_app(archive), host=server.HOST, port=port)


def run_status(args: argparse.Namespace) -> None:
    archive = default_archive()
    running = server.status(archive)
    if running is None:
        console.say("serveur arrêté")
    else:
        console.say(
            f"serveur : {running.url} (pid {running.pid}, depuis {running.started_at})"
        )


def run_stop(args: argparse.Namespace) -> None:
    archive = default_archive()
    running = server.stop(archive)
    console.say("serveur arrêté" if running else "aucun serveur en cours")
