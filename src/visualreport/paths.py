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
from dataclasses import dataclass
from pathlib import Path

DEFAULT_ROOT = Path.home() / ".claude" / "html-reports"


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
