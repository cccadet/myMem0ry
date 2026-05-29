#!/usr/bin/env bash
# Claude Code SessionStart hook.
# 1. Sends session-start observation to myMem0ry server
# 2. Fetches pending handoff and prints to stdout (prepended to first prompt)
#
# Claude Code delivers a JSON payload on stdin (session_id, cwd, transcript_path).
# We use the real session_id so observations from one session group together —
# fabricating a timestamp here breaks auto-handoff on session end.
set -euo pipefail

PAYLOAD="$(cat 2>/dev/null || true)"
SERVER="${MEM0RY_SERVER_URL:-http://127.0.0.1:49374}"

BODY="$(printf '%s' "$PAYLOAD" | python3 -c "
import sys, json, os
try:
    d = json.load(sys.stdin)
except Exception:
    d = {}
sid = d.get('session_id') or os.environ.get('MYMEM0RY_SESSION_ID') or 'unknown'
cwd = d.get('cwd') or os.getcwd()
print(json.dumps({'kind': 'session-start', 'session_id': sid, 'cwd': cwd, 'agent': 'claude-code'}))
" 2>/dev/null || true)"

CWD_ENC="$(printf '%s' "$PAYLOAD" | python3 -c "
import sys, json, os, urllib.parse
try:
    d = json.load(sys.stdin)
except Exception:
    d = {}
print(urllib.parse.quote(d.get('cwd') or os.getcwd(), safe=''))
" 2>/dev/null || true)"

if [[ -n "$BODY" ]]; then
  curl -sf --max-time 0.5 -X POST "${SERVER}/hook" \
    -H "Content-Type: application/json" \
    -d "$BODY" \
    2>/dev/null || true
fi

HANDOFF=$(curl -sf --max-time 1 "${SERVER}/handoff/accept?cwd=${CWD_ENC}&agent=claude-code" 2>/dev/null || echo "")
if [[ -n "$HANDOFF" ]] && [[ "$HANDOFF" != "null" ]]; then
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
