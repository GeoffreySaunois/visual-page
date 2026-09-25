"""Private objects and transactional report metadata."""

from collections.abc import Callable
from hashlib import sha256
from typing import Protocol
from uuid import uuid4

from fastapi import HTTPException
from google.cloud import firestore, storage
from google.cloud.firestore_v1.base_query import FieldFilter

from .reports import Report, Role, page_fields


class Reports(Protocol):
    def read(self, document_id: str) -> Report: ...
    def visible(
        self, email: str, administrator: bool, folders: list[str]
    ) -> list[Report]: ...
    def gallery(
        self, email: str, administrator: bool, folders: list[str]
    ) -> list[Report]: ...
    def history(self, document_id: str) -> list[Report]: ...
    def page(self, page_name: str) -> Report: ...
    def archive(self, path: str) -> dict: ...
    def version(self, document_id: str, page_name: str) -> Report: ...
    def mutate(
        self,
        document_id: str,
        change: Callable[[Report | None], Report],
        version: dict | None,
    ) -> Report: ...


class FolderShares(Protocol):
    def all(self) -> dict[str, dict[str, Role]]: ...
    def share(
        self, folder: str, recipient: str, role: Role | None
    ) -> dict[str, Role]: ...


class Objects(Protocol):
    def upload(self, document_id: str, html: str, source: str) -> tuple[str, str]: ...
    def read(self, key: str) -> str: ...
    def read_bytes(self, key: str) -> bytes: ...


class FirestoreReports:
    def __init__(self, client: firestore.Client):
        self.client = client
        self.collection = client.collection("reports")
        self.pages = client.collection("pages")

    def read(self, document_id: str) -> Report:
        snapshot = self.collection.document(document_id).get()
        if not snapshot.exists:
            raise HTTPException(404, "Report not found")
        return Report.model_validate(snapshot.to_dict()["report"])

    def visible(
        self, email: str, administrator: bool, folders: list[str]
    ) -> list[Report]:
        """Reports `email` may read: all for an administrator, otherwise those
        naming it as a member plus those filed in a folder shared with it."""
        if administrator:
            rows = list(self.collection.stream())
        else:
            members = FieldFilter("members", "array_contains", email)
            rows = list(self.collection.where(filter=members).stream()) + [
                row
                for chunk in chunks(folders)
                for row in self.collection.where(
                    filter=FieldFilter("report.folder", "in", chunk)
                ).stream()
            ]
        reports = [Report.model_validate(row.to_dict()["report"]) for row in rows]
        return list({report.document_id: report for report in reports}.values())

    def mutate(
        self,
        document_id: str,
        change: Callable[[Report | None], Report],
        version: dict | None,
    ) -> Report:
        reference = self.collection.document(document_id)

        @firestore.transactional
        def commit(transaction):
            snapshot = reference.get(transaction=transaction)
            current = (
                Report.model_validate(snapshot.to_dict()["report"])
                if snapshot.exists
                else None
            )
            updated = change(current)
            payload = updated.model_dump(mode="json")
            if len(updated.model_dump_json().encode()) > 700_000:
                raise HTTPException(413, "Report metadata and comments exceed 700 KB")
            transaction.set(
                reference,
                {
                    "report": payload,
                    "members": sorted({updated.owner, *updated.grants}),
                },
                merge=True,
            )
            if version is not None:
                transaction.set(
                    self.pages.document(page_id(version["page_name"])),
                    {"document_id": document_id, "listed": True, **version},
                    merge=True,
                )
            return updated

        return commit(self.client.transaction())

    def archive(self, path: str) -> dict:
        snapshot = (
            self.client.collection("archive_objects").document(page_id(path)).get()
        )
        if not snapshot.exists:
            raise HTTPException(404, "Archive file not found")
        return snapshot.to_dict()

    def gallery(
        self, email: str, administrator: bool, folders: list[str]
    ) -> list[Report]:
        visible = {
            r.document_id: r for r in self.visible(email, administrator, folders)
        }
        if not visible:
            return []
        if administrator:
            rows = list(self.pages.stream())
        else:
            rows = [
                row
                for chunk in chunks(list(visible))
                for row in self.pages.where(
                    filter=FieldFilter("document_id", "in", chunk)
                ).stream()
            ]
        versions = [
            version_of(visible[data["document_id"]], data)
            for row in rows
            if (data := row.to_dict())["listed"] and data["document_id"] in visible
        ]
        covered = {r.document_id for r in versions}
        return versions + [r for key, r in visible.items() if key not in covered]

    def history(self, document_id: str) -> list[Report]:
        report = self.read(document_id)
        rows = list(
            self.pages.where(
                filter=FieldFilter("document_id", "==", document_id)
            ).stream()
        )
        versions = [
            version_of(report, row.to_dict()) for row in rows if row.to_dict()["listed"]
        ]
        return sorted(
            versions or [report], key=lambda item: (item.date, item.page_name)
        )

    def page(self, page_name: str) -> Report:
        snapshot = self.pages.document(page_id(page_name)).get()
        if not snapshot.exists:
            raise HTTPException(404, "Report version not found")
        data = snapshot.to_dict()
        return version_of(self.read(data["document_id"]), data)

    def version(self, document_id: str, page_name: str) -> Report:
        report = self.page(page_name)
        if report.document_id != document_id:
            raise HTTPException(404, "Report version not found")
        return report


class FirestoreFolderShares:
    """One document per shared folder: `{folder, grants}`."""

    def __init__(self, client: firestore.Client):
        self.client = client
        self.collection = client.collection("folder_shares")

    def all(self) -> dict[str, dict[str, Role]]:
        return {
            (data := row.to_dict())["folder"]: {
                email: Role(role) for email, role in data["grants"].items()
            }
            for row in self.collection.stream()
        }

    def share(self, folder: str, recipient: str, role: Role | None) -> dict[str, Role]:
        reference = self.collection.document(page_id(folder))

        @firestore.transactional
        def commit(transaction):
            snapshot = reference.get(transaction=transaction)
            grants = snapshot.to_dict()["grants"] if snapshot.exists else {}
            if role is None:
                grants.pop(recipient, None)
            else:
                grants[recipient] = role.value
            transaction.set(reference, {"folder": folder, "grants": grants})
            return {email: Role(value) for email, value in grants.items()}

        return commit(self.client.transaction())


def chunks(values: list[str]) -> list[list[str]]:
    """Firestore caps an `in` filter at 30 values."""
    return [values[offset : offset + 30] for offset in range(0, len(values), 30)]


def page_id(page_name: str) -> str:
    return sha256(page_name.encode()).hexdigest()


def version_of(report: Report, snapshot: dict) -> Report:
    return report.model_copy(update={key: snapshot[key] for key in page_fields(report)})


class BucketObjects:
    def __init__(self, client: storage.Client, bucket: str):
        self.bucket = client.bucket(bucket)

    def upload(self, document_id: str, html: str, source: str) -> tuple[str, str]:
        prefix = f"reports/{document_id}/{uuid4().hex}"
        html_key, source_key = f"{prefix}/page.html", f"{prefix}/source.md"
        self.bucket.blob(html_key).upload_from_string(
            html, content_type="text/html", if_generation_match=0
        )
        self.bucket.blob(source_key).upload_from_string(
            source, content_type="text/markdown", if_generation_match=0
        )
        return html_key, source_key

    def read(self, key: str) -> str:
        return self.bucket.blob(key).download_as_text()

    def read_bytes(self, key: str) -> bytes:
        return self.bucket.blob(key).download_as_bytes()
