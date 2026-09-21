"""Hosted authoring using the owner's cached Cloudflare Access session."""

import os
import subprocess
from pathlib import Path
from urllib.parse import quote

from .. import comments
from ..document import read_source
from ..hosted.client import exchange
from ..hosted.publication import Publication

ORIGIN = "https://artefacts.saunois.xyz"


def token() -> str:
    explicit = os.environ.get("ARTEFACTS_ACCESS_JWT")
    if explicit:
        return explicit
    try:
        return subprocess.check_output(
            ["cloudflared", "access", "token", "--app=" + ORIGIN],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        raise RuntimeError(
            "Connexion Artefacts requise : cloudflared access login " + ORIGIN
        ) from None


def request(document: str, suffix: str, payload: dict | None, method: str) -> dict:
    return exchange(
        ORIGIN,
        token(),
        "/api/documents/" + quote(document, safe="") + suffix,
        payload,
        method,
    )


def publish(page: Path, source: Path, rehome_comments: bool) -> str:
    metadata, _ = read_source(source)
    publication = Publication(
        page_name=page.name,
        title=metadata.title,
        html=page.read_text(encoding="utf-8"),
        source=source.read_text(encoding="utf-8"),
        rehome_comments=rehome_comments,
    )
    result = exchange(ORIGIN, token(), "/api/publish", publication.model_dump(), "POST")
    return ORIGIN + result["url"]


def threads(document: str) -> comments.ReportThreads:
    result = request(document, "/threads", None, "GET")
    model = comments.ReportThreads.empty(document)
    for value in result["threads"]:
        value.pop("is_open", None)
        value.pop("awaiting", None)
        model.threads.append(comments.Thread.model_validate(value))
    model.next_number = max((int(t.id[1:]) for t in model.threads), default=0) + 1
    return model
