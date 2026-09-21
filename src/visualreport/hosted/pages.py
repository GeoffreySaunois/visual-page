"""Only authorized report objects are exposed; archive directories are private."""

import html
import json
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from ..comments import report_view
from ..paths import archived_page
from .identity import AccessIdentity
from .service import ReportService


def page_html(service: ReportService, document_id: str, email: str) -> str:
    report = service.read(document_id, email)
    content = service.objects.read(report.html_key)
    seed = json.dumps(report_view(report.threads, report.revision)).replace(
        "<", "\\u003c"
    )
    return re.sub(
        r'(<script\b[^>]*\bid="vr-bootstrap"[^>]*>).*?(</script>)',
        lambda match: match[1] + seed + match[2],
        content,
        flags=re.DOTALL,
    )


def page_router(service: ReportService, identity: AccessIdentity) -> APIRouter:
    routes = APIRouter()

    def email(request: Request) -> str:
        return identity.email(request.headers.get("Cf-Access-Jwt-Assertion"))

    @routes.get("/", response_class=HTMLResponse)
    def gallery(request: Request):
        user = email(request)
        reports = service.reports.visible(user, user in service.owners)
        links = "".join(
            f'<li><a href="/reports/{html.escape(r.document_id, quote=True)}">{html.escape(r.title)}</a></li>'
            for r in reports
        )
        return f'<!doctype html><html lang="fr"><meta charset="utf-8"><title>Artefacts</title><h1>Artefacts</h1><ul>{links}</ul></html>'

    @routes.get("/reports/{document_id}", response_class=HTMLResponse)
    def report(document_id: str, request: Request):
        return page_html(service, document_id, email(request))

    @routes.get("/{page_name}", response_class=HTMLResponse)
    def legacy_page(page_name: str, request: Request):
        page = archived_page(Path(page_name))
        if page is None:
            raise HTTPException(404, "Page not found")
        user = email(request)
        report = service.read(page.document_id, user)
        if report.page_name != page_name:
            raise HTTPException(404, "Only the published report version is available")
        return page_html(service, page.document_id, user)

    return routes
