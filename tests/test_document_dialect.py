"""The markdown dialect as it converts: lists written under a sentence, prices
beside math, charts without data, and the iteration diff over both."""

from __future__ import annotations

import json

from visualreport.document import (
    PageAssets,
    address_blocks,
    build_converter,
    compose,
    literal_fence_markers,
    split_blocks,
)
from visualreport.iteration import align
from visualreport.iteration.annotate import make_decorator
from visualreport.iteration.matching import ChangeKind, similar


def convert(source: str) -> str:
    return build_converter(PageAssets(), include_toc=False).convert(source)


def revise(old: str, new: str) -> str:
    """`new` converted with its blocks annotated against `old`, as a render does."""
    old_blocks, new_blocks = split_blocks(old), split_blocks(new)
    decorators = [make_decorator(align(old_blocks, new_blocks)), address_blocks]
    return convert(compose(new_blocks, decorators))


# ---------------------------------------------------------------- Lists -----


def test_a_list_right_under_a_paragraph_renders_as_a_list():
    # Regression: bullets written on the line after a sentence rendered as one
    # paragraph of literal dashes.
    rendered = convert("Window: one day.\n- **Activity.** 106 sessions.\n- **Users.** 11.")
    assert rendered.count("<li>") == 2
    assert "Window: one day.</p>" in rendered


def test_only_an_ordered_item_numbered_one_interrupts_a_paragraph():
    assert convert("Text\n1. first\n2. second").count("<li>") == 2
    assert "<li>" not in convert("In 2026 we shipped\n3. versions")


def test_a_lazy_list_continuation_keeps_its_list_tight():
    rendered = convert("- first\ncontinued\n- second")
    assert rendered.count("<li>") == 2 and "<p>" not in rendered


def test_an_outer_item_right_under_a_nested_paragraph_stays_an_item():
    rendered = convert(
        "- **AM.** Relaunch.\n"
        "    - one case per error;\n"
        "    - one run relaunched.\n\n"
        "    The three cases fail on the old code.\n"
        "- **F.** Foundry in the image.\n"
        "- **Tests.** All pass."
    )
    assert rendered.count("<li>") == 5
    assert "- **" not in rendered


def test_a_dash_inside_a_fence_under_a_sentence_stays_code():
    rendered = convert("```text\nline\n- not an item\n```")
    assert "<li>" not in rendered and "- not an item" in rendered


def test_a_fence_that_never_parsed_is_still_reported():
    # Regression: a diff fence inside a tab that never closed used to surface as
    # literal list markers in a paragraph; now that its `+ ` lines become a list,
    # the fence opener left in prose is what gives it away.
    broken = convert('=== "lease.rs"\n\n    ```diff title="x"\n    + one\n    + two\n')
    closed = convert('=== "lease.rs"\n\n    ```diff title="x"\n    + one\n    ```\n')
    assert literal_fence_markers(broken) and not literal_fence_markers(closed)


# ----------------------------------------------------------------- Math -----


def test_prices_in_parentheses_never_pair_into_math():
    # Regression: smart dollars closed a formula on the `$` after `(`, so
    # "($1.53) exceeds its overflow ($14.25)" typeset as TeX.
    rendered = convert("The bribe ($1.53) exceeds its overflow ($14.25), and $0.24 (at $5).")
    assert "arithmatex" not in rendered


def test_math_beside_a_price_still_typesets():
    assert r'<span class="arithmatex">\(x^2\)</span>' in convert("Spend $5 when $x^2$ holds.")


def test_revision_of_prices_never_pairs_dollars_into_math():
    # Regression: `<del class="vr-del">$6.48.</del>` made the `$` after `>` a
    # closing delimiter, so the paragraph rendered from `$0.24` on as TeX.
    rendered = revise(
        "Oct 3 had $0.24, and Oct 7 has three, worth $6.48. Bars.",
        "Oct 3 had $0.24, and Oct 7 has five, worth $12.38. Bars.",
    )
    assert "arithmatex" not in rendered
    assert '<del class="vr-del">$6.48.</del>' in rendered
    assert '<ins class="vr-ins">$12.38.</ins>' in rendered


def test_revision_of_a_paragraph_with_math_never_splices_tags_into_it():
    rendered = revise("Fit $y = a x + b$ here.", "Fit $y = a x + c$ here.")
    assert "<del " not in rendered
    assert r'<span class="arithmatex">\(y = a x + c\)</span>' in rendered


# ------------------------------------------------------- Iteration caps -----


def one_line_json(seed: int, items: int) -> str:
    return "```json\n" + json.dumps([{"id": i, "v": (i * 7919 + seed * 104729) % 10007} for i in range(items)]) + "\n```"


def test_a_large_one_line_fence_edited_in_place_is_modified():
    # A regenerated 150 KB one-line fence used to take minutes to compare: its
    # few edits now bound the comparison.
    old = one_line_json(0, 7_000)
    middle = len(old) // 2
    new = old[:middle] + ("1" if old[middle] != "1" else "2") + old[middle + 1 :]
    assert len(old) > 150_000
    alignment = align(split_blocks(old), split_blocks(new))
    assert [match.kind for match in alignment.matches] == [ChangeKind.MODIFIED]


def test_unrelated_blocks_are_not_paired_past_the_edit_cap():
    old, new = one_line_json(0, 1_700), one_line_json(1, 1_700)
    assert not similar(split_blocks(old)[0].normalized, split_blocks(new)[0].normalized)


def test_a_prose_revision_past_the_word_cap_is_boxed_without_a_word_diff():
    # Splitting a word in two is one character but three word edits, so a pair
    # within the character cap can still exceed the word cap.
    words = [f"measurement{index}" for index in range(400)]
    split = [f"measure ment{index}" if index % 2 == 0 else word for index, word in enumerate(words)]
    rendered = revise(" ".join(words), " ".join(split))
    assert "vr-chg mod" in rendered and '<del class="vr-del">' not in rendered


# --------------------------------------------------------------- Charts -----


def test_a_chart_without_a_data_object_never_reaches_the_chart_script():
    # The page script reads `config.data.datasets` of every chart in one loop, so
    # a chart without data would throw and leave every chart of the page blank.
    assets = PageAssets()
    build_converter(assets, include_toc=False).convert(
        '```chart\n{"type": "bar"}\n```\n\n```chart\n{"type": "bar", "data": {"datasets": []}}\n```\n'
    )
    assert [chart["type"] for chart in assets.charts] == ["bar"] and "data" in assets.charts[0]
