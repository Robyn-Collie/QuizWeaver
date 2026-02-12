#!/usr/bin/env bash
# ============================================================
#  QuizWeaver Launcher for macOS / Linux
#  Run: chmod +x run.sh && ./run.sh
# ============================================================

set -e

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
    PYTHON="python"
else
    echo "  [FAIL] Python is not installed."
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

echo ""
echo "  Starting QuizWeaver..."
echo "  Your browser will open automatically."
echo ""
echo "  To stop the server, press Ctrl+C."
echo "  ============================================"
echo ""

# --- Open browser after a short delay ---
(sleep 2 && {
    if command -v xdg-open &>/dev/null; then
        xdg-open "http://localhost:5000" 2>/dev/null
    elif command -v open &>/dev/null; then
        open "http://localhost:5000"
    fi
}) &

# --- Start the app ---
python -c "
import yaml
with open('config.yaml') as f:
    config = yaml.safe_load(f)
from src.web.app import create_app
app = create_app(config)
app.run(host='127.0.0.1', port=5000)
"
