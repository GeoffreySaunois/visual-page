"""Giving every block a DOM address, so a comment can point at a passage.

The page carries `data-vr-block="<index>"` on each block: the panel resolves a
selection to the block that holds it, and the store records that index together
with the quoted text. Headings take the attribute through `attr_list` rather
than a wrapper — wrapping a heading would put it inside a div and break the
single-pass table of contents.
"""

from __future__ import annotations

from .blocks import Block
from .composition import wrap_markdown_div

BLOCK_ATTRIBUTE = "data-vr-block"


def address_blocks(block: Block, markdown: str) -> str:
    if block.is_heading:
        return f'{markdown.rstrip()} {{: {BLOCK_ATTRIBUTE}="{block.index}" }}'
    return wrap_markdown_div(markdown, "vr-b", f'{BLOCK_ATTRIBUTE}="{block.index}"')
