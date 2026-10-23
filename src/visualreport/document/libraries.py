"""The CDN libraries a page pulls — exactly the ones its content needs.

Versions are pinned exactly and each script carries its SHA-384 integrity: a
range would let a page silently change behavior between two renders of the same
source, and a republished file would run unnoticed. Every URL names a file of
the npm package itself, never one jsDelivr minifies on demand, whose bytes (and
so whose integrity) it does not guarantee. Refresh the integrity from the exact
new bundle when changing a version:
`curl -sL URL | openssl dgst -sha384 -binary | base64`.
"""

from __future__ import annotations

from dataclasses import dataclass

from .assets import PageAssets


@dataclass(frozen=True)
class Library:
    url: str
    integrity: str

    def tag(self, defer: bool) -> str:
        loading = " defer" if defer else ""
        return (
            f'<script{loading} src="{self.url}" integrity="{self.integrity}" '
            f'crossorigin="anonymous"></script>'
        )


MATHJAX = Library(
    "https://cdn.jsdelivr.net/npm/mathjax@3.2.2/es5/tex-mml-chtml.js",
    "sha384-Wuix6BuhrWbjDBs24bXrjf4ZQ5aFeFWBuKkFekO2t8xFU0iNaLQfp2K6/1Nxveei",
)
CHARTJS = Library(
    "https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.js",
    "sha384-dug+JxfBvklEQdJ4AYuBBAIScUz0bVN73xpy273gcAwHjb3qI0fXmuYNaNfdyYJG",
)
# 10.9.1, the earlier pin, carries known advisories.
MERMAID = Library(
    "https://cdn.jsdelivr.net/npm/mermaid@12.2.0/dist/mermaid.min.js",
    "sha384-8xUhuLNMjW/cI2Dacg3DR4WliYznvIg0LVG1stctThKD/YVrJFI9TNCFxft5NYgp",
)

# MathJax typesets only what the converter marked as math (`arithmatex` spans,
# whose `$…$` became `\(…\)`; `document/math.py` keeps prices out of them), and
# its `safe` extension filters the URLs and styles a formula could carry.
MATHJAX_CONFIG = """<script>
window.MathJax = {
  loader: { load: ['ui/safe'] },
  tex: { inlineMath: [['\\\\(','\\\\)']], displayMath: [['\\\\[','\\\\]']] },
  options: { ignoreHtmlClass: '.*', processHtmlClass: 'arithmatex' }
};
</script>"""


def head_libraries(content: str, assets: PageAssets) -> str:
    tags = []
    if 'class="arithmatex"' in content:
        tags.append(f"{MATHJAX_CONFIG}\n{MATHJAX.tag(defer=True)}")
    if assets.charts:
        tags.append(CHARTJS.tag(defer=False))
    if assets.has_mermaid:
        tags.append(MERMAID.tag(defer=False))
    return "\n".join(tags)
