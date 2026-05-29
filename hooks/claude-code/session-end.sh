#!/usr/bin/env bash
# Claude Code SessionEnd hook — must complete fast (< 1s) to avoid "Hook cancelled"
# during Claude Code shutdown. Uses grep/jq instead of python3 to avoid the
# 200-500ms Python startup overhead on Windows.
set -euo pipefail

PAYLOAD="$(cat 2>/dev/null || true)"
SERVER="${MEM0RY_SERVER_URL:-http://127.0.0.1:49374}"

# Extract a JSON string field via grep — works for values without embedded quotes.
# Handles backslash sequences (Windows paths) since [^"]* passes through backslashes.
_jstr() { printf '%s' "$1" | grep -o "\"$2\":[[:space:]]*\"[^\"]*\"" 2>/dev/null | sed 's/.*":[[:space:]]*"\(.*\)"/\1/' | head -1; }

if command -v jq &>/dev/null && [[ -n "$PAYLOAD" ]]; then
    SESSION_ID="$(printf '%s' "$PAYLOAD" | jq -r '.session_id // empty' 2>/dev/null || true)"
    CWD="$(printf '%s' "$PAYLOAD" | jq -r '.cwd // empty' 2>/dev/null || true)"
    TRANSCRIPT="$(printf '%s' "$PAYLOAD" | jq -r '.transcript_path // empty' 2>/dev/null || true)"
else
    SESSION_ID="$(_jstr "$PAYLOAD" "session_id" || true)"
    CWD="$(_jstr "$PAYLOAD" "cwd" || true)"
    TRANSCRIPT="$(_jstr "$PAYLOAD" "transcript_path" || true)"
fi

[[ -z "${SESSION_ID:-}" ]] && SESSION_ID="${MYMEM0RY_SESSION_ID:-unknown}"
[[ -z "${CWD:-}" ]] && CWD="$(pwd 2>/dev/null || echo '.')"

# Build JSON body — use jq for correct escaping, else construct directly (values
# already come from JSON so backslashes are already JSON-escaped).
if command -v jq &>/dev/null; then
    if [[ -n "${TRANSCRIPT:-}" ]]; then
        BODY="$(jq -nc --arg s "$SESSION_ID" --arg c "$CWD" --arg t "$TRANSCRIPT" \
            '{kind:"session-end",session_id:$s,cwd:$c,agent:"claude-code",transcript_path:$t}')"
    else
        BODY="$(jq -nc --arg s "$SESSION_ID" --arg c "$CWD" \
            '{kind:"session-end",session_id:$s,cwd:$c,agent:"claude-code"}')"
    fi
elif [[ -n "${TRANSCRIPT:-}" ]]; then
    BODY="{\"kind\":\"session-end\",\"session_id\":\"${SESSION_ID}\",\"cwd\":\"${CWD}\",\"agent\":\"claude-code\",\"transcript_path\":\"${TRANSCRIPT}\"}"
else
    BODY="{\"kind\":\"session-end\",\"session_id\":\"${SESSION_ID}\",\"cwd\":\"${CWD}\",\"agent\":\"claude-code\"}"
fi

# Server returns 202 immediately (async), so 0.3s is ample for localhost.
curl -sf --max-time 0.3 -X POST "${SERVER}/hook" \
  -H "Content-Type: application/json" \
  -d "$BODY" \
  2>/dev/null || true
