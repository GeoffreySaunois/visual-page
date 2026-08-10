"""Embedding local images, so a page stays one self-contained file."""

from __future__ import annotations

import base64
import mimetypes
import re
from pathlib import Path

IMG_SRC_RE = re.compile(r'(<img\b[^>]*?\bsrc=")([^"]*)("[^>]*>)', re.IGNORECASE)


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
        if src.startswith(("data:", "http://", "https://")):
            return match.group(0)
        path = Path(src).expanduser()
        if not path.is_absolute():
            path = base_dir / path
        if not path.is_file():
            warnings.append(f"image not found, left as-is: {src}")
            return match.group(0)
        mime = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        data = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"{prefix}data:{mime};base64,{data}{suffix}"

    return IMG_SRC_RE.sub(replace, content), warnings
