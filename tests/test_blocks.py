"""The splitter is what every cross-version feature aligns on: if it merges or
splits a block differently, comments and diffs land on the wrong passage."""

from __future__ import annotations

from visualreport.document import split_blocks

BODY = """## Titre

Un paragraphe
sur deux lignes.

```chart title="x"
{"a": 1,

 "b": 2}
```

!!! note "Attention"
    Un corps de callout

    avec un blanc au milieu.

- item un
- item deux

| a | b |
|---|---|
| 1 | 2 |
"""


def test_fences_and_callouts_survive_their_blank_lines():
    blocks = split_blocks(BODY)
    texts = [block.text for block in blocks]
    assert texts[0] == "## Titre"
    assert texts[1] == "Un paragraphe\nsur deux lignes."
    assert texts[2].startswith("```chart") and texts[2].endswith("```")
    assert '"b": 2}' in texts[2]
    assert texts[3].startswith('!!! note') and "avec un blanc au milieu." in texts[3]
    assert texts[4] == "- item un\n- item deux"
    assert texts[5].startswith("| a | b |")


def test_only_paragraphs_are_word_diffable():
    prose = [block.index for block in split_blocks(BODY) if block.is_prose]
    # Only block 1, the paragraph: heading, fence, callout, list and table are all
    # structural, and splicing <ins>/<del> into them would corrupt the markup.
    assert prose == [1]


def test_heading_lookup_walks_backwards():
    blocks = split_blocks(BODY)
    from visualreport.document import nearest_heading

    assert nearest_heading(blocks, 4) == "Titre"


def test_unterminated_fence_does_not_swallow_the_rest_silently():
    blocks = split_blocks("para\n\n```py\ncode\n")
    assert len(blocks) == 2
    assert blocks[1].text.startswith("```py")
