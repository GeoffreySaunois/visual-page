"""The gallery: every page in the archive, filed by section and folder, newest
first within each, with what is pending on it.

The taxonomy (`folders.py`) gives the page its shape: one section per top-level
folder, the pages filed directly in the section first, then one collapsible
drawer per folder. Pages that name no folder gather in a trailing "À classer"
section. A card shows the count of open comments and flags the ones waiting on
Claude, so the archive doubles as the queue of what is left to answer.
"""

from __future__ import annotations

import html
from pathlib import Path

from .. import folders
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
        body = "\n".join(section(entry, entries) for entry in folders.sections())
        body += unfiled_section(entries)
    else:
        body = '  <p class="empty">Aucune page. Rends-en une avec /visual.</p>'
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    return (
        template.replace("{{SECTIONS}}", body)
        .replace("{{COUNT}}", html.escape(summary(entries)))
        .replace("{{FAVICON}}", favicon_link("gallery"))
    )


def summary(entries: list[Entry]) -> str:
    plural = "s" if len(entries) != 1 else ""
    count = f"{len(entries)} page{plural}"
    if pending := sum(entry.awaiting_agent for entry in entries):
        count += f" · {pending} commentaire(s) en attente de Claude"
    return count


def section(root: folders.Folder, entries: list[Entry]) -> str:
    """A top-level section: its loose pages, then a drawer per folder. A section
    with nothing filed anywhere under it is not rendered at all."""
    members = [entry for entry in entries if entry.folder.section == root.path]
    if not members:
        return ""
    loose = [entry for entry in members if entry.folder == root]
    drawers = "\n".join(drawer(child, members) for child in folders.folders_of(root))
    return "\n".join(
        [
            f'  <section class="section" data-folder="{html.escape(root.path)}">',
            f"    {section_heading(root, len(members))}",
            grid(loose, root.path),
            drawers,
            "  </section>",
        ]
    )


def section_heading(root: folders.Folder, count: int) -> str:
    return (
        f'<h2 class="section-title">{html.escape(root.label)} '
        f'<span class="count" data-count>{count}</span></h2>'
    )


def drawer(child: folders.Folder, members: list[Entry]) -> str:
    """One folder as a collapsible block; absent when nothing is filed in it."""
    filed = [entry for entry in members if entry.folder == child]
    if not filed:
        return ""
    pending = sum(entry.awaiting_agent for entry in filed)
    badge = f'<span class="badge waiting">{pending} pour Claude</span>' if pending else ""
    return "\n".join(
        [
            f'    <details class="folder" data-folder="{html.escape(child.path)}" open>',
            "      <summary>",
            f'        <span class="folder-name">{html.escape(child.label)}</span>',
            f'        <span class="folder-hint">{html.escape(child.hint)}</span>',
            f'        <span class="count" data-count>{len(filed)}</span>{badge}',
            "      </summary>",
            grid(filed, child.path),
            "    </details>",
        ]
    )


def unfiled_section(entries: list[Entry]) -> str:
    """Pages rendered before folders existed, or whose folder left the taxonomy —
    kept visible so they get filed, never silently hidden."""
    loose = [entry for entry in entries if entry.folder == folders.UNFILED]
    if not loose:
        return ""
    return "\n".join(
        [
            '\n  <section class="section unfiled" data-folder="">',
            f"    {section_heading(folders.UNFILED, len(loose))}",
            grid(loose, ""),
            "  </section>",
        ]
    )


def grid(filed: list[Entry], folder_path: str) -> str:
    """The cards of one folder; an empty grid still exists so the script has
    one container per folder, but renders nothing."""
    cards = "\n".join(card(entry) for entry in filed)
    return f'    <div class="grid" data-grid="{html.escape(folder_path)}">\n{cards}\n    </div>'


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
