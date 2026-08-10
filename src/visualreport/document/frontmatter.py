"""The YAML front matter of a source: what the page and the archive key on."""

from __future__ import annotations

import re
import unicodedata
from datetime import date
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError

FRONT_MATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)


class SourceError(Exception):
    """A source file the renderer refuses — reported to the user, not a traceback."""


class ReportMeta(BaseModel):
    """Every field is required: the documented fallbacks are applied by
    `parse_source` before the model is built, so nothing is implicit here."""

    model_config = ConfigDict(extra="forbid")

    title: str
    eyebrow: str
    subtitle: str
    date: str
    slug: str
    lang: str


def parse_source(text: str) -> tuple[ReportMeta, str]:
    """Split a source into its metadata and its body.

    `title`, `eyebrow` and `subtitle` must be written by the author. `date`
    defaults to today, `lang` to French, `slug` to a slugified title — the three
    derivations the dialect documents.
    """
    match = FRONT_MATTER_RE.match(text)
    if not match:
        raise SourceError(
            "missing YAML front matter (--- … ---) with title / eyebrow / subtitle"
        )
    fields = yaml.safe_load(match.group(1)) or {}
    if not isinstance(fields, dict):
        raise SourceError("front matter must be a YAML mapping")
    # YAML reads an unquoted 2026-07-29 as a date object; the page only ever
    # prints it, so it is normalized to its ISO form.
    fields["date"] = str(fields.get("date") or date.today().isoformat())
    fields.setdefault("lang", "fr")
    if fields.get("title"):
        fields.setdefault("slug", slugify(str(fields["title"])))
    try:
        meta = ReportMeta(**fields)
    except ValidationError as error:
        raise SourceError(f"invalid front matter:\n{error}") from error
    return meta, text[match.end() :]


def read_source(path: Path) -> tuple[ReportMeta, str]:
    if not path.is_file():
        raise SourceError(f"source not found: {path}")
    return parse_source(path.read_text(encoding="utf-8"))


def slugify(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_value.lower()).strip("-")
