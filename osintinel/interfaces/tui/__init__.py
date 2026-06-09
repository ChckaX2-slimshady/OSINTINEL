"""Terminal UI (Textual) — the terminal-native front door (`osintinel tui`).

A launch splash with the animated sentinel mascot, then a full investigation console with
per-tier model control. Textual is an optional dependency; importing :func:`run_tui` pulls it in.
The pure logic/art (``logic``, ``mascot``) import no Textual and are unit-tested directly.
"""

from __future__ import annotations


def run_tui() -> None:
    """Launch the TUI (imports Textual lazily so the core stays stdlib-only)."""
    from .app import run_tui as _run

    _run()


__all__ = ["run_tui"]
