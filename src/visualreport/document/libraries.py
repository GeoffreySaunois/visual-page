"""The CDN libraries a page pulls — exactly the ones its content needs.

Versions are pinned exactly: a range would let a page silently change behavior
between two renders of the same source.
"""

from __future__ import annotations

from .assets import PageAssets

MATHJAX = "https://cdn.jsdelivr.net/npm/mathjax@3.2.2/es5/tex-mml-chtml.js"
CHARTJS = "https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"
MERMAID = "https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.min.js"

# `$` is never a delimiter: it collides with the literal dollar amounts a cost or
# benchmark report is full of, and MathJax would render the prose between two of
# them as italic math garbage.
MATHJAX_CONFIG = """<script>
window.MathJax = {
  tex: { inlineMath: [['\\\\(','\\\\)']], displayMath: [['\\\\[','\\\\]']] },
  options: { ignoreHtmlClass: '.*', processHtmlClass: 'arithmatex' }
};
</script>"""


def head_libraries(content: str, assets: PageAssets) -> str:
    tags = []
    if 'class="arithmatex"' in content:
        tags.append(f'{MATHJAX_CONFIG}\n<script defer src="{MATHJAX}"></script>')
    if assets.charts:
        tags.append(f'<script src="{CHARTJS}"></script>')
    if assets.has_mermaid:
        tags.append(f'<script src="{MERMAID}"></script>')
    return "\n".join(tags)
