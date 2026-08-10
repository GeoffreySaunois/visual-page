"""Keeping a thread pointed at its passage across rewrites.

A comment is anchored on a block index and a quoted run of text, but the source
keeps being edited — that is the point of the loop. So on every render each
thread is re-homed against the new blocks: the block is found again by
similarity, and the thread reports honestly how well it landed. Nothing is ever
dropped for having lost its anchor.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..document import Block, nearest_heading, normalize
from ..iteration import best_match
from ..iteration.matching import MODIFIED_RATIO
from .model import Anchor, AnchorState, CommentError, ReportThreads, Thread

CONTEXT_LENGTH = 60


@dataclass(frozen=True)
class RehomeReport:
    """What became of the threads of a report after a re-render."""

    anchored: int
    drifted: int
    orphaned: int

    @property
    def total(self) -> int:
        return self.anchored + self.drifted + self.orphaned

    def summary(self) -> str:
        parts = [f"{self.anchored} ancrés"]
        if self.drifted:
            parts.append(f"{self.drifted} dérivés (texte cité réécrit)")
        if self.orphaned:
            parts.append(f"{self.orphaned} orphelins (bloc disparu)")
        return ", ".join(parts)


def rehome_all(threads: ReportThreads, blocks: list[Block]) -> RehomeReport:
    """Re-point every anchored thread at the current blocks, in place."""
    counts = {AnchorState.ANCHORED: 0, AnchorState.DRIFTED: 0, AnchorState.ORPHANED: 0}
    for thread in threads.threads:
        if thread.anchor is None:
            continue
        counts[rehome(thread, blocks)] += 1
    return RehomeReport(
        anchored=counts[AnchorState.ANCHORED],
        drifted=counts[AnchorState.DRIFTED],
        orphaned=counts[AnchorState.ORPHANED],
    )


def rehome(thread: Thread, blocks: list[Block]) -> AnchorState:
    """Find the thread's block again and restate how well the anchor holds.

    The block reference is one-step, like the iteration diff: once matched, the
    anchor adopts the new block text, so the next render compares against what
    the reader last saw rather than against the original wording.
    """
    anchor = thread.anchor
    block, ratio = best_match(anchor.block_source, blocks)
    if block is None or ratio < MODIFIED_RATIO:
        thread.state = AnchorState.ORPHANED
        return thread.state
    thread.anchor = anchor.model_copy(
        update={
            "block_index": block.index,
            "block_digest": block.digest,
            "block_source": block.text,
            "section": nearest_heading(blocks, block.index),
        }
    )
    thread.state = AnchorState.ANCHORED if holds_quote(block, anchor.quote) else AnchorState.DRIFTED
    return thread.state


def anchor_on(blocks: list[Block], block_index: int, quote: str, prefix: str, suffix: str) -> Anchor:
    """Build an anchor from what the page reports about a selection.

    The page knows the block it selected in and the text it selected; the source
    block and the section come from the document itself, so the agent gets a
    handle on the passage without the browser having to send one.
    """
    block = next((candidate for candidate in blocks if candidate.index == block_index), None)
    if block is None:
        raise ValueError(f"bloc {block_index} absent de la source ({len(blocks)} blocs)")
    return Anchor(
        block_index=block.index,
        block_digest=block.digest,
        block_source=block.text,
        section=nearest_heading(blocks, block.index),
        quote=quote.strip(),
        prefix=prefix[-CONTEXT_LENGTH:],
        suffix=suffix[:CONTEXT_LENGTH],
    )


def anchor_for_quote(blocks: list[Block], quote: str) -> Anchor:
    """Anchor on a passage given only its words — how the agent comments.

    Claude has no selection to report, so it names the passage it means; the
    first block whose text contains those words becomes the anchor.
    """
    for block in blocks:
        if holds_quote(block, quote):
            return anchor_on(blocks, block.index, quote, prefix="", suffix="")
    raise CommentError(f"passage introuvable dans la source : « {quote} »")


def holds_quote(block: Block, quote: str) -> bool:
    """Whether the quoted words are still in the block.

    The quote was captured from the rendered page and the block is markdown, so
    both sides are reduced to plain text before comparing — otherwise emphasis or
    a link around the selection would read as a rewrite.
    """
    needle = normalize(plain_text(quote))
    return bool(needle) and needle in normalize(plain_text(block.text))


INLINE_MARKUP_RE = re.compile(r"(\*\*|__|~~|[*_`])")
LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
LINE_PREFIX_RE = re.compile(r"^\s*([>#]+|[-*+]|\d+[.)])\s*", re.MULTILINE)


def plain_text(markdown: str) -> str:
    """The words of a markdown fragment, without the syntax that decorates them."""
    text = LINK_RE.sub(r"\1", markdown)
    text = LINE_PREFIX_RE.sub("", text)
    return INLINE_MARKUP_RE.sub("", text)
