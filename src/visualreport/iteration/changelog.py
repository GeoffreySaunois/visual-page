"""The band at the top of an iteration: one line per change, linked to its section."""

from __future__ import annotations

import html
from dataclasses import dataclass

from ..document import Block, heading_anchor, nearest_heading
from .annotate import BADGE_WORDS
from .matching import Alignment, ChangeKind

GIST_LENGTH = 60


@dataclass(frozen=True)
class ChangeEntry:
    kind: ChangeKind
    section: str | None
    gist: str


def collect(alignment: Alignment, new_blocks: list[Block]) -> list[ChangeEntry]:
    entries = [
        ChangeEntry(
            kind=match.kind,
            section=nearest_heading(new_blocks, block.index),
            gist=block.gist(GIST_LENGTH),
        )
        for block, match in zip(new_blocks, alignment.matches)
        if match.kind is not ChangeKind.EQUAL
    ]
    entries.extend(
        ChangeEntry(kind=ChangeKind.REMOVED, section=None, gist=block.gist(GIST_LENGTH))
        for block in alignment.removed
    )
    return entries


def render(entries: list[ChangeEntry]) -> str:
    plural = "s" if len(entries) > 1 else ""
    items = "\n".join(f"    {render_entry(entry)}" for entry in entries)
    return (
        '<div class="vr-changelog">\n'
        f'  <div class="vr-cl-head">▲ {len(entries)} changement{plural} '
        '<span class="vr-cl-date">(version précédente → actuelle)</span></div>\n'
        f"  <ul>\n{items}\n  </ul>\n"
        "</div>"
    )


def render_entry(entry: ChangeEntry) -> str:
    badge = f'<span class="vr-badge-inline {entry.kind}">{BADGE_WORDS[entry.kind]}</span>'
    gist = html.escape(entry.gist)
    if entry.section:
        link = f'<a href="#{heading_anchor(entry.section)}">{html.escape(entry.section)}</a>'
        return f"<li>{badge}{link} — {gist}</li>"
    return f"<li>{badge}{gist}</li>"
