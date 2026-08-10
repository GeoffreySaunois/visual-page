"""The lifecycle shared by the engine's background processes.

Two processes make an archive reachable: the local server, and the tunnel that
publishes it. Both live the same way — a `Popen` detached from the current
session, a state file next to the archive that finds them again on the next
command, a log file they append to, an HTTP probe that says when they are
actually usable, and a SIGTERM to end them. A state file whose process is gone
means "stopped": it is ignored on reads and replaced on the next start.

What stays in the domain modules is what differs: the command line, the shape of
the recorded state, and the probe.
"""

from __future__ import annotations

import contextlib
import json
import os
import signal
import subprocess
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

POLL_INTERVAL_S = 0.15


class LaunchError(Exception):
    """A background process could not be started or reached — its label says which."""


@dataclass(frozen=True)
class DetachedProcess:
    """One background process, identified by the files that outlive its command.

    `label` is the noun used in the French messages the user reads ("le serveur",
    "le tunnel"), `timeout_s` the deadline `await_ready` gives it to answer.
    """

    state_path: Path
    log_path: Path
    label: str
    timeout_s: float

    def recorded(self) -> dict | None:
        """The recorded state, or None when the file is missing, unreadable, or
        describes a process that no longer runs."""
        if not self.state_path.exists():
            return None
        try:
            state = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        if not isinstance(state, dict) or not isinstance(state.get("pid"), int):
            return None
        return state if alive(state["pid"]) else None

    def launch(self, command: Sequence[str], **details: object) -> dict:
        """Spawn the command outside the current session and record its state.

        `details` are the domain's own fields (a port, a hostname); `pid` and
        `started_at` are always part of the state.
        """
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_path, "a") as log:
            process = subprocess.Popen(
                list(command),
                stdout=log,
                stderr=log,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            )
        state = {
            "pid": process.pid,
            "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            **details,
        }
        self.record(state)
        return state

    def record(self, state: Mapping[str, object]) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(dict(state)), encoding="utf-8")

    def await_ready(self, pid: int, probe: Callable[[], bool]) -> None:
        """Poll until the process answers its probe, and fail loudly otherwise —
        a process that died on start-up is a different message than one still
        starting when the deadline passes, and both point at the log."""
        deadline = time.monotonic() + self.timeout_s
        while time.monotonic() < deadline:
            if probe():
                return
            if not alive(pid):
                raise LaunchError(f"{self.label} s'est arrêté au démarrage — voir {self.log_path}")
            time.sleep(POLL_INTERVAL_S)
        raise LaunchError(
            f"{self.label} n'a pas répondu en {self.timeout_s:.0f}s — voir {self.log_path}"
        )

    def halt(self) -> None:
        """Terminate the recorded process and forget it. Doing it on a state file
        with nothing behind it is a no-op, not an error."""
        state = self.recorded()
        self.state_path.unlink(missing_ok=True)
        if state is None:
            return
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.kill(state["pid"], signal.SIGTERM)


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True
