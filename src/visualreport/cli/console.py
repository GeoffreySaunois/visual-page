"""Terminal output: one voice for every command."""

from __future__ import annotations

import sys


def say(message: str) -> None:
    print(message)


def warn(message: str) -> None:
    print(f"attention : {message}", file=sys.stderr)


def fail(message: str) -> None:
    """Stop with a message the user can act on, never a traceback."""
    raise SystemExit(f"erreur : {message}")
