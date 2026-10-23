"""Only authorized report objects are exposed; archive directories are private."""

import json
import re
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ..comments import report_view
from .gallery import gallery_html
from .history import archive_response
from .identity import AccessIdentity
from .reports import Report
from .service import ReportService


def report_html(service: ReportService, report: Report) -> str:
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
        return gallery_html(service, user)

    @routes.get("/index.html", response_class=HTMLResponse)
    def gallery_index(request: Request):
        return gallery_html(service, email(request))

    @routes.get("/reports/{document_id}", response_class=HTMLResponse)
    def report(document_id: str, request: Request):
        current = service.read(document_id, email(request))
        return RedirectResponse(
            "/" + quote(current.page_name, safe=""), status_code=307
        )

    @routes.get("/{page_name}", response_class=HTMLResponse)
    def legacy_page(page_name: str, request: Request):
        user = email(request)
        try:
            report = service.reports.page(page_name)
        except HTTPException as error:
            if error.status_code != 404:
                raise
            return archive_response(request, page_name, service, identity)
        report.authorize(user, False, service.access())
        return report_html(service, report)

    return routes
