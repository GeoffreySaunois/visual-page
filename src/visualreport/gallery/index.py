"""The gallery: the archive browsed like a file system, in the pages' Lab frame.

One directory is on screen at a time — the root shows the sections (*Swaap*,
*Personal*) as folder cards, a section shows its folders and then the pages
filed directly in it, a folder shows its pages. The URL hash carries the
current directory (`#/swaap/gym`), so a directory can be bookmarked, a page's
back arrow and breadcrumb can open its own folder, and the browser's back
button climbs out of it. Every directory is rendered into the page and the
script reveals the current one; the page stays one static file. Search
flattens all of it into one result list, each page labeled with its folder.

Folder and page cards share one size and one anatomy: a preview, then the
name. A page's preview is its top, framed in a scaled-down script-less
iframe the script mounts only while the card is on screen, over a cut-down
copy of the page (`preview.py`); a folder's is its most recent page, as the
top sheet of a stack.
"""

from __future__ import annotations

import html
from datetime import date as Date
from pathlib import Path

from .. import folders
from ..branding import favicon_link
from ..document.controls import icon_button
from ..document.page import TEMPLATE_DIR, concatenate, read_partial, read_script
from ..paths import Archive
from . import preview
from .catalog import Entry, collect

TEMPLATE_PATH = TEMPLATE_DIR / "gallery.html"
STYLE_ORDER = ("charte.css", "gallery.css")
SCRIPT_ORDER = ("appearance.js", "tooltip.js", "sidebar.js", "gallery.js", "paste.js")
MONTHS = (
    "janv.", "févr.", "mars", "avr.", "mai", "juin",
    "juil.", "août", "sept.", "oct.", "nov.", "déc.",
)  # fmt: skip


def rebuild(archive: Archive) -> tuple[Path, int]:
    archive.root.mkdir(parents=True, exist_ok=True)
    entries = collect(archive)
    preview.refresh(archive, [entry.href for entry in entries])
    archive.index.write_text(render(entries), encoding="utf-8")
    return archive.index, len(entries)


def render(entries: list[Entry]) -> str:
    if entries:
        body = "\n".join(directory(node, entries) for node in directories(entries))
    else:
        body = '  <p class="empty">Aucune page. Rends-en une avec /visual.</p>'
    slots = {
        "FAVICON": favicon_link("gallery"),
        "ICONS": (TEMPLATE_DIR / "icons" / "sprite.svg").read_text(encoding="utf-8"),
        "STYLES": concatenate(TEMPLATE_DIR / "styles", STYLE_ORDER),
        "TREE": tree(entries),
        "APPEARANCE_TOGGLE": icon_button(
            "appearance-toggle",
            "monitor",
            "Apparence",
            'aria-haspopup="dialog" aria-expanded="false" aria-controls="appearance-menu"',
            badge="",
        ),
        "APPEARANCE_MENU": read_partial("appearance-menu.html"),
        "DIRECTORIES": body,
        "SCRIPTS": "\n".join(
            f"<script>\n{read_script(name)}\n</script>" for name in SCRIPT_ORDER
        ),
    }
    page = TEMPLATE_PATH.read_text(encoding="utf-8")
    for slot, value in slots.items():
        page = page.replace(f"{{{{{slot}}}}}", value)
    return page


ROOT = folders.Folder("", "Galerie", "")


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
    """The folder cards a directory shows: the sections at the root (plus the
    unfiled shelf when it exists), then only the immediate children of each folder."""
    if node is ROOT:
        shelves = folders.sections()
        if any(entry.folder == folders.UNFILED for entry in entries):
            shelves = shelves + [folders.UNFILED]
        return [shelf for shelf in shelves if under(shelf, entries)]
    if node is not folders.UNFILED:
        return [child for child in folders.folders_of(node) if under(child, entries)]
    return []


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


def pages(count: int) -> str:
    return f"{count} page{'s' if count != 1 else ''}"


def readable_date(iso: str) -> str:
    """`2026-10-23` as `23 oct. 2026`; anything else as it was written."""
    try:
        day = Date.fromisoformat(iso)
    except ValueError:
        return iso
    return f"{day.day} {MONTHS[day.month - 1]} {day.year}"


# --- The sidebar --------------------------------------------------------------


def tree(entries: list[Entry]) -> str:
    """The sidebar's folder tree: every directory, indented by depth, with the
    number of pages under it."""
    rows = [tree_link(node, len(under(node, entries))) for node in directories(entries)]
    return (
        '<nav class="folder-tree" aria-label="Dossiers">\n'
        + "\n".join(rows)
        + "\n    </nav>"
    )


