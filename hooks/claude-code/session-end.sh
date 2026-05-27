#!/usr/bin/env bash
# Claude Code SessionEnd hook.
# Sends session-end observation to myMem0ry server (auto-triggers handoff creation).
set -euo pipefail

CWD="$(pwd)"
SESSION_ID="${MYMEM0RY_SESSION_ID:-$(date +%s | md5sum | head -c 8)}"
SERVER="${MEM0RY_SERVER_URL:-http://127.0.0.1:49374}"

curl -sf --max-time 0.2 -X POST "${SERVER}/hook" \
  -H "Content-Type: application/json" \
  -d "{\"kind\":\"session-end\",\"session_id\":\"${SESSION_ID}\",\"cwd\":\"${CWD}\",\"agent\":\"claude-code\"}" \
  2>/dev/null || true
