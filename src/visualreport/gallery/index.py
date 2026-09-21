"""The gallery: the archive browsed like a file system.

One directory is on screen at a time — the root shows the sections (*Swaap*,
*Personal*) as folder tiles, a section shows its folders as tiles and then the
pages filed directly in it, a folder shows its pages. The URL hash carries the
current directory (`#/swaap/gym`), so a directory can be bookmarked and the
back button climbs out of it. Every directory is rendered into the page and the
script reveals the current one; the page stays one static file. Search flattens
all of it into one result list, each page labeled with its folder.

A card shows the count of open comments and flags the ones waiting on Claude,
and a tile totals what is pending underneath it, so the archive doubles as the
queue of what is left to answer.
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
        body = "\n".join(directory(node, entries) for node in directories(entries))
    else:
        body = '  <p class="empty">Aucune page. Rends-en une avec /visual.</p>'
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    return (
        template.replace("{{DIRECTORIES}}", body)
        .replace("{{COUNT}}", html.escape(summary(entries)))
        .replace("{{FAVICON}}", favicon_link("gallery"))
    )


def summary(entries: list[Entry]) -> str:
    plural = "s" if len(entries) != 1 else ""
    count = f"{len(entries)} page{plural}"
    if pending := sum(entry.awaiting_agent for entry in entries):
        count += f" · {pending} commentaire(s) en attente de Claude"
    return count


ROOT = folders.Folder("", "Archive", "")


def directories(entries: list[Entry]) -> list[folders.Folder]:
    """Every directory the page can show: the root, each taxonomy node that has
    something under it, and the unfiled shelf when a page needs it."""
    nodes = [ROOT] + [node for node in folders.TAXONOMY if under(node, entries)]
    if any(entry.folder == folders.UNFILED for entry in entries):
        nodes.append(folders.UNFILED)
    return nodes


def under(node: folders.Folder, entries: list[Entry]) -> list[Entry]:
    """The pages filed in `node` or in any folder nested under it."""
    if node is ROOT:
        return entries
    if node is folders.UNFILED:
        return [entry for entry in entries if entry.folder == folders.UNFILED]
    return [
        entry
        for entry in entries
        if entry.folder == node or entry.folder.path.startswith(node.path + "/")
    ]


def children(node: folders.Folder, entries: list[Entry]) -> list[folders.Folder]:
    """The tiles a directory shows: the sections at the root (plus the unfiled
    shelf when it exists), then only the immediate children of each folder."""
    if node is ROOT:
        shelves = folders.sections()
        if any(entry.folder == folders.UNFILED for entry in entries):
            shelves = shelves + [folders.UNFILED]
        return [shelf for shelf in shelves if under(shelf, entries)]
    if node is not folders.UNFILED:
        return [child for child in folders.folders_of(node) if under(child, entries)]
    return []


def directory(node: folders.Folder, entries: list[Entry]) -> str:
    """One directory: its breadcrumb, its folder tiles, then its own pages."""
    own = (
        [entry for entry in entries if entry.folder == node] if node is not ROOT else []
    )
    tiles = "\n".join(tile(child, entries) for child in children(node, entries))
    path = html.escape(node.path)
    return "\n".join(
        [
            f'  <section class="dir" data-path="{path}" hidden>',
            f"    {breadcrumb(node)}",
            f'    <div class="tiles">\n{tiles}\n    </div>' if tiles else "",
            f'    <p class="dir-label">{html.escape(location(node))}</p>',
            grid(own),
            "  </section>",
        ]
    )


def breadcrumb(node: folders.Folder) -> str:
    """`Archive › Swaap › Gym`, every ancestor a link to its own directory."""
    trail = ['<a href="#/">Archive</a>']
    if node is not ROOT:
        parts = node.path.split("/")
        for depth in range(1, len(parts)):
            ancestor = folders.folder("/".join(parts[:depth]))
            assert ancestor is not None
            trail.append(
                f'<a href="#/{html.escape(ancestor.path)}">{html.escape(ancestor.label)}</a>'
            )
        trail.append(f"<span>{html.escape(node.label)}</span>")
    return '<nav class="crumbs">' + " <i>›</i> ".join(trail) + "</nav>"


def location(node: folders.Folder) -> str:
    """Where a directory's own pages sit, as the search results label them."""
    if node is ROOT:
        return ""
    parts = node.path.split("/")
    lineage = [
        folders.folder("/".join(parts[:depth])) for depth in range(1, len(parts) + 1)
    ]
    return (
        " › ".join(ancestor.label for ancestor in lineage if ancestor is not None)
        or node.label
    )


def tile(child: folders.Folder, entries: list[Entry]) -> str:
    filed = under(child, entries)
    pending = sum(entry.awaiting_agent for entry in filed)
    badge = (
        f'<span class="badge waiting">{pending} pour Claude</span>' if pending else ""
    )
    plural = "s" if len(filed) != 1 else ""
    return "\n".join(
        [
            f'      <a class="tile" href="#/{html.escape(child.path)}">',
            '        <span class="tile-icon" aria-hidden="true"></span>',
            f'        <span class="tile-name">{html.escape(child.label)}</span>',
            f'        <span class="tile-hint">{html.escape(child.hint)}</span>',
            f'        <span class="tile-count">{len(filed)} page{plural}{badge}</span>',
            "      </a>",
        ]
    )


def grid(filed: list[Entry]) -> str:
    cards = "\n".join(card(entry) for entry in filed)
    return f'    <div class="grid">\n{cards}\n    </div>'


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
        return (
            f'<p class="badge waiting">{label} · {entry.awaiting_agent} pour Claude</p>'
        )
    return f'<p class="badge">{label}</p>'
