"""The comment commands — the agent's half of the loop.

Reading (`comments`) prints the open threads with the passage each points at.
Hosted writes use the authenticated API. --local explicitly selects the local
archive for a preview or offline work.
"""

from __future__ import annotations

import argparse

from .. import comments
from ..document import parse_source, split_blocks
from ..paths import Archive, default_archive
from . import console, remote, remote_discussion

AUTHORS = {"claude": comments.CLAUDE, "geoffrey": comments.GEOFFREY}


def add_parsers(subparsers: argparse._SubParsersAction) -> None:
    listing = subparsers.add_parser("comments", help="afficher les fils d'un document")
    listing.add_argument("document", help="identité du document, ex. report-mon-sujet")
    listing.add_argument("--all", action="store_true", help="inclure les fils résolus")
    listing.set_defaults(handler=run_list)

    opening = subparsers.add_parser("comment", help="ouvrir un fil sur un document")
    opening.add_argument("document")
    opening.add_argument("--body", required=True, help="le commentaire")
    opening.add_argument(
        "--quote",
        help="passage visé, cherché verbatim dans la source ; sans lui le fil porte sur le document",
    )
    add_author(opening)
    opening.set_defaults(handler=run_open)

    replying = subparsers.add_parser("reply", help="répondre dans un fil")
    replying.add_argument("document")
    replying.add_argument("thread", help="identifiant du fil, ex. t3")
    replying.add_argument("--body", required=True)
    add_author(replying)
    replying.set_defaults(handler=run_reply)

    resolving = subparsers.add_parser("resolve", help="résoudre un fil")
    resolving.add_argument("document")
    resolving.add_argument("thread")
    resolving.add_argument(
        "--body", help="mot de clôture ajouté au fil avant résolution"
    )
    add_author(resolving)
    resolving.set_defaults(handler=run_resolve)

    reopening = subparsers.add_parser("reopen", help="réouvrir un fil résolu")
    reopening.add_argument("document")
    reopening.add_argument("thread")
    reopening.set_defaults(handler=run_reopen)

    editing_cmd = subparsers.add_parser("edit", help="réécrire un message")
    editing_cmd.add_argument("document")
    editing_cmd.add_argument("comment", help="identifiant du message, ex. t3.2")
    editing_cmd.add_argument("--body", required=True)
    editing_cmd.set_defaults(handler=run_edit)

    deleting = subparsers.add_parser("delete", help="supprimer un fil ou un message")
    deleting.add_argument("document")
    deleting.add_argument("target", help="un fil (t3) ou un message (t3.2)")
    deleting.set_defaults(handler=run_delete)

    for command in (
        listing,
        opening,
        replying,
        resolving,
        reopening,
        editing_cmd,
        deleting,
    ):
        command.add_argument(
            "--local", action="store_true", help="utiliser les commentaires locaux"
        )


def add_author(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--as",
        dest="author",
        choices=sorted(AUTHORS),
        default="claude",
        help="auteur du message (défaut : claude, ces commandes étant pilotées par l'agent)",
    )


def run_list(args: argparse.Namespace) -> None:
    threads = (
        comments.store_for(default_archive(), args.document).read()
        if args.local
        else remote.threads(args.document)
    )
    console.say(comments.digest(threads, include_resolved=args.all))


def run_open(args: argparse.Namespace) -> None:
    if not args.local:
        run_remote(args, "open")
        return
    archive = default_archive()
    store = comments.store_for(archive, args.document)
    anchor, state = resolve_anchor(archive, args.document, args.quote)
    with store.edit() as threads:
        thread = threads.open_thread(
            anchor=anchor,
            state=state,
            author=AUTHORS[args.author],
            body=args.body,
            now=comments.now_utc(),
        )
        console.say(f"fil ouvert : {thread.id} sur {args.document}")


def run_reply(args: argparse.Namespace) -> None:
    if not args.local:
        run_remote(args, "reply")
        return
    with editing(args) as threads:
        threads.require(args.thread).add_comment(
            AUTHORS[args.author], args.body, comments.now_utc()
        )
    console.say(f"réponse ajoutée à {args.thread}")


def run_resolve(args: argparse.Namespace) -> None:
    if not args.local:
        run_remote(args, "resolve")
        return
    author = AUTHORS[args.author]
    with editing(args) as threads:
        thread = threads.require(args.thread)
        if args.body:
            thread.add_comment(author, args.body, comments.now_utc())
        thread.resolve(author, comments.now_utc())
    console.say(f"fil résolu : {args.thread}")


def run_reopen(args: argparse.Namespace) -> None:
    if not args.local:
        run_remote(args, "reopen")
        return
    with editing(args) as threads:
        threads.require(args.thread).reopen(comments.now_utc())
    console.say(f"fil réouvert : {args.thread}")


def run_edit(args: argparse.Namespace) -> None:
    if not args.local:
        run_remote(args, "edit")
        return
    with editing(args) as threads:
        threads.require(thread_of(args.comment)).edit_comment(
            args.comment, args.body, comments.now_utc()
        )
    console.say(f"message réécrit : {args.comment}")


def run_delete(args: argparse.Namespace) -> None:
    if not args.local:
        run_remote(args, "delete")
        return
    """A dot in the target means a message; without one, the whole thread."""
    if "." not in args.target:
        with editing(args) as threads:
            threads.delete(args.target)
        console.say(f"fil supprimé : {args.target}")
        return
    with editing(args) as threads:
        emptied = threads.delete_comment(
            thread_of(args.target), args.target, comments.now_utc()
        )
    suffix = (
        f" (dernier message : le fil {thread_of(args.target)} est supprimé)"
        if emptied
        else ""
    )
    console.say(f"message supprimé : {args.target}{suffix}")


def thread_of(comment_id: str) -> str:
    return comment_id.split(".")[0]


def editing(args: argparse.Namespace):
    return comments.store_for(default_archive(), args.document).edit()


def resolve_anchor(
    archive: Archive, document: str, quote: str | None
) -> tuple[comments.Anchor | None, comments.AnchorState]:
    if quote is None:
        return None, comments.AnchorState.DOCUMENT
    source = archive.latest_source(document)
    if source is None:
        console.fail(
            f"aucune source archivée pour {document} — impossible d'ancrer un passage"
        )
    blocks = split_blocks(parse_source(source.read_text(encoding="utf-8"))[1])
    return comments.anchor_for_quote(blocks, quote), comments.AnchorState.ANCHORED


def run_remote(args: argparse.Namespace, operation: str) -> None:
    anchor = None
    if operation == "open":
        anchor, _ = resolve_anchor(default_archive(), args.document, args.quote)
    remote_discussion.submit(args, operation, anchor)
