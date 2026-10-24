"""A gallery preview keeps the top of its page and nothing that runs or weighs."""

from __future__ import annotations

from visualreport.gallery import preview


def page(blocks: list[str], after: str = "") -> str:
    body = "".join(
        f'<div class="vr-b" data-vr-block="{index}">{block}</div>\n'
        for index, block in enumerate(blocks)
    )
    return (
        "<html><head><script>localStorage.setItem('vr-theme','dark')</script>"
        '<style>.x{}</style></head><body><div class="vr-app"><main>'
        '<header class="doc-head"><h1>Title</h1></header>\n'
        f"{body}</main></div>{after}"
        '<script type="application/json" id="vr-bootstrap">{"threads": []}</script>'
        "<script>poll()</script></body></html>"
    )


def test_the_preview_keeps_whole_leading_blocks_and_runs_nothing():
    blocks = [f"<p>block {index}</p>" for index in range(10)]
    cut = preview.snapshot(page(blocks))
    assert "<h1>Title</h1>" in cut and "<style>.x{}</style>" in cut
    kept = [index for index in range(10) if f"block {index}<" in cut]
    assert kept == list(range(preview.PREVIEW_BLOCKS))
    assert "<script" not in cut
    # The cut falls between blocks, never inside one: the last kept one is whole.
    assert f"block {preview.PREVIEW_BLOCKS - 1}</p></div>" in cut


def test_a_long_block_ends_the_preview_on_the_markup_budget():
    blocks = [
        "<p>short</p>",
        "<p>" + "x" * preview.MARKUP_BUDGET + "</p>",
        "<p>after</p>",
    ]
    cut = preview.snapshot(page(blocks))
    assert "short" in cut and "after" not in cut


def test_heavy_screenshots_past_the_budget_become_neutral_boxes():
    """A page built around multi-megabyte screenshots must not cost its full
    weight per card: the first image fits the budget, the next ones do not."""
    shot = "data:image/png;base64," + "A" * (preview.IMAGE_BUDGET // 2 + 1)
    blocks = [f'<img src="{shot}" alt="{index}">' for index in range(3)]
    cut = preview.snapshot(page(blocks))
    assert cut.count(shot) == 1
    assert cut.count(preview.PLACEHOLDER) == 2
    assert len(cut) < preview.IMAGE_BUDGET + 10_000


def test_a_page_without_a_main_column_still_previews_without_scripts():
    legacy = "<html><body><div class='wrap'><h1>Old</h1></div><script>x()</script></body></html>"
    cut = preview.snapshot(legacy)
    assert "<h1>Old</h1>" in cut and "<script" not in cut


def test_inline_handlers_are_dropped_with_the_scripts():
    # A hand-written page wires its buttons with onclick: each one would be a
    # blocked-script error on the gallery's console.
    cut = preview.snapshot(
        page(['<button onclick="openChangelog()">Changelog</button>'])
    )
    assert "onclick" not in cut and ">Changelog</button>" in cut
