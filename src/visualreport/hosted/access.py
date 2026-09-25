"""Who may read or discuss a report: owners, then per-report and folder grants.

A folder grant covers every report filed in that folder or any folder nested
under it, including reports published after the grant. A reader's effective
role on a report is the strongest of its report grant and its folder grants.
"""

from dataclasses import dataclass

from .. import folders
from .reports import Role, strongest

FolderGrants = dict[str, dict[str, Role]]


def covers(granted: str, folder: str) -> bool:
    return folder == granted or folder.startswith(granted + "/")


@dataclass(frozen=True)
class Access:
    owners: set[str]
    folder_grants: FolderGrants

    def is_owner(self, email: str) -> bool:
        return email in self.owners

    def folder_role(self, folder: str, email: str) -> Role | None:
        return strongest(
            [
                grants.get(email)
                for granted, grants in self.folder_grants.items()
                if covers(granted, folder)
            ]
        )

    def covered_folders(self, email: str) -> list[str]:
        """Every taxonomy folder a folder grant opens to `email`."""
        granted = [
            path for path, grants in self.folder_grants.items() if email in grants
        ]
        return [
            entry.path
            for entry in folders.TAXONOMY
            if any(covers(path, entry.path) for path in granted)
        ]
