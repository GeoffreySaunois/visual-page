"""Hosted gallery preserves dated links and the archive's nested navigation."""

from visualreport.comments import ReportThreads
from visualreport.gallery.index import render
from visualreport.hosted.gallery import gallery_entry
from visualreport.hosted.reports import Report


def report(page_name: str, folder: str, title: str) -> Report:
    return Report(
        document_id="report-demo",
        title=title,
        owner="owner@example.com",
        grants={},
        page_name=page_name,
        html_key="page",
        source_key=None,
        threads=ReportThreads.empty("report-demo"),
        revision=1,
        folder=folder,
        eyebrow="Review",
        subtitle="A dated report",
        date=page_name[-15:-5],
    )


def test_dated_versions_keep_distinct_links_in_nested_gallery():
    # Linking every card to /reports/id would silently open the latest version.
    versions = [
        report("report-demo-2026-09-20.html", "swaap/gym/lab", "First version"),
        report("report-demo-2026-09-21.html", "swaap/gym/lab", "Second version"),
    ]
    page = render([gallery_entry(version) for version in versions])
    assert 'href="/report-demo-2026-09-20.html"' in page
    assert 'href="/report-demo-2026-09-21.html"' in page
    assert 'data-path="swaap/gym/lab"' in page
    assert "Swaap › Gym › Gym Lab" in page
    assert "2 pages" in page


def test_unknown_folder_stays_visible_and_metadata_cannot_inject_html():
    # Old reports may name retired folders; they belong on the unfiled shelf.
    entry = gallery_entry(
        report(
            "report-demo-2026-09-21.html",
            "retired/folder",
            '<script>alert("x")</script>',
        )
    )
    page = render([entry])
    assert 'data-path="a-classer"' in page
    assert 'href="/report-demo-2026-09-21.html"' in page
    assert '<script>alert("x")</script>' not in page
    assert "&lt;script&gt;" in page
