"""The comment domain: threads anchored on a passage, replied to, then resolved.

The model follows what a document tool like Notion settled on, because the
behaviors are the ones that matter in practice:

- a **thread** is the unit — it anchors on a passage (or on the document as a
  whole), holds an ordered list of comments, and is either open or resolved;
- a thread is never silently lost when the text it points at is rewritten: it
  *drifts* (the block survived, the quoted words did not) or is *orphaned* (the
  block itself is gone), and stays visible either way;
- resolving hides a thread from the default view without deleting it, and it can
  be reopened.

One thing is ours rather than Notion's: both a human and an agent write here, so
every thread derives **who it is waiting on** — the participant who did not write
the last comment. That is what turns a comment list into an iteration loop.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

SCHEMA_VERSION = 2


class AuthorKind(StrEnum):
    HUMAN = "human"
    AGENT = "agent"


class Author(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: AuthorKind
    name: str

    @property
    def counterpart(self) -> AuthorKind:
        return AuthorKind.AGENT if self.kind is AuthorKind.HUMAN else AuthorKind.HUMAN


GEOFFREY = Author(kind=AuthorKind.HUMAN, name="Geoffrey")
CLAUDE = Author(kind=AuthorKind.AGENT, name="Claude")


class AnchorState(StrEnum):
    DOCUMENT = "document"  # a page-level thread, anchored to nothing in particular
    ANCHORED = "anchored"  # the quoted passage is still in the document
    DRIFTED = "drifted"  # the block survived, the quoted words did not
    ORPHANED = "orphaned"  # the block itself is gone


class Anchor(BaseModel):
    """Where a thread points, recorded so it survives a rewrite.

    `block_source` is the verbatim markdown of the block at the time the anchor
    was last resolved: it is both what re-anchoring matches on and what the agent
    reads to find the passage in the source file.
    """

    model_config = ConfigDict(extra="forbid")

    block_index: int
    block_digest: str
    block_source: str
    section: str | None
    quote: str
    prefix: str
    suffix: str


class Comment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    author: Author
    body: str
    created_at: datetime
    edited_at: datetime | None


class Resolution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    by: Author
    at: datetime


class Thread(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    anchor: Anchor | None
    state: AnchorState
    comments: list[Comment]
    # Counted rather than derived from the list, so a deleted comment never sees
    # its id handed to a later one.
    next_comment_number: int
    resolution: Resolution | None
    created_at: datetime
    updated_at: datetime

    @property
    def is_open(self) -> bool:
        return self.resolution is None

    @property
    def last_comment(self) -> Comment:
        return self.comments[-1]

    @property
    def awaiting(self) -> AuthorKind | None:
        """Who owes the next move — nobody once the thread is resolved."""
        if not self.is_open or not self.comments:
            return None
        return self.last_comment.author.counterpart

    def add_comment(self, author: Author, body: str, now: datetime) -> Comment:
        comment = Comment(
            id=f"{self.id}.{self.next_comment_number}",
            author=author,
            body=body,
            created_at=now,
            edited_at=None,
        )
        self.next_comment_number += 1
        self.comments.append(comment)
        self.updated_at = now
        return comment

    def find_comment(self, comment_id: str) -> Comment | None:
        return next((comment for comment in self.comments if comment.id == comment_id), None)

    def require_comment(self, comment_id: str) -> Comment:
        comment = self.find_comment(comment_id)
        if comment is None:
            known = ", ".join(c.id for c in self.comments)
            raise CommentError(f"message inconnu : {comment_id} (existants : {known})")
        return comment

    def edit_comment(self, comment_id: str, body: str, now: datetime) -> Comment:
        """Rewrite a message, keeping its author and its place in the exchange."""
        comment = self.require_comment(comment_id)
        comment.body = body
        comment.edited_at = now
        self.updated_at = now
        return comment

    def remove_comment(self, comment_id: str, now: datetime) -> None:
        self.require_comment(comment_id)
        self.comments = [comment for comment in self.comments if comment.id != comment_id]
        self.updated_at = now

    def resolve(self, author: Author, now: datetime) -> None:
        self.resolution = Resolution(by=author, at=now)
        self.updated_at = now

    def reopen(self, now: datetime) -> None:
        self.resolution = None
        self.updated_at = now


class ReportThreads(BaseModel):
    """Every thread of one report — the whole content of its comments file."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int
    document_id: str
    next_number: int
    threads: list[Thread]

    @classmethod
    def empty(cls, document_id: str) -> ReportThreads:
        return cls(
            schema_version=SCHEMA_VERSION, document_id=document_id, next_number=1, threads=[]
        )

    @property
    def open_threads(self) -> list[Thread]:
        return [thread for thread in self.threads if thread.is_open]

    def awaiting(self, kind: AuthorKind) -> list[Thread]:
        return [thread for thread in self.open_threads if thread.awaiting is kind]

    def find(self, thread_id: str) -> Thread | None:
        return next((thread for thread in self.threads if thread.id == thread_id), None)

    def require(self, thread_id: str) -> Thread:
        thread = self.find(thread_id)
        if thread is None:
            known = ", ".join(t.id for t in self.threads) or "aucun"
            raise CommentError(f"thread inconnu : {thread_id} (existants : {known})")
        return thread

    def open_thread(
        self, anchor: Anchor | None, state: AnchorState, author: Author, body: str, now: datetime
    ) -> Thread:
        thread = Thread(
            id=f"t{self.next_number}",
            anchor=anchor,
            state=state,
            comments=[],
            next_comment_number=1,
            resolution=None,
            created_at=now,
            updated_at=now,
        )
        thread.add_comment(author, body, now)
        self.next_number += 1
        self.threads.append(thread)
        return thread

    def delete(self, thread_id: str) -> None:
        self.threads = [thread for thread in self.threads if thread.id != self.require(thread_id).id]

    def delete_comment(self, thread_id: str, comment_id: str, now: datetime) -> bool:
        """Remove one message. A thread with nothing left in it is itself removed —
        an empty thread would keep an anchor and a highlight with nothing to say.
        Returns whether the thread went away."""
        thread = self.require(thread_id)
        thread.remove_comment(comment_id, now)
        if thread.comments:
            return False
        self.delete(thread_id)
        return True


class CommentError(Exception):
    """An operation the comment store refuses — a bad id, an unknown thread."""


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
