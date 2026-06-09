"""OSINTINEL mascot + splash animation — pure, dependency-free frame generation.

The TUI shows this on launch (à la oterm's llama): the wordmark, an all-seeing **sentinel eye**
whose pupil scans, and a KITT-style radar beam sweeping while modules warm up. Kept free of any
Textual/Rich import so the frames are unit-testable and the art lives in one place.
"""

from __future__ import annotations

# OSINTINEL wordmark — assembled from a clean 5-row block alphabet with a 2-space gutter so it
# reads crisply at any size (every glyph's rows are padded to equal width before joining).
_GLYPHS: dict[str, list[str]] = {
    "O": [" ██████ ", "██    ██", "██    ██", "██    ██", " ██████ "],
    "S": ["███████", "██     ", "███████", "     ██", "███████"],
    "I": ["██████", "  ██  ", "  ██  ", "  ██  ", "██████"],
    "N": ["██   ██", "███  ██", "██ █ ██", "██  ███", "██   ██"],
    "T": ["███████", "   ██  ", "   ██  ", "   ██  ", "   ██  "],
    "E": ["███████", "██     ", "█████  ", "██     ", "███████"],
    "L": ["██    ", "██    ", "██    ", "██    ", "██████"],
}


def _assemble(text: str, gutter: int = 2) -> list[str]:
    glyphs = [[r.ljust(max(len(r) for r in _GLYPHS[c])) for r in _GLYPHS[c]] for c in text]
    gap = " " * gutter
    return [gap.join(g[row] for g in glyphs) for row in range(5)]


WORDMARK: list[str] = _assemble("OSINTINEL")

TAGLINE = "· Open-Source Intelligence Sentinel ·"

_PUPILS = ["●··", "·●·", "··●", "·●·"]
_STATUSES = [
    "initializing ledger",
    "loading adapters",
    "warming inference tiers",
    "calibrating skeptic",
    "all systems nominal",
]
_TRACK = 17


def _eye(pupil: str) -> list[str]:
    """The sentinel eye; ``pupil`` is a 3-cell field that scans left→right."""
    return [
        r'      .-"""-.      ',
        r"    .'  ___  '.    ",
        rf"   /   ({pupil})   \   ",
        r"   '.   ‾‾‾   .'   ",
        r"     '-.....-'     ",
    ]


def _beam(pos: int, length: int = _TRACK) -> str:
    """A radar sweep: a bright head with a fading tail across a fixed track."""
    cells = []
    for i in range(length):
        d = abs(i - pos)
        cells.append("█" if d == 0 else "▓" if d == 1 else "▒" if d == 2 else "░" if d == 3 else "·")
    return "⟦" + "".join(cells) + "⟧"


def _compose(pupil: str, pos: int, status: str) -> str:
    width = max(len(line) for line in WORDMARK)
    lines = list(WORDMARK)
    lines += ["", TAGLINE.center(width), ""]
    lines += [row.center(width) for row in _eye(pupil)]
    lines += ["", f"{_beam(pos)}  {status}…".center(width)]
    return "\n".join(lines)


def splash_frames() -> list[str]:
    """The full launch animation as a list of multi-line frames (cycle them on a timer)."""
    sweep = list(range(_TRACK)) + list(range(_TRACK - 2, 0, -1))  # bounce
    n = max(len(sweep), 24)
    frames = []
    for i in range(n):
        pupil = _PUPILS[i % len(_PUPILS)]
        pos = sweep[i % len(sweep)]
        status = _STATUSES[min(i * len(_STATUSES) // n, len(_STATUSES) - 1)]
        frames.append(_compose(pupil, pos, status))
    return frames


def banner() -> str:
    """A single static frame (wordmark + eye + tagline), e.g. for a header or `--version`."""
    return _compose(_PUPILS[1], _TRACK // 2, _STATUSES[-1])
