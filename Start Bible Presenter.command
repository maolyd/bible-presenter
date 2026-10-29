#!/bin/bash
# Double-click this file in Finder to start Bible Presenter (macOS).
# It must stay in the bible-presentation-app folder (you can put an alias of it on the Desktop or Dock).
cd "$(dirname "$0")" || exit 1

if [ ! -x .venv/bin/python ]; then
    echo "Bible Presenter is not set up yet in:"
    echo "  $(pwd)"
    echo
    echo "Run these commands once in Terminal, then double-click this file again:"
    echo "  cd \"$(pwd)\""
    echo "  python3.10 -m venv .venv"
    echo "  .venv/bin/pip install -r requirements.txt"
    echo
    read -r -p "Press Return to close this window."
    exit 1
fi

LOG="$HOME/Library/Logs/BiblePresenter.log"
mkdir -p "$(dirname "$LOG")"
echo "Starting Bible Presenter..."
nohup .venv/bin/python main.py > "$LOG" 2>&1 &
PID=$!
disown

# If the program stops within a few seconds, something went wrong: show why.
sleep 6
if ! kill -0 "$PID" 2>/dev/null; then
    echo
    echo "Bible Presenter could not start. The error was:"
    echo "--------------------------------------------------"
    tail -n 25 "$LOG"
    echo "--------------------------------------------------"
    echo "(Full log: $LOG)"
    read -r -p "Press Return to close this window."
    exit 1
fi
echo "Bible Presenter is running. You can close this Terminal window."
