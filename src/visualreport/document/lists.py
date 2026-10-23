"""Lists that start right under a paragraph line, as CommonMark reads them.

Python-Markdown only opens a list after a blank line: a `- ` item written on
the line after a sentence stays inside the paragraph, and the whole list renders
as one run of prose with literal dashes. Agents write lists that way, so before
the block parser runs, a blank line is inserted between a paragraph and an item
starting at the paragraph's own indentation or less: a nested paragraph is
closed by an item of an enclosing list just as a top-level one is by its own
item. Like CommonMark, only a bullet or
an ordered item numbered 1 interrupts a paragraph. Fences are stashed by then,
so their bodies are never touched.
"""

from __future__ import annotations

import re

import markdown
from markdown.preprocessors import Preprocessor

LIST_ITEM = re.compile(r"(?P<indent> *)(?:[-*+]|1[.)]) +\S")

# After the fences are stashed (25), before HTML blocks are (20): the blocks
# wrapped in `markdown="1"` divs are still plain lines here.
PRIORITY = 22


class ParagraphListSeparator(Preprocessor):
    def run(self, lines: list[str]) -> list[str]:
        separated: list[str] = []
        paragraph_start: str | None = None
        for line in lines:
            if not line.strip():
                paragraph_start = None
            elif paragraph_start is None:
                paragraph_start = line
            elif interrupts(paragraph_start, line):
                separated.append("")
                paragraph_start = line
            separated.append(line)
        return separated


def interrupts(paragraph_start: str, line: str) -> bool:
    """Whether `line` opens a list under a paragraph that began with
    `paragraph_start`, rather than continuing a list or a nested item."""
    item = LIST_ITEM.match(line)
    if item is None or LIST_ITEM.match(paragraph_start):
        return False
    return len(item["indent"]) <= len(indentation(paragraph_start))


def indentation(line: str) -> str:
    return line[: len(line) - len(line.lstrip(" "))]


def separate_lists_from_paragraphs(converter: markdown.Markdown) -> None:
    converter.preprocessors.register(
        ParagraphListSeparator(converter), "paragraph_list_separator", PRIORITY
    )
