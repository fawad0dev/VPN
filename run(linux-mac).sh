#!/usr/bin/env bash
# ── VPN Client launcher — Linux / macOS ──────────────────────────────────
set -euo pipefail
cd "$(dirname "$(realpath "$0" 2>/dev/null || readlink -f "$0" 2>/dev/null || echo "$0")")"

# ── Check Python ─────────────────────────────────────────────────────────
PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        VER=$("$cmd" -c "import sys; print(sys.version_info >= (3,10))" 2>/dev/null)
        if [ "$VER" = "True" ]; then
            PYTHON="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo "[ERROR] Python 3.10+ is required but not found."
    if [ "$(uname)" = "Darwin" ]; then
        echo "  Install via Homebrew:  brew install python"
        echo "  Or download from:      https://www.python.org/downloads/"
    else
        echo "  Install via apt:       sudo apt install python3 python3-venv python3-pip"
        echo "  Or download from:      https://www.python.org/downloads/"
    fi
    exit 1
fi

echo "[INFO]  Using Python: $($PYTHON --version)"

# ── Check / create venv ──────────────────────────────────────────────────
if [ ! -f ".venv/bin/python" ]; then
    echo "[SETUP] Creating virtual environment..."
    "$PYTHON" -m venv .venv
fi

# ── Install / upgrade dependencies ───────────────────────────────────────
echo "[SETUP] Checking dependencies..."
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt

# ── Linux: check PyQt6 system deps (xcb etc.) ────────────────────────────
if [ "$(uname)" = "Linux" ]; then
    if ! .venv/bin/python -c "from PyQt6.QtWidgets import QApplication" 2>/dev/null; then
        echo "[WARN]  PyQt6 import failed. You may need system Qt libraries:"
        echo "        sudo apt install libxcb-cursor0 libgl1"
    fi
fi

# ── Launch ───────────────────────────────────────────────────────────────
echo "[INFO]  Starting VPN Client..."
exec .venv/bin/python main.py "$@"
