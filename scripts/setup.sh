#!/usr/bin/env bash
# OSINTINEL — one-command local setup (macOS / Linux, bash or zsh).
#
# Creates an isolated virtualenv, installs the package, and runs the preflight `doctor`. Safe to
# re-run. It never touches your system Python: everything lands in ./.venv.
#
#   ./scripts/setup.sh            # venv + install + doctor
#   ./scripts/setup.sh --tui      # …also install the terminal UI (Textual)
#   ./scripts/setup.sh --serve    # …and launch the web Investigation Console when done
#
# Why a venv? Homebrew's Python (incl. 3.14) marks itself "externally managed" (PEP 668) and will
# refuse a bare `pip install`. A venv is the clean, supported path.
set -euo pipefail

EXTRAS="dev"            # default install includes pytest so `pytest -q` works out of the box
WANT_SERVE=0
for arg in "$@"; do
  case "$arg" in
    --tui)   EXTRAS="dev,tui" ;;
    --serve) WANT_SERVE=1 ;;
    -h|--help)
      # print the header comment block (skip the shebang), stop at the first non-comment line
      awk 'NR==1{next} /^#/{sub(/^# ?/,""); print; next} {exit}' "$0"; exit 0 ;;
    *) echo "unknown option: $arg (try --help)"; exit 2 ;;
  esac
done

# Resolve the repo root (this script lives in scripts/) and work from there.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Pick a Python: prefer the newest of python3.13 / python3.12 / python3 actually present.
PYBIN=""
for cand in python3.13 python3.12 python3 python3.14; do
  if command -v "$cand" >/dev/null 2>&1; then PYBIN="$cand"; break; fi
done
if [ -z "$PYBIN" ]; then
  echo "No python3 found. Install Python 3.11+ (e.g. 'brew install python') and re-run." >&2
  exit 1
fi
echo "==> Using $($PYBIN --version) at $(command -v "$PYBIN")"

# Create the venv if missing.
if [ ! -d ".venv" ]; then
  echo "==> Creating virtualenv at ./.venv"
  "$PYBIN" -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

echo "==> Upgrading pip"
python -m pip install --quiet --upgrade pip

echo "==> Installing OSINTINEL (extras: ${EXTRAS})"
if ! pip install --quiet -e ".[${EXTRAS}]"; then
  echo "" >&2
  echo "Install failed. If a dependency had no wheel for your Python version, create the venv" >&2
  echo "with a slightly older interpreter, e.g.:  python3.13 -m venv .venv  (then re-run)." >&2
  exit 1
fi

echo "==> Preflight"
osintinel doctor || true   # doctor's warnings (e.g. Ollama not running) shouldn't abort setup

cat <<EOF

OSINTINEL is installed in ./.venv. Activate it in new shells with:
    source .venv/bin/activate

Then:
    osintinel serve          # web Investigation Console → http://127.0.0.1:8765
    osintinel tui            # terminal UI (needs --tui above)
    pytest -q                # run the test suite

Local, private models (optional): start Ollama, then pick the 'ollama' profile in the UI:
    ollama serve & ollama pull qwen2.5:3b-instruct nomic-embed-text
EOF

if [ "$WANT_SERVE" -eq 1 ]; then
  echo "==> Launching the web app (Ctrl+C to stop)"
  exec osintinel serve
fi
