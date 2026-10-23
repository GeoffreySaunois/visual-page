"""Report ownership, sharing and comment permissions."""

from typing import TYPE_CHECKING

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field

from ..comments import ReportThreads
from .grants import Grantee, Grants, Role, strongest

if TYPE_CHECKING:
    from .access import Access


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
    # Reports stored before the grant to every verified email existed carry no
    # such field: absent means not open to everyone.
    everyone: Role | None = None
    page_name: str
    html_key: str
    source_key: str | None
    threads: ReportThreads
    revision: int = Field(ge=1)

    @property
    def sharing(self) -> Grants:
        return Grants(emails=self.grants, everyone=self.everyone)

    def share(self, grantee: Grantee, role: Role | None) -> None:
        updated = self.sharing.granting(grantee, role)
        self.grants, self.everyone = dict(updated.emails), updated.everyone

    def role(self, email: str, access: "Access") -> Role | None:
        return strongest(
            [self.sharing.role(email), access.folder_role(self.folder, email)]
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
