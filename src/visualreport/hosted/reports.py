"""Report ownership, sharing and comment permissions."""

from enum import StrEnum

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field

from ..comments import ReportThreads


class Role(StrEnum):
    READER = "reader"
    COMMENTER = "commenter"


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

    def authorize(self, email: str, write: bool, owners: set[str]) -> None:
        if email == self.owner or email in owners:
            return
        role = self.grants.get(email)
        if role is None:
            raise HTTPException(404, "Report not found")
        if write and role != Role.COMMENTER:
            raise HTTPException(403, "Comment access required")

    def authorize_owner(self, email: str, owners: set[str]) -> None:
        if email != self.owner and email not in owners:
            raise HTTPException(403, "Report owner required")

    def authorize_comment(self, email: str, author: str, owners: set[str]) -> None:
        self.authorize(email, True, owners)
        if email != author and email != self.owner and email not in owners:
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
