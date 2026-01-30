#!/bin/bash
# Run API server locally (no Docker)
set -e
cd "$(dirname "$0")"

# Load env
if [ -f .env ]; then
    set -a; source .env; set +a
fi

export PYTHONPATH="$(pwd)"
echo "Starting API server on http://0.0.0.0:8989"
uvicorn api.server:app --host 0.0.0.0 --port 8989 --reload
