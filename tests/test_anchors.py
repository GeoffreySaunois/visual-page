"""Re-anchoring is the load-bearing part of the comment loop: the source keeps
being rewritten between renders, and a thread must follow its passage or say
honestly that it lost it."""

from __future__ import annotations

from visualreport import comments
from visualreport.document import split_blocks

QUOTE = "le coût marginal par idée"
BODY = """## Contexte

Ici, le coût marginal par idée est de 3,20 €.

## Méthode

Trois métriques.
"""


def thread_on(body: str, quote: str) -> comments.Thread:
    blocks = split_blocks(body)
    threads = comments.ReportThreads.empty("report-test")
    anchor = comments.anchor_for_quote(blocks, quote)
    return threads.open_thread(
        anchor=anchor,
        state=comments.AnchorState.ANCHORED,
        author=comments.GEOFFREY,
        body="vérifie ce chiffre",
        now=comments.now_utc(),
    )


def test_a_block_that_moved_keeps_its_anchor_at_the_new_index():
    thread = thread_on(BODY, QUOTE)
    assert thread.anchor.block_index == 1
    moved = BODY.replace("## Contexte", "## Préambule\n\nUn ajout.\n\n## Contexte")
    state = comments.anchors.rehome(thread, split_blocks(moved))
    assert state is comments.AnchorState.ANCHORED
    assert thread.anchor.block_index == 3
    assert thread.anchor.section == "Contexte"


def test_a_rewritten_quote_drifts_but_the_thread_survives():
    thread = thread_on(BODY, QUOTE)
    edited = BODY.replace("le coût marginal par idée", "la dépense par idée retenue")
    state = comments.anchors.rehome(thread, split_blocks(edited))
    assert state is comments.AnchorState.DRIFTED
    # The anchor adopts the current wording, so the agent reads what is there now.
    assert "la dépense par idée retenue" in thread.anchor.block_source
    assert thread.anchor.quote == QUOTE


def test_a_deleted_block_orphans_the_thread():
    thread = thread_on(BODY, QUOTE)
    without = "## Méthode\n\nTrois métriques.\n"
    assert comments.anchors.rehome(thread, split_blocks(without)) is comments.AnchorState.ORPHANED


def test_a_quote_wrapped_in_emphasis_is_still_found():
    """The quote comes from the rendered page; the source carries markdown."""
    body = BODY.replace(QUOTE, f"**{QUOTE}**")
    thread = thread_on(body, QUOTE)
    assert thread.anchor.block_index == 1


def test_rehoming_counts_every_state():
    blocks = split_blocks(BODY)
    threads = comments.ReportThreads.empty("report-test")
    for quote in (QUOTE, "Trois métriques"):
        threads.open_thread(
            anchor=comments.anchor_for_quote(blocks, quote),
            state=comments.AnchorState.ANCHORED,
            author=comments.GEOFFREY,
            body="?",
            now=comments.now_utc(),
        )
    threads.open_thread(
        anchor=None,
        state=comments.AnchorState.DOCUMENT,
        author=comments.GEOFFREY,
        body="global",
        now=comments.now_utc(),
    )
    report = comments.rehome_all(threads, split_blocks(BODY.replace("Trois métriques.", "")))
    assert (report.anchored, report.orphaned, report.total) == (1, 1, 2)


def test_plain_text_drops_the_syntax_not_the_words():
    assert comments.plain_text("- un [lien](http://x) et `du code`") == "un lien et du code"
