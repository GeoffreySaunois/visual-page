"""Rebuilding a markdown body from its blocks, through a chain of decorators.

Several features need to annotate the source *per block* before the single
markdown conversion pass: the iteration diff boxes changed blocks, comment
anchoring gives each block a DOM address. They compose here instead of each
rewriting the body on its own — a new per-block feature is a new decorator, and
the block indices every feature refers to stay the ones of the original source.

Decorators are applied in list order, so the last one wraps outermost.
"""

from __future__ import annotations

from typing import Protocol

from .blocks import Block


class BlockDecorator(Protocol):
    """Rewrites one block's markdown, given the block it came from."""

    def __call__(self, block: Block, markdown: str) -> str: ...


def compose(blocks: list[Block], decorators: list[BlockDecorator]) -> str:
    parts = []
    for block in blocks:
        markdown = block.text
        for decorate in decorators:
            markdown = decorate(block, markdown)
        parts.append(markdown)
    return "\n\n".join(parts)


def wrap_markdown_div(markdown: str, css_class: str, attributes: str) -> str:
    """An `md_in_html` wrapper: the inner markdown is still processed by the
    single conversion pass, so wrappers can nest."""
    return (
        f'<div class="{css_class}" {attributes} markdown="1">\n\n'
        f"{markdown}\n\n"
        f"</div>"
    )
