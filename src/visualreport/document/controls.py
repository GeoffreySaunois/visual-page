"""The reader toolbar at the right end of the page's top bar.

The iteration-diff toggle when there is a diff to review, the comment panel, the
PDF export and the appearance menu — icon buttons whose label is their tooltip.
Each control's behavior lives in the page scripts (the comment toggle in
comments.js); this only decides which ones the page carries.
"""

from __future__ import annotations


def toolbar(has_iteration: bool) -> str:
    controls = []
    if has_iteration:
        controls.append(
            icon_button(
                "diff-toggle",
                "file-diff",
                "Changements de cette version",
                'aria-pressed="true"',
                badge="",
            )
        )
    controls.append(
        icon_button(
            "comments-toggle",
            "message-square",
            "Commentaires",
            'aria-pressed="false" aria-controls="vr-panel" data-tooltip-shortcut="C"',
            badge='<span id="comments-count" class="panel-badge" hidden></span>',
        )
    )
    # Every page prints, served or opened by double-click: the export is the
    # browser's own print dialog over the page's print stylesheet, so it needs
    # neither the server nor anything installed.
    controls.append(
        icon_button(
            "pdf-export",
            "download",
            "Exporter en PDF",
            'data-tooltip="Exporter en PDF"',
            badge="",
        )
    )
    controls.append(
        icon_button(
            "appearance-toggle",
            "monitor",
            "Apparence",
            'aria-haspopup="dialog" aria-expanded="false" aria-controls="appearance-menu"',
            badge="",
        )
    )
    return "\n      ".join(controls)


def icon_button(
    element_id: str, icon: str, label: str, attributes: str, badge: str
) -> str:
    return (
        f'<button type="button" class="icon-button" id="{element_id}" aria-label="{label}" {attributes}>'
        f'<svg class="icon" aria-hidden="true"><use href="#vr-i-{icon}"></use></svg>{badge}</button>'
    )
