"""Aligning the blocks of two versions of a document.

Both cross-version features build on this: the iteration diff needs to know
which block changed, and a comment anchor needs to find where its block moved
to after a rewrite. The diff pairs blocks by a bounded edit distance (`edits`),
so a huge block never stalls a render; re-homing a comment scores candidates
with difflib's ratio, against `MODIFIED_RATIO`.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from enum import StrEnum

from ..document import Block, normalize
from .edits import edit_distance

# A comment's block re-homes onto the closest block whose difflib ratio reaches
# this; below it, the block is taken as gone.
MODIFIED_RATIO = 0.5

# A `replace` pair is one modified block when its similarity, (T - D) / T for
# T characters on both sides and D the insertions plus deletions between them
# (so twice their longest common subsequence over T), reaches this; below it,
# the pair is a removal plus an unrelated addition. Unrelated prose scores up
# to about 0.5 (a common subsequence of frequent letters and spaces), while a
# reworded paragraph scores 0.8 to 0.9 and one that gains a sentence as long
# as itself about 0.65.
MODIFIED_SHARE = 0.55

# The most edits a modified pair may differ by, whatever its length. Measuring
# a pair costs O(T · D) (``edits``), so it stops at this many and the pair is a
# removal plus an addition: a block rewritten past it reads as new anyway.
EDIT_CAP = 500


class ChangeKind(StrEnum):
    EQUAL = "equal"
    ADDED = "add"
    MODIFIED = "mod"
    REMOVED = "rem"


@dataclass(frozen=True)
class BlockMatch:
    """What happened to one block of the new version."""

    kind: ChangeKind
    previous: Block | None


@dataclass(frozen=True)
class Alignment:
    """Per-new-block matches, plus the old blocks that disappeared."""

    matches: list[BlockMatch]
    removed: list[Block]

    @property
    def changed(self) -> bool:
        return bool(self.removed) or any(m.kind is not ChangeKind.EQUAL for m in self.matches)


def align(old_blocks: list[Block], new_blocks: list[Block]) -> Alignment:
    matcher = difflib.SequenceMatcher(
        a=[b.normalized for b in old_blocks], b=[b.normalized for b in new_blocks], autojunk=False
    )
    matches = [BlockMatch(ChangeKind.EQUAL, None)] * len(new_blocks)
    removed: list[Block] = []
    for tag, old_start, old_end, new_start, new_end in matcher.get_opcodes():
        if tag == "equal":
            continue
        if tag == "insert":
            for index in range(new_start, new_end):
                matches[index] = BlockMatch(ChangeKind.ADDED, None)
        elif tag == "delete":
            removed.extend(old_blocks[old_start:old_end])
        else:
            resolve_replacement(
                old_blocks[old_start:old_end],
                new_blocks[new_start:new_end],
                new_start,
                matches,
                removed,
            )
    return Alignment(matches=matches, removed=removed)


def resolve_replacement(
    old_run: list[Block],
    new_run: list[Block],
    new_start: int,
    matches: list[BlockMatch],
    removed: list[Block],
) -> None:
    """Pair a replaced run positionally: a close-enough pair is a modification,
    anything else splits into a removal and an addition."""
    paired = min(len(old_run), len(new_run))
    for offset in range(paired):
        old_block, new_block = old_run[offset], new_run[offset]
        if similar(old_block.normalized, new_block.normalized):
            matches[new_start + offset] = BlockMatch(ChangeKind.MODIFIED, old_block)
        else:
            removed.append(old_block)
            matches[new_start + offset] = BlockMatch(ChangeKind.ADDED, None)
    for offset in range(paired, len(new_run)):
        matches[new_start + offset] = BlockMatch(ChangeKind.ADDED, None)
    removed.extend(old_run[paired:])


def similar(left: str, right: str) -> bool:
    """Whether two blocks' texts are close enough for one to be a modification
    of the other: their similarity reaches ``MODIFIED_SHARE`` within
    ``EDIT_CAP`` edits."""
    total = len(left) + len(right)
    budget = min(int(total * (1 - MODIFIED_SHARE)), EDIT_CAP)
    return edit_distance(left, right, budget) is not None


def similarity(left: str, right: str) -> float:
    return difflib.SequenceMatcher(a=left, b=right, autojunk=False).ratio()


def best_match(text: str, blocks: list[Block]) -> tuple[Block | None, float]:
    """The block of `blocks` closest to `text`, with its similarity ratio.

    Used to re-home a comment whose block moved or was rewritten between two
    renders. An exact normalized match short-circuits at 1.0.
    """
    target = normalize(text)
    best: Block | None = None
    best_ratio = 0.0
    for block in blocks:
        if block.normalized == target:
            return block, 1.0
        ratio = similarity(target, block.normalized)
        if ratio > best_ratio:
            best, best_ratio = block, ratio
    return best, best_ratio
