"""Checks that catch a broken source the browser hides — on the blocks it was
split into, and on the HTML they converted to."""

from __future__ import annotations

import re

from .blocks import Block

PARAGRAPH_RE = re.compile(r"<p>(.*?)</p>", re.DOTALL)
LITERAL_MARKER_RE = re.compile(r"\n\s*(?:[-*+]|\d+\.)\s+\S")
ORPHAN_NEST_RE = re.compile(r"^(?: {4,}|\t)\s*(`{3,}|~{3,}|!!!|\?\?\?)")


def orphaned_nested_blocks(blocks: list[Block]) -> list[str]:
    """Warn when a fence or a callout opens indented with nothing to nest under.

    Indented content belongs to the passage above it — a list item, a tab body.
    A block that *starts* indented has no such passage: the previous block is a
    heading, a fence, or the document begins there. Markdown then reads the 4
    spaces as an indented code block and the ``` or the ``!!!`` shows as literal
    text, which the browser displays without complaining.
    """
    warnings = []
    for block in blocks:
        first_line = block.text.splitlines()[0] if block.text.splitlines() else ""
        if not (hit := ORPHAN_NEST_RE.match(first_line)):
            continue
        warnings.append(
            f"indented {hit.group(1)} block with nothing above it to nest under — it renders "
            "as literal text inside a code block (remove the indentation, or move the block "
            f"under the list item / tab it belongs to): {first_line.strip()[:70]!r}"
        )
    return warnings


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
