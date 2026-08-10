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


NESTED = """- Premier item, avec une fence indentée :

    ```bash
    echo hello
    ```

- Deuxième item.
"""


def test_a_fence_nested_in_a_list_item_stays_in_it():
    """Regression: the 4-space indent SKILL.md documents for a fence inside a
    list item used to be cut into a block of its own, where markdown read the
    indentation as a code block and printed the ``` as literal text."""
    blocks = split_blocks(NESTED)
    assert len(blocks) == 2
    assert blocks[0].text.startswith("- Premier item") and "echo hello" in blocks[0].text
    assert blocks[1].text == "- Deuxième item."


def test_a_callout_nested_in_a_numbered_item_stays_in_it():
    body = '1. Un point.\n\n    !!! note "Contexte"\n        Le corps.\n\n2. Le suivant.\n'
    blocks = split_blocks(body)
    assert len(blocks) == 2
    assert "!!! note" in blocks[0].text


def test_a_tab_body_stays_with_the_tab_it_belongs_to():
    body = '=== "Un"\n\n    ```py\n    a = 1\n    ```\n\n=== "Deux"\n\n    Du texte.\n'
    blocks = split_blocks(body)
    assert [block.text.splitlines()[0] for block in blocks] == ['=== "Un"', '=== "Deux"']


def test_a_nested_fence_body_may_hold_blank_and_unindented_lines():
    """Inside a nested fence everything is verbatim, so neither a blank line nor
    a line back at column 0 may end the block early."""
    body = "- Un item :\n\n    ```text\n    sortie\n\nrevenu en marge\n    ```\n\nUn paragraphe.\n"
    blocks = split_blocks(body)
    assert len(blocks) == 2
    assert "revenu en marge" in blocks[0].text
    assert blocks[1].text == "Un paragraphe."


def test_loose_list_items_remain_one_block_each():
    """The granularity a comment anchor addresses: items separated by a blank
    line are distinct passages, and absorbing indented content must not fuse
    them into one block."""
    blocks = split_blocks("- un\n\n- deux\n\n- trois\n")
    assert [block.text for block in blocks] == ["- un", "- deux", "- trois"]


def test_a_paragraph_still_ends_at_the_next_top_level_construct():
    blocks = split_blocks("Un paragraphe.\n```py\nx\n```\n")
    assert blocks[0].text == "Un paragraphe."
    assert blocks[1].text.startswith("```py")
