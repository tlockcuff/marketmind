#!/bin/bash
# Run Next.js dev server locally (no Docker)
set -e
cd "$(dirname "$0")/web"

echo "Starting Next.js dev server on http://localhost:5000"
npm run dev
