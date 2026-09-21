"""Comment operations with access checks inside the metadata transaction."""

from dataclasses import dataclass

from fastapi import HTTPException

from .. import comments
from ..document import parse_source, split_blocks
from .reports import Report


@dataclass(frozen=True)
class CommentAction:
    kind: str
    thread_id: str | None
    comment_id: str | None
    body: str | None
    anchor: dict | None

    def apply(self, report: Report, email: str, owners: set[str], source: str) -> None:
        report.authorize(email, True, owners)
        author = comments.Author(kind=comments.AuthorKind.HUMAN, name=email)
        if self.kind == "create":
            self.create(report, author, source)
            return
        try:
            self.update_thread(report, author, owners)
        except comments.CommentError as error:
            raise HTTPException(404, "Comment or thread not found") from error

    def create(self, report: Report, author: comments.Author, source: str) -> None:
        anchor, state = None, comments.AnchorState.DOCUMENT
        if self.anchor is not None:
            blocks = split_blocks(parse_source(source)[1])
            try:
                anchor = comments.anchor_on(blocks, **self.anchor)
            except (ValueError, IndexError) as error:
                raise HTTPException(
                    409, "Comment anchor does not match the report"
                ) from error
            state = comments.AnchorState.ANCHORED
        report.threads.open_thread(anchor, state, author, self.body, comments.now_utc())

    def update_thread(
        self, report: Report, author: comments.Author, owners: set[str]
    ) -> None:
        thread = report.threads.require(self.thread_id)
        now = comments.now_utc()
        if self.kind == "reply":
            thread.add_comment(author, self.body, now)
        elif self.kind in {"edit", "delete_comment"}:
            comment = thread.require_comment(self.comment_id)
            report.authorize_comment(author.name, comment.author.name, owners)
            if self.kind == "edit":
                thread.edit_comment(self.comment_id, self.body, now)
            else:
                report.threads.delete_comment(self.thread_id, self.comment_id, now)
        else:
            report.authorize_owner(author.name, owners)
            if self.kind == "resolve":
                thread.resolve(author, now)
            elif self.kind == "reopen":
                thread.reopen(now)
            elif self.kind == "delete_thread":
                report.threads.delete(self.thread_id)
            else:
                raise ValueError("Unknown comment operation")
