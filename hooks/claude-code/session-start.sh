#!/usr/bin/env bash
# Hook for Claude Code — Session Start.
#fires on session start to load context from myMem0ry.
set -euo pipefail

MYMEM0RY_URL="${MYMEM0RY_URL:-http://127.0.0.1:49374}"
CWD="$(pwd)"
SESSION_ID="$(date +%s | md5sum | head -c 8)"

curl -sf -X POST "${MYMEM0RY_URL}/hook" \
    -H "Content-Type: application/json" \
    -d "{\"event\": \"SessionStart\", \"cwd\": \"${CWD}\", \"session_id\": \"${SESSION_ID}\"}" \
    --max-time 1 2>/dev/null || true

echo "myMem0ry session: ${SESSION_ID}"
