"""Publish immutable objects and atomically promote an owner-controlled report."""

from pathlib import Path

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..comments import ReportThreads, rehome_all
from ..document import parse_source, split_blocks
from ..document.frontmatter import SourceError
from ..paths import archived_page
from .reports import Report
from .storage import Objects, Reports


class Publication(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Public API: ordinary publication re-homes comments; refresh explicitly opts out.
    rehome_comments: bool = True
    page_name: str
    title: str = Field(min_length=1, max_length=200)
    html: str = Field(max_length=8_000_000)
    source: str = Field(max_length=1_000_000)

    @model_validator(mode="after")
    def validate_page(self):
        if (
            Path(self.page_name).name != self.page_name
            or archived_page(Path(self.page_name)) is None
        ):
            raise ValueError(
                "Expected a rendered report filename without path components"
            )
        if self.document_id not in self.html:
            raise ValueError("Rendered page must contain its document identity")
        try:
            metadata, _ = parse_source(self.source)
        except SourceError as error:
            raise ValueError(str(error)) from error
        if self.document_id.split("-", 1)[1] != metadata.slug:
            raise ValueError("Source slug must match the published report identity")
        return self

    @property
    def document_id(self) -> str:
        return archived_page(Path(self.page_name)).document_id


def publish(
    reports: Reports,
    objects: Objects,
    publication: Publication,
    email: str,
    owners: set[str],
) -> Report:
    if email not in owners:
        raise HTTPException(403, "Only configured owners may publish")
    metadata, body = parse_source(publication.source)
    blocks = split_blocks(body)
    published_date = archived_page(Path(publication.page_name)).day
    html_key, source_key = objects.upload(
        publication.document_id, publication.html, publication.source
    )

    def promote(current: Report | None) -> Report:
        threads = (
            current.threads if current else ReportThreads.empty(publication.document_id)
        )
        if current and published_date < current.date:
            return current
        if current and publication.rehome_comments:
            rehome_all(threads, blocks)
        return Report(
            document_id=publication.document_id,
            title=publication.title,
            eyebrow=metadata.eyebrow,
            subtitle=metadata.subtitle,
            folder=metadata.folder,
            date=published_date,
            owner=current.owner if current else email,
            grants=current.grants if current else {},
            page_name=publication.page_name,
            html_key=html_key,
            source_key=source_key,
            threads=threads,
            revision=current.revision + 1 if current else 1,
        )

    version = {
        "page_name": publication.page_name,
        "title": publication.title,
        "eyebrow": metadata.eyebrow,
        "subtitle": metadata.subtitle,
        "folder": metadata.folder,
        "date": published_date,
        "html_key": html_key,
        "source_key": source_key,
    }
    return reports.mutate(publication.document_id, promote, version)
