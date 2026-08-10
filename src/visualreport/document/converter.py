"""The markdown converter: standard extensions plus the report dialect's fences."""

from __future__ import annotations

import markdown

from .assets import PageAssets
from .fences import custom_fences

BASE_EXTENSIONS = (
    "tables",
    "attr_list",
    "md_in_html",
    "footnotes",
    "admonition",
    "pymdownx.superfences",
    "pymdownx.details",
    "pymdownx.highlight",
    "pymdownx.arithmatex",
    "pymdownx.tabbed",
)


def build_converter(assets: PageAssets, include_toc: bool) -> markdown.Markdown:
    """A converter sharing `assets` with the page.

    `include_toc` is off for nested conversions (the halves of a ```cols block),
    so their headings never pollute the sidebar table of contents.
    """
    extensions = list(BASE_EXTENSIONS)
    if include_toc:
        extensions.insert(0, "toc")
    return markdown.Markdown(
        extensions=extensions,
        extension_configs={
            "toc": {"toc_depth": "2-3", "permalink": "¶"},
            "pymdownx.highlight": {"css_class": "highlight", "guess_lang": False},
            "pymdownx.arithmatex": {"generic": True},
            "pymdownx.tabbed": {"alternate_style": True},
            "pymdownx.superfences": {
                "custom_fences": custom_fences(
                    assets, lambda: build_converter(assets, include_toc=False)
                )
            },
        },
    )
