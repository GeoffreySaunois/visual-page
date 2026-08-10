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
class RenderRequest:
    source: Path
    kind: str
    output: Path | None
    iteration: IterationMode
    archive: Archive


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
    blocks = split_blocks(body)
    page_path = resolve_output(request, meta)
    identity = document_id(request.kind, meta.slug)

    iteration = resolve_iteration(request, identity, page_path, blocks)
    store = comments.store_for(request.archive, identity)
    rehomed = rehome_threads(store, request.archive.holds(page_path), blocks)

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
    archive_source(request, page_path, identity)

    return RenderOutcome(
        page=page_path,
        document_id=identity,
        warnings=warnings,
        changes=None if iteration is None else iteration.change_count,
        threads=rehomed,
    )


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

    A page rendered outside the archive (an explicit `-o`) is a one-off export: it
    still displays the threads, but never rewrites the store.
    """
    if not persist or not store.path.exists():
        return None
    with store.edit() as threads:
        return comments.rehome_all(threads, blocks)


def archive_source(request: RenderRequest, page_path: Path, identity: str) -> None:
    """Keep the source next to the page so it can be re-rendered later, and record
    it as the version the next iteration diff compares against."""
    if not request.archive.holds(page_path):
        return
    text = request.source.read_text(encoding="utf-8")
    target = request.archive.source_of(page_path)
    request.archive.sources.mkdir(parents=True, exist_ok=True)
    if request.source.resolve() != target:
        target.write_text(text, encoding="utf-8")
    kept = request.archive.previous_source(identity)
    kept.parent.mkdir(parents=True, exist_ok=True)
    kept.write_text(text, encoding="utf-8")
