"""A page files in one folder of the taxonomy, and the gallery shelves it there."""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import SOURCE

from visualreport import gallery
from visualreport.document import SourceError, parse_source
from visualreport.paths import Archive
from visualreport.rendering import IterationMode, RenderRequest, render


def test_a_folder_outside_the_taxonomy_is_refused_with_the_list():
    with pytest.raises(SourceError) as failure:
        parse_source(SOURCE.replace("folder: swaap/gym", "folder: swaap/gmy"))
    assert "swaap/gym" in str(failure.value)
    assert "personal/azul" in str(failure.value)


def test_a_source_naming_no_folder_is_refused():
    with pytest.raises(SourceError):
        parse_source(SOURCE.replace("folder: swaap/gym\n", ""))


def test_the_gallery_shelves_a_page_in_its_folder_and_the_tagless_ones_apart(
    source: Path, archive: Archive
):
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
    # A page rendered before folders existed carries no folder tag at all.
    legacy = archive.root / "report-legacy-2026-01-01.html"
    legacy.write_text(
        '<html><head><meta name="report-title" content="Une vieille page" />'
        "<title>Une vieille page</title></head><body></body></html>",
        encoding="utf-8",
    )

    gallery.rebuild(archive)
    index = archive.index.read_text(encoding="utf-8")

    gym = index.index('data-path="swaap/gym"')
    filed = index.index("Une page de test")
    unfiled = index.index('data-path="a-classer"')
    old = index.index("Une vieille page")
    assert gym < filed < unfiled < old
    # The root offers Swaap and the shelf as tiles, Swaap offers its Gym folder.
    assert 'href="#/swaap"' in index and 'href="#/a-classer"' in index
    assert 'href="#/swaap/gym"' in index
    # Nothing is filed under Personal, so neither its tile nor its directory exists.
    assert "#/personal" not in index and 'data-path="personal"' not in index
