#!/usr/bin/env bash
# Claude Code SessionStart hook.
# 1. Sends session-start observation to myMem0ry server
# 2. Fetches pending handoff and prints to stdout (prepended to first prompt)
set -euo pipefail

CWD="$(pwd)"
SESSION_ID="${MYMEM0RY_SESSION_ID:-$(date +%s | md5sum | head -c 8)}"
SERVER="${MEM0RY_SERVER_URL:-http://127.0.0.1:49374}"

curl -sf --max-time 0.2 -X POST "${SERVER}/hook" \
  -H "Content-Type: application/json" \
  -d "{\"kind\":\"session-start\",\"session_id\":\"${SESSION_ID}\",\"cwd\":\"${CWD}\",\"agent\":\"claude-code\"}" \
  2>/dev/null || true

HANDOFF=$(curl -sf --max-time 1 "${SERVER}/handoff/accept?cwd=${CWD}&agent=claude-code" 2>/dev/null || echo "")
if [ -n "$HANDOFF" ] && [ "$HANDOFF" != "null" ] && [ "$HANDOFF" != "" ]; then
  echo "📥 myMem0ry: pending handoff"
  echo "$HANDOFF" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(f'From: {d.get(\"from_agent\",\"?\")} @ {d.get(\"created_at\",\"\")[:10]}')
    print(d.get('summary',''))
    for q in d.get('open_questions', []):
        print(f'  ? {q}')
    for s in d.get('next_steps', []):
        print(f'  → {s}')
except Exception:
    pass
" 2>/dev/null || true
fi
