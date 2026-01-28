#!/bin/bash
set -e

cd "$(dirname "$0")"

# Create logs dir if needed
mkdir -p logs

# Check for .env
if [ ! -f .env ]; then
    echo "Error: .env file not found. Copy .env.example and fill in API keys."
    exit 1
fi

# Check for venv
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate

# Install deps if needed
if ! python -c "import ta" 2>/dev/null; then
    echo "Installing dependencies..."
    pip install -r requirements.txt
fi

# Run with unbuffered output for realtime logs
export PYTHONUNBUFFERED=1
export PYTHONPATH="$(pwd):$PYTHONPATH"

echo "Starting trading bot..."
echo "Logs: logs/trading.log"
echo "Press Ctrl+C to stop"
echo "---"

python -u src/main.py "$@"
