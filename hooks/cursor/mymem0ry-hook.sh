#!/usr/bin/env bash
# Hook for Cursor — lifecycle events.
# Install: configure in Cursor settings as external command hooks.
set -euo pipefail

MYMEM0RY_URL="${MYMEM0RY_URL:-http://127.0.0.1:49374}"
EVENT="${1:-}"
CWD="$(pwd)"

CONTENT=""
if [ ! -t 0 ]; then
    CONTENT="$(cat)"
fi

curl -sf -X POST "${MYMEM0RY_URL}/hook" \
    -H "Content-Type: application/json" \
    -d "{\"event\": \"${EVENT}\", \"cwd\": \"${CWD}\", \"content\": $(printf '%s' "$CONTENT" | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()))')}" \
    --max-time 1 2>/dev/null || true
