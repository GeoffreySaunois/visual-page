"""Authenticated report APIs compatible with the rendered comment panel."""

from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..comments import AuthorKind, report_view
from ..server.api import AnchorRequest
from .comments import CommentAction
from .identity import AccessIdentity
from .publication import Publication, publish
from .reports import Role
from .service import ReportService


class Actor(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # Public API: browsers omit this field; agent attribution requires ownership.
    actor: AuthorKind = AuthorKind.HUMAN


class Message(Actor):
    model_config = ConfigDict(extra="forbid")
    body: str = Field(min_length=1, max_length=20_000)


class NewThread(Message):
    anchor: AnchorRequest | None


class Share(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str
    role: Role | None

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        value = value.strip().lower()
        if "@" not in value or len(value) > 254 or any(c.isspace() for c in value):
            raise ValueError("Expected an email address")
        return value


def router(service: ReportService, identity: AccessIdentity) -> APIRouter:
    routes = APIRouter(prefix="/api")

    def authenticated(request: Request) -> str:
        return identity.email(request.headers.get("Cf-Access-Jwt-Assertion"))

    User = Annotated[str, Depends(authenticated)]

    @routes.get("/health")
    def health(email: User):
        return {"ok": True}

    @routes.get("/documents")
    def documents(email: User):
        return {
            "documents": [
                r.summary()
                for r in service.reports.visible(email, email in service.owners)
            ]
        }

    @routes.post("/publish")
    def publication(body: Publication, email: User):
        return publish(
            service.reports, service.objects, body, email, service.owners
        ).summary()

    @routes.put("/documents/{document_id}/shares")
    def share(document_id: str, body: Share, email: User):
        report = service.share(document_id, email, body.email, body.role)
        return {"grants": report.grants}

    @routes.get("/documents/{document_id}/shares")
    def shares(document_id: str, email: User):
        report = service.read(document_id, email)
        report.authorize_owner(email, service.owners)
        return {"owner": report.owner, "grants": report.grants}

    @routes.get("/documents/{document_id}/threads")
    def threads(document_id: str, email: User):
        report = service.read(document_id, email)
        return report_view(report.threads, report.revision)

    @routes.post("/documents/{document_id}/threads")
    def create(document_id: str, body: NewThread, email: User):
        action = CommentAction(
            "create",
            None,
            None,
            body.body,
            body.anchor.model_dump() if body.anchor else None,
            body.actor,
        )
        report = service.comment(document_id, email, action)
        return report_view(report.threads, report.revision)

    @routes.post("/documents/{document_id}/threads/{thread_id}/comments")
    def reply(document_id: str, thread_id: str, body: Message, email: User):
        report = service.comment(
            document_id,
            email,
            CommentAction("reply", thread_id, None, body.body, None, body.actor),
        )
        return report_view(report.threads, report.revision)

    @routes.patch("/documents/{document_id}/threads/{thread_id}/comments/{comment_id}")
    def edit(
        document_id: str, thread_id: str, comment_id: str, body: Message, email: User
    ):
        report = service.comment(
            document_id,
            email,
            CommentAction("edit", thread_id, comment_id, body.body, None, body.actor),
        )
        return report_view(report.threads, report.revision)

    @routes.delete("/documents/{document_id}/threads/{thread_id}/comments/{comment_id}")
    def delete_comment(document_id: str, thread_id: str, comment_id: str, email: User):
        report = service.comment(
            document_id,
            email,
            CommentAction(
                "delete_comment", thread_id, comment_id, None, None, AuthorKind.HUMAN
            ),
        )
        return report_view(report.threads, report.revision)

    @routes.delete("/documents/{document_id}/threads/{thread_id}")
    def delete_thread(document_id: str, thread_id: str, email: User):
        report = service.comment(
            document_id,
            email,
            CommentAction(
                "delete_thread", thread_id, None, None, None, AuthorKind.HUMAN
            ),
        )
        return report_view(report.threads, report.revision)

    @routes.post("/documents/{document_id}/threads/{thread_id}/{operation}")
    def lifecycle(
        document_id: str,
        thread_id: str,
        operation: str,
        email: User,
        body: Annotated[Actor | None, Body()] = None,
    ):
        if operation not in {"resolve", "reopen"}:
            raise HTTPException(404, "Unknown operation")
        report = service.comment(
            document_id,
            email,
            CommentAction(
                operation,
                thread_id,
                None,
                None,
                None,
                body.actor if body else AuthorKind.HUMAN,
            ),
        )
        return report_view(report.threads, report.revision)

    return routes
