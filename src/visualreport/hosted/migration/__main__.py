"""Snapshot the local archive, then explicitly import that frozen snapshot."""

import argparse
import json
import os
import subprocess
from pathlib import Path

from google.cloud import firestore, storage
from google.oauth2.credentials import Credentials

from .cloud import Importer
from .snapshot import prepare


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    snapshot = commands.add_parser("prepare")
    snapshot.add_argument("--archive", type=Path, required=True)
    snapshot.add_argument("--snapshot", type=Path, required=True)
    apply = commands.add_parser("apply")
    apply.add_argument("--snapshot", type=Path, required=True)
    apply.add_argument("--account", required=True)
    apply.add_argument("--project", required=True)
    apply.add_argument("--database", required=True)
    apply.add_argument("--bucket", required=True)
    apply.add_argument("--owner", required=True)
    apply.add_argument("--allow-writes", action="store_true")
    return parser.parse_args()


def credentials(account: str) -> Credentials:
    result = subprocess.run(
        ["gcloud", "auth", "print-access-token", f"--account={account}", "--quiet"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(
            "Explicit Google account authentication unavailable; token not logged"
        )
    return Credentials(result.stdout.strip())


def main() -> None:
    args = arguments()
    os.umask(0o077)
    if args.action == "prepare":
        manifest = prepare(args.archive, args.snapshot)
        print(json.dumps(manifest["counts"], indent=2))
        print(f"Frozen manifest: {args.snapshot / 'manifest.json'}")
        return
    if not args.allow_writes:
        raise SystemExit("--allow-writes required; no cloud operation performed")
    manifest = json.loads((args.snapshot / "manifest.json").read_text())
    if manifest["schema"] != 1:
        raise ValueError("Unsupported snapshot schema")
    identity = credentials(args.account)
    importer = Importer(
        firestore.Client(
            project=args.project, database=args.database, credentials=identity
        ),
        storage.Client(project=args.project, credentials=identity).bucket(args.bucket),
        args.snapshot,
        args.owner.lower(),
    )
    print(json.dumps(importer.apply(manifest), indent=2))


if __name__ == "__main__":
    main()
