"""Assembling the HTML page from the template and its style/script partials.

The template is a skeleton with `{{SLOT}}` placeholders; the charte lives in
`templates/styles/*.css` and the behavior in `templates/scripts/*.js`, both
concatenated inline at build time so the page stays a single file. A new style
sheet or script is one file plus one entry in the order tuples below.
"""

from __future__ import annotations

import html
import json
import os
from dataclasses import dataclass
from pathlib import Path

from markdown.extensions.toc import slugify as toc_slugify

from .. import folders
from ..branding import favicon_link
from .assets import PageAssets
from .frontmatter import ReportMeta
from .libraries import head_libraries

TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates"
STYLE_ORDER = (
    "charte.css",
    "blocks.css",
    "tables.css",
    "copy.css",
    "lightbox.css",
    "figure-actions.css",
    "iteration.css",
    "comments.css",
    "selection-actions.css",
    "print.css",
)
SCRIPT_ORDER = (
    "appearance.js",
    "tooltip.js",
    "sidebar.js",
    "contents.js",
    "page.js",
    "tables.js",
    "copy.js",
    "lightbox.js",
    "figure-actions.js",
    "selection-actions.js",
    "comments.js",
    "paste.js",
)


@dataclass(frozen=True)
class PageContent:
    """Everything the template needs beyond the metadata."""

    document_id: str
    body: str
    changelog: str
    toolbar: str
    comments_bootstrap: dict
    assets: PageAssets


def render_page(meta: ReportMeta, content: PageContent) -> str:
    slots = {
        "LANG": html.escape(meta.lang),
        "TITLE": html.escape(meta.title),
        "EYEBROW": html.escape(meta.eyebrow),
        "DATE": html.escape(meta.date),
        "SUBTITLE": html.escape(meta.subtitle),
        "FOLDER": html.escape(meta.folder),
        "DOCUMENT": html.escape(content.document_id),
        # The Claude Code session that rendered this page, when run from inside
        # one — lets the status line show only the current session's reports.
        "SESSION": html.escape(os.environ.get("CLAUDE_CODE_SESSION_ID", "")),
        "FAVICON": favicon_link("page"),
        "BREADCRUMB": breadcrumb(meta.folder),
        "ICONS": (TEMPLATE_DIR / "icons" / "sprite.svg").read_text(encoding="utf-8"),
        "TOOLBAR": content.toolbar,
        "CONTENT": content.body,
        "CHANGELOG": content.changelog,
        "BOOTSTRAP": json.dumps(content.comments_bootstrap, ensure_ascii=False),
        "HEAD_LIBS": head_libraries(content.body, content.assets),
        "STYLES": concatenate(TEMPLATE_DIR / "styles", STYLE_ORDER),
        "SCRIPTS": page_scripts(content.assets),
    }
    template = (TEMPLATE_DIR / "page.html").read_text(encoding="utf-8")
    for slot, value in slots.items():
        template = template.replace(f"{{{{{slot}}}}}", value)
    return template


def page_scripts(assets: PageAssets) -> str:
    """The always-on behavior, plus the initializers of the libraries in use."""
    scripts = [read_script(name) for name in SCRIPT_ORDER]
    if assets.charts:
        configs = json.dumps(assets.charts, ensure_ascii=False)
        scripts.append(read_script("charts.js").replace("{{CHART_CONFIGS}}", configs))
    if assets.has_mermaid:
        scripts.append(read_script("mermaid.js"))
    return "\n".join(f"<script>\n{body}\n</script>" for body in scripts)


def read_script(name: str) -> str:
    return (TEMPLATE_DIR / "scripts" / name).read_text(encoding="utf-8")


def concatenate(directory: Path, names: tuple[str, ...]) -> str:
    return "\n".join((directory / name).read_text(encoding="utf-8") for name in names)


def breadcrumb(folder_path: str) -> str:
    """The top bar's trail: the gallery, then each folder down to the page's own."""
    crumbs = ['<a href="index.html">Galerie</a>']
    segments = folder_path.split("/") if folder_path else []
    for depth in range(1, len(segments) + 1):
        folder = folders.folder("/".join(segments[:depth]))
        label = folder.label if folder is not None else segments[depth - 1]
        crumbs.append(f"<span>{html.escape(label)}</span>")
    separator = '<svg class="icon crumb-separator" aria-hidden="true"><use href="#vr-i-chevron-right"></use></svg>'
    return f'<nav class="reader-crumbs" aria-label="Emplacement">{separator.join(crumbs)}</nav>'


def heading_anchor(heading: str) -> str:
    """The DOM id markdown will give a heading — so links built outside the
    conversion (changelog, comment listings) point at the real anchor."""
    return toc_slugify(heading, "-")
