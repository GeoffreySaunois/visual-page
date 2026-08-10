"""The archive layout — the single place that knows where things live on disk.

Everything a report accumulates sits under one directory outside any repo:

    ~/.claude/html-reports/
      report-<slug>-<date>.html     the rendered pages
      index.html                    the gallery
      src/report-<slug>-<date>.md   the markdown sources, kept for re-renders
      comments/<slug>.json          the comment threads of a report
      logs/server.log               the comment server's output
      logs/tunnel.log               the cloudflared tunnel's output
      .server.json                  the running server's pid + port
      .tunnel.json                  the running tunnel's pid + metrics port + hostname
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

DEFAULT_ROOT = Path.home() / ".claude" / "html-reports"

PAGE_NAME = re.compile(r"^(?P<document>[a-z][a-z0-9]*-.+)-(?P<day>\d{4}-\d{2}-\d{2})\.html$")


@dataclass(frozen=True)
class ArchivedPage:
    """A rendered page, read back from its filename.

    The name carries everything that identifies it: the document it belongs to,
    and the date it was published at — the date a re-render has to keep.
    """

    path: Path
    document_id: str
    day: str


@dataclass(frozen=True)
class Archive:
    """A report archive rooted at `root`."""

    root: Path

    @property
    def sources(self) -> Path:
        return self.root / "src"

    @property
    def comments(self) -> Path:
        return self.root / "comments"

    @property
    def logs(self) -> Path:
        return self.root / "logs"

    @property
    def index(self) -> Path:
        return self.root / "index.html"

    @property
    def server_state(self) -> Path:
        return self.root / ".server.json"

    @property
    def tunnel_state(self) -> Path:
        return self.root / ".tunnel.json"

    def page(self, prefix: str, slug: str, day: str) -> Path:
        return self.root / f"{prefix}-{slug}-{day}.html"

    def previous_source(self, document_id: str) -> Path:
        """The version of a document last rendered — what the next iteration diff
        compares against. Kept per document rather than per date, so refining a
        page twice in the same day still shows a delta."""
        return self.sources / ".last-rendered" / f"{document_id}.md"

    def pages(self) -> list[ArchivedPage]:
        """Every rendered page of the archive, in filename order.

        The gallery is not one of them, and neither is anything whose name does
        not end on a date — those were not written by a render.
        """
        if not self.root.is_dir():
            return []
        read = (archived_page(path) for path in sorted(self.root.glob("*.html")))
        return [page for page in read if page is not None]

    def source_of(self, page: Path) -> Path:
        """The archived markdown source belonging to a rendered page."""
        return self.sources / (page.stem + ".md")

    def sources_of(self, document_id: str) -> list[Path]:
        """Every archived source of a document, oldest first (filenames sort by ISO date)."""
        return sorted(self.sources.glob(f"{document_id}-*.md"))

    def latest_source(self, document_id: str) -> Path | None:
        candidates = self.sources_of(document_id)
        return candidates[-1] if candidates else None

    def threads_of(self, document_id: str) -> Path:
        return self.comments / f"{document_id}.json"

    def holds(self, page: Path) -> bool:
        """Whether a rendered page belongs to this archive (vs an explicit -o path)."""
        return page.parent == self.root


def archived_page(path: Path) -> ArchivedPage | None:
    """Read a page's document and date off its name, or nothing if the name is
    not one a render produced."""
    match = PAGE_NAME.match(path.name)
    if match is None:
        return None
    return ArchivedPage(path=path, document_id=match["document"], day=match["day"])


def default_archive() -> Archive:
    """The archive every command works on. `VISUAL_REPORT_ARCHIVE` moves it —
    used by the tests, and by anyone who wants a scratch archive."""
    override = os.environ.get("VISUAL_REPORT_ARCHIVE")
    return Archive(Path(override).expanduser() if override else DEFAULT_ROOT)


def document_id(kind: str, slug: str) -> str:
    """The identity of a document across its renders — the page filename without
    the date. Comments and iterations are keyed on it, so a `plan` and a `report`
    that happen to share a slug stay separate documents."""
    return f"{kind}-{slug}"
