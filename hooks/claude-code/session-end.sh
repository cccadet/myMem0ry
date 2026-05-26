#!/usr/bin/env bash
# Claude Code SessionEnd hook.
# Saves session summary to myMem0ry.
set -euo pipefail

CWD="$(pwd)"
SUMMARY="${1:-Session completed.}"
SESSION_ID="${MYMEM0RY_SESSION_ID:-$(date +%s | md5sum | head -c 8)}"

mymem0ry save "Session end" "$SUMMARY" \
    --cwd "$CWD" \
    --session "$SESSION_ID" \
    --scope session \
    --type log \
    2>/dev/null || true