def tree_link(node: folders.Folder, count: int) -> str:
    icon = "library" if node is ROOT else "folder"
    depth = node.path.count("/") + (0 if node is ROOT else 1)
    path = html.escape(node.path)
    label = "Toutes les pages" if node is ROOT else node.label
    return (
        f'      <a class="tree-link" href="#/{path}" data-path="{path}" data-depth="{depth}">'
        f'<svg class="icon" aria-hidden="true"><use href="#vr-i-{icon}"></use></svg>'
        f'<span class="label">{html.escape(label)}</span>'
        f'<span class="tree-count">{count}</span></a>'
    )


# --- A directory --------------------------------------------------------------


def directory(node: folders.Folder, entries: list[Entry]) -> str:
    """One directory: what it holds, its folder cards, then its own pages."""
    own = (
        [entry for entry in entries if entry.folder == node] if node is not ROOT else []
    )
    nested = children(node, entries)
    path = html.escape(node.path)
    parts = [
        f'  <section class="dir" data-path="{path}" data-label="{html.escape(node.label)}" hidden>',
        f'    <p class="dir-summary">{html.escape(summary(node, entries))}</p>',
    ]
    if nested:
        parts += [
            '    <h2 class="dir-label folders-label">Dossiers</h2>',
            '    <div class="cards folders">',
            *(folder_card(child, entries) for child in nested),
            "    </div>",
        ]
    if own:
        parts += [
            (
                '    <h2 class="dir-label pages-label">'
                '<span class="when-browsing">Pages</span>'
                f'<span class="when-searching">{html.escape(location(node))}</span></h2>'
            ),
            '    <div class="cards pages">',
            *(page_card(entry) for entry in own),
            "    </div>",
        ]
    parts.append("  </section>")
    return "\n".join(parts)


def summary(node: folders.Folder, entries: list[Entry]) -> str:
    """The line under the top bar: what the directory is for and how much it holds."""
    count = pages(len(under(node, entries)))
    return f"{node.hint} · {count}" if node.hint else count


def folder_card(child: folders.Folder, entries: list[Entry]) -> str:
    filed = under(child, entries)
    nested = len(children(child, entries))
    meta = pages(len(filed))
    if nested:
        meta += f" · {nested} dossier{'s' if nested > 1 else ''}"
    latest = filed[0]
    return "\n".join(
        [
            '      <article class="card folder-card">',
            '        <div class="thumb thumb-stack" aria-hidden="true">',
            f'          <div class="sheet" data-preview="{html.escape(latest.preview)}"></div>',
            "        </div>",
            '        <div class="card-body">',
            (
                '          <p class="card-kicker"><svg class="icon" aria-hidden="true">'
                '<use href="#vr-i-folder"></use></svg>Dossier</p>'
            ),
            (
                f'          <h3 class="card-title"><a class="card-link" href="#/{html.escape(child.path)}">'
                f"{html.escape(child.label)}</a></h3>"
            ),
            f'          <p class="card-desc">{html.escape(child.hint)}</p>',
            f'          <p class="card-meta">{html.escape(meta)}</p>',
            "        </div>",
            "      </article>",
        ]
    )


def page_card(entry: Entry) -> str:
    return "\n".join(
        [
            (
                f'      <article class="card page-card" data-title="{html.escape(entry.title.lower())}"'
                f' data-date="{html.escape(entry.date)}" data-text="{html.escape(entry.haystack)}">'
            ),
            f'        <div class="thumb" aria-hidden="true" data-preview="{html.escape(entry.preview)}"></div>',
            '        <div class="card-body">',
            f'          <p class="card-kicker">{html.escape(entry.eyebrow or entry.kind)}</p>',
            (
                f'          <h3 class="card-title"><a class="card-link" href="{html.escape(entry.href)}"'
                f' title="{html.escape(entry.title)}">{html.escape(entry.title)}</a></h3>'
            ),
            f'          <p class="card-desc">{html.escape(entry.subtitle)}</p>',
            f'          <p class="card-meta">{card_meta(entry)}</p>',
            "        </div>",
            "      </article>",
        ]
    )


def card_meta(entry: Entry) -> str:
    """The date, and how many threads are still open on the page when any are."""
    meta = f'<time datetime="{html.escape(entry.date)}">{html.escape(readable_date(entry.date))}</time>'
    if entry.open_comments:
        plural = "s" if entry.open_comments > 1 else ""
        meta += (
            f'<span class="card-comments" title="{entry.open_comments} fil{plural} ouvert{plural}">'
            '<svg class="icon" aria-hidden="true"><use href="#vr-i-message-square"></use></svg>'
            f"{entry.open_comments}</span>"
        )
    return meta
