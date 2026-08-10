"""The top-level block splitter — the unit every cross-version feature aligns on.

A *block* is the smallest chunk of a markdown source that both the iteration
diff and the comment anchors address: a paragraph, a heading, a fenced block, a
callout, a table, a list. Splitting is pragmatic rather than a full markdown
parse — good enough to align two versions of the same document and to hang a
comment off a passage that survived an edit.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

HEADING_RE = re.compile(r"^#{1,6}\s")
ADMONITION_RE = re.compile(r"^(!!!|\?\?\?)(\s|$)")
FENCE_RE = re.compile(r"^(`{3,}|~{3,})")
LIST_ITEM_RE = re.compile(r"^\s*([-*+]|\d+[.)])\s")
TABLE_RULE_RE = re.compile(r"^\s*\|?[\s:|-]*-[\s:|-]*$", re.MULTILINE)


@dataclass(frozen=True)
class Block:
    """One top-level block, with its position in the source it came from."""

    index: int
    text: str

    @property
    def normalized(self) -> str:
        """Whitespace-collapsed text — what similarity is measured on."""
        return normalize(self.text)

    @property
    def digest(self) -> str:
        return hashlib.sha1(self.normalized.encode("utf-8")).hexdigest()[:12]

    @property
    def is_heading(self) -> bool:
        return bool(HEADING_RE.match(self.text.lstrip()))

    @property
    def heading_text(self) -> str | None:
        match = re.match(r"#{1,6}\s+(.*)", self.text.strip())
        return match.group(1).strip() if match else None

    @property
    def is_prose(self) -> bool:
        """Prose = an ordinary paragraph, the only shape a word diff can splice
        into. Everything structural (heading, fence, callout, list, table) is not."""
        stripped = self.text.lstrip()
        if is_block_start(stripped):
            return False
        first_line = stripped.splitlines()[0] if stripped.splitlines() else ""
        if LIST_ITEM_RE.match(first_line):
            return False
        if "|" in self.text and TABLE_RULE_RE.search(self.text):
            return False
        return True

    def gist(self, length: int) -> str:
        """A short plain-text summary, for changelog lines and comment listings."""
        text = self.normalized
        text = re.sub(r"^#{1,6}\s*", "", text)
        text = re.sub(r"^(!!!|\?\?\?)\s*\w*\s*", "", text)
        text = re.sub(r"^(```|~~~)\w*\s*", "", text)
        text = re.sub(r"[`*_>#|]", "", text).strip()
        return text[:length].rstrip() + "…" if len(text) > length else text


def split_blocks(body: str) -> list[Block]:
    """Split a markdown body into top-level blocks.

    A block is a run of non-blank lines delimited by blank lines, with three
    exceptions kept whole even when they contain blank lines:
      - fenced blocks (``` or ~~~), verbatim to the matching close;
      - callouts and collapsibles (`!!! …` / `??? …`) plus their indented body;
      - headings, which are always a block of their own.
    """
    lines = body.split("\n")
    blocks: list[str] = []
    index, total = 0, len(lines)
    while index < total:
        line = lines[index]
        if not line.strip():
            index += 1
        elif HEADING_RE.match(line):
            blocks.append(line)
            index += 1
        elif (fence := opening_fence(line)) is not None:
            index = consume_fence(lines, index, fence, blocks)
        elif ADMONITION_RE.match(line):
            index = consume_admonition(lines, index, blocks)
        else:
            index = consume_paragraph(lines, index, blocks)
    return [Block(index=i, text=text) for i, text in enumerate(blocks)]


def consume_fence(lines: list[str], start: int, fence: str, out: list[str]) -> int:
    end = start + 1
    while end < len(lines) and not is_closing_fence(lines[end], fence):
        end += 1
    end += 1  # include the closing fence line (or run past EOF)
    out.append("\n".join(lines[start:end]))
    return end


def consume_admonition(lines: list[str], start: int, out: list[str]) -> int:
    end = start + 1
    while end < len(lines) and (not lines[end].strip() or lines[end][:1] in (" ", "\t")):
        end += 1
    last = end
    while last > start and not lines[last - 1].strip():
        last -= 1
    out.append("\n".join(lines[start:last]))
    return end


def consume_paragraph(lines: list[str], start: int, out: list[str]) -> int:
    end = start + 1
    while end < len(lines) and lines[end].strip() and not is_block_start(lines[end]):
        end += 1
    out.append("\n".join(lines[start:end]))
    return end


def opening_fence(line: str) -> str | None:
    match = FENCE_RE.match(line)
    return match.group(1) if match else None


def is_closing_fence(line: str, marker: str) -> bool:
    """A closing fence is a run of the marker char at least as long as the
    opener, alone on its line (superfences/CommonMark rule)."""
    return bool(re.match(rf"^{re.escape(marker[0])}{{{len(marker)},}}\s*$", line))


def is_block_start(line: str) -> bool:
    return bool(HEADING_RE.match(line) or ADMONITION_RE.match(line) or opening_fence(line))


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def nearest_heading(blocks: list[Block], index: int) -> str | None:
    """Text of the nearest heading at or before `index` — the section a block
    belongs to, used to label changes and comments."""
    for block in reversed(blocks[: index + 1]):
        if (heading := block.heading_text) is not None:
            return heading
    return None
