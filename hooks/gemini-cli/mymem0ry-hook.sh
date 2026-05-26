#!/usr/bin/env bash
# Gemini CLI lifecycle hook.
# Logs events to session memory via CLI.
set -euo pipefail

CWD="$(pwd)"
EVENT="${1:-}"
SESSION_ID="${MYMEM0RY_SESSION_ID:-$(date +%s | md5sum | head -c 8)}"

CONTENT=""
if [ ! -t 0 ]; then
    CONTENT="$(cat)"
fi

if [ -n "$CONTENT" ]; then
    printf '%s' "$CONTENT" | mymem0ry log --cwd "$CWD" --session "$SESSION_ID" --role user 2>/dev/null || true
fi
