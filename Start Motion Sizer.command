#!/bin/bash
# Double-click this file to start the Motion Axis Sizer.
# First run installs what it needs (a few minutes). After that it starts in seconds.
cd "$(dirname "$0")"
echo "=== Motion Axis Sizer ==="
if ! command -v python3 >/dev/null 2>&1 || ! python3 -c "import venv" >/dev/null 2>&1; then
  echo ""
  echo "Python 3 is not installed yet."
  echo "If a pop-up asks to install 'command line developer tools', click Install,"
  echo "wait for it to finish, then double-click this file again."
  echo "Or install Python from https://www.python.org/downloads/macos/"
  xcode-select --install >/dev/null 2>&1
  read -p "Press Enter to close..."
  exit 1
fi
if [ ! -d ".venv" ]; then
  echo "First run: setting up (this takes a few minutes)..."
  python3 -m venv .venv || { echo "Could not create environment."; read -p "Press Enter..."; exit 1; }
fi
source .venv/bin/activate
python -m pip install -q --upgrade pip
python -m pip install -q -r requirements.txt || { echo "Install failed. Check your internet."; read -p "Press Enter..."; exit 1; }
echo ""
echo "Starting... your browser will open at http://localhost:8501"
echo "Keep this window open while you use the tool. Close it (or press Ctrl+C) to stop."
echo ""
(sleep 4; open "http://localhost:8501") &
python -m streamlit run app.py --server.headless true --browser.gatherUsageStats false
