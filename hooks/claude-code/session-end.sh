#!/usr/bin/env bash
# Hook for Claude Code — Session End.
set -euo pipefail

MYMEM0RY_URL="${MYMEM0RY_URL:-http://127.0.0.1:49374}"
CWD="$(pwd)"
SUMMARY="${1:-Session completed.}"

curl -sf -X POST "${MYMEM0RY_URL}/hook" \
    -H "Content-Type: application/json" \
    -d "{\"event\": \"SessionEnd\", \"cwd\": \"${CWD}\", \"content\": \"${SUMMARY}\"}" \
    --max-time 1 2>/dev/null || true
