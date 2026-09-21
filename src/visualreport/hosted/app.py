"""Hosted app: fail-closed identity, per-report access and private responses."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .api import router
from .history import history_router
from .identity import AccessIdentity
from .pages import page_router
from .service import ReportService


def create_app(
    service: ReportService, identity: AccessIdentity, public_origin: str
) -> FastAPI:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.middleware("http")(response_guard(public_origin))
    app.include_router(router(service, identity))
    app.include_router(page_router(service, identity))
    app.include_router(history_router(service, identity))
    return app


def response_guard(public_origin: str):
    async def guard(request: Request, call_next):
        origin = request.headers.get("origin")
        if request.method not in {"GET", "HEAD", "OPTIONS"} and (
            (origin is not None and origin != public_origin)
            or request.headers.get("sec-fetch-site") == "cross-site"
        ):
            response = JSONResponse(
                {"detail": "Cross-origin mutation refused"}, status_code=403
            )
        else:
            response = await call_next(request)
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = "frame-ancestors 'none'"
        return response

    return guard
