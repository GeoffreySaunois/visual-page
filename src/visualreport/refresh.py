"""Rebuilding pages the archive already holds, with today's templates.

A page inlines its styles and its scripts, so it keeps the templates it was built
with for as long as it exists: a fix to the comment panel or to the charte reaches
the pages published afterwards and no others. A refresh closes that gap — it
replays each archived source through the current templates and rewrites the page
in place, under its own name and its own date.

It is not an iteration. The source is the very one that produced the page, so
there is nothing to diff against and nothing to record: no changelog, the
iteration reference untouched, the comment threads left on the homes they have.

A page is rebuilt beside its target and promoted only once it is whole. A source
whose screenshots left the disk therefore never overwrites a page that still
carries them — the images come from the page being replaced, and what cannot be
carried leaves that page alone.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .document import SourceError, carry_over_images
from .document.images import MISSING_IMAGE
from .paths import Archive, ArchivedPage
from .rendering import IterationMode, Refresh, RenderOutcome, RenderRequest, render

REBUILD_SUFFIX = ".rebuilding"


@dataclass(frozen=True)
class Rewritten:
    """A page rebuilt in place, with whatever the render had to say about it."""

    page: ArchivedPage
    warnings: list[str]


@dataclass(frozen=True)
class Skipped:
    """A page left exactly as it was, and why."""

    page: ArchivedPage
    reason: str


@dataclass(frozen=True)
class Outcome:
    """What one pass over the archive did."""

    rewritten: list[Rewritten]
    skipped: list[Skipped]


def survey(archive: Archive, document: str | None) -> tuple[list[ArchivedPage], list[Skipped]]:
    """The pages a refresh would rebuild, and the ones it cannot reach.

    `document` narrows the pass to one `<kind>-<slug>`, all of its dates. A page
    whose source is not archived beside it cannot be replayed at all: it is named
    rather than passed over in silence.
    """
    selected = [page for page in archive.pages() if document in (None, page.document_id)]
    replayable: list[ArchivedPage] = []
    unreachable: list[Skipped] = []
    for page in selected:
        source = archive.source_of(page.path)
        if source.is_file():
            replayable.append(page)
        else:
            local = source.relative_to(archive.root)
            unreachable.append(Skipped(page, f"source archivée absente ({local})"))
    return replayable, unreachable


def run(archive: Archive, document: str | None) -> Outcome:
    """Rebuild every page of the archive, or every page of one document."""
    replayable, skipped = survey(archive, document)
    rewritten: list[Rewritten] = []
    for page in replayable:
        result = rebuild(archive, page)
        if isinstance(result, Rewritten):
            rewritten.append(result)
        else:
            skipped.append(result)
    return Outcome(rewritten=rewritten, skipped=skipped)


def rebuild(archive: Archive, page: ArchivedPage) -> Rewritten | Skipped:
    """Replay one page's source and swap the result in, or say why not."""
    draft = page.path.with_name(page.path.name + REBUILD_SUFFIX)
    try:
        outcome = compile_draft(archive, page, draft)
        if outcome.document_id != page.document_id:
            return Skipped(page, f"la source déclare le document {outcome.document_id}")
        whole, lost = carry_over_images(
            draft.read_text(encoding="utf-8"), page.path.read_text(encoding="utf-8")
        )
        if lost:
            return Skipped(page, "images introuvables : " + ", ".join(lost))
        draft.write_text(whole, encoding="utf-8")
        os.replace(draft, page.path)
    except SourceError as error:
        return Skipped(page, str(error))
    finally:
        draft.unlink(missing_ok=True)
    return Rewritten(page, kept_warnings(outcome))


def compile_draft(archive: Archive, page: ArchivedPage, draft: Path) -> RenderOutcome:
    """Render the archived source into a file beside the page it will replace."""
    kind, _, _ = page.document_id.partition("-")
    return render(
        RenderRequest(
            source=archive.source_of(page.path),
            kind=kind,
            output=draft,
            iteration=IterationMode.OFF,
            archive=archive,
            refresh=Refresh(day=page.day),
        )
    )


def kept_warnings(outcome: RenderOutcome) -> list[str]:
    """What the render said, minus the images the page being replaced supplies —
    those are repaired, so naming them would report a loss that did not happen."""
    return [warning for warning in outcome.warnings if not warning.startswith(MISSING_IMAGE)]
