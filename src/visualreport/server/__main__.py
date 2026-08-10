"""Foreground entry point — what the daemon spawns, and what `serve --foreground` runs."""

from __future__ import annotations

import argparse
from pathlib import Path

import uvicorn

from ..paths import DEFAULT_ROOT, Archive
from .app import HOST, create_app


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--archive", default=str(DEFAULT_ROOT))
    args = parser.parse_args()
    app = create_app(Archive(root=Path(args.archive)))
    uvicorn.run(app, host=HOST, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
