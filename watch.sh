#!/bin/bash
# Live TUI Dashboard for trading bot

cd "$(dirname "$0")"

source venv/bin/activate 2>/dev/null || {
    echo "Run ./run.sh first to setup venv"
    exit 1
}

export PYTHONPATH="$(pwd):$PYTHONPATH"

# Check for --live flag
if [[ "$1" == "--live" ]]; then
    export TRADING_MODE=live
    echo "⚠️  LIVE TRADING MODE"
    read -p "Type 'YES' to confirm: " confirm
    if [[ "$confirm" != "YES" ]]; then
        echo "Aborted."
        exit 1
    fi
fi

python src/dashboard.py "$@"
