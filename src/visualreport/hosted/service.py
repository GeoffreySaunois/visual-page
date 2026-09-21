"""Hosted report operations shared by browser and publication API."""

from dataclasses import dataclass

from fastapi import HTTPException

from .comments import CommentAction
from .reports import Report, Role
from .storage import Objects, Reports


@dataclass(frozen=True)
class ReportService:
    reports: Reports
    objects: Objects
    owners: set[str]

    def read(self, document_id: str, email: str) -> Report:
        report = self.reports.read(document_id)
        report.authorize(email, False, self.owners)
        return report

    def comment(self, document_id: str, email: str, action: CommentAction) -> Report:
        report = self.read(document_id, email)
        source = (
            self.objects.read(report.source_key) if action.anchor is not None else ""
        )

        def change(current: Report | None) -> Report:
            if current is None:
                raise HTTPException(404, "Report not found")
            if action.anchor is not None and current.source_key != report.source_key:
                raise HTTPException(409, "Report changed; reload before commenting")
            action.apply(current, email, self.owners, source)
            current.revision += 1
            return current

        return self.reports.mutate(document_id, change)

    def share(
        self, document_id: str, email: str, recipient: str, role: Role | None
    ) -> Report:
        def change(current: Report | None) -> Report:
            if current is None:
                raise HTTPException(404, "Report not found")
            current.authorize_owner(email, self.owners)
            if role is None:
                current.grants.pop(recipient, None)
            else:
                current.grants[recipient] = role
            current.revision += 1
            return current

        return self.reports.mutate(document_id, change)
