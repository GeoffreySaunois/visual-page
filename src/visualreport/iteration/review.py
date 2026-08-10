"""The iteration layer: a re-render shows what changed since the previous version.

A report is rarely one-shot. When a previous archived source of the same slug
exists, the page is rendered as a review of the delta — changed blocks boxed or
word-diffed, a changelog band at the top, and an in-page toggle back to the
clean document.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..document import Block, parse_source, split_blocks
from ..document.composition import BlockDecorator
from . import changelog
from .annotate import make_decorator
from .matching import align


@dataclass(frozen=True)
class Iteration:
    """What a diff against the previous version contributes to the page."""

    decorator: BlockDecorator
    changelog_html: str
    change_count: int


def review(previous_source: Path, new_blocks: list[Block]) -> Iteration | None:
    """Compare a body against a previous source. None when nothing changed."""
    _, previous_body = parse_source(previous_source.read_text(encoding="utf-8"))
    alignment = align(split_blocks(previous_body), new_blocks)
    if not alignment.changed:
        return None
    entries = changelog.collect(alignment, new_blocks)
    return Iteration(
        decorator=make_decorator(alignment),
        changelog_html=changelog.render(entries),
        change_count=len(entries),
    )
