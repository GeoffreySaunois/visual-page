"""The mark the pages carry: the favicon a rendered page and the gallery ship.

Inlined as a base64 data URI rather than referenced as a file next to the page.
Hard rule 1 is that a page opens by double-click with no local assets, so a
`href="favicon.svg"` would be a broken tab the moment the page is moved, mailed
or opened from the archive over http — the icon has to travel inside the file.

The sources live in `templates/icons/`; add a mark by dropping an SVG there and
naming it at the call site.
"""

from __future__ import annotations

import base64
from pathlib import Path

ICON_DIR = Path(__file__).resolve().parent / "templates" / "icons"


def favicon_link(name: str) -> str:
    """The `<link rel="icon">` tag for `templates/icons/<name>.svg`, inlined."""
    encoded = base64.b64encode((ICON_DIR / f"{name}.svg").read_bytes()).decode("ascii")
    return f'<link rel="icon" type="image/svg+xml" href="data:image/svg+xml;base64,{encoded}" />'
