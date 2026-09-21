"""Private objects and transactional report metadata."""

from collections.abc import Callable
from typing import Protocol
from uuid import uuid4

from fastapi import HTTPException
from google.cloud import firestore, storage
from google.cloud.firestore_v1.base_query import FieldFilter

from .reports import Report


class Reports(Protocol):
    def read(self, document_id: str) -> Report: ...
    def visible(self, email: str, administrator: bool) -> list[Report]: ...
    def mutate(
        self, document_id: str, change: Callable[[Report | None], Report]
    ) -> Report: ...


class Objects(Protocol):
    def upload(self, document_id: str, html: str, source: str) -> tuple[str, str]: ...
    def read(self, key: str) -> str: ...


class FirestoreReports:
    def __init__(self, client: firestore.Client):
        self.client = client
        self.collection = client.collection("reports")

    def read(self, document_id: str) -> Report:
        snapshot = self.collection.document(document_id).get()
        if not snapshot.exists:
            raise HTTPException(404, "Report not found")
        return Report.model_validate(snapshot.to_dict()["report"])

    def visible(self, email: str, administrator: bool) -> list[Report]:
        query = (
            self.collection
            if administrator
            else self.collection.where(
                filter=FieldFilter("members", "array_contains", email)
            )
        )
        return [
            Report.model_validate(row.to_dict()["report"]) for row in query.stream()
        ]

    def mutate(
        self, document_id: str, change: Callable[[Report | None], Report]
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
            )
            return updated

        return commit(self.client.transaction())


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
