#!/usr/bin/env bash
# Hook for Claude Code — fires on lifecycle events.
# Install: cp mymem0ry-hook.sh ~/.claude/hooks/mymem0ry.sh
# Then add to ~/.claude/settings.json hooks array.

set -euo pipefail

MYMEM0RY_URL="${MYMEM0RY_URL:-http://127.0.0.1:49374}"
EVENT="${1:-}"
CWD="$(pwd)"

# Read stdin if available (some hooks pipe content)
CONTENT=""
if [ ! -t 0 ]; then
    CONTENT="$(cat)"
fi

curl -sf -X POST "${MYMEM0RY_URL}/hook" \
    -H "Content-Type: application/json" \
    -d "{\"event\": \"${EVENT}\", \"cwd\": \"${CWD}\", \"content\": $(printf '%s' "$CONTENT" | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()))')}" \
    --max-time 1 2>/dev/null || true
