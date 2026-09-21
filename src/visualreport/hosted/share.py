"""Grant or revoke report access without editing Terraform."""

import argparse
import os
from urllib.parse import quote

from .api import Share
from .client import exchange


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--document", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument(
        "--role", choices=["reader", "commenter", "revoke"], required=True
    )
    parser.add_argument("--origin", required=True)
    args = parser.parse_args()
    request = Share(email=args.email, role=None if args.role == "revoke" else args.role)
    exchange(
        args.origin,
        os.environ["ARTEFACTS_ACCESS_JWT"],
        f"/api/documents/{quote(args.document, safe='')}/shares",
        request.model_dump(mode="json"),
        "PUT",
    )
    print(f"{args.document}: {args.email} — {args.role}")


if __name__ == "__main__":
    main()
