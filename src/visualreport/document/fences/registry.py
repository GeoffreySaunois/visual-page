"""The custom-fence table handed to pymdownx.superfences.

Adding a fence to the dialect means one formatter and one line here.
"""

from __future__ import annotations

import re
from typing import Callable

import markdown

from ..assets import PageAssets
from ..frontmatter import SourceError
from .code import format_diff
from .data import format_filetree, format_kpi, format_transcript
from .figures import make_chart_formatter, make_mermaid_formatter
from .filmstrip import format_filmstrip
from .layout import make_cols_formatter

OPTION_KEYS = ("caption", "title", "height", "left", "right", "mode")
OPTION_LINE_RE = re.compile(rf'^\s*({"|".join(OPTION_KEYS)})\s*=\s*".*"\s*$')


def custom_fences(
    assets: PageAssets, nested_converter: Callable[[], markdown.Markdown]
) -> list[dict]:
    """Every fence is guarded against options written one line too low, except
    ```diff whose verbatim body may legitimately contain such a line."""
    guarded = {
        "chart": make_chart_formatter(assets),
        "mermaid": make_mermaid_formatter(assets),
        "kpi": format_kpi,
        "filetree": format_filetree,
        "cols": make_cols_formatter(nested_converter),
        "transcript": format_transcript,
        "filmstrip": format_filmstrip,
    }
    fences = [
        {"name": name, "class": name, "validator": accept_options, "format": guard_options(fmt)}
        for name, fmt in guarded.items()
    ]
    fences.append(
        {"name": "diff", "class": "diff", "validator": accept_options, "format": format_diff}
    )
    return fences


def accept_options(language, inputs, options, attrs, md) -> bool:
    """Accept any key="value" pair on the fence header as an option."""
    options.update(inputs)
    return True


def guard_options(formatter):
    """Reject fence options written on the line *below* the fence marker.

    Options belong on the fence line itself (```mermaid caption="…"). One line
    lower they are body content, and the failure is silent or cryptic: mermaid
    parses `caption="…"` as its first statement and the diagram dies in the
    browser with "Syntax error in text", a ```cols label becomes prose atop the
    left column, a ```chart reports only "invalid JSON". The page still renders,
    so nothing surfaces at build time — hence a hard failure here, naming the fix.
    """

    def guarded(source, language, css_class, options, md, **kwargs) -> str:
        if stray := leading_option_lines(source):
            raise SourceError(
                f"```{language} — fence options written inside the block body: "
                f"{', '.join(stray)}\n"
                f"  move them onto the fence line: ```{language} {' '.join(stray)}"
            )
        return formatter(source, language, css_class, options, md, **kwargs)

    return guarded


def leading_option_lines(source: str) -> list[str]:
    """The `key="value"` lines at the top of a fence body, before any content."""
    stray = []
    for line in source.splitlines():
        if not line.strip():
            continue
        if not OPTION_LINE_RE.match(line):
            break
        stray.append(line.strip())
    return stray
