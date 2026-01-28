#!/usr/bin/env bash
# Reset paper trading data (preserves logs as backups)
set -e

LOGS_DIR="$(dirname "$0")/logs"

# Archive old data
ts=$(date +%Y%m%d_%H%M%S)
for f in trade_history.json paper_trade_history.json paper_options_positions.json; do
    if [ -f "$LOGS_DIR/$f" ]; then
        mv "$LOGS_DIR/$f" "$LOGS_DIR/${f%.json}_$ts.json"
        echo "Archived $f -> ${f%.json}_$ts.json"
    fi
done

# Clear log file
if [ -f "$LOGS_DIR/trading.log" ]; then
    > "$LOGS_DIR/trading.log"
    echo "Cleared trading.log"
fi

# Remove stale lock
rm -f "$LOGS_DIR/bot.lock"

echo "Paper account reset. Go reset in Alpaca dashboard too."
