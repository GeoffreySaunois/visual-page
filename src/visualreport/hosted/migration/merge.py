"""Idempotent import decisions that never overwrite concurrent hosted changes."""

from ..reports import Report
from .snapshot import digest

UNSHARED = {"grants": {}, "everyone": None}


def fingerprint(report: Report) -> str:
    # Sharing is not imported content: callers blank `grants` (UNSHARED), and
    # `everyone` stays out of the digest so it equals the baselines stored in
    # Firestore by imports that predate that field.
    return digest(report.model_dump_json(exclude={"everyone"}).encode())


def reconcile(
    existing: dict | None, incoming: Report, versions_hash: str
) -> tuple[Report, dict, bool]:
    marker = {
        "incoming": digest((fingerprint(incoming) + versions_hash).encode()),
        "applied": fingerprint(incoming),
    }
    if existing is None:
        return incoming, marker, True
    current = Report.model_validate(existing["report"])
    previous = existing.get("archive_import")
    if previous is None:
        raise ValueError(
            f"Existing hosted report has no migration baseline: {incoming.document_id}"
        )
    if previous["incoming"] == marker["incoming"]:
        return current, previous, False
    # Grant changes are independent of imported content and must survive updates.
    comparison = current.model_copy(
        update={**UNSHARED, "revision": previous["revision"]}
    )
    if fingerprint(comparison) != previous["applied"]:
        raise ValueError(
            f"Local and hosted report both changed: {incoming.document_id}; neither overwritten"
        )
    updated = incoming.model_copy(
        update={
            "grants": current.grants,
            "everyone": current.everyone,
            "revision": current.revision + 1,
        }
    )
    marker["applied"] = fingerprint(updated.model_copy(update=UNSHARED))
    return updated, marker, True
