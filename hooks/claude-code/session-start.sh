#!/usr/bin/env bash
# Claude Code SessionStart hook.
# Loads context from myMem0ry and prints to stdout.
# Claude Code prepends session-start stdout to the first prompt.
set -euo pipefail

CWD="$(pwd)"
SESSION_ID="${MYMEM0RY_SESSION_ID:-$(date +%s | md5sum | head -c 8)}"

mymem0ry context --cwd "$CWD" --session "$SESSION_ID" 2>/dev/null || true
