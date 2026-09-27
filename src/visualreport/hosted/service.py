"""Hosted report operations shared by browser and publication API."""

from dataclasses import dataclass

from fastapi import HTTPException

from .. import folders
from .access import Access, FolderGrants
from .comments import CommentAction
from .grants import Grantee, Grants, Role
from .reports import Report
from .storage import FolderShares, Objects, Reports


@dataclass(frozen=True)
class ReportService:
    reports: Reports
    objects: Objects
    folder_shares: FolderShares
    owners: set[str]

    def access(self) -> Access:
        return Access(self.owners, self.folder_shares.all())

    def read(self, document_id: str, email: str) -> Report:
        report = self.reports.read(document_id)
        report.authorize(email, False, self.access())
        return report

    def visible(self, email: str) -> list[Report]:
        return self.reports.visible(
            email, email in self.owners, self.access().covered_folders(email)
        )

    def gallery(self, email: str) -> list[Report]:
        return self.reports.gallery(
            email, email in self.owners, self.access().covered_folders(email)
        )

    def comment(self, document_id: str, email: str, action: CommentAction) -> Report:
        report = self.read(document_id, email)
        if action.anchor is not None and report.source_key is None:
            raise HTTPException(
                409, "This archived report has no markdown source for anchoring"
            )
        access = self.access()
        source = (
            self.objects.read(report.source_key) if action.anchor is not None else ""
        )

        def change(current: Report | None) -> Report:
            if current is None:
                raise HTTPException(404, "Report not found")
            if action.anchor is not None and current.source_key != report.source_key:
                raise HTTPException(409, "Report changed; reload before commenting")
            action.apply(current, email, access, source)
            current.revision += 1
            return current

        return self.reports.mutate(document_id, change, None)

    def share(
        self, document_id: str, email: str, grantee: Grantee, role: Role | None
    ) -> Report:
        def change(current: Report | None) -> Report:
            if current is None:
                raise HTTPException(404, "Report not found")
            current.authorize_owner(email, self.access())
            current.share(grantee, role)
            current.revision += 1
            return current

        return self.reports.mutate(document_id, change, None)

    def share_folder(
        self, email: str, folder: str, grantee: Grantee, role: Role | None
    ) -> Grants:
        self.require_owner(email)
        if folders.folder(folder) is None:
            raise HTTPException(404, "Unknown folder")
        return self.folder_shares.share(folder, grantee, role)

    def shares(self, email: str) -> tuple[FolderGrants, dict[str, Grants]]:
        """Every grant in the archive: by folder, then by report."""
        self.require_owner(email)
        reports = {
            report.document_id: report.sharing
            for report in self.reports.visible(email, True, [])
            if not report.sharing.empty
        }
        folder_grants = {
            path: grants
            for path, grants in self.folder_shares.all().items()
            if not grants.empty
        }
        return folder_grants, reports

    def require_owner(self, email: str) -> None:
        if email not in self.owners:
            raise HTTPException(403, "Archive owner required")
