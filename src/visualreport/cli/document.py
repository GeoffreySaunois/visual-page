"""`render` and `gallery` — turning a source into a page, and listing the archive."""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

from .. import gallery, server
from ..document import SourceError
from ..paths import default_archive
from ..rendering import IterationMode, RenderOutcome, RenderRequest, render
from . import console, serving

# The families in use; the flag accepts any dash-free token, so a new one needs
# no code change. A dash would make `<kind>-<slug>` ambiguous.
KNOWN_KINDS = ("report", "plan", "recap", "uidiff")
KIND_RE = re.compile(r"^[a-z][a-z0-9]*$")


def kind(value: str) -> str:
    if not KIND_RE.match(value):
        raise argparse.ArgumentTypeError(
            f"famille invalide : {value!r} — minuscules et chiffres, sans tiret"
        )
    return value


def add_parsers(subparsers: argparse._SubParsersAction) -> None:
    render_parser = subparsers.add_parser("render", help="compiler une source en page HTML")
    render_parser.add_argument("source", help="fichier markdown source")
    render_parser.add_argument(
        "--kind",
        type=kind,
        default="report",
        metavar="|".join(KNOWN_KINDS),
        help="famille de page : décide le nom du fichier et l'identité du document",
    )
    render_parser.add_argument("-o", "--output", help="chemin de sortie explicite (hors archive)")
    render_parser.add_argument("--open", action="store_true", help="ouvrir la page à la fin")
    render_parser.add_argument(
        "--serve",
        action="store_true",
        help="démarrer serveur et tunnel si besoin, ouvrir la page et donner ses deux "
        "adresses (nécessaire pour commenter)",
    )
    render_parser.add_argument("--no-index", action="store_true", help="ne pas régénérer la galerie")
    iteration = render_parser.add_mutually_exclusive_group()
    iteration.add_argument(
        "--diff", action="store_true", help="forcer le diff d'itération (erreur si pas de version précédente)"
    )
    iteration.add_argument("--no-diff", action="store_true", help="désactiver le diff d'itération")
    render_parser.set_defaults(handler=run_render)

    gallery_parser = subparsers.add_parser("gallery", help="régénérer l'index de l'archive")
    gallery_parser.set_defaults(handler=run_gallery)


def run_render(args: argparse.Namespace) -> None:
    archive = default_archive()
    request = RenderRequest(
        source=Path(args.source).resolve(),
        kind=args.kind,
        output=Path(args.output) if args.output else None,
        iteration=iteration_mode(args),
        archive=archive,
    )
    try:
        outcome = render(request)
    except SourceError as error:
        console.fail(str(error))
        return
    for warning in outcome.warnings:
        console.warn(warning)
    report(outcome, archive, args)


def iteration_mode(args: argparse.Namespace) -> IterationMode:
    if args.diff:
        return IterationMode.FORCE
    if args.no_diff:
        return IterationMode.OFF
    return IterationMode.AUTO


def report(outcome: RenderOutcome, archive, args: argparse.Namespace) -> None:
    console.say(f"page : {outcome.page}")
    if outcome.changes is not None:
        console.say(f"itération : {outcome.changes} changement(s) depuis la version précédente")
    if outcome.threads is not None and outcome.threads.total:
        console.say(f"commentaires : {outcome.threads.summary()}")
    if not args.no_index:
        index, count = gallery.rebuild(archive)
        console.say(f"galerie : {index} ({count} page(s))")
    open_page(outcome, archive, args)


def open_page(outcome: RenderOutcome, archive, args: argparse.Namespace) -> None:
    """`--serve` opens the page through the server, which is the only way the
    comment panel can write; `--open` alone opens the file directly."""
    if args.serve:
        running = server.ensure_running(archive, server.DEFAULT_PORT)
        console.say(f"serveur : {running.url} (pid {running.pid})")
        local = running.page_url(outcome.page)
        announce(local, serving.publish(archive), outcome.page)
        # The Mac opens the loopback address: same page, no Access round-trip.
        subprocess.run(["open", local], check=False)
    elif args.open:
        subprocess.run(["open", str(outcome.page)], check=False)


def announce(local: str, tunnel: server.Tunnel | None, page: Path) -> None:
    """The two addresses of a served page. The public one comes first: it is the
    link to hand over, the one that opens on a phone as well as on the Mac. With
    no tunnel, the loopback address is the only one there is."""
    if tunnel is None:
        console.say(f"commentable : {local}")
        return
    console.say(f"commentable (téléphone ou Mac) : {tunnel.page_url(page)}")
    console.say(f"en local sur ce Mac : {local}")


def run_gallery(args: argparse.Namespace) -> None:
    index, count = gallery.rebuild(default_archive())
    console.say(f"galerie : {index} ({count} page(s))")
