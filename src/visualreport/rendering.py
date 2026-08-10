"""Compiling a source into a page — the one place the features meet.

    source.md ──► blocks ──► decorators ──► markdown ──► page.html
                    │            ▲
                    │            ├── iteration: box what changed since last time
                    │            └── anchoring: give each block a DOM address
                    └──────────► comments: re-home the threads on those blocks

Each feature reads the same block list, so the indices a comment stored and the
indices a diff computed always mean the same passage.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from . import comments
from .document import (
    PageAssets,
    PageContent,
    SourceError,
    address_blocks,
    build_converter,
    compose,
    inline_local_images,
    literal_list_markers,
    read_source,
    render_page,
    split_blocks,
)
from .document.blocks import Block
from .document.controls import side_controls
from .document.frontmatter import ReportMeta
from .iteration import Iteration, review
from .paths import Archive, document_id


class IterationMode(StrEnum):
    AUTO = "auto"  # diff iff a previous version of this document is archived
    FORCE = "force"  # diff, and fail if there is nothing to diff against
    OFF = "off"


@dataclass(frozen=True)
class Refresh:
    """Replaying a source the archive already holds, through today's templates.

    `day` is the date the page was published at: it names the file and it is what
    the header prints, in place of the date the front matter derives — an archived
    source carries no explicit `date`, so a replay would otherwise be stamped
    today and land beside the page instead of on it.

    A refresh advances nothing about the document: the source stays archived as
    it is, the iteration reference keeps pointing at the version last published,
    and the comment threads keep the homes they have.
    """

    day: str


@dataclass(frozen=True)
class RenderRequest:
    source: Path
    kind: str
    output: Path | None
    iteration: IterationMode
    archive: Archive
    refresh: Refresh | None


@dataclass(frozen=True)
class RenderOutcome:
    page: Path
    document_id: str
    warnings: list[str]
    changes: int | None
    threads: comments.RehomeReport | None

    @property
    def archived(self) -> bool:
        return self.threads is not None


def render(request: RenderRequest) -> RenderOutcome:
    meta, body = read_source(request.source)
    meta = stamped(meta, request.refresh)
    blocks = split_blocks(body)
    page_path = resolve_output(request, meta)
    identity = document_id(request.kind, meta.slug)
    advances = advances_document(request, page_path)

    iteration = resolve_iteration(request, identity, page_path, blocks)
    store = comments.store_for(request.archive, identity)
    rehomed = rehome_threads(store, advances, blocks)

    decorators = [address_blocks] if iteration is None else [iteration.decorator, address_blocks]
    assets = PageAssets()
    converter = build_converter(assets, include_toc=True)
    html_body = converter.convert(compose(blocks, decorators))
    html_body, warnings = inline_local_images(html_body, request.source.parent)
    warnings.extend(literal_list_markers(html_body))

    page = render_page(
        meta,
        PageContent(
            document_id=identity,
            body=html_body,
            toc_tokens=converter.toc_tokens,
            changelog="" if iteration is None else iteration.changelog_html,
            side_controls=side_controls(has_iteration=iteration is not None),
            comments_bootstrap=comments.report_view(store.read(), store.revision),
            assets=assets,
        ),
    )
    page_path.parent.mkdir(parents=True, exist_ok=True)
    page_path.write_text(page, encoding="utf-8")
    if advances:
        archive_source(request, page_path, identity)

    return RenderOutcome(
        page=page_path,
        document_id=identity,
        warnings=warnings,
        changes=None if iteration is None else iteration.change_count,
        threads=rehomed,
    )


def stamped(meta: ReportMeta, refresh: Refresh | None) -> ReportMeta:
    """The date the page goes out under — the refreshed page's own, when there is
    one, so a replay lands on the file it rebuilds."""
    if refresh is None:
        return meta
    return meta.model_copy(update={"date": refresh.day})


def advances_document(request: RenderRequest, page_path: Path) -> bool:
    """Whether this render becomes the document's new state.

    Two renders do not: a refresh rebuilds a page that is already published, and
    a page written outside the archive (an explicit `-o`) is a one-off export.
    Both read the document's threads and neither owns them.
    """
    return request.refresh is None and request.archive.holds(page_path)


def resolve_output(request: RenderRequest, meta: ReportMeta) -> Path:
    if request.output is not None:
        return request.output.resolve()
    return request.archive.page(request.kind, meta.slug, meta.date)


def resolve_iteration(
    request: RenderRequest, identity: str, page_path: Path, blocks: list[Block]
) -> Iteration | None:
    """The diff is computed before the source is archived, which would overwrite
    the very version being compared against."""
    if request.iteration is IterationMode.OFF:
        return None
    previous = previous_source(request, identity, page_path)
    if previous is None:
        if request.iteration is IterationMode.FORCE:
            raise SourceError(
                f"--diff demandé mais aucune version précédente de {identity} "
                f"dans {request.archive.sources}"
            )
        return None
    return review(previous, blocks)


def previous_source(request: RenderRequest, identity: str, page_path: Path) -> Path | None:
    """The version this render compares against: the one last rendered.

    Falls back to the newest dated source of the document — how the archive was
    laid out before versions were tracked per document — excluding the file this
    render is about to overwrite. One step back only, never a history.
    """
    kept = request.archive.previous_source(identity)
    if kept.is_file():
        return kept
    if not request.archive.sources.is_dir():
        return None
    target = request.archive.source_of(page_path)
    candidates = [
        candidate for candidate in request.archive.sources_of(identity) if candidate != target
    ]
    return candidates[-1] if candidates else None


def rehome_threads(
    store: comments.ThreadStore, persist: bool, blocks: list[Block]
) -> comments.RehomeReport | None:
    """Re-point the document's threads at the new blocks.

    Only the render that publishes a new version moves them; a one-off export and
    a refresh both display the threads without rewriting the store. A refresh
    especially: it replays an old version, and re-homing threads on it would drag
    the anchors backwards, away from the version they are aimed at.
    """
    if not persist or not store.path.exists():
        return None
    with store.edit() as threads:
        return comments.rehome_all(threads, blocks)


def archive_source(request: RenderRequest, page_path: Path, identity: str) -> None:
    """Keep the source next to the page so it can be re-rendered later, and record
    it as the version the next iteration diff compares against."""
    text = request.source.read_text(encoding="utf-8")
    target = request.archive.source_of(page_path)
    request.archive.sources.mkdir(parents=True, exist_ok=True)
    if request.source.resolve() != target:
        target.write_text(text, encoding="utf-8")
    kept = request.archive.previous_source(identity)
    kept.parent.mkdir(parents=True, exist_ok=True)
    kept.write_text(text, encoding="utf-8")
