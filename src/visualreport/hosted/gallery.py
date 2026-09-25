"""The existing archive gallery rendered from authorized hosted versions."""

from urllib.parse import quote

from .. import comments, folders
from ..gallery.catalog import Entry
from ..gallery.index import render
from .reports import Report
from .service import ReportService


def gallery_entry(report: Report) -> Entry:
    return Entry(
        href="/" + quote(report.page_name, safe=""),
        document_id=report.document_id,
        kind=report.document_id.split("-")[0],
        title=report.title,
        eyebrow=report.eyebrow,
        subtitle=report.subtitle,
        folder=folders.folder(report.folder) or folders.UNFILED,
        date=report.date,
        modified=0,
        open_comments=len(report.threads.open_threads),
        awaiting_agent=len(report.threads.awaiting(comments.AuthorKind.AGENT)),
    )


def gallery_html(service: ReportService, email: str) -> str:
    versions = service.gallery(email)
    entries = [gallery_entry(report) for report in versions]
    entries.sort(key=lambda entry: entry.sort_key, reverse=True)
    return render(entries)
