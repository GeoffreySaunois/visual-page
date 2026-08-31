"""A page on paper — the HTML the archive holds, printed to PDF.

The page already knows what it looks like on paper: `templates/styles/print.css`
forces the light palette, drops the navigation and the comment layer, and keeps
blocks whole across page breaks. This module only drives a browser over it, so
the CLI's `--pdf`, the page's own PDF button and a plain Cmd-P all produce the
same document from the same stylesheet.

The browser is the only dependency — no PDF engine is vendored, which is also
what keeps a page's charts and Mermaid diagrams looking on paper exactly like
they look on screen. It is never made visible: `--headless` prints without ever
opening a window. A machine with no Chromium-family browser gets an error naming
what to install, never a silently different rendering.
"""

from __future__ import annotations

import os
import signal
import subprocess
import tempfile
import time
from pathlib import Path

# Where a Mac keeps a Chromium-family browser, the most likely one first. Any of
# them speaks `--print-to-pdf` and the flags below, so the first one present wins.
BROWSERS = (
    Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
    Path("/Applications/Chromium.app/Contents/MacOS/Chromium"),
    Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
    Path("/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"),
)

# A page fetches its CDN libraries (Chart.js, Mermaid, MathJax) and lays its
# figures out before it is worth printing. Virtual time lets the browser run
# that clock as fast as it can and print once it is spent, so waiting for a
# chart costs milliseconds rather than the fifteen seconds budgeted here.
LAYOUT_BUDGET_MS = 15_000

# How long a print may take before it is called a failure, and how often the
# file is looked at while it runs.
DEADLINE_S = 90
POLL_S = 0.2

# The trailer that ends every PDF. A file caught mid-write does not carry it,
# which is what makes it a completion signal rather than a guess.
TRAILER = b"%%EOF"


class PrintError(RuntimeError):
    """A page could not be printed — the caller decides how loud that is."""


def export(page: Path, output: Path) -> Path:
    """Print `page` to `output` through a headless browser, and hand back the PDF."""
    engine = browser()
    output.parent.mkdir(parents=True, exist_ok=True)
    # A PDF left by an earlier export would otherwise be read as this one's.
    output.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory(prefix="visual-report-print-") as profile:
        run_browser(print_command(engine, page, output, Path(profile)), output)
    return output


def companion(page: Path) -> Path:
    """Where a page's PDF lands by default: beside it, under the same name."""
    return page.with_suffix(".pdf")


def browser() -> Path:
    for candidate in BROWSERS:
        if candidate.is_file():
            return candidate
    raise PrintError(
        "aucun navigateur Chromium trouvé pour imprimer — installer Google Chrome, "
        "ou utiliser le bouton PDF de la page (impression du navigateur)"
    )


def print_command(engine: Path, page: Path, output: Path, profile: Path) -> list[str]:
    """Headless, on a throwaway profile, with no browser-drawn header or footer —
    the page prints its own title block and the archive names the file.

    The profile is disposable so a print never touches the browser the user has
    open, and never waits on a first-run or default-browser prompt.
    """
    return [
        str(engine),
        "--headless",
        "--disable-gpu",
        "--no-first-run",
        "--no-default-browser-check",
        f"--user-data-dir={profile}",
        "--no-pdf-header-footer",
        f"--virtual-time-budget={LAYOUT_BUDGET_MS}",
        f"--print-to-pdf={output}",
        page.resolve().as_uri(),
    ]


def run_browser(command: list[str], output: Path) -> None:
    """Print, then end the browser.

    Chrome writes the PDF within seconds and then, depending on its version,
    keeps running and ignores a polite signal — Chrome 152 does both. So the
    completion signal read here is the artefact, not the exit code: the file is
    done when it carries its trailer. The browser is then killed by process
    group, which is also what collects the children it spawned; one left behind
    would outlive every export and pile up.
    """
    process = subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    try:
        await_pdf(output, process)
    finally:
        end(process)


def await_pdf(output: Path, process: subprocess.Popen) -> None:
    limit = time.monotonic() + DEADLINE_S
    while time.monotonic() < limit:
        if complete(output):
            return
        if process.poll() is not None:
            raise PrintError(
                f"le navigateur s'est arrêté (code {process.returncode}) sans écrire de PDF"
            )
        time.sleep(POLL_S)
    raise PrintError(f"impression toujours inachevée après {DEADLINE_S} s")


def complete(output: Path) -> bool:
    """Whether the file on disk is a whole PDF — the trailer is written last."""
    if not output.is_file():
        return False
    with output.open("rb") as handle:
        handle.seek(max(0, output.stat().st_size - len(TRAILER) - 8))
        return TRAILER in handle.read()


def end(process: subprocess.Popen) -> None:
    """Terminate the browser's whole process group, then insist."""
    for sign in (signal.SIGTERM, signal.SIGKILL):
        if process.poll() is not None:
            return
        try:
            os.killpg(os.getpgid(process.pid), sign)
        except (ProcessLookupError, PermissionError):
            return
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            continue
