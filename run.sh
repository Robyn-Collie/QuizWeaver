#!/usr/bin/env bash
# ============================================================
#  QuizWeaver Launcher for macOS / Linux
#  Run: chmod +x run.sh && ./run.sh
# ============================================================

set -e

# --- Clean shutdown on Ctrl+C ---
cleanup() {
    echo ""
    echo ""
    echo "  QuizWeaver stopped. You can close this terminal."
    echo ""
    exit 0
}
trap cleanup INT TERM

echo ""
echo "  ============================================"
echo "   QuizWeaver - Language-Model-Assisted"
echo "   Teaching Platform"
echo "  ============================================"
echo ""

# --- Change to script directory ---
cd "$(dirname "$0")"

# --- Check Python ---
PYTHON=""
if command -v python3 &>/dev/null; then
    PYTHON="python3"
elif command -v python &>/dev/null; then
    # Guard against macOS system Python 2
    PY_MAJOR_CHECK=$(python -c "import sys; print(sys.version_info.major)" 2>/dev/null || echo "0")
    if [ "$PY_MAJOR_CHECK" -ge 3 ]; then
        PYTHON="python"
    fi
fi

if [ -z "$PYTHON" ]; then
    echo "  [FAIL] Python 3 is not installed."
    echo ""
    echo "  To install Python:"
    echo "    macOS:  brew install python3"
    echo "    Ubuntu: sudo apt install python3 python3-pip python3-venv"
    echo "    Other:  https://www.python.org/downloads/"
    echo ""
    exit 1
fi

PYVER=$($PYTHON --version 2>&1)
echo "  [OK] Found $PYVER"

# --- Check Python version (need 3.9+) ---
PY_MAJOR=$($PYTHON -c "import sys; print(sys.version_info.major)")
PY_MINOR=$($PYTHON -c "import sys; print(sys.version_info.minor)")
if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 9 ]; }; then
    echo "  [FAIL] Python 3.9 or newer is required (found $PYVER)"
    exit 1
fi

# --- Create virtual environment if needed ---
if [ ! -d ".venv" ]; then
    echo "  Creating virtual environment (first run only)..."
    $PYTHON -m venv .venv
    echo "  [OK] Virtual environment created"
fi

# --- Activate virtual environment ---
source .venv/bin/activate
echo "  [OK] Virtual environment active"

# --- Ensure pip is available (macOS venv sometimes omits it) ---
if ! python -m pip --version &>/dev/null; then
    echo "  [NOTE] pip not found in venv. Installing pip..."
    python -m ensurepip --upgrade --default-pip 2>/dev/null || python -m ensurepip 2>/dev/null
    echo "  [OK] pip installed"
fi

# --- Install dependencies if needed ---
if [ ! -f ".deps_installed" ]; then
    echo ""
    echo "  Installing dependencies (first run only, may take a minute)..."
    echo ""
    pip install -r requirements.txt --quiet
    touch .deps_installed
    echo "  [OK] Dependencies installed"
else
    echo "  [OK] Dependencies already installed"
fi

# --- Create config.yaml if missing ---
if [ ! -f "config.yaml" ]; then
    echo "  Creating default config.yaml..."
    cat > config.yaml << 'YAML'
paths:
  database_file: quiz_warehouse.db
llm:
  provider: mock
generation:
  default_grade_level: 7th Grade
YAML
    echo "  [OK] Created config.yaml with safe defaults"
fi

# --- Detect port conflict (macOS AirPlay Receiver uses 5000) ---
PORT=5000
if command -v lsof &>/dev/null && lsof -iTCP:$PORT -sTCP:LISTEN &>/dev/null; then
    echo "  [NOTE] Port $PORT is in use (macOS AirPlay Receiver?)."
    echo "  Using port 5001 instead."
    PORT=5001
elif command -v ss &>/dev/null && ss -tlnp 2>/dev/null | grep -q ":${PORT} "; then
    echo "  [NOTE] Port $PORT is in use."
    echo "  Using port 5001 instead."
    PORT=5001
fi

echo ""
echo "  Starting QuizWeaver..."
echo "  URL: http://localhost:${PORT}"
echo ""
echo "  To stop the server, press Ctrl+C."
echo "  ============================================"
echo ""

# --- Open browser after a short delay ---
(sleep 2 && {
    if command -v xdg-open &>/dev/null; then
        xdg-open "http://localhost:${PORT}" 2>/dev/null
    elif command -v open &>/dev/null; then
        open "http://localhost:${PORT}"
    fi
}) &
BROWSER_PID=$!

# --- Start the app ---
python -c "
import os
# Load .env file if it exists (API keys, overrides)
try:
    from dotenv import load_dotenv
    if os.path.exists('.env'):
        load_dotenv('.env')
except ImportError:
    pass

import yaml
with open('config.yaml') as f:
    config = yaml.safe_load(f)
from src.web.app import create_app
app = create_app(config)
app.run(host='127.0.0.1', port=${PORT})
" || true

# Clean up background browser-open process if still running
kill $BROWSER_PID 2>/dev/null || true
