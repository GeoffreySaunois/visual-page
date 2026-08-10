"""The lints exist to name a source that renders wrong without erroring."""

from __future__ import annotations

from visualreport.document import orphaned_nested_blocks, split_blocks


def test_an_indented_fence_with_nothing_to_nest_under_is_named():
    """A fence indented under a heading hangs from nothing: markdown prints it as
    literal text, and only a lint tells the author before the reader does."""
    blocks = split_blocks("## Titre\n\n    ```bash\n    echo hello\n    ```\n")
    warnings = orphaned_nested_blocks(blocks)
    assert len(warnings) == 1
    assert "nothing above it to nest under" in warnings[0]


def test_a_fence_properly_nested_in_a_list_item_is_not_flagged():
    blocks = split_blocks("- Un item :\n\n    ```bash\n    echo hello\n    ```\n")
    assert orphaned_nested_blocks(blocks) == []
