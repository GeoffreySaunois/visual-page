"""A page's preview: the page cut down to what a gallery card shows of it.

A card frames the top of its page — the heading and the first blocks — so the
preview keeps the page's own frame and styles (the card's crop depends on that
layout) and drops everything a thumbnail never shows: every script, the
embedded threads, and the document past its first blocks. Images are kept
within a budget and replaced past it by a neutral box of the same role, so a
page built around multi-megabyte screenshots previews in a few hundred
kilobytes instead of its full weight.

The local archive writes one per page under `previews/` when the gallery is
rebuilt; the hosted service cuts them on request from the stored page.
"""

from __future__ import annotations

import re

from ..paths import Archive

PREVIEW_BLOCKS = 6
MARKUP_BUDGET = 40_000
IMAGE_BUDGET = 900_000

SCRIPT = re.compile(r"<script\b.*?</script>", re.IGNORECASE | re.DOTALL)
HANDLER = re.compile(r"""\son[a-z]+\s*=\s*(?:"[^"]*"|'[^']*')""", re.IGNORECASE)
MAIN_OPEN = re.compile(r"<main\b[^>]*>", re.IGNORECASE)
MAIN_CLOSE = re.compile(r"</main>", re.IGNORECASE)
BLOCK_START = re.compile(r'<(?:h[1-6]|div)\b[^>]*\bdata-vr-block="\d+"')
DATA_URI = re.compile(r'(\bsrc=")(data:[^"]*)(")', re.IGNORECASE)
PLACEHOLDER = (
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 10'%3E"
    "%3Crect width='16' height='10' fill='%23EFEDFA'/%3E%3C/svg%3E"
)
CLOSING = "\n</main>\n</div>\n</div>\n</div>\n</body>\n</html>\n"


def snapshot(page: str) -> str:
    """The preview of `page`: its frame and its first blocks, without scripts."""
    opening, closing = MAIN_OPEN.search(page), MAIN_CLOSE.search(page)
    if opening is None or closing is None or closing.start() < opening.end():
        return shrink_images(inert(page))
    body = page[opening.end() : closing.start()]
    kept = body[: cut_point(body)]
    return inert(page[: opening.end()]) + shrink_images(inert(kept)) + CLOSING


def inert(markup: str) -> str:
    """`markup` with nothing left to run: no script element, no inline handler.
    The preview frame would refuse them anyway, but each refusal is a console
    error on the gallery."""
    return HANDLER.sub("", SCRIPT.sub("", markup))


def cut_point(body: str) -> int:
    """Where the preview stops: before the first block past the block count or
    the markup budget (images aside), so every block it keeps is whole."""
    for count, start in enumerate(
        match.start() for match in BLOCK_START.finditer(body)
    ):
        if count >= PREVIEW_BLOCKS or markup_size(body[:start]) > MARKUP_BUDGET:
            return start
    return len(body)


def markup_size(markup: str) -> int:
    return len(DATA_URI.sub("", markup))


def shrink_images(markup: str) -> str:
    """Embedded images in page order while they fit the budget; a neutral box
    in place of each one after."""
    spent = 0

    def keep_or_replace(match: re.Match[str]) -> str:
        nonlocal spent
        spent += len(match[2])
        if spent <= IMAGE_BUDGET:
            return match[0]
        return match[1] + PLACEHOLDER + match[3]

    return DATA_URI.sub(keep_or_replace, markup)


def refresh(archive: Archive, page_names: list[str]) -> None:
    """Bring `previews/` in line with the archive: write the preview of every
    page newer than its own, and drop those whose page is gone."""
    archive.previews.mkdir(parents=True, exist_ok=True)
    for name in page_names:
        page, preview = archive.root / name, archive.previews / name
        if preview.exists() and preview.stat().st_mtime >= page.stat().st_mtime:
            continue
        source = page.read_text(encoding="utf-8", errors="replace")
        preview.write_text(snapshot(source), encoding="utf-8")
    wanted = set(page_names)
    for stale in archive.previews.glob("*.html"):
        if stale.name not in wanted:
            stale.unlink()
