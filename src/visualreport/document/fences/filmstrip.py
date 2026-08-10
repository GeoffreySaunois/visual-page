"""```filmstrip — a sequence of images flipped through one at a time, like a slideshow."""

from __future__ import annotations

import html

from ..frontmatter import SourceError
from .data import yaml_items


def format_filmstrip(source, language, css_class, options, md, **kwargs) -> str:
    items = yaml_items(source, "filmstrip", "{path, caption?}")
    if len(items) < 2:
        raise SourceError(
            "```filmstrip needs at least 2 images — a single image is a plain ![](path)"
        )
    label = f"Séquence de {len(items)} images — flèches gauche/droite pour naviguer"
    parts = [
        '<div class="filmstrip" tabindex="0" role="group" aria-roledescription="carousel" '
        f'aria-label="{html.escape(label)}">'
    ]
    if head := options.get("title", ""):
        parts.append(f'<div class="fig-head">{html.escape(head)}</div>')
    parts.append('<div class="filmstrip-stage">')
    parts.append("".join(format_slide(index, item) for index, item in enumerate(items)))
    parts.append(
        '<button class="filmstrip-nav filmstrip-prev" type="button" '
        'aria-label="Image précédente">&#8249;</button>'
        '<button class="filmstrip-nav filmstrip-next" type="button" '
        'aria-label="Image suivante">&#8250;</button>'
        "</div>"
        f'<div class="filmstrip-count">1 / {len(items)}</div>'
        "</div>"
    )
    return "".join(parts)


def format_slide(index: int, item) -> str:
    if not isinstance(item, dict) or "path" not in item:
        raise SourceError("```filmstrip items must be mappings with at least {path}")
    caption = str(item.get("caption", ""))
    alt = caption or f"image {index + 1}"
    active = " is-active" if index == 0 else ""
    caption_html = f'<div class="filmstrip-caption">{html.escape(caption)}</div>' if caption else ""
    return (
        f'<div class="filmstrip-slide{active}">'
        f'<img src="{html.escape(str(item["path"]))}" alt="{html.escape(alt)}">'
        f"{caption_html}</div>"
    )
