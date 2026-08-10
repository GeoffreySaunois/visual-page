"""Checks on the converted HTML that catch a broken source the browser hides."""

from __future__ import annotations

import re

PARAGRAPH_RE = re.compile(r"<p>(.*?)</p>", re.DOTALL)
LITERAL_MARKER_RE = re.compile(r"\n\s*(?:[-*+]|\d+\.)\s+\S")


def literal_list_markers(content: str) -> list[str]:
    """Warn when a list marker survives as literal text inside a paragraph.

    Classic cause: inside a list item, a fenced block or continuation paragraph
    that is not indented 4 spaces terminates the list, and the following
    ``- item`` lines are lazily absorbed into the paragraph — they render as
    literal "- " text instead of ``<li>``. The symptom in the output is always
    the same, which this scan catches regardless of cause.
    """
    warnings = []
    for paragraph in PARAGRAPH_RE.finditer(content):
        hit = LITERAL_MARKER_RE.search(paragraph.group(1))
        if not hit:
            continue
        excerpt = re.sub(r"<[^>]+>", "", paragraph.group(1)[hit.start() : hit.start() + 90]).strip()
        warnings.append(
            "literal list marker inside a paragraph — a list was probably broken by an "
            "unindented fence or a missing blank line (indent nested blocks/paragraphs "
            f"4 spaces inside list items, blank line before the next item): …{excerpt!r}…"
        )
    return warnings
