"""Persistence: one JSON file per report, safe for two writers.

The page (through the server) and the agent (through the CLI) both write, and
neither goes through the other: every mutation takes an exclusive lock, re-reads
the file, applies the change, and replaces the file atomically. So the agent can
comment while nothing is served, and the page picks it up on its next poll.
"""

from __future__ import annotations

import fcntl
import os
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from pydantic import ValidationError

from ..paths import Archive
from .model import SCHEMA_VERSION, CommentError, ReportThreads


@dataclass(frozen=True)
class ThreadStore:
    """The comment file of one report."""

    document_id: str
    path: Path

    @property
    def lock_path(self) -> Path:
        return self.path.with_suffix(".lock")

    @property
    def revision(self) -> int:
        """A cheap change token the page polls on — the file's mtime in ns."""
        return self.path.stat().st_mtime_ns if self.path.exists() else 0

    def read(self) -> ReportThreads:
        if not self.path.exists():
            return ReportThreads.empty(self.document_id)
        try:
            threads = ReportThreads.model_validate_json(self.path.read_text(encoding="utf-8"))
        except ValidationError as error:
            raise CommentError(f"fichier de commentaires illisible : {self.path}\n{error}") from error
        if threads.schema_version != SCHEMA_VERSION:
            raise CommentError(
                f"{self.path} est en schéma v{threads.schema_version}, "
                f"ce binaire lit v{SCHEMA_VERSION}"
            )
        return threads

    @contextmanager
    def edit(self) -> Iterator[ReportThreads]:
        """Read-modify-write under an exclusive lock; the write is atomic."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.lock_path, "w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                threads = self.read()
                yield threads
                self.write(threads)
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def write(self, threads: ReportThreads) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = threads.model_dump_json(indent=2)
        temporary = self.path.with_suffix(".json.tmp")
        temporary.write_text(payload + "\n", encoding="utf-8")
        os.replace(temporary, self.path)


def store_for(archive: Archive, document_id: str) -> ThreadStore:
    return ThreadStore(document_id=document_id, path=archive.threads_of(document_id))


def commented_documents(archive: Archive) -> list[str]:
    """Every report that has a comment file, for the gallery's counters."""
    if not archive.comments.is_dir():
        return []
    return sorted(path.stem for path in archive.comments.glob("*.json"))
