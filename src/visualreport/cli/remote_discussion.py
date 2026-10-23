"""Discussion operations against the hosted report API."""

import argparse

from ..comments import Anchor
from . import console, remote


def submit(args: argparse.Namespace, operation: str, anchor: Anchor | None) -> None:
    actor = "agent" if getattr(args, "author", "claude") == "claude" else "human"
    if operation == "open":
        result = remote.request(
            args.document, "/threads", opening(args.body, actor, anchor), "POST"
        )
        console.say(f"fil ouvert : {result['threads'][-1]['id']} sur {args.document}")
        return
    if operation in {"reply", "resolve", "reopen"}:
        update_thread(args, operation, actor)
    elif operation == "edit":
        remote.request(
            args.document,
            message_path(args.comment),
            {"body": args.body, "actor": actor},
            "PATCH",
        )
    else:
        path = (
            message_path(args.target)
            if "." in args.target
            else "/threads/" + args.target
        )
        remote.request(args.document, path, None, "DELETE")
    console.say(f"{operation} : enregistré sur Artefacts")


def opening(body: str, actor: str, anchor: Anchor | None) -> dict:
    selection = (
        None
        if anchor is None
        else {
            key: getattr(anchor, key)
            for key in ("block_index", "quote", "prefix", "suffix")
        }
    )
    return {"body": body, "actor": actor, "anchor": selection}


def update_thread(args: argparse.Namespace, operation: str, actor: str) -> None:
    base = "/threads/" + args.thread
    if operation == "reply" or (operation == "resolve" and args.body):
        remote.request(
            args.document,
            base + "/comments",
            {"body": args.body, "actor": actor},
            "POST",
        )
    if operation != "reply":
        remote.request(args.document, base + "/" + operation, {"actor": actor}, "POST")


def message_path(comment: str) -> str:
    return "/threads/" + comment.split(".")[0] + "/comments/" + comment
