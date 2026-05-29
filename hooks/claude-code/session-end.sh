#!/usr/bin/env bash
# Claude Code SessionEnd hook.
#
# "Hook cancelled" is NOT a timeout — SessionEnd does not block Claude Code's
# shutdown, so anything still running (a foreground curl, a backgrounded curl that
# hasn't sent yet) gets killed when the process tree unwinds. And on Windows the
# myMem0ry server itself lived inside Claude Code's Job Object, so it was dying at
# the same instant — the POST had nowhere to land.
#
# So we DON'T POST here. We drop the event as a JSON file in the spool dir using
# bash built-ins only (zero subprocess spawns → ~0.2s, finishes before any kill).
# The server drains the spool on startup and on a timer, so capture no longer
# depends on winning the shutdown race or on the server being alive right now.
set -euo pipefail

# Read all of stdin with a builtin (read -d '') instead of $(cat) — one less
# subprocess spawn, so the only process cost is bash startup itself.
PAYLOAD=""
IFS= read -r -d '' PAYLOAD || true

# Extract a JSON string field with bash's built-in regex — no subprocess spawned.
# [^"]* passes backslashes through; the values we read (session id, cwd, transcript
# path) never contain embedded quotes.
_jstr() {
  local re="\"$2\"[[:space:]]*:[[:space:]]*\"([^\"]*)\""
  [[ "$1" =~ $re ]] && printf '%s' "${BASH_REMATCH[1]}"
}

SESSION_ID="$(_jstr "$PAYLOAD" session_id || true)"
CWD="$(_jstr "$PAYLOAD" cwd || true)"
TRANSCRIPT="$(_jstr "$PAYLOAD" transcript_path || true)"

[[ -z "${SESSION_ID:-}" ]] && SESSION_ID="${MYMEM0RY_SESSION_ID:-unknown}"
[[ -z "${CWD:-}" ]] && CWD="$(pwd 2>/dev/null || echo '.')"

# Resolve the spool dir the server agreed on. Order: explicit env → runtime file the
# server writes (authoritative, raw path on line 1) → derive from DB_PATH like
# MemoryConfig does → home fallback. Use USERPROFILE not HOME: git-bash's $HOME often
# differs from Python's Path.home() on Windows.
_HOME_DIR="${USERPROFILE:-$HOME}"
_HOME_FS="${_HOME_DIR//\\//}"
RUNTIME="${_HOME_FS}/.mymem0ry/runtime"

SPOOL="${MEM0RY_SPOOL_DIR:-}"
if [[ -z "$SPOOL" && -f "$RUNTIME" ]]; then
  IFS= read -r SPOOL < "$RUNTIME" || true
  SPOOL="${SPOOL%$'\r'}"   # strip a stray CR in case the file was written CRLF
fi
if [[ -z "$SPOOL" && -n "${DB_PATH:-}" ]]; then
  _d="${DB_PATH%/}"; _d="${_d%\\}"
  case "$_d" in
    *.db) _d="${_d%[\\/]*}" ;;   # DB_PATH was a file → use its directory
  esac
  SPOOL="${_d}/spool"
fi
[[ -z "$SPOOL" ]] && SPOOL="${_HOME_FS}/.mymem0ry/spool"

# Normalise backslashes to forward slashes for msys filesystem ops.
SPOOL_FS="${SPOOL//\\//}"

# Build the event body. Values came from JSON, so their backslashes are still
# escaped and re-embed verbatim.
if [[ -n "${TRANSCRIPT:-}" ]]; then
    BODY="{\"kind\":\"session-end\",\"session_id\":\"${SESSION_ID}\",\"cwd\":\"${CWD}\",\"agent\":\"claude-code\",\"transcript_path\":\"${TRANSCRIPT}\"}"
else
    BODY="{\"kind\":\"session-end\",\"session_id\":\"${SESSION_ID}\",\"cwd\":\"${CWD}\",\"agent\":\"claude-code\"}"
fi

# mkdir only if missing ([[ -d ]] is a builtin), so the steady-state path spawns
# nothing. Write atomically enough: a single redirect is one fast write() and the
# drainer discards any file it can't parse.
[[ -d "$SPOOL_FS" ]] || mkdir -p "$SPOOL_FS" 2>/dev/null || true
printf '%s' "$BODY" > "${SPOOL_FS}/${SESSION_ID}.json" 2>/dev/null || true

exit 0
