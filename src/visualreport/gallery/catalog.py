"""Reading the archive back: what pages exist, and what is pending on each.

The pages are the source of truth — each one carries its own metadata in
`<meta name="report-*">` tags, with a `<title>` and the date in the filename as
fallbacks for pages rendered before those tags existed.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from pathlib import Path

from .. import comments
from ..paths import Archive

DATE_IN_NAME = re.compile(r"-(\d{4}-\d{2}-\d{2})\.html$")
TITLE_RE = re.compile(r"<title>(.*?)</title>", re.IGNORECASE | re.DOTALL)


@dataclass(frozen=True)
class Entry:
    """One page in the gallery."""

    href: str
    document_id: str
    kind: str
    title: str
    eyebrow: str
    subtitle: str
    date: str
    modified: float
    open_comments: int
    awaiting_agent: int

    @property
    def sort_key(self) -> tuple[str, float]:
        return self.date, self.modified

    @property
    def haystack(self) -> str:
        return " ".join(part for part in (self.title, self.eyebrow, self.subtitle) if part).lower()


def collect(archive: Archive) -> list[Entry]:
    entries = [
        read_entry(archive, path)
        for path in sorted(archive.root.glob("*.html"))
        if path.name != "index.html"
    ]
    return sorted(entries, key=lambda entry: entry.sort_key, reverse=True)


def read_entry(archive: Archive, path: Path) -> Entry:
    source = path.read_text(encoding="utf-8", errors="replace")
    date_match = DATE_IN_NAME.search(path.name)
    date = meta(source, "date") or (date_match.group(1) if date_match else "")
    identity = meta(source, "document") or path.name.removesuffix(
        f"-{date}.html" if date else ".html"
    )
    threads = comments.store_for(archive, identity).read()
    return Entry(
        href=path.name,
        document_id=identity,
        kind=identity.split("-")[0],
        title=meta(source, "title") or title_of(source) or path.stem,
        eyebrow=meta(source, "eyebrow") or "",
        subtitle=meta(source, "subtitle") or "",
        date=date,
        modified=path.stat().st_mtime,
        open_comments=len(threads.open_threads),
        awaiting_agent=len(threads.awaiting(comments.AuthorKind.AGENT)),
    )


def meta(source: str, name: str) -> str | None:
    pattern = rf'<meta\s+name="report-{re.escape(name)}"\s+content="([^"]*)"'
    match = re.search(pattern, source, re.IGNORECASE)
    return html.unescape(match.group(1)).strip() if match else None


def title_of(source: str) -> str | None:
    match = TITLE_RE.search(source)
    return html.unescape(match.group(1)).strip() if match else None
