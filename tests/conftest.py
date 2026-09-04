from __future__ import annotations

from pathlib import Path

import pytest

from visualreport.paths import Archive

SOURCE = """---
title: Une page de test
eyebrow: Test
subtitle: Sous-titre
slug: page-test
lang: fr
folder: swaap/gym
---

## Contexte

Le coût marginal par idée est de 3,20 € sur la dernière série.

## Méthode

Chaque run est évalué sur trois métriques.
"""


@pytest.fixture
def archive(tmp_path: Path) -> Archive:
    return Archive(root=tmp_path / "html-reports")


@pytest.fixture
def source(tmp_path: Path) -> Path:
    path = tmp_path / "page.md"
    path.write_text(SOURCE, encoding="utf-8")
    return path
