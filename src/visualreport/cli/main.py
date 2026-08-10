"""The `visual-report` command line.

    render    compiler une source markdown en page HTML
    refresh   régénérer des pages de l'archive avec les gabarits courants
    serve     démarrer le serveur local (requis pour commenter) et le tunnel
    status    état du serveur et du tunnel, et l'adresse publique de l'archive
    stop      arrêter le serveur et le tunnel
    comments  afficher les fils d'un document
    comment   ouvrir un fil (avec --quote pour viser un passage)
    reply     répondre dans un fil
    resolve   résoudre un fil
    reopen    réouvrir un fil
    gallery   régénérer l'index de l'archive
"""

from __future__ import annotations

import argparse

from ..comments import CommentError
from . import console, discussion, document, refresh, serving


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="visual-report",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    document.add_parsers(subparsers)
    refresh.add_parsers(subparsers)
    serving.add_parsers(subparsers)
    discussion.add_parsers(subparsers)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        args.handler(args)
    except CommentError as error:
        console.fail(str(error))
