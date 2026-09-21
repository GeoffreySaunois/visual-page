"""Owner-only original archive files; report pages retain their independent ACLs."""

from pathlib import PurePosixPath

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from .identity import AccessIdentity
from .service import ReportService


def archive_response(
    request: Request, path: str, service: ReportService, identity: AccessIdentity
) -> Response:
    email = identity.email(request.headers.get("Cf-Access-Jwt-Assertion"))
    if email not in service.owners:
        raise HTTPException(404, "Archive file not found")
    if (
        any(part in {".", ".."} for part in path.split("/"))
        or PurePosixPath(path).is_absolute()
    ):
        raise HTTPException(404, "Archive file not found")
    record = service.reports.archive(path)
    content = service.objects.read_bytes(record["object_key"])
    return Response(content, media_type=record["content_type"])


def history_router(service: ReportService, identity: AccessIdentity) -> APIRouter:
    routes = APIRouter()

    @routes.get("/archive/{path:path}")
    def archive(path: str, request: Request):
        return archive_response(request, path, service, identity)

    @routes.get("/{path:path}")
    def legacy_asset(path: str, request: Request):
        return archive_response(request, path, service, identity)

    return routes
