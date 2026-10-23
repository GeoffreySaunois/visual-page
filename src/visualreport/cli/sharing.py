"""Who can open the hosted archive: grant, revoke and list access."""

from __future__ import annotations

import argparse
from urllib.parse import quote

from . import console, remote

EVERYONE_LABEL = "tout email vérifié"


def add_parsers(subparsers: argparse._SubParsersAction) -> None:
    share = subparsers.add_parser(
        "share", help="donner ou retirer l'accès à un document ou à un dossier"
    )
    grantee = share.add_mutually_exclusive_group(required=True)
    grantee.add_argument("email", nargs="?", help="l'adresse de la personne invitée")
    grantee.add_argument(
        "--everyone",
        action="store_true",
        help="toute personne dont Cloudflare Access a vérifié l'email",
    )
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
    grantee = {"everyone": True} if args.everyone else {"email": args.email}
    remote.api(path, {**grantee, "role": role}, "PUT")
    who = EVERYONE_LABEL if args.everyone else args.email
    console.say(f"{args.document or args.folder + '/'} : {who} — {args.role}")


def run_shares(args: argparse.Namespace) -> None:
    result = remote.api("/api/shares", None, "GET")
    for heading, targets in (
        ("dossiers", {f"{path}/": g for path, g in result["folders"].items()}),
        ("documents", result["documents"]),
    ):
        console.say(heading)
        if not targets:
            console.say("  (aucun partage)")
        for target, grants in sorted(targets.items()):
            for who, role in grant_rows(grants):
                console.say(f"  {target:<48} {who:<32} {role}")


def grant_rows(grants: dict) -> list[tuple[str, str]]:
    everyone = [(EVERYONE_LABEL, grants["everyone"])] if grants["everyone"] else []
    return everyone + sorted(grants["emails"].items())
