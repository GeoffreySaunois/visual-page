"""Where a page files: the closed taxonomy of folders the gallery is organized by.

A page names its folder in its front matter (`folder: swaap/gym`); the gallery
groups pages by it. The list is closed on purpose — an author picks the folder
that fits, never invents one, so the gallery keeps a stable shape across
hundreds of pages. Adding a folder is one entry below.

Sections and nested folders can hold pages directly. Each folder names its
parent through its path, so a theme can grow its own subfolders.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Folder:
    """One place a page can be filed, with what belongs there."""

    path: str
    label: str
    hint: str

    @property
    def section(self) -> str:
        return self.path.split("/")[0]

    @property
    def is_section(self) -> bool:
        return "/" not in self.path


TAXONOMY: tuple[Folder, ...] = (
    Folder(
        "swaap",
        "Swaap",
        "le travail au bureau : gym, trading, infra, veille — ou ce qui n'entre dans aucun de ces dossiers",
    ),
    Folder(
        "swaap/gym",
        "Gym",
        "la plateforme gym : projets, runs, thinker, reviewer, dashboard, coûts LLM des runs",
    ),
    Folder(
        "swaap/gym/lab",
        "Gym Lab",
        "vision, architecture, livraison et développement de Gym Lab",
    ),
    Folder(
        "swaap/trading",
        "Trading & prod",
        "searcher, strats HL, arb, rfq, backtester, incidents et digests de prod",
    ),
    Folder(
        "swaap/infra",
        "Infra & outillage",
        "CI, cluster, data platform, accès, quotas des services",
    ),
    Folder(
        "swaap/research",
        "Veille & recherche",
        "modèles, providers, papers, revues de littérature",
    ),
    Folder(
        "personal",
        "Personal",
        "Azul, voyages, organisation, marchés, outillage — ou ce qui n'entre dans aucun de ces dossiers",
    ),
    Folder(
        "personal/azul",
        "Azul",
        "le produit Azul : plans, recaps de PR, UI, QA, démos, pitch",
    ),
    Folder("personal/travel", "Voyages", "roadbooks, logements, activités"),
    Folder("personal/admin", "Organisation", "mails, rappels, démarches"),
    Folder(
        "personal/markets", "Marchés & paris", "Polymarket, analyses quant hors Swaap"
    ),
    Folder(
        "personal/tooling",
        "Outillage",
        "Claude Code, skills, l'archive visuelle, la machine",
    ),
)

# Not a taxonomy entry: nothing can be filed there on purpose, it is only where
# the gallery shelves a page whose folder tag is missing or unknown.
UNFILED = Folder(
    "a-classer", "À classer", "pages rendues avant que la galerie ait des dossiers"
)

BY_PATH: dict[str, Folder] = {folder.path: folder for folder in TAXONOMY}


def folder(path: str) -> Folder | None:
    """The folder at `path`, or nothing when the taxonomy has none there."""
    return BY_PATH.get(path)


def sections() -> list[Folder]:
    return [entry for entry in TAXONOMY if entry.is_section]


def folders_of(section: Folder) -> list[Folder]:
    """The immediate child folders, in taxonomy order."""
    return [
        entry for entry in TAXONOMY if entry.path.rpartition("/")[0] == section.path
    ]


def describe() -> str:
    """The taxonomy as an author reads it in an error message: one line per folder."""
    return "\n".join(f"  {entry.path:<18} {entry.hint}" for entry in TAXONOMY)
