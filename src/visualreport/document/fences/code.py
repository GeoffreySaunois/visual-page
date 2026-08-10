"""```diff — code changes, unified by default, split for a genuine before/after."""

from __future__ import annotations

import html

from ..frontmatter import SourceError

HALF_SEPARATOR = "~~~"


def format_diff(source, language, css_class, options, md, **kwargs) -> str:
    mode = options.get("mode", "unified")
    if mode not in ("unified", "split"):
        raise SourceError(f'```diff mode must be "unified" or "split", got {mode!r}')
    title = options.get("title", "")
    if mode == "unified":
        body = render_unified(source, title)
    else:
        left, right = split_halves(source, "diff")
        body = render_split(
            left, right, options.get("left", "Avant"), options.get("right", "Après"), title
        )
    return f'<figure class="diff">{body}</figure>'


def render_unified(source: str, title: str) -> str:
    """One row per source line; the marker prefix picks the row kind and the slim
    gutter carries the +/− sign (the tint carries the semantics)."""
    rows = []
    for line in source.rstrip("\n").split("\n"):
        if line.startswith("+ ") or line == "+":
            rows.append(unified_row("add", "+", line[2:]))
        elif line.startswith("- ") or line == "-":
            rows.append(unified_row("del", "−", line[2:]))
        elif line.startswith("@ ") or line == "@":
            rows.append(
                '<tr class="annot"><td colspan="2">'
                f'<span class="marker">▸</span>{html.escape(line[2:])}</td></tr>'
            )
        else:
            rows.append(unified_row("ctx", "", line))
    caption = f"<caption><code>{html.escape(title)}</code></caption>" if title else ""
    return f'<table class="diff-table">{caption}<tbody>{"".join(rows)}</tbody></table>'


def unified_row(kind: str, sign: str, text: str) -> str:
    code = html.escape(text) if text else "&nbsp;"
    return f'<tr class="{kind}"><td class="gut">{sign}</td><td class="code">{code}</td></tr>'


def render_split(left: str, right: str, left_label: str, right_label: str, title: str) -> str:
    parts = []
    if title:
        parts.append(f'<div class="diff-title"><code>{html.escape(title)}</code></div>')
    parts.append(
        '<div class="diff-split">'
        f'<div class="diff-half left"><div class="col-label">{html.escape(left_label)}</div>'
        f"<pre>{html.escape(left)}</pre></div>"
        f'<div class="diff-half right"><div class="col-label">{html.escape(right_label)}</div>'
        f"<pre>{html.escape(right)}</pre></div>"
        "</div>"
    )
    return "".join(parts)


def split_halves(source: str, fence: str) -> tuple[str, str]:
    """Split a two-half fence body on its lone `~~~` line."""
    lines = source.split("\n")
    if HALF_SEPARATOR not in lines:
        raise SourceError(
            f"```{fence} block needs a line containing exactly `{HALF_SEPARATOR}` "
            "between its two halves"
        )
    cut = lines.index(HALF_SEPARATOR)
    return "\n".join(lines[:cut]).strip("\n"), "\n".join(lines[cut + 1 :]).strip("\n")
