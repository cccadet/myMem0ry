#!/usr/bin/env bash
# Claude Code SessionEnd hook.
# Sends session-end observation to myMem0ry server (auto-triggers handoff creation)
# and forwards transcript_path so the server can archive the conversation with
# zero LLM tokens.
#
# Uses the real session_id from the stdin payload so the auto-handoff can gather
# this session's observations — a fabricated id would find none.
set -euo pipefail

PAYLOAD="$(cat 2>/dev/null || true)"
SERVER="${MEM0RY_SERVER_URL:-http://127.0.0.1:49374}"

BODY="$(printf '%s' "$PAYLOAD" | python3 -c "
import sys, json, os
try:
    d = json.load(sys.stdin)
except Exception:
    d = {}
out = {
    'kind': 'session-end',
    'session_id': d.get('session_id') or os.environ.get('MYMEM0RY_SESSION_ID') or 'unknown',
    'cwd': d.get('cwd') or os.getcwd(),
    'agent': 'claude-code',
}
tp = d.get('transcript_path')
if tp:
    out['transcript_path'] = tp
print(json.dumps(out))
" 2>/dev/null || true)"

[[ -z "$BODY" ]] && BODY='{"kind":"session-end","session_id":"unknown","agent":"claude-code"}'

curl -sf --max-time 0.5 -X POST "${SERVER}/hook" \
  -H "Content-Type: application/json" \
  -d "$BODY" \
  2>/dev/null || true
