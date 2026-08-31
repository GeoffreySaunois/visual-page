"""Printing a page: the invocation never opens a window, a half-written file is
never mistaken for a finished one, and a rendered page really does come back as
a readable PDF."""

from __future__ import annotations

from pathlib import Path

import pytest

from visualreport import pdf
from visualreport.paths import Archive
from visualreport.rendering import IterationMode, RenderRequest, render

NO_BROWSER = not any(candidate.is_file() for candidate in pdf.BROWSERS)


def request_for(source: Path, archive: Archive) -> RenderRequest:
    return RenderRequest(
        source=source,
        kind="report",
        output=None,
        iteration=IterationMode.AUTO,
        archive=archive,
        refresh=None,
    )


def test_printing_never_opens_a_window(tmp_path: Path):
    """The engine prints from a terminal, often while Geoffrey is working on
    something else: an invocation that lost `--headless` would steal the focus
    on every render."""
    command = pdf.print_command(
        Path("/browser"), tmp_path / "page.html", tmp_path / "page.pdf", tmp_path / "profile"
    )
    assert "--headless" in command
    # A shared profile would collide with the browser he has open, and a
    # first-run prompt would hold the print until the deadline.
    assert f"--user-data-dir={tmp_path / 'profile'}" in command
    assert command[-1].startswith("file://")


def test_a_pdf_still_being_written_does_not_count_as_finished(tmp_path: Path):
    """The export watches the file rather than the browser's exit code, because
    Chrome writes the PDF and keeps running. Reading a truncated file as a
    finished one would hand over a corrupt PDF and call it a success."""
    written = tmp_path / "page.pdf"
    assert not pdf.complete(written)
    written.write_bytes(b"%PDF-1.4\nstill writing")
    assert not pdf.complete(written)
    written.write_bytes(b"%PDF-1.4\nbody\ntrailer\n" + pdf.TRAILER + b"\n")
    assert pdf.complete(written)


def test_the_page_carries_a_print_control_and_a_print_stylesheet(source: Path, archive: Archive):
    """The button is the export for anyone reading the page, including from an
    archived file with no server: losing it takes the feature with it."""
    page = render(request_for(source, archive)).page.read_text(encoding="utf-8")
    assert 'id="pdf-export"' in page
    assert "@media print" in page


@pytest.mark.skipif(NO_BROWSER, reason="aucun navigateur Chromium installé")
def test_a_rendered_page_prints_to_a_readable_pdf(source: Path, archive: Archive):
    outcome = render(request_for(source, archive))
    written = pdf.export(outcome.page, pdf.companion(outcome.page))
    assert written == outcome.page.with_suffix(".pdf")
    content = written.read_bytes()
    assert content.startswith(b"%PDF-")
    assert content.rstrip().endswith(pdf.TRAILER)
