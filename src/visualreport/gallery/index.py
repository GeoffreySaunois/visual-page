"""The gallery: every page in the archive, newest first, with what is pending on it.

A card shows the count of open comments and flags the ones waiting on Claude, so
the archive doubles as the queue of what is left to answer.
"""

from __future__ import annotations

import html
from pathlib import Path

from ..branding import favicon_link
from ..paths import Archive
from .catalog import Entry, collect

TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "templates" / "gallery.html"


def rebuild(archive: Archive) -> tuple[Path, int]:
    archive.root.mkdir(parents=True, exist_ok=True)
    entries = collect(archive)
    archive.index.write_text(render(entries), encoding="utf-8")
    return archive.index, len(entries)


def render(entries: list[Entry]) -> str:
    if entries:
        cards = "\n".join(card(entry) for entry in entries)
    else:
        cards = '  <p class="empty">Aucune page. Rends-en une avec /visual.</p>'
    plural = "s" if len(entries) != 1 else ""
    pending = sum(entry.awaiting_agent for entry in entries)
    count = f"{len(entries)} page{plural}"
    if pending:
        count += f" · {pending} commentaire(s) en attente de Claude"
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    return (
        template.replace("{{CARDS}}", cards)
        .replace("{{COUNT}}", html.escape(count))
        .replace("{{FAVICON}}", favicon_link("gallery"))
    )


def card(entry: Entry) -> str:
    parts = [
        f'  <a class="card" href="{html.escape(entry.href)}"',
        f'     data-title="{html.escape(entry.title.lower())}"',
        f'     data-date="{html.escape(entry.date)}"',
        f'     data-comments="{entry.open_comments}"',
        f'     data-text="{html.escape(entry.haystack)}">',
        f'    <p class="eyebrow">{html.escape(entry.eyebrow or entry.kind)}</p>',
        f"    <h2>{html.escape(entry.title)}</h2>",
    ]
    if meta_line := " · ".join(bit for bit in (entry.date, entry.subtitle) if bit):
        parts.append(f'    <p class="meta">{html.escape(meta_line)}</p>')
    if badge := comment_badge(entry):
        parts.append(f"    {badge}")
    parts.append("  </a>")
    return "\n".join(parts)


def comment_badge(entry: Entry) -> str:
    if not entry.open_comments:
        return ""
    label = f"{entry.open_comments} ouvert{'s' if entry.open_comments > 1 else ''}"
    if entry.awaiting_agent:
        return f'<p class="badge waiting">{label} · {entry.awaiting_agent} pour Claude</p>'
    return f'<p class="badge">{label}</p>'
