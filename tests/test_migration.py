"""Archive migration preserves original bytes, identities and hosted concurrent writes."""

from types import SimpleNamespace

import pytest

from visualreport.comments import CLAUDE, GEOFFREY, ReportThreads, now_utc
from visualreport.hosted.migration.merge import reconcile
from visualreport.hosted.migration.snapshot import prepare
from visualreport.hosted.publication import Publication, publish
from visualreport.hosted.reports import Report, Role


def report():
    threads = ReportThreads.empty("report-demo")
    thread = threads.open_thread(None, "document", GEOFFREY, "Original", now_utc())
    thread.add_comment(CLAUDE, "Reply", now_utc())
    thread.resolve(GEOFFREY, now_utc())
    return Report(
        document_id="report-demo",
        title="Demo",
        eyebrow="Test",
        subtitle="Demo",
        folder="personal/tooling",
        date="2026-09-21",
        owner="owner@example.com",
        grants={},
        page_name="report-demo-2026-09-21.html",
        html_key="latest-html",
        source_key="latest-source",
        threads=threads,
        revision=1,
    )


def existing(value):
    updated, marker, _ = reconcile(None, value, "versions-v1")
    marker["revision"] = updated.revision
    return {"report": updated.model_dump(mode="json"), "archive_import": marker}


def test_repeat_import_preserves_live_new_comments_and_original_ids():
    incoming = report()
    remote = existing(incoming)
    current = Report.model_validate(remote["report"])
    current.threads.require("t1").add_comment(GEOFFREY, "Live cloud comment", now_utc())
    current.revision += 1
    remote["report"] = current.model_dump(mode="json")
    result, _, changed = reconcile(remote, incoming, "versions-v1")
    assert not changed
    assert [c.id for c in result.threads.require("t1").comments] == [
        "t1.1",
        "t1.2",
        "t1.3",
    ]
    assert result.threads.require("t1").comments[-1].body == "Live cloud comment"
    assert result.threads.require("t1").resolution is not None


def test_divergent_local_and_cloud_comments_fail_instead_of_overwriting():
    incoming = report()
    remote = existing(incoming)
    current = Report.model_validate(remote["report"])
    current.threads.require("t1").add_comment(GEOFFREY, "Cloud", now_utc())
    remote["report"] = current.model_dump(mode="json")
    incoming.threads.require("t1").add_comment(CLAUDE, "Local", now_utc())
    with pytest.raises(ValueError, match="both changed"):
        reconcile(remote, incoming, "versions-v1")
    assert remote["report"]["threads"]["threads"][0]["comments"][-1]["body"] == "Cloud"


def test_incremental_local_import_preserves_live_sharing_permissions():
    incoming = report()
    remote = existing(incoming)
    remote["report"]["grants"] = {"alice@example.com": "reader"}
    remote["report"]["revision"] += 1
    incoming.threads.require("t1").add_comment(CLAUDE, "Local update", now_utc())
    result, _, changed = reconcile(remote, incoming, "versions-v1")
    assert changed
    assert result.grants["alice@example.com"] == Role.READER
    assert result.threads.require("t1").comments[-1].body == "Local update"


def test_snapshot_keeps_original_bytes_and_rewrites_served_links(tmp_path):
    archive, target = tmp_path / "archive", tmp_path / "snapshot"
    archive.mkdir()
    (archive / "comments").mkdir()
    (archive / "logs").mkdir()
    html = '<title>Demo</title><a href="https://reports.askazul.fr/report-demo-2026-09-21.html">Demo</a>'
    page = archive / "report-demo-2026-09-21.html"
    page.write_text(html)
    (archive / "alias.html").symlink_to(page.name)
    threads = report().threads
    threads.require("t1").comments[
        0
    ].body = "https://reports.askazul.fr/report-demo-2026-09-21.html"
    (archive / "comments/report-demo.json").write_text(threads.model_dump_json())
    (archive / "comments/report-orphan.json").write_text(
        ReportThreads.empty("report-orphan").model_dump_json()
    )
    (archive / "logs/private.log").write_text("not a report")
    (archive / ".server.json").write_text("runtime state")
    manifest = prepare(archive, target)
    assert manifest["counts"]["reports"] == 1
    assert manifest["counts"]["source_missing"] == 1
    assert manifest["counts"]["messages"] == 2
    assert manifest["orphan_comment_stores"] == ["report-orphan"]
    assert not any(
        name.startswith("logs/") or name == ".server.json" for name in manifest["files"]
    )
    record = manifest["files"][page.name]
    assert (target / "blobs" / record["sha256"]).read_text() == html
    assert (
        "https://artefacts.saunois.xyz"
        in (target / "blobs" / record["served_sha256"]).read_text()
    )
    comments = manifest["files"]["comments/report-demo.json"]
    served = ReportThreads.model_validate_json(
        (target / "blobs" / comments["served_sha256"]).read_bytes()
    )
    assert served.threads[0].id == "t1" and served.threads[0].resolution is not None
    assert (
        served.threads[0].comments[0].body.startswith("https://artefacts.saunois.xyz/")
    )
    assert manifest["files"]["alias.html"]["alias_target"] == page.name


def test_historical_refresh_does_not_promote_older_page_or_rehome_comments():
    current = report()
    recorded = []

    def mutate(document_id, change, version):
        recorded.append(version)
        return change(current.model_copy(deep=True))

    source = "---\ntitle: Demo\neyebrow: Test\nsubtitle: Demo\nfolder: personal/tooling\nslug: demo\n---\n\nOlder body."
    publication = Publication(
        page_name="report-demo-2026-09-01.html",
        title="Old",
        html="report-demo",
        source=source,
        rehome_comments=False,
    )
    result = publish(
        SimpleNamespace(mutate=mutate),
        SimpleNamespace(upload=lambda *args: ("old-html", "old-source")),
        publication,
        current.owner,
        {current.owner},
    )
    assert result.page_name == current.page_name
    assert result.html_key == "latest-html"
    assert result.threads == current.threads
    assert recorded[0]["date"] == "2026-09-01"
