"""Marking changed blocks in the markdown, before the single conversion pass."""

from __future__ import annotations

import re

from ..document import Block, wrap_markdown_div
from ..document.math import MATH
from .edits import opcodes
from .matching import EDIT_CAP, Alignment, BlockMatch, ChangeKind

BADGE_WORDS = {ChangeKind.ADDED: "nouveau", ChangeKind.MODIFIED: "modifié", ChangeKind.REMOVED: "retiré"}

# Splicing inline <ins>/<del> into a token carrying markdown or HTML inline
# syntax would corrupt it — an emphasis run, a code span or a link cut in half.
# When any of these appear, the block falls back to a wrapper plus a badge, and
# so does a block holding math, where a spliced tag would be read as TeX.
WORD_DIFF_UNSAFE = re.compile(r"(\*\*|__|~~|`|\[|\]\(|[*_<>|])")
# A dollar outside math is a literal one, a price. A spliced tag can still pair
# it with another into a formula — `>` before a `$` makes it a valid closing
# delimiter — so the word diff escapes every one it emits.
UNESCAPED_DOLLAR = re.compile(r"(?<!\\)\$")


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
        diffed = revised_words(block, match, markdown)
        return wrap_change(markdown, match.kind) if diffed is None else diffed

    return annotate


def revised_words(block: Block, match: BlockMatch, markdown: str) -> str | None:
    """A modified block as a word diff against the text it replaced, when both
    are plain prose and differ by at most ``EDIT_CAP`` words; None otherwise."""
    previous = match.previous
    if match.kind is not ChangeKind.MODIFIED or previous is None or not word_diffable(block, previous):
        return None
    return word_diff(previous.text, markdown)


def word_diffable(block: Block, previous: Block) -> bool:
    return (
        block.is_prose
        and is_word_diff_safe(block.text)
        and is_word_diff_safe(previous.text)
    )


def is_word_diff_safe(text: str) -> bool:
    return not WORD_DIFF_UNSAFE.search(text) and not MATH.search(text)


def wrap_change(markdown: str, kind: ChangeKind) -> str:
    badge = f'<span class="vr-badge {kind}">{BADGE_WORDS[kind]}</span>'
    return wrap_markdown_div(f"{badge}\n\n{markdown}", f"vr-chg {kind}", "")


def word_diff(old_text: str, new_text: str) -> str | None:
    """A whitespace-tokenized word diff as inline <ins>/<del>, or None past
    ``EDIT_CAP`` word edits. Runs of spaces collapse to one, which is harmless
    in prose."""
    old_tokens, new_tokens = literal_dollars(old_text), literal_dollars(new_text)
    script = opcodes(old_tokens, new_tokens, EDIT_CAP)
    if script is None:
        return None
    parts = []
    for tag, old_start, old_end, new_start, new_end in script:
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


def literal_dollars(text: str) -> list[str]:
    """`text`'s words, each dollar escaped so no spliced tag can open math."""
    return UNESCAPED_DOLLAR.sub(r"\\$", text).split()
