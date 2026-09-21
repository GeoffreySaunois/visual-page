"""Immutable local snapshot of useful archive files and their publication metadata."""

import hashlib
import json
import mimetypes
import os
from pathlib import Path

from ...comments import ReportThreads
from ...gallery.catalog import read_entry
from ...paths import Archive

OLD_ORIGIN = b"https://reports.askazul.fr"
NEW_ORIGIN = b"https://artefacts.saunois.xyz"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def include(path: Path) -> bool:
    return (
        path.as_posix() != "index.html"
        and path.parts[0] != "logs"
        and path.name not in {".server.json", ".tunnel.json", ".DS_Store"}
        and path.suffix != ".lock"
    )


def save_blob(directory: Path, data: bytes) -> str:
    sha = digest(data)
    path = directory / "blobs" / sha
    if not path.exists():
        path.write_bytes(data)
        path.chmod(0o600)
    return sha


def snapshot_file(root: Path, path: Path, directory: Path) -> dict:
    relative = path.relative_to(root).as_posix()
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"Archive symlink escapes root: {relative}")
    original = path.read_bytes()
    served = (
        original.replace(OLD_ORIGIN, NEW_ORIGIN)
        if path.suffix in {".html", ".md", ".css", ".js", ".json"}
        else original
    )
    raw_sha, served_sha = save_blob(directory, original), save_blob(directory, served)
    return {
        "path": relative,
        "bytes": len(original),
        "sha256": raw_sha,
        "served_sha256": served_sha,
        "rewritten_links": original.count(OLD_ORIGIN) if served != original else 0,
        "original_key": f"archive/original/{raw_sha}/{relative}",
        "object_key": f"archive/served/{served_sha}/{relative}",
        "content_type": mimetypes.guess_type(relative)[0] or "application/octet-stream",
        "alias": path.is_symlink(),
        "alias_target": path.resolve().relative_to(root.resolve()).as_posix()
        if path.is_symlink()
        else None,
    }


def report_metadata(root: Path, files: dict[str, dict]) -> list[dict]:
    reports = {}
    archive = Archive(root)
    for path in sorted(root.glob("*.html")):
        if path.name not in files or files[path.name]["alias"]:
            continue
        entry = read_entry(archive, path)
        if "/" in entry.document_id or entry.document_id in {".", ".."}:
            raise ValueError("Invalid archived report identity")
        source = files.get(f"src/{path.stem}.md")
        page = {
            "page_name": path.name,
            "html_key": files[path.name]["object_key"],
            "source_key": source["object_key"] if source else None,
            "title": entry.title,
            "eyebrow": entry.eyebrow,
            "subtitle": entry.subtitle,
            "folder": entry.folder.path,
            "date": entry.date,
        }
        record = reports.setdefault(
            entry.document_id,
            {"document_id": entry.document_id, "versions": [], "comments_path": None},
        )
        record["versions"].append(page)
        comment_path = f"comments/{entry.document_id}.json"
        if comment_path in files:
            record["comments_path"] = comment_path
    return list(reports.values())


def prepare(root: Path, directory: Path) -> dict:
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    (directory / "blobs").mkdir(exist_ok=True, mode=0o700)
    files = {
        p.relative_to(root).as_posix(): snapshot_file(root, p, directory)
        for p in sorted(root.rglob("*"))
        if p.is_file() and include(p.relative_to(root))
    }
    tree = directory / "tree"
    for name, record in files.items():
        target = tree / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            target.unlink()
        os.link(directory / "blobs" / record["sha256"], target)
    reports = report_metadata(tree, files)
    # Validate comments from snapshotted bytes, not mutable files during the upload.
    stores = [
        ReportThreads.model_validate_json(
            (directory / "blobs" / value["sha256"]).read_bytes()
        )
        for name, value in files.items()
        if name.startswith("comments/") and name.endswith(".json")
    ]
    ids = {report["document_id"] for report in reports}
    orphans = [store.document_id for store in stores if store.document_id not in ids]
    manifest = {
        "schema": 1,
        "orphan_comment_stores": orphans,
        "files": files,
        "reports": reports,
        "counts": {
            "files": len(files),
            "bytes": sum(f["bytes"] for f in files.values()),
            "reports": len(reports),
            "versions": sum(len(r["versions"]) for r in reports),
            "source_missing": sum(
                v["source_key"] is None for r in reports for v in r["versions"]
            ),
            "comment_stores": len(stores),
            "orphan_comment_stores": len(orphans),
            "threads": sum(len(s.threads) for s in stores),
            "messages": sum(len(t.comments) for s in stores for t in s.threads),
            "rewritten_links": sum(f["rewritten_links"] for f in files.values()),
        },
    }
    path = directory / "manifest.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    path.chmod(0o600)
    return manifest
