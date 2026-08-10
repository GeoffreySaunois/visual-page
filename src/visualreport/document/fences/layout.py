"""```cols — two markdown halves side by side."""

from __future__ import annotations

import html
from typing import Callable

import markdown

from .code import split_halves


def make_cols_formatter(nested_converter: Callable[[], markdown.Markdown]):
    """Each half is converted by its own nested converter: it shares the page's
    assets but drops the TOC extension, so column headings never reach the
    sidebar."""

    def format_cols(source, language, css_class, options, md, **kwargs) -> str:
        left_source, right_source = split_halves(source, "cols")
        columns = []
        for side, label, source_half in (
            ("left", options.get("left", ""), left_source),
            ("right", options.get("right", ""), right_source),
        ):
            inner = nested_converter().convert(source_half)
            label_html = f'<div class="col-label">{html.escape(label)}</div>' if label else ""
            columns.append(f'<div class="col col-{side}">{label_html}{inner}</div>')
        return f'<div class="cols">{"".join(columns)}</div>'

    return format_cols
