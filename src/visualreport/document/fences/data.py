"""The YAML-driven fences: ```kpi, ```filetree, ```transcript."""

from __future__ import annotations

import html

import yaml

from ..frontmatter import SourceError

FILETREE_FLAGS = {"added": "A", "modified": "M", "removed": "D", "renamed": "R"}
TRANSCRIPT_ROLES = ("system", "user", "assistant", "tool", "tool-error")


def yaml_items(source: str, fence: str, shape: str) -> list:
    items = yaml.safe_load(source)
    if not isinstance(items, list):
        raise SourceError(f"```{fence} block must contain a YAML list of {shape}")
    return items


def format_kpi(source, language, css_class, options, md, **kwargs) -> str:
    cards = []
    for item in yaml_items(source, "kpi", "{value, label, note?}"):
        note = item.get("note", "")
        cards.append(
            '<div class="kpi">'
            f'<div class="kpi-value">{html.escape(str(item["value"]))}</div>'
            f'<div class="kpi-label">{html.escape(str(item["label"]))}</div>'
            + (f'<div class="kpi-note">{html.escape(str(note))}</div>' if note else "")
            + "</div>"
        )
    return f'<div class="kpis">{"".join(cards)}</div>'


def format_filetree(source, language, css_class, options, md, **kwargs) -> str:
    rows = []
    for item in yaml_items(source, "filetree", "{path, flag, note?}"):
        if not isinstance(item, dict) or "path" not in item:
            raise SourceError("```filetree items must be mappings with at least {path, flag}")
        flag = str(item.get("flag", ""))
        if flag not in FILETREE_FLAGS:
            raise SourceError(
                f"```filetree flag must be one of: {', '.join(FILETREE_FLAGS)}"
                f" (got {flag!r} for path {item['path']!r})"
            )
        note = item.get("note", "")
        rows.append(
            f'<div class="ft-row ft-{flag}">'
            f'<span class="ft-flag">{FILETREE_FLAGS[flag]}</span>'
            f'<code class="ft-path">{html.escape(str(item["path"]))}</code>'
            + (f'<span class="ft-note">{html.escape(str(note))}</span>' if note else "")
            + "</div>"
        )
    return f'<div class="filetree">{"".join(rows)}</div>'


def format_transcript(source, language, css_class, options, md, **kwargs) -> str:
    blocks = []
    for item in yaml_items(source, "transcript", "{role, label?, content} or {annot} items"):
        if not isinstance(item, dict):
            raise SourceError(
                "```transcript items must be mappings ({role, label?, content} or {annot})"
            )
        blocks.append(transcript_annotation(item) if "annot" in item else transcript_message(item))
    return f'<div class="transcript">{"".join(blocks)}</div>'


def transcript_annotation(item: dict) -> str:
    return (
        '<div class="msg-annot"><span class="marker">▸</span>'
        f"{html.escape(str(item['annot']))}</div>"
    )


def transcript_message(item: dict) -> str:
    role = str(item.get("role", ""))
    if role not in TRANSCRIPT_ROLES:
        raise SourceError(
            f"```transcript role must be one of: {', '.join(TRANSCRIPT_ROLES)} (got {role!r})"
        )
    if "content" not in item:
        raise SourceError(f"```transcript message with role {role!r} is missing its content")
    label = str(item.get("label", role))
    return (
        f'<div class="msg msg-{role}">'
        f'<span class="msg-role">{html.escape(label)}</span>'
        f'<pre class="msg-body">{html.escape(str(item["content"]))}</pre>'
        "</div>"
    )
