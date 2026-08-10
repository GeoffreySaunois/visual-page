"""Embedding local images, so a page stays one self-contained file."""

from __future__ import annotations

import base64
import itertools
import mimetypes
import re
from pathlib import Path

IMG_SRC_RE = re.compile(r'(<img\b[^>]*?\bsrc=")([^"]*)("[^>]*>)', re.IGNORECASE)

# The one wording for an image the page could not embed. Callers that repair a
# page match on it, so it lives here rather than being spelled out twice.
MISSING_IMAGE = "image not found, left as-is: "


def inline_local_images(content: str, base_dir: Path) -> tuple[str, list[str]]:
    """Rewrite local image sources as base64 data URIs.

    `data:` and `http(s):` sources are left untouched. Relative paths resolve
    against the markdown source's directory; absolute and `~` paths are honored.
    A missing file is reported as a warning and left as-is. Covers both markdown
    `![alt](path)` and raw `<img>` tags — by this point both are `<img>`.
    """
    warnings: list[str] = []

    def replace(match: re.Match) -> str:
        prefix, src, suffix = match.groups()
        if is_embedded(src):
            return match.group(0)
        path = Path(src).expanduser()
        if not path.is_absolute():
            path = base_dir / path
        if not path.is_file():
            warnings.append(f"{MISSING_IMAGE}{src}")
            return match.group(0)
        mime = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        data = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"{prefix}data:{mime};base64,{data}{suffix}"

    return IMG_SRC_RE.sub(replace, content), warnings


def carry_over_images(page: str, replaced: str) -> tuple[str, list[str]]:
    """Fill the images a render could not embed from the page it replaces.

    Re-rendering an archived source finds the screenshots gone from the disk they
    were captured on, while the page being rewritten still carries them as data
    URIs. Both pages come from the same source, so their `<img>` tags are the same
    sequence in the same order and a gap is filled from its counterpart. A
    different count means the two are not the same document: nothing is carried
    and every gap is reported, so the caller can leave the page alone.
    """
    current = image_sources(page)
    gaps = [index for index, src in enumerate(current) if not is_embedded(src)]
    if not gaps:
        return page, []
    donors = image_sources(replaced)
    aligned = len(donors) == len(current)
    carried = {
        index: donors[index]
        for index in gaps
        if aligned and donors[index].startswith("data:")
    }
    lost = [f"{MISSING_IMAGE}{current[index]}" for index in gaps if index not in carried]
    return substitute_sources(page, carried), lost


def image_sources(content: str) -> list[str]:
    """Every `<img>` source of a page, in document order."""
    return [match.group(2) for match in IMG_SRC_RE.finditer(content)]


def is_embedded(src: str) -> bool:
    """Whether a source needs no file on disk to display."""
    return src.startswith(("data:", "http://", "https://"))


def substitute_sources(content: str, sources: dict[int, str]) -> str:
    """Replace the sources of the `<img>` tags at the given positions."""
    positions = itertools.count()

    def swap(match: re.Match) -> str:
        prefix, _, suffix = match.groups()
        replacement = sources.get(next(positions))
        return match.group(0) if replacement is None else f"{prefix}{replacement}{suffix}"

    return IMG_SRC_RE.sub(swap, content)
