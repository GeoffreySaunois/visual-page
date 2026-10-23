"""The TeX the converter typesets, told apart from prices written with `$`.

Arithmatex's smart dollars accept any `$` with a non-space on its left as a
closing delimiter, so `($1.53) exceeds its overflow ($14.25)` pairs the two
prices into one formula. Like Pandoc, a closing `$` here is never followed by a
digit: a dollar before a number is a price, and `$x^2$` still typesets.
"""

from __future__ import annotations

import re

import markdown
from pymdownx.arithmatex import (
    RE_BRACKET_BLOCK,
    RE_BRACKET_INLINE,
    RE_DOLLAR_BLOCK,
    RE_SMART_DOLLAR_INLINE,
    RE_TEX_BLOCK,
    InlineArithmatexPattern,
)

ARITHMATEX_CONFIG = {"generic": True}

SMART_DOLLAR_CLOSING = r"(?:\$))"
PRICE_AWARE_DOLLAR_INLINE = RE_SMART_DOLLAR_INLINE.replace(
    SMART_DOLLAR_CLOSING, r"(?:\$)(?!\d))"
)
if PRICE_AWARE_DOLLAR_INLINE == RE_SMART_DOLLAR_INLINE:
    raise ImportError("pymdownx smart-dollar pattern changed; review math.py")

INLINE_MATH = f"(?:{PRICE_AWARE_DOLLAR_INLINE}|{RE_BRACKET_INLINE})"

# Every span of `text` the converter would typeset, inline or as a block.
MATH = re.compile(
    "|".join((INLINE_MATH, RE_DOLLAR_BLOCK, RE_TEX_BLOCK, RE_BRACKET_BLOCK))
)


def use_price_aware_math(converter: markdown.Markdown) -> None:
    """Replace arithmatex's inline pattern, at its priority, with `INLINE_MATH`."""
    converter.inlinePatterns.register(
        InlineArithmatexPattern(INLINE_MATH, ARITHMATEX_CONFIG),
        "arithmatex-inline",
        189.9,
    )
