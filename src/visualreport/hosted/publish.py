"""Publish one explicitly selected report using an existing Access session."""

import argparse
import os
from pathlib import Path

from .client import exchange
from .publication import Publication


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--page", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--origin", required=True)
    args = parser.parse_args()
    publication = Publication(
        page_name=args.page.name,
        title=args.title,
        html=args.page.read_text(),
        source=args.source.read_text(),
    )
    result = exchange(
        args.origin,
        os.environ["ARTEFACTS_ACCESS_JWT"],
        "/api/publish",
        publication.model_dump(),
        "POST",
    )
    print(args.origin + result["url"])


if __name__ == "__main__":
    main()
