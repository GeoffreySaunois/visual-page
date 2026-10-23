"""Explicit administrator import of frozen archive objects and report records."""

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from google.api_core.exceptions import PreconditionFailed
from google.cloud import firestore, storage

from ...comments import ReportThreads
from ...document import parse_source
from ..reports import Report, page_fields
from ..storage import page_id
from .merge import reconcile
from .snapshot import digest


class Importer:
    def __init__(
        self,
        database: firestore.Client,
        bucket: storage.Bucket,
        directory: Path,
        owner: str,
    ):
        self.database, self.bucket, self.directory, self.owner = (
            database,
            bucket,
            directory,
            owner,
        )

    def upload(self, record: dict) -> None:
        for key, sha in [
            (record["original_key"], record["sha256"]),
            (record["object_key"], record["served_sha256"]),
        ]:
            data = (self.directory / "blobs" / sha).read_bytes()
            if digest(data) != sha:
                raise ValueError("Snapshot blob checksum mismatch")
            blob = self.bucket.blob(key)
            blob.metadata = {"sha256": sha}
            try:
                blob.upload_from_string(
                    data, content_type=record["content_type"], if_generation_match=0
                )
            except PreconditionFailed:
                blob.reload()
                if not blob.metadata or blob.metadata.get("sha256") != sha:
                    raise ValueError(
                        "Existing archive object checksum mismatch"
                    ) from None
        self.database.collection("archive_objects").document(
            page_id(record["path"])
        ).set(record)

    def incoming(self, record: dict, files: dict) -> Report:
        latest = max(
            record["versions"],
            key=lambda version: (version["date"], version["page_name"]),
        )
        threads = ReportThreads.empty(record["document_id"])
        if record["comments_path"]:
            source = files[record["comments_path"]]
            threads = ReportThreads.model_validate_json(
                (self.directory / "blobs" / source["served_sha256"]).read_bytes()
            )
        if threads.document_id != record["document_id"]:
            raise ValueError("Comment store identity does not match report")
        return Report(
            **latest,
            document_id=record["document_id"],
            owner=self.owner,
            grants={},
            everyone=None,
            threads=threads,
            revision=1,
        )

    def import_report(self, record: dict, files: dict) -> str:
        incoming = self.incoming(record, files)
        reference = self.database.collection("reports").document(incoming.document_id)

        @firestore.transactional
        def commit(transaction):
            snapshot = reference.get(transaction=transaction)
            updated, marker, changed = reconcile(
                snapshot.to_dict() if snapshot.exists else None,
                incoming,
                digest(json.dumps(record["versions"], sort_keys=True).encode()),
            )
            if not changed:
                return "unchanged"
            for version in record["versions"]:
                page = (
                    self.database.collection("pages")
                    .document(page_id(version["page_name"]))
                    .get(transaction=transaction)
                )
                if page.exists:
                    data = page.to_dict()
                    previous = data.get("archive_import_sha")
                    current_sha = digest(
                        json.dumps(
                            {key: data[key] for key in version}, sort_keys=True
                        ).encode()
                    )
                    if previous is None or previous != current_sha:
                        raise ValueError(
                            f"Hosted historical version changed: {version['page_name']}; not overwritten"
                        )
            marker["revision"] = updated.revision
            if len(updated.model_dump_json().encode()) > 700_000:
                raise ValueError("Imported report exceeds application metadata limit")
            transaction.set(
                reference,
                {
                    "report": updated.model_dump(mode="json"),
                    "members": sorted({updated.owner, *updated.grants}),
                    "archive_import": marker,
                },
                merge=True,
            )
            for version in record["versions"]:
                transaction.set(
                    self.database.collection("pages").document(
                        page_id(version["page_name"])
                    ),
                    {
                        **version,
                        "document_id": incoming.document_id,
                        "listed": True,
                        "archive_import_sha": digest(
                            json.dumps(version, sort_keys=True).encode()
                        ),
                    },
                )
            return "imported"

        return commit(self.database.transaction())

    def aliases(self, manifest: dict) -> None:
        pages = {
            version["page_name"]: {**version, "document_id": report["document_id"]}
            for report in manifest["reports"]
            for version in report["versions"]
        }
        for record in manifest["files"].values():
            target = pages.get(record["alias_target"])
            if target:
                self.database.collection("pages").document(page_id(record["path"])).set(
                    {**target, "page_name": record["path"], "listed": False}
                )

    def backfill(self) -> int:
        upgraded = 0
        for snapshot in self.database.collection("reports").stream():
            original = snapshot.to_dict()["report"]
            if all(
                key in original for key in ("folder", "eyebrow", "subtitle", "date")
            ):
                continue
            metadata, _ = parse_source(
                self.bucket.blob(original["source_key"]).download_as_text()
            )
            metadata_fields = {
                key: getattr(metadata, key)
                for key in ("folder", "eyebrow", "subtitle", "date")
            }
            self.backfill_one(snapshot.reference, metadata_fields)
            upgraded += 1
        return upgraded

    def backfill_one(self, reference, metadata_fields: dict) -> None:
        @firestore.transactional
        def commit(transaction):
            latest = reference.get(transaction=transaction).to_dict()
            report = Report.model_validate({**latest["report"], **metadata_fields})
            transaction.update(reference, {"report": report.model_dump(mode="json")})
            transaction.set(
                self.database.collection("pages").document(page_id(report.page_name)),
                {
                    **page_fields(report),
                    "document_id": report.document_id,
                    "listed": True,
                },
                merge=True,
            )

        commit(self.database.transaction())

    def apply(self, manifest: dict) -> dict:
        counts = {"upgraded_hosted": self.backfill(), "imported": 0, "unchanged": 0}
        with ThreadPoolExecutor(max_workers=8) as pool:
            for index, _ in enumerate(
                pool.map(self.upload, manifest["files"].values()), 1
            ):
                if index % 50 == 0:
                    print(
                        f"Uploaded and checked {index}/{len(manifest['files'])} archive files",
                        flush=True,
                    )
        for record in manifest["reports"]:
            counts[self.import_report(record, manifest["files"])] += 1
        self.aliases(manifest)
        return counts
