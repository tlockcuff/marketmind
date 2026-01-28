#!/bin/bash
# Development mode - auto-reload dashboard on code changes

cd "$(dirname "$0")"
source venv/bin/activate 2>/dev/null || { echo "Run ./run.sh first"; exit 1; }

export PYTHONPATH="$(pwd):$PYTHONPATH"

# Check for fswatch (macOS) or inotifywait (Linux)
if command -v fswatch &> /dev/null; then
    WATCHER="fswatch"
elif command -v inotifywait &> /dev/null; then
    WATCHER="inotify"
else
    echo "Install fswatch (brew install fswatch) for hot-reload"
    echo "Running without hot-reload..."
    python src/dashboard.py
    exit
fi

echo "Dashboard with hot-reload enabled"
echo "Edit src/dashboard.py and it will auto-restart"
echo "---"

while true; do
    python src/dashboard.py &
    PID=$!

    if [ "$WATCHER" = "fswatch" ]; then
        fswatch -1 src/dashboard.py > /dev/null 2>&1
    else
        inotifywait -e modify src/dashboard.py > /dev/null 2>&1
    fi

    echo "File changed, reloading..."
    kill $PID 2>/dev/null
    sleep 0.5
done
