"""The thread lifecycle and its persistence — including who the loop is waiting on."""

from __future__ import annotations

import pytest

from visualreport import comments
from visualreport.paths import Archive


def store_of(archive: Archive) -> comments.ThreadStore:
    return comments.store_for(archive, "report-test")


def open_one(threads: comments.ReportThreads, author: comments.Author) -> comments.Thread:
    return threads.open_thread(
        anchor=None,
        state=comments.AnchorState.DOCUMENT,
        author=author,
        body="premier message",
        now=comments.now_utc(),
    )


def test_awaiting_flips_to_the_other_participant(archive: Archive):
    threads = comments.ReportThreads.empty("report-test")
    thread = open_one(threads, comments.GEOFFREY)
    assert thread.awaiting is comments.AuthorKind.AGENT
    thread.add_comment(comments.CLAUDE, "corrigé", comments.now_utc())
    assert thread.awaiting is comments.AuthorKind.HUMAN
    assert threads.awaiting(comments.AuthorKind.HUMAN) == [thread]


def test_resolving_stops_the_loop_and_reopening_restarts_it(archive: Archive):
    threads = comments.ReportThreads.empty("report-test")
    thread = open_one(threads, comments.GEOFFREY)
    thread.resolve(comments.CLAUDE, comments.now_utc())
    assert thread.awaiting is None and not threads.open_threads
    thread.reopen(comments.now_utc())
    assert thread.awaiting is comments.AuthorKind.AGENT


def test_thread_ids_never_get_reused_after_a_delete(archive: Archive):
    store = store_of(archive)
    with store.edit() as threads:
        open_one(threads, comments.GEOFFREY)
        open_one(threads, comments.GEOFFREY)
    with store.edit() as threads:
        threads.delete("t1")
    with store.edit() as threads:
        assert open_one(threads, comments.GEOFFREY).id == "t3"


def test_comment_ids_are_stable_within_a_thread(archive: Archive):
    threads = comments.ReportThreads.empty("report-test")
    thread = open_one(threads, comments.GEOFFREY)
    second = thread.add_comment(comments.CLAUDE, "réponse", comments.now_utc())
    assert (thread.comments[0].id, second.id) == ("t1.1", "t1.2")


def test_editing_keeps_the_author_and_records_that_it_was_edited(archive: Archive):
    threads = comments.ReportThreads.empty("report-test")
    thread = open_one(threads, comments.GEOFFREY)
    edited = thread.edit_comment("t1.1", "en fait, vérifie plutôt la série du 2/08", comments.now_utc())
    assert edited.body.startswith("en fait")
    assert edited.author == comments.GEOFFREY
    assert edited.edited_at is not None


def test_a_deleted_comment_never_lends_its_id_to_the_next_one(archive: Archive):
    """Numbering from the list length would hand t1.2 to a new message after the
    first t1.2 was deleted, and two different messages would share an id."""
    threads = comments.ReportThreads.empty("report-test")
    thread = open_one(threads, comments.GEOFFREY)
    thread.add_comment(comments.CLAUDE, "réponse", comments.now_utc())
    thread.remove_comment("t1.2", comments.now_utc())
    assert thread.add_comment(comments.CLAUDE, "autre réponse", comments.now_utc()).id == "t1.3"


def test_deleting_the_only_comment_takes_the_thread_with_it(archive: Archive):
    threads = comments.ReportThreads.empty("report-test")
    open_one(threads, comments.GEOFFREY)
    assert threads.delete_comment("t1", "t1.1", comments.now_utc()) is True
    assert threads.threads == []


def test_deleting_one_comment_of_several_keeps_the_thread(archive: Archive):
    threads = comments.ReportThreads.empty("report-test")
    thread = open_one(threads, comments.GEOFFREY)
    thread.add_comment(comments.CLAUDE, "réponse", comments.now_utc())
    assert threads.delete_comment("t1", "t1.2", comments.now_utc()) is False
    assert [comment.id for comment in threads.require("t1").comments] == ["t1.1"]


def test_an_unknown_comment_is_named_in_the_error(archive: Archive):
    threads = comments.ReportThreads.empty("report-test")
    thread = open_one(threads, comments.GEOFFREY)
    with pytest.raises(comments.CommentError, match="t1.9"):
        thread.require_comment("t1.9")


def test_the_store_round_trips_and_moves_its_revision(archive: Archive):
    store = store_of(archive)
    assert store.read().threads == []
    before = store.revision
    with store.edit() as threads:
        open_one(threads, comments.CLAUDE)
    assert store.revision != before
    reloaded = store.read()
    assert reloaded.threads[0].comments[0].author == comments.CLAUDE


def test_an_unknown_thread_is_named_in_the_error(archive: Archive):
    threads = comments.ReportThreads.empty("report-test")
    open_one(threads, comments.GEOFFREY)
    with pytest.raises(comments.CommentError, match="t9"):
        threads.require("t9")


def test_the_digest_says_what_is_pending(archive: Archive):
    threads = comments.ReportThreads.empty("report-test")
    open_one(threads, comments.GEOFFREY)
    text = comments.digest(threads, include_resolved=False)
    assert "attend Claude" in text
    assert "1 ouvert(s), dont 1 en attente de Claude" in text
