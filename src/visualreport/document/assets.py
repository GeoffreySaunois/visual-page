"""What the fences collect while converting, and which libraries that implies."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PageAssets:
    """Artifacts gathered during conversion, so the page ships CDN tags for
    exactly the libraries it uses and nothing else."""

    charts: list[dict] = field(default_factory=list)
    has_mermaid: bool = False

    def add_chart(self, spec: dict) -> str:
        self.charts.append(spec)
        return f"vr-chart-{len(self.charts)}"
