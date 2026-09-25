"""Who can open the hosted archive: grant, revoke and list access."""

from __future__ import annotations

import argparse
from urllib.parse import quote

from . import console, remote


def add_parsers(subparsers: argparse._SubParsersAction) -> None:
    share = subparsers.add_parser(
        "share", help="donner ou retirer l'accès à un document ou à un dossier"
    )
    share.add_argument("email", help="l'adresse de la personne invitée")
    target = share.add_mutually_exclusive_group(required=True)
    target.add_argument("--document", help="un document (<kind>-<slug>)")
    target.add_argument(
        "--folder",
        help="un dossier de la taxonomie : couvre ses sous-dossiers et les documents à venir",
    )
    share.add_argument(
        "--role", choices=["reader", "commenter", "revoke"], required=True
    )
    share.set_defaults(handler=run_share)

    shares = subparsers.add_parser("shares", help="qui a accès à quoi sur Artefacts")
    shares.set_defaults(handler=run_shares)


def run_share(args: argparse.Namespace) -> None:
    path = (
        f"/api/documents/{quote(args.document, safe='')}/shares"
        if args.document
        else f"/api/folders/{quote(args.folder, safe='/')}/shares"
    )
    role = None if args.role == "revoke" else args.role
    remote.api(path, {"email": args.email, "role": role}, "PUT")
    console.say(f"{args.document or args.folder + '/'} : {args.email} — {args.role}")


def run_shares(args: argparse.Namespace) -> None:
    result = remote.api("/api/shares", None, "GET")
    for heading, grants in (
        ("dossiers", {f"{path}/": g for path, g in result["folders"].items()}),
        ("documents", result["documents"]),
    ):
        console.say(heading)
        shared = {target: g for target, g in sorted(grants.items()) if g}
        if not shared:
            console.say("  (aucun partage)")
        for target, grants_of in shared.items():
            for email, role in sorted(grants_of.items()):
                console.say(f"  {target:<48} {email:<32} {role}")
