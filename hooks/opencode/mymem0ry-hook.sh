#!/usr/bin/env bash
# OpenCode lifecycle hook.
# Sends observations to myMem0ry server via HTTP.
set -euo pipefail

CWD="$(pwd)"
EVENT="${1:-other}"
SESSION_ID="${MYMEM0RY_SESSION_ID:-$(date +%s | md5sum | head -c 8)}"
SERVER="${MEM0RY_SERVER_URL:-http://127.0.0.1:49374}"

KIND="other"
case "$EVENT" in
    session-start) KIND="session-start" ;;
    session-end) KIND="session-end" ;;
    user-prompt) KIND="user-prompt" ;;
    PostToolUse) KIND="post-tool-use" ;;
    *) KIND="other" ;;
esac

CONTENT=""
if [ ! -t 0 ]; then
    CONTENT="$(head -c 4096)"
fi

BODY_FIELD=""
if [ -n "$CONTENT" ]; then
    CONTENT_ESCAPED=$(printf '%s' "$CONTENT" | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()))' 2>/dev/null || echo '""')
    BODY_FIELD="\"body\":${CONTENT_ESCAPED},"
fi

curl -sf --max-time 0.2 -X POST "${SERVER}/hook" \
  -H "Content-Type: application/json" \
  -d "{${BODY_FIELD}\"kind\":\"${KIND}\",\"session_id\":\"${SESSION_ID}\",\"cwd\":\"${CWD}\",\"agent\":\"opencode\"}" \
  2>/dev/null || true

if [ "$KIND" = "session-start" ]; then
    HANDOFF=$(curl -sf --max-time 1 "${SERVER}/handoff/accept?cwd=${CWD}&agent=opencode" 2>/dev/null || echo "")
    if [ -n "$HANDOFF" ] && [ "$HANDOFF" != "null" ] && [ "$HANDOFF" != "" ]; then
        echo "📥 myMem0ry: pending handoff"
        echo "$HANDOFF" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(f'From: {d.get(\"from_agent\",\"?\")} @ {d.get(\"created_at\",\"\")[:10]}')
    print(d.get('summary',''))
except Exception:
    pass
" 2>/dev/null || true
    fi
fi
