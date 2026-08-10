"""The shape the page reads — one serialization for the API and for the seeded
copy embedded in an archived file.

Derived facts (open, awaiting) are computed here rather than in JavaScript, so
the browser and the CLI never disagree about the state of a thread.
"""

from __future__ import annotations

from .model import ReportThreads, Thread


def thread_view(thread: Thread) -> dict:
    view = thread.model_dump(mode="json")
    view["is_open"] = thread.is_open
    view["awaiting"] = thread.awaiting
    return view


def report_view(threads: ReportThreads, revision: int) -> dict:
    return {
        "document_id": threads.document_id,
        "revision": revision,
        "threads": [thread_view(thread) for thread in threads.threads],
    }
