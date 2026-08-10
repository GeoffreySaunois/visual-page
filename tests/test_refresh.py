"""Rebuilding an archived page: it keeps its date, and it moves nothing else."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from visualreport import comments, refresh
from visualreport.document import split_blocks
from visualreport.paths import Archive
from visualreport.rendering import IterationMode, RenderRequest, render

PUBLISHED = "2026-01-15"
DOCUMENT = "report-page-test"


def publish(source: Path, archive: Archive) -> None:
    render(
        RenderRequest(
            source=source,
            kind="report",
            output=None,
            iteration=IterationMode.AUTO,
            archive=archive,
            refresh=None,
        )
    )


def backdate(archive: Archive, day: str) -> Path:
    """Move today's page and its source back to `day` — the shape of every page
    the archive accumulated: an old file, and a source that never named a date."""
    today = archive.page("report", "page-test", date.today().isoformat())
    page = archive.page("report", "page-test", day)
    archive.source_of(today).rename(archive.source_of(page))
    today.rename(page)
    return page


@pytest.fixture
def published(source: Path, archive: Archive) -> Path:
    publish(source, archive)
    return backdate(archive, PUBLISHED)


def test_a_rebuilt_page_keeps_the_date_it_was_published_at(published: Path, archive: Archive):
    """The archived sources carry no `date`, so a replay would otherwise be
    stamped today: a new file beside the page, instead of the page rebuilt."""
    outcome = refresh.run(archive, DOCUMENT)
    assert [rewritten.page.path for rewritten in outcome.rewritten] == [published]
    assert f'name="report-date" content="{PUBLISHED}"' in published.read_text(encoding="utf-8")
    assert not archive.page("report", "page-test", date.today().isoformat()).exists()


def test_a_rebuild_leaves_the_iteration_reference_alone(published: Path, archive: Archive):
    """The reference is what the *next* real iteration diffs against. A refresh
    that overwrote it with an older version would silently fake that diff."""
    reference = archive.previous_source(DOCUMENT)
    reference.write_text("--- une version plus récente ---\n", encoding="utf-8")
    refresh.run(archive, DOCUMENT)
    assert reference.read_text(encoding="utf-8") == "--- une version plus récente ---\n"


def test_a_rebuild_never_moves_a_thread(published: Path, archive: Archive, source: Path):
    """Threads are homed on the version last published; re-homing them on an old
    page would drag their anchors backwards, onto blocks nobody is reading."""
    store = comments.store_for(archive, DOCUMENT)
    blocks = split_blocks(source.read_text(encoding="utf-8").split("---\n", 2)[2])
    with store.edit() as threads:
        threads.open_thread(
            anchor=comments.anchor_for_quote(blocks, "trois métriques"),
            state=comments.AnchorState.ANCHORED,
            author=comments.GEOFFREY,
            body="lesquelles ?",
            now=comments.now_utc(),
        )
    archive.source_of(published).write_text(
        "---\ntitle: Une page de test\neyebrow: Test\nsubtitle: Sous-titre\n"
        "slug: page-test\nlang: fr\n---\n\n## Contexte\n\nUn seul bloc.\n",
        encoding="utf-8",
    )
    refresh.run(archive, DOCUMENT)
    assert store.read().threads[0].anchor.block_index == 3
    # The page still ships the thread, so it reads offline like any other.
    assert "lesquelles ?" in published.read_text(encoding="utf-8")


def test_a_page_whose_source_is_gone_is_named_not_passed_over(
    published: Path, archive: Archive
):
    archive.source_of(published).unlink()
    before = published.read_text(encoding="utf-8")
    outcome = refresh.run(archive, DOCUMENT)
    assert outcome.rewritten == []
    assert [skipped.page.path for skipped in outcome.skipped] == [published]
    assert "source archivée absente" in outcome.skipped[0].reason
    assert published.read_text(encoding="utf-8") == before


def test_an_image_gone_from_the_disk_is_carried_over_from_the_page(
    source: Path, archive: Archive, tmp_path: Path
):
    """A screenshot captured in a worktree that no longer exists still lives in
    the page as a data URI — the rebuild takes it back rather than losing it."""
    shot = tmp_path / "capture.png"
    shot.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 32)
    source.write_text(
        source.read_text(encoding="utf-8") + f"\n![]({shot})\n",
        encoding="utf-8",
    )
    publish(source, archive)
    page = backdate(archive, PUBLISHED)
    shot.unlink()

    outcome = refresh.run(archive, DOCUMENT)
    assert outcome.skipped == []
    rebuilt = page.read_text(encoding="utf-8")
    assert 'src="data:image/png;base64,' in rebuilt
    assert str(shot) not in rebuilt


def test_an_image_neither_on_disk_nor_in_the_page_leaves_the_page_alone(
    source: Path, archive: Archive, tmp_path: Path
):
    """Half a page is worse than an untouched one: the rebuild is dropped."""
    publish(source, archive)
    page = backdate(archive, PUBLISHED)
    before = page.read_text(encoding="utf-8")
    archived = archive.source_of(page)
    archived.write_text(
        archived.read_text(encoding="utf-8") + f"\n![]({tmp_path / 'jamais.png'})\n",
        encoding="utf-8",
    )
    outcome = refresh.run(archive, DOCUMENT)
    assert outcome.rewritten == []
    assert "images introuvables" in outcome.skipped[0].reason
    assert page.read_text(encoding="utf-8") == before


def test_a_survey_reads_the_dates_off_the_archive_and_ignores_the_gallery(
    published: Path, archive: Archive
):
    (archive.root / "index.html").write_text("galerie", encoding="utf-8")
    (archive.root / "note.html").write_text("écrit à la main", encoding="utf-8")
    replayable, skipped = refresh.survey(archive, None)
    assert [(page.document_id, page.day) for page in replayable] == [(DOCUMENT, PUBLISHED)]
    assert skipped == []
