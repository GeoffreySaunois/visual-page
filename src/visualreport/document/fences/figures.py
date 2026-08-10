"""```chart and ```mermaid — the two fences that pull a JS library."""

from __future__ import annotations

import html
import json

from ..assets import PageAssets
from ..frontmatter import SourceError


def make_chart_formatter(assets: PageAssets):
    """A Chart.js config as strict JSON; colors and theme reactivity are added
    by the page's chart script, not here."""

    def format_chart(source, language, css_class, options, md, **kwargs) -> str:
        try:
            spec = json.loads(source)
        except json.JSONDecodeError as error:
            raise SourceError(f"invalid JSON in ```chart block: {error}") from error
        chart_id = assets.add_chart(spec)
        height = html.escape(options.get("height", "340"))
        parts = ['<figure class="fig-card">']
        if head := options.get("title", ""):
            parts.append(f'<div class="fig-head">{html.escape(head)}</div>')
        parts.append(
            f'<div style="position:relative;height:{height}px">'
            f'<canvas id="{chart_id}"></canvas></div>'
        )
        if caption := options.get("caption", ""):
            parts.append(f"<figcaption>{html.escape(caption)}</figcaption>")
        parts.append("</figure>")
        return "".join(parts)

    return format_chart


def make_mermaid_formatter(assets: PageAssets):
    def format_mermaid(source, language, css_class, options, md, **kwargs) -> str:
        assets.has_mermaid = True
        parts = ["<figure>", f'<div class="mermaid">{html.escape(source)}</div>']
        if caption := options.get("caption", ""):
            parts.append(f"<figcaption>{html.escape(caption)}</figcaption>")
        parts.append("</figure>")
        return "".join(parts)

    return format_mermaid
