"""Report ownership, sharing and comment permissions."""

from enum import StrEnum
from typing import TYPE_CHECKING

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field

from ..comments import ReportThreads

if TYPE_CHECKING:
    from .access import Access


class Role(StrEnum):
    READER = "reader"
    COMMENTER = "commenter"


STRENGTH = {Role.READER: 1, Role.COMMENTER: 2}


def strongest(roles: list[Role | None]) -> Role | None:
    granted = [role for role in roles if role is not None]
    return max(granted, key=STRENGTH.__getitem__, default=None)


class Report(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str
    title: str
    eyebrow: str
    subtitle: str
    folder: str
    date: str
    owner: str
    grants: dict[str, Role]
    page_name: str
    html_key: str
    source_key: str | None
    threads: ReportThreads
    revision: int = Field(ge=1)

    def role(self, email: str, access: "Access") -> Role | None:
        return strongest(
            [self.grants.get(email), access.folder_role(self.folder, email)]
        )

    def authorize(self, email: str, write: bool, access: "Access") -> None:
        if email == self.owner or access.is_owner(email):
            return
        role = self.role(email, access)
        if role is None:
            raise HTTPException(404, "Report not found")
        if write and role != Role.COMMENTER:
            raise HTTPException(403, "Comment access required")

    def authorize_owner(self, email: str, access: "Access") -> None:
        if email != self.owner and not access.is_owner(email):
            raise HTTPException(403, "Report owner required")

    def authorize_comment(self, email: str, author: str, access: "Access") -> None:
        self.authorize(email, True, access)
        if email != author and email != self.owner and not access.is_owner(email):
            raise HTTPException(
                403, "Only the author or report owner may change this comment"
            )

    def summary(self) -> dict:
        return {
            "document_id": self.document_id,
            "title": self.title,
            "url": f"/reports/{self.document_id}",
            "open": len(self.threads.open_threads),
            "total": len(self.threads.threads),
        }


PAGE_FIELDS = (
    "page_name",
    "html_key",
    "source_key",
    "title",
    "eyebrow",
    "subtitle",
    "folder",
    "date",
)


def page_fields(report: Report) -> dict:
    return report.model_dump(mode="json", include=set(PAGE_FIELDS))
