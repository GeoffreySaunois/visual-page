"""The local server: the archive as static files, plus the comment API.

It binds the loopback interface only. Serving the pages itself is what makes the
comment round-trip possible at all — a page opened as `file://` cannot write
anywhere, so it would have nothing to talk to.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from ..paths import Archive
from .api import build_router

HOST = "127.0.0.1"
DEFAULT_PORT = 8787


def create_app(archive: Archive) -> FastAPI:
    archive.root.mkdir(parents=True, exist_ok=True)
    app = FastAPI(title="visual-report", docs_url="/api/docs", openapi_url="/api/openapi.json")
    app.include_router(build_router(archive))
    # Mounted last and at the root, so /api keeps priority over a file of the
    # same name in the archive.
    app.mount("/", StaticFiles(directory=archive.root, html=True), name="archive")
    return app
