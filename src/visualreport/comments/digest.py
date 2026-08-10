"""The threads as the agent reads them: markdown on the terminal.

Each thread carries what is needed to act on it without opening the browser —
the quoted passage, the source block it lives in, the section, and the exchange
so far.
"""

from __future__ import annotations

from .model import AnchorState, AuthorKind, Comment, ReportThreads, Thread

STATE_NOTES = {
    AnchorState.ANCHORED: "ancré",
    AnchorState.DRIFTED: "dérivé — le texte cité a été réécrit depuis",
    AnchorState.ORPHANED: "orphelin — le bloc visé a disparu de la source",
    AnchorState.DOCUMENT: "commentaire de document",
}
AWAITING_LABELS = {AuthorKind.AGENT: "attend Claude", AuthorKind.HUMAN: "attend Geoffrey"}


def digest(threads: ReportThreads, include_resolved: bool) -> str:
    shown = threads.threads if include_resolved else threads.open_threads
    if not shown:
        scope = "commentaire" if include_resolved else "commentaire ouvert"
        return f"aucun {scope} sur {threads.document_id}"
    sections = [header(threads)] + [thread_section(thread) for thread in shown]
    return "\n\n".join(sections)


def header(threads: ReportThreads) -> str:
    waiting = len(threads.awaiting(AuthorKind.AGENT))
    resolved = len(threads.threads) - len(threads.open_threads)
    return (
        f"## Commentaires — {threads.document_id}\n"
        f"{len(threads.open_threads)} ouvert(s), dont {waiting} en attente de Claude · "
        f"{resolved} résolu(s)"
    )


def thread_section(thread: Thread) -> str:
    lines = [f"### {thread.id} — {status_line(thread)}"]
    if thread.anchor is not None:
        lines.append(f"Passage cité : « {thread.anchor.quote} »")
        lines.append(f"Bloc {thread.anchor.block_index} de la source :")
        lines.append(indent(thread.anchor.block_source))
    lines.extend(f"- {exchange_line(comment)}" for comment in thread.comments)
    return "\n".join(lines)


def status_line(thread: Thread) -> str:
    parts = ["ouvert" if thread.is_open else "résolu"]
    if thread.awaiting is not None:
        parts.append(AWAITING_LABELS[thread.awaiting])
    if thread.anchor is not None and thread.anchor.section:
        parts.append(f"§ {thread.anchor.section}")
    parts.append(STATE_NOTES[thread.state])
    return " · ".join(parts)


def exchange_line(comment: Comment) -> str:
    stamp = comment.created_at.astimezone().strftime("%d/%m %H:%M")
    return f"**{comment.author.name}** · {stamp} — {comment.body}"


def indent(text: str) -> str:
    return "\n".join(f"    {line}" for line in text.splitlines())
