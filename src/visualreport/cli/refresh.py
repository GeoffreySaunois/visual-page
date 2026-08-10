"""`refresh` — rebuilding archived pages with the current templates."""

from __future__ import annotations

import argparse

from .. import gallery, refresh
from ..paths import default_archive
from . import console


def add_parsers(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "refresh",
        help="régénérer des pages de l'archive avec les gabarits courants",
    )
    parser.add_argument(
        "document",
        nargs="?",
        help="document à régénérer (<kind>-<slug>), toutes ses dates ; "
        "toute l'archive par défaut",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="lister ce qui serait réécrit, sans toucher à un seul fichier",
    )
    parser.set_defaults(handler=run_refresh)


def run_refresh(args: argparse.Namespace) -> None:
    archive = default_archive()
    if args.dry_run:
        preview(archive, args.document)
        return
    outcome = refresh.run(archive, args.document)
    for rewritten in outcome.rewritten:
        console.say(f"  {rewritten.page.path.name}")
        for warning in rewritten.warnings:
            console.warn(f"{rewritten.page.path.name} : {warning}")
    console.say(f"régénérées : {len(outcome.rewritten)} page(s)")
    announce_skipped(outcome.skipped)
    index, count = gallery.rebuild(archive)
    console.say(f"galerie : {index} ({count} page(s))")


def preview(archive, document: str | None) -> None:
    """What a real pass would rebuild. A source that fails to compile, or images
    a page cannot give back, only show up on the pass itself — reaching them
    means rendering, which is what this mode declines to do."""
    replayable, skipped = refresh.survey(archive, document)
    for page in replayable:
        console.say(f"  {page.path.name} ({page.day})")
    console.say(f"à régénérer : {len(replayable)} page(s) — rien n'a été écrit")
    announce_skipped(skipped)


def announce_skipped(skipped: list[refresh.Skipped]) -> None:
    if not skipped:
        return
    console.say(f"sautées : {len(skipped)} page(s)")
    for entry in skipped:
        console.say(f"  {entry.page.path.name} — {entry.reason}")
