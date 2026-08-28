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
# Content nested under the block above it: the 4-space (or tab) indent markdown
# requires of a fence or a paragraph continuing a list item or a tab body.
CONTINUATION_RE = re.compile(r"^(?: {4,}|\t)\s*\S")
# `![alt](path)` and `[text](url)`, reduced to what a person reads. An image's
# path is an absolute local one — the source addresses a file on disk — so left
# in, it is what a changelog line about a screenshot would consist of.
IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)]*)\)")
LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)]*)\)")


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
        text = IMAGE_RE.sub(_image_gist, text)
        text = LINK_RE.sub(r"\1", text)
        text = re.sub(r"[`*_>#|]", "", text).strip()
        return text[:length].rstrip() + "…" if len(text) > length else text


def split_blocks(body: str) -> list[Block]:
    """Split a markdown body into top-level blocks.

    A block is a run of non-blank lines delimited by blank lines, with four
    exceptions kept whole even when they contain blank lines:
      - fenced blocks (``` or ~~~), verbatim to the matching close;
      - callouts and collapsibles (`!!! …` / `??? …`) plus their indented body;
      - headings, which are always a block of their own;
      - a paragraph and the indented content nested under it — the fences and
        continuation paragraphs of a list item or of a tab body, which belong to
        the passage they hang from and are meaningless on their own.
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
    """A paragraph (a list included) together with everything indented under it.

    Markdown nests a fence or a continuation paragraph inside a list item — or
    inside a tab body — behind a blank line and a 4-space indent. Ending the
    block on that blank line would leave the indented part alone in a block of
    its own, where the 4 spaces read as an indented code block and a fence shows
    as literal text.
    """
    end = consume_run(lines, start)
    while (nested := continuation_start(lines, end)) is not None:
        end = consume_run(lines, nested)
    out.append("\n".join(lines[start:end]))
    return end


def consume_run(lines: list[str], start: int) -> int:
    """One run of non-blank lines, stopping at the next top-level construct.
    An indented fence inside the run is opaque: its body may hold blank lines
    and lines of any indentation."""
    end = start
    while end < len(lines) and lines[end].strip():
        if end > start and is_block_start(lines[end]):
            break
        if (fence := indented_fence(lines[end])) is not None:
            end = skip_fence_body(lines, end, fence)
            continue
        end += 1
    return end


def continuation_start(lines: list[str], end: int) -> int | None:
    """Index of the indented content hanging under the run that ends at `end`,
    across the blank lines between them — `None` when what follows starts a
    block of its own."""
    probe = end
    while probe < len(lines) and not lines[probe].strip():
        probe += 1
    if probe == end or probe >= len(lines):
        return None
    return probe if CONTINUATION_RE.match(lines[probe]) else None


def skip_fence_body(lines: list[str], start: int, fence: str) -> int:
    end = start + 1
    while end < len(lines) and not is_closing_fence(lines[end].lstrip(), fence):
        end += 1
    return min(end + 1, len(lines))


def indented_fence(line: str) -> str | None:
    """The fence marker of a fence opened under an indent — the shape a fence
    takes inside a list item. A fence at column 0 is a block of its own."""
    if not CONTINUATION_RE.match(line):
        return None
    return opening_fence(line.lstrip())


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


def _image_gist(match: re.Match[str]) -> str:
    """What an image contributes to a summary line: its alt text when it carries
    one, its file name otherwise. Never its path — a changelog reads to a person,
    and a directory tree tells them nothing about which picture moved."""
    alt = match.group(1).strip()
    if alt:
        return alt
    name = match.group(2).strip().rsplit("/", 1)[-1]
    return f"image {name}" if name else "image"
