"""The `visual-report` command line.

render    compiler une source markdown en page HTML
pdf       imprimer une page de l'archive en PDF (navigateur headless)
refresh   régénérer des pages de l'archive avec les gabarits courants
serve     démarrer un aperçu local explicite
status    état du serveur local
stop      arrêter le serveur local
comments  afficher les fils d'un document
comment   ouvrir un fil (avec --quote pour viser un passage)
reply     répondre dans un fil
resolve   résoudre un fil
reopen    réouvrir un fil
gallery   régénérer l'index de l'archive
share     donner ou retirer l'accès à un document ou à un dossier
shares    qui a accès à quoi sur Artefacts
"""

from __future__ import annotations

import argparse

from ..comments import CommentError
from . import console, discussion, document, refresh, serving, sharing


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
    sharing.add_parsers(subparsers)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        args.handler(args)
    except (CommentError, RuntimeError) as error:
        console.fail(str(error))
