"""End to end: a source becomes a page whose blocks are addressable, and a second
render of the same document reviews the delta."""

from __future__ import annotations

from pathlib import Path

from visualreport import comments
from visualreport.document import split_blocks
from visualreport.paths import Archive
from visualreport.rendering import IterationMode, RenderRequest, render


def request_for(source: Path, archive: Archive) -> RenderRequest:
    return RenderRequest(
        source=source,
        kind="report",
        output=None,
        iteration=IterationMode.AUTO,
        archive=archive,
        refresh=None,
    )


def test_every_block_is_addressable_in_the_page(source: Path, archive: Archive):
    outcome = render(request_for(source, archive))
    page = outcome.page.read_text(encoding="utf-8")
    blocks = split_blocks(source.read_text(encoding="utf-8").split("---\n", 2)[2])
    for block in blocks:
        assert f'data-vr-block="{block.index}"' in page
    # Headings take the attribute inline, so the table of contents still resolves.
    assert '<h2 data-vr-block="0" id=' in page


def test_a_second_render_the_same_day_still_shows_the_delta(source: Path, archive: Archive):
    """Regression: versions used to be keyed by date, so refining a page twice in
    one day compared it against itself and reported no change at all."""
    render(request_for(source, archive))
    source.write_text(
        source.read_text(encoding="utf-8").replace("3,20 €", "4,10 €"), encoding="utf-8"
    )
    outcome = render(request_for(source, archive))
    assert outcome.changes == 1
    assert "vr-changelog" in outcome.page.read_text(encoding="utf-8")


def test_an_unchanged_re_render_reports_no_iteration(source: Path, archive: Archive):
    render(request_for(source, archive))
    assert render(request_for(source, archive)).changes is None


def test_threads_are_rehomed_and_seeded_into_the_page(source: Path, archive: Archive):
    render(request_for(source, archive))
    store = comments.store_for(archive, "report-page-test")
    blocks = split_blocks(source.read_text(encoding="utf-8").split("---\n", 2)[2])
    with store.edit() as threads:
        threads.open_thread(
            anchor=comments.anchor_for_quote(blocks, "trois métriques"),
            state=comments.AnchorState.ANCHORED,
            author=comments.GEOFFREY,
            body="lesquelles ?",
            now=comments.now_utc(),
        )
    source.write_text(
        source.read_text(encoding="utf-8").replace("## Contexte", "## Préambule\n\nAjout.\n\n## Contexte"),
        encoding="utf-8",
    )
    outcome = render(request_for(source, archive))
    assert outcome.threads.anchored == 1
    # The page ships the thread, so an archived file read offline still shows it.
    assert "lesquelles ?" in outcome.page.read_text(encoding="utf-8")
    # Two blocks were inserted above it, so the passage is now block 5.
    assert store.read().threads[0].anchor.block_index == 5


def test_a_page_rendered_outside_the_archive_never_touches_the_store(
    source: Path, archive: Archive, tmp_path: Path
):
    export = tmp_path / "export.html"
    outcome = render(
        RenderRequest(
            source=source,
            kind="report",
            output=export,
            iteration=IterationMode.AUTO,
            archive=archive,
            refresh=None,
        )
    )
    assert outcome.threads is None
    assert not archive.sources.exists()
