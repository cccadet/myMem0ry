#!/usr/bin/env bash
# Claude Code generic hook — fires on PreToolUse, PostToolUse, Notification, etc.
# Sends an observation to myMem0ry server via HTTP.
#
# Reads the real session_id from the stdin JSON payload so observations group
# under the same session as session-start/session-end (required for auto-handoff).
set -euo pipefail

PAYLOAD="$(cat 2>/dev/null || true)"
EVENT="${1:-PostToolUse}"
SERVER="${MEM0RY_SERVER_URL:-http://127.0.0.1:49374}"

BODY="$(printf '%s' "$PAYLOAD" | python3 -c "
import sys, json, os
event = sys.argv[1] if len(sys.argv) > 1 else 'PostToolUse'
try:
    d = json.load(sys.stdin)
except Exception:
    d = {}
kind = 'post-tool-use' if event in ('PreToolUse', 'PostToolUse') else 'other'
out = {
    'kind': kind,
    'session_id': d.get('session_id') or os.environ.get('MYMEM0RY_SESSION_ID') or 'unknown',
    'cwd': d.get('cwd') or os.getcwd(),
    'agent': 'claude-code',
    'tool_name': d.get('tool_name', 'unknown'),
    'tool_input': d.get('tool_input') or {},
    'tool_response': d.get('tool_response') or {},
    'body': 'tool-use',
}
print(json.dumps(out))
" "$EVENT" 2>/dev/null || true)"

if [[ -n "$BODY" ]]; then
  curl -sf --max-time 0.2 -X POST "${SERVER}/hook" \
    -H "Content-Type: application/json" \
    -d "$BODY" \
    2>/dev/null || true
fi
