"""Marking changed blocks in the markdown, before the single conversion pass."""

from __future__ import annotations

import difflib
import re

from ..document import Block, wrap_markdown_div
from .matching import Alignment, ChangeKind

BADGE_WORDS = {ChangeKind.ADDED: "nouveau", ChangeKind.MODIFIED: "modifié", ChangeKind.REMOVED: "retiré"}

# Splicing inline <ins>/<del> into a token carrying markdown or HTML inline
# syntax would corrupt it — an emphasis run, a code span or a link cut in half.
# When any of these appear, the block falls back to a wrapper plus a badge.
WORD_DIFF_UNSAFE = re.compile(r"(\*\*|__|~~|`|\[|\]\(|[*_<>|])")


def make_decorator(alignment: Alignment):
    """A block decorator that boxes what changed since the previous version.

    Headings are emitted verbatim: wrapping one would put it inside a div and
    break the single-pass table of contents, so a heading change is recorded in
    the changelog only. Removed blocks are never re-inserted into the body.
    """

    def annotate(block: Block, markdown: str) -> str:
        match = alignment.matches[block.index]
        if match.kind is ChangeKind.EQUAL or block.is_heading:
            return markdown
        if match.kind is ChangeKind.MODIFIED and word_diffable(block, match.previous):
            return word_diff(match.previous.text, markdown)
        return wrap_change(markdown, match.kind)

    return annotate


def word_diffable(block: Block, previous: Block | None) -> bool:
    return (
        previous is not None
        and block.is_prose
        and is_word_diff_safe(block.text)
        and is_word_diff_safe(previous.text)
    )


def is_word_diff_safe(text: str) -> bool:
    return not WORD_DIFF_UNSAFE.search(text)


def wrap_change(markdown: str, kind: ChangeKind) -> str:
    badge = f'<span class="vr-badge {kind}">{BADGE_WORDS[kind]}</span>'
    return wrap_markdown_div(f"{badge}\n\n{markdown}", f"vr-chg {kind}", "")


def word_diff(old_text: str, new_text: str) -> str:
    """A whitespace-tokenized word diff as inline <ins>/<del>. Runs of spaces
    collapse to one, which is harmless in prose."""
    old_tokens, new_tokens = old_text.split(), new_text.split()
    matcher = difflib.SequenceMatcher(a=old_tokens, b=new_tokens, autojunk=False)
    parts = []
    for tag, old_start, old_end, new_start, new_end in matcher.get_opcodes():
        removed = " ".join(old_tokens[old_start:old_end])
        added = " ".join(new_tokens[new_start:new_end])
        if tag == "equal":
            parts.append(added)
        else:
            if tag in ("delete", "replace"):
                parts.append(f'<del class="vr-del">{removed}</del>')
            if tag in ("insert", "replace"):
                parts.append(f'<ins class="vr-ins">{added}</ins>')
    return " ".join(part for part in parts if part)
