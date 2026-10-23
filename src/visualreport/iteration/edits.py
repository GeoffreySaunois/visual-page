"""Bounded edit scripts between two sequences, by Myers' difference algorithm.

Myers' greedy search finds the shortest insert/delete script between sequences
of lengths N and M in O((N + M) · D) time, D being the length of that script.
Two versions of one block differ by few edits, so it stays linear in the block
whatever its size, where ``difflib.SequenceMatcher`` grows faster than
quadratically with the length (minutes on a 150 KB one-line JSON fence). Two
unrelated blocks differ by D ~ N + M edits, which makes Myers quadratic too:
every search therefore stops past a caller's ``limit`` and reports the pair as
too far apart, which bounds it at O((N + M) · limit).
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Literal

OpcodeTag = Literal["equal", "replace", "delete", "insert"]
# ``difflib``'s opcode shape: ``old[old_start:old_end]`` became
# ``new[new_start:new_end]`` through ``tag``.
Opcode = tuple[OpcodeTag, int, int, int, int]
# A run of ``size`` equal items starting at ``old[old_start]`` and ``new[new_start]``.
Run = tuple[int, int, int]


def edit_distance(
    old: Sequence[object], new: Sequence[object], limit: int
) -> int | None:
    """The fewest insertions plus deletions turning ``old`` into ``new``, or
    None when it exceeds ``limit``."""
    for distance, (_, reached) in enumerate(_frontiers(old, new, limit)):
        if reached:
            return distance
    return None


def opcodes(
    old: Sequence[object], new: Sequence[object], limit: int
) -> list[Opcode] | None:
    """The shortest edit script from ``old`` to ``new`` as ``difflib`` opcodes,
    or None when it takes more than ``limit`` insertions plus deletions."""
    trace: list[dict[int, int]] = []
    for frontier, reached in _frontiers(old, new, limit):
        trace.append(dict(frontier))
        if reached:
            return _to_opcodes(
                _equal_runs(trace, len(old), len(new)), len(old), len(new)
            )
    return None


def _frontiers(
    old: Sequence[object], new: Sequence[object], limit: int
) -> Iterator[tuple[dict[int, int], bool]]:
    """Myers' forward search, one round per edit.

    After round d, the frontier maps each diagonal k = x - y reachable with d
    edits to the furthest x reached on it, ``old[:x]`` aligned with
    ``new[:x - k]``; the flag says whether the round reached both ends. The
    search stops at that round, or after round ``limit``.
    """
    old_len, new_len = len(old), len(new)
    frontier = {1: 0}
    for distance in range(limit + 1):
        for k in range(-distance, distance + 1, 2):
            x = _step(frontier, k, distance)
            while x < old_len and x - k < new_len and old[x] == new[x - k]:
                x += 1
            frontier[k] = x
            if x >= old_len and x - k >= new_len:
                yield frontier, True
                return
        yield frontier, False


def _step(frontier: dict[int, int], k: int, distance: int) -> int:
    """Where diagonal k starts in round ``distance``: one insertion down from
    diagonal k + 1, or one deletion right from diagonal k - 1, whichever of
    the two reached further in the previous round."""
    if _came_down(frontier, k, distance):
        return frontier[k + 1]
    return frontier[k - 1] + 1


def _came_down(frontier: dict[int, int], k: int, distance: int) -> bool:
    return k == -distance or (k != distance and frontier[k - 1] < frontier[k + 1])


def _equal_runs(trace: list[dict[int, int]], old_len: int, new_len: int) -> list[Run]:
    """The equal runs of the script whose rounds ``trace`` recorded, walked
    back from both ends to the origin and returned in order."""
    runs: list[Run] = []
    x, y = old_len, new_len
    for distance in range(len(trace) - 1, 0, -1):
        k = x - y
        previous = trace[distance - 1]
        down = _came_down(previous, k, distance)
        start_k = k + 1 if down else k - 1
        start_x = previous[start_k]
        snake_x = start_x if down else start_x + 1
        if x > snake_x:
            runs.append((snake_x, snake_x - k, x - snake_x))
        x, y = start_x, start_x - start_k
    if x > 0:
        runs.append((0, 0, x))
    runs.reverse()
    return runs


def _to_opcodes(runs: list[Run], old_len: int, new_len: int) -> list[Opcode]:
    """Equal runs as opcodes, each gap between two of them one edit opcode."""
    codes: list[Opcode] = []
    old_at = new_at = 0
    for old_start, new_start, size in [*runs, (old_len, new_len, 0)]:
        tag = _gap_tag(old_start > old_at, new_start > new_at)
        if tag is not None:
            codes.append((tag, old_at, old_start, new_at, new_start))
        if size:
            codes.append(
                ("equal", old_start, old_start + size, new_start, new_start + size)
            )
        old_at, new_at = old_start + size, new_start + size
    return codes


def _gap_tag(removes: bool, adds: bool) -> OpcodeTag | None:
    if removes and adds:
        return "replace"
    if removes:
        return "delete"
    return "insert" if adds else None
