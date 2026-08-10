"""The comment API — what the page calls to write.

Every mutation returns the document's whole thread list with a fresh revision, so
a client is never left guessing what changed: it replaces its state and repaints.
Reads and writes both go through the locked store, which is also what the CLI
uses, so the agent and the browser can write at the same time.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from .. import comments
from ..document import parse_source, split_blocks
from ..paths import Archive


class AnchorRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    block_index: int
    quote: str
    prefix: str
    suffix: str


class NewThread(BaseModel):
    model_config = ConfigDict(extra="forbid")

    anchor: AnchorRequest | None
    body: str


class NewComment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body: str


def build_router(archive: Archive) -> APIRouter:
    router = APIRouter(prefix="/api")

    @router.get("/health")
    def health() -> dict:
        return {"ok": True, "archive": str(archive.root)}

    @router.get("/documents")
    def documents() -> dict:
        return {
            "documents": [
                summary(archive, document_id)
                for document_id in comments.commented_documents(archive)
            ]
        }

    @router.get("/documents/{document_id}/threads")
    def read_threads(document_id: str) -> dict:
        store = comments.store_for(archive, document_id)
        return comments.report_view(store.read(), store.revision)

    @router.post("/documents/{document_id}/threads")
    def create_thread(document_id: str, request: NewThread) -> dict:
        store = comments.store_for(archive, document_id)
        anchor, anchor_state = resolve_anchor(archive, document_id, request.anchor)
        with store.edit() as threads:
            threads.open_thread(
                anchor=anchor,
                state=anchor_state,
                author=comments.GEOFFREY,
                body=request.body,
                now=comments.now_utc(),
            )
        return view(store)

    @router.post("/documents/{document_id}/threads/{thread_id}/comments")
    def create_comment(document_id: str, thread_id: str, request: NewComment) -> dict:
        store = comments.store_for(archive, document_id)
        with store.edit() as threads:
            guard(threads, thread_id).add_comment(
                comments.GEOFFREY, request.body, comments.now_utc()
            )
        return view(store)

    @router.patch("/documents/{document_id}/threads/{thread_id}/comments/{comment_id}")
    def edit_comment(document_id: str, thread_id: str, comment_id: str, request: NewComment) -> dict:
        store = comments.store_for(archive, document_id)
        with store.edit() as threads:
            edited = guard(threads, thread_id)
            try:
                edited.edit_comment(comment_id, request.body, comments.now_utc())
            except comments.CommentError as error:
                raise HTTPException(status_code=404, detail=str(error)) from error
        return view(store)

    @router.delete("/documents/{document_id}/threads/{thread_id}/comments/{comment_id}")
    def delete_comment(document_id: str, thread_id: str, comment_id: str) -> dict:
        store = comments.store_for(archive, document_id)
        with store.edit() as threads:
            guard(threads, thread_id)
            try:
                threads.delete_comment(thread_id, comment_id, comments.now_utc())
            except comments.CommentError as error:
                raise HTTPException(status_code=404, detail=str(error)) from error
        return view(store)

    @router.post("/documents/{document_id}/threads/{thread_id}/resolve")
    def resolve_thread(document_id: str, thread_id: str) -> dict:
        store = comments.store_for(archive, document_id)
        with store.edit() as threads:
            guard(threads, thread_id).resolve(comments.GEOFFREY, comments.now_utc())
        return view(store)

    @router.post("/documents/{document_id}/threads/{thread_id}/reopen")
    def reopen_thread(document_id: str, thread_id: str) -> dict:
        store = comments.store_for(archive, document_id)
        with store.edit() as threads:
            guard(threads, thread_id).reopen(comments.now_utc())
        return view(store)

    @router.delete("/documents/{document_id}/threads/{thread_id}")
    def delete_thread(document_id: str, thread_id: str) -> dict:
        store = comments.store_for(archive, document_id)
        with store.edit() as threads:
            guard(threads, thread_id)
            threads.delete(thread_id)
        return view(store)

    return router


def view(store: comments.ThreadStore) -> dict:
    return comments.report_view(store.read(), store.revision)


def guard(threads: comments.ReportThreads, thread_id: str) -> comments.Thread:
    try:
        return threads.require(thread_id)
    except comments.CommentError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


def resolve_anchor(
    archive: Archive, document_id: str, request: AnchorRequest | None
) -> tuple[comments.Anchor | None, comments.AnchorState]:
    """Turn a selection into an anchor by reading the document's own source.

    The browser reports which block it selected in and what it selected; the
    source block and the section come from the archived markdown, so the agent
    gets a usable handle without the page having to send one.
    """
    if request is None:
        return None, comments.AnchorState.DOCUMENT
    source = archive.latest_source(document_id)
    if source is None:
        raise HTTPException(
            status_code=409,
            detail=f"aucune source archivée pour {document_id} — impossible d'ancrer",
        )
    blocks = split_blocks(parse_source(Path(source).read_text(encoding="utf-8"))[1])
    try:
        anchor = comments.anchor_on(
            blocks, request.block_index, request.quote, request.prefix, request.suffix
        )
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return anchor, comments.AnchorState.ANCHORED


def summary(archive: Archive, document_id: str) -> dict:
    """What the gallery needs to show a document's comment state."""
    threads = comments.store_for(archive, document_id).read()
    return {
        "document_id": document_id,
        "open": len(threads.open_threads),
        "awaiting_agent": len(threads.awaiting(comments.AuthorKind.AGENT)),
        "total": len(threads.threads),
    }
