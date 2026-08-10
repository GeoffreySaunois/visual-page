"""Assembling the HTML page from the template and its style/script partials.

The template is a skeleton with `{{SLOT}}` placeholders; the charte lives in
`templates/styles/*.css` and the behavior in `templates/scripts/*.js`, both
concatenated inline at build time so the page stays a single file. A new style
sheet or script is one file plus one entry in the order tuples below.
"""

from __future__ import annotations

import html
import json
from dataclasses import dataclass
from pathlib import Path

from markdown.extensions.toc import slugify as toc_slugify

from ..branding import favicon_link
from .assets import PageAssets
from .frontmatter import ReportMeta
from .libraries import head_libraries

TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates"
STYLE_ORDER = ("charte.css", "blocks.css", "iteration.css", "comments.css", "print.css")
SCRIPT_ORDER = ("page.js", "comments.js")


@dataclass(frozen=True)
class PageContent:
    """Everything the template needs beyond the metadata."""

    document_id: str
    body: str
    toc_tokens: list
    changelog: str
    side_controls: str
    comments_bootstrap: dict
    assets: PageAssets


def render_page(meta: ReportMeta, content: PageContent) -> str:
    slots = {
        "LANG": html.escape(meta.lang),
        "TITLE": html.escape(meta.title),
        "EYEBROW": html.escape(meta.eyebrow),
        "DATE": html.escape(meta.date),
        "SUBTITLE": html.escape(meta.subtitle),
        "DOCUMENT": html.escape(content.document_id),
        "FAVICON": favicon_link("page"),
        "TOC": render_toc(content.toc_tokens),
        "CONTENT": content.body,
        "CHANGELOG": content.changelog,
        "SIDE_CONTROLS": content.side_controls,
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


def render_toc(toc_tokens: list) -> str:
    """The sidebar table of contents, h2 with its h3 children."""

    def label(name: str) -> str:
        # The toc extension's `name` is already escaped; unescape then re-escape so
        # an entity resolves to exactly one level of escaping rather than double.
        return html.escape(html.unescape(str(name)))

    lines = []
    for h2 in toc_tokens:
        lines.append(f'    <a href="#{h2["id"]}">{label(h2["name"])}</a>')
        for h3 in h2.get("children", []):
            lines.append(f'    <a class="toc-h3" href="#{h3["id"]}">{label(h3["name"])}</a>')
    return "\n".join(lines)


def heading_anchor(heading: str) -> str:
    """The DOM id markdown will give a heading — so links built outside the
    conversion (changelog, comment listings) point at the real anchor."""
    return toc_slugify(heading, "-")
