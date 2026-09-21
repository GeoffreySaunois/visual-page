"""`render`, `pdf` and `gallery` — turning a source into a page, putting a page on
paper, and listing the archive."""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

from .. import gallery, pdf, server
from ..document import SourceError
from ..paths import Archive, default_archive
from ..rendering import IterationMode, RenderOutcome, RenderRequest, render
from . import console, remote

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
    render_parser = subparsers.add_parser(
        "render", help="compiler une source en page HTML"
    )
    render_parser.add_argument("source", help="fichier markdown source")
    render_parser.add_argument(
        "--kind",
        type=kind,
        default="report",
        metavar="|".join(KNOWN_KINDS),
        help="famille de page : décide le nom du fichier et l'identité du document",
    )
    render_parser.add_argument(
        "-o", "--output", help="chemin de sortie explicite (hors archive)"
    )
    render_parser.add_argument(
        "--open", action="store_true", help="ouvrir la page à la fin"
    )
    render_parser.add_argument(
        "--serve",
        action="store_true",
        help="publier la page commentable sur Artefacts",
    )
    render_parser.add_argument(
        "--local", action="store_true", help="aperçu local explicite avec --serve"
    )
    render_parser.add_argument(
        "--no-index", action="store_true", help="ne pas régénérer la galerie"
    )
    render_parser.add_argument(
        "--pdf",
        action="store_true",
        help="imprimer aussi la page en PDF, à côté d'elle dans l'archive",
    )
    iteration = render_parser.add_mutually_exclusive_group()
    iteration.add_argument(
        "--diff",
        action="store_true",
        help="forcer le diff d'itération (erreur si pas de version précédente)",
    )
    iteration.add_argument(
        "--no-diff", action="store_true", help="désactiver le diff d'itération"
    )
    render_parser.set_defaults(handler=run_render)

    pdf_parser = subparsers.add_parser(
        "pdf", help="imprimer une page de l'archive en PDF"
    )
    pdf_parser.add_argument(
        "document", help="identité du document (<kind>-<slug>) ou chemin d'une page"
    )
    pdf_parser.add_argument(
        "-o", "--output", help="chemin du PDF (défaut : à côté de la page)"
    )
    pdf_parser.set_defaults(handler=run_pdf)

    gallery_parser = subparsers.add_parser(
        "gallery", help="régénérer l'index de l'archive"
    )
    gallery_parser.set_defaults(handler=run_gallery)


def run_render(args: argparse.Namespace) -> None:
    archive = default_archive()
    request = RenderRequest(
        source=Path(args.source).resolve(),
        kind=args.kind,
        output=Path(args.output) if args.output else None,
        iteration=iteration_mode(args),
        archive=archive,
        refresh=None,
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
        console.say(
            f"itération : {outcome.changes} changement(s) depuis la version précédente"
        )
    if outcome.threads is not None and outcome.threads.total:
        console.say(f"commentaires : {outcome.threads.summary()}")
    if not args.no_index:
        index, count = gallery.rebuild(archive)
        console.say(f"galerie : {index} ({count} page(s))")
    if args.pdf:
        # A page that renders but does not print is still a page: a browser
        # missing or refusing costs a warning, never the render.
        print_page(outcome.page, output=None)
    open_page(outcome, archive, args)


def open_page(outcome: RenderOutcome, archive, args: argparse.Namespace) -> None:
    """Publish a commentable page without opening or starting a local process."""
    if args.serve and not args.local:
        console.say(
            f"commentable : {remote.publish(outcome.page, Path(args.source), True)}"
        )
    elif args.serve:
        running = server.ensure_running(archive, server.DEFAULT_PORT)
        console.say(f"aperçu local : {running.page_url(outcome.page)}")
    elif args.open:
        subprocess.run(["open", str(outcome.page)], check=False)


def run_pdf(args: argparse.Namespace) -> None:
    """Print a page the archive already holds. Re-rendering it just to get a PDF
    would advance the document — a new iteration reference, threads re-homed —
    so the export reads the published page and changes nothing."""
    archive = default_archive()
    page = page_to_print(archive, args.document)
    if page is None:
        console.fail(f"aucune page pour {args.document!r} dans {archive.root}")
        return
    if print_page(page, Path(args.output) if args.output else None) is None:
        raise SystemExit(1)


def page_to_print(archive: Archive, target: str) -> Path | None:
    """The `pdf` argument is either the path of a page or a document identity,
    in which case the document's most recent page is the one printed."""
    candidate = Path(target)
    if candidate.suffix == ".html" and candidate.is_file():
        return candidate.resolve()
    return archive.latest_page(target)


def print_page(page: Path, output: Path | None) -> Path | None:
    """Print a page and say where the PDF landed — None when it could not be
    printed, the message already said why."""
    try:
        written = pdf.export(page, output or pdf.companion(page))
    except pdf.PrintError as error:
        console.warn(str(error))
        return None
    console.say(f"pdf : {written}")
    return written


def run_gallery(args: argparse.Namespace) -> None:
    index, count = gallery.rebuild(default_archive())
    console.say(f"galerie : {index} ({count} page(s))")
