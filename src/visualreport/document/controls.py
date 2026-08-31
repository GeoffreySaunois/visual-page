"""The control strip at the top of the sidebar.

Back to the gallery, the iteration-diff toggle when there is a diff to review,
the comment panel, and the PDF export. Each control's behavior lives in the page
scripts; this only decides which ones the page carries.
"""

from __future__ import annotations


def side_controls(has_iteration: bool) -> str:
    controls = ['<a class="ctrl" href="index.html" title="Retour à la galerie">← Index</a>']
    if has_iteration:
        controls.append(
            '<button class="ctrl" id="diff-toggle" aria-pressed="true">Diff <b>on</b></button>'
        )
    controls.append(
        '<button class="ctrl" id="comments-toggle" aria-pressed="false">'
        'Commentaires <b id="comments-count">0</b></button>'
    )
    # Every page prints, served or opened by double-click: the export is the
    # browser's own print dialog over the page's print stylesheet, so it needs
    # neither the local server nor anything installed.
    controls.append(
        '<button class="ctrl" id="pdf-export" '
        'title="Exporter en PDF — « Enregistrer au format PDF » dans la boîte d\'impression" '
        'aria-label="Exporter en PDF">PDF</button>'
    )
    joined = "\n    ".join(controls)
    return f'<div class="side-controls">\n    {joined}\n  </div>'
