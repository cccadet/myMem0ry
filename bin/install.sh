#!/usr/bin/env bash
# bin/install.sh — Add mymem0ry MCP server to your AI agent.
#
# Usage:
#   bin/install.sh                  # auto-detect agent
#   bin/install.sh claude           # Claude Code
#   bin/install.sh opencode         # OpenCode
#   bin/install.sh codex            # Codex CLI
#   bin/install.sh code             # VS Code
#   bin/install.sh cursor           # Cursor
#
# Set MYMEM0RY_SOURCE to override the package source:
#   MYMEM0RY_SOURCE="git+https://github.com/cccadet/myMem0ry" bin/install.sh
#
# For TestPyPI:
#   MYMEM0RY_SOURCE="--index-url https://test.pypi.org/simple/ mymem0ry" bin/install.sh

set -euo pipefail

SOURCE="${MYMEM0RY_SOURCE:-mymem0ry}"
_PKG_NAME="mymem0ry"

detect_agent() {
    if command -v claude &>/dev/null && claude mcp list &>/dev/null 2>&1; then
        echo "claude"
    elif command -v opencode &>/dev/null; then
        echo "opencode"
    elif command -v codex &>/dev/null; then
        echo "codex"
    elif command -v cursor &>/dev/null; then
        echo "cursor"
    elif command -v code &>/dev/null; then
        echo "code"
    else
        echo ""
    fi
}

install_claude() {
    echo "Installing mymem0ry for Claude Code..."
    if [[ "$SOURCE" == "$_PKG_NAME" ]]; then
        claude mcp add --scope user "$_PKG_NAME" -- mymem0ry-mcp
    else
        local repo_path
        repo_path="$(cd "$(dirname "$0")/.." && pwd)"
        claude mcp add --scope user "$_PKG_NAME" -- uv run --directory "$repo_path" mymem0ry-mcp
    fi
    echo "Done. Run 'claude mcp list' to verify."
}

install_opencode() {
    echo "Installing mymem0ry for OpenCode..."
    echo ""
    echo "Add this to your opencode.json:"
    if [[ "$SOURCE" == "$_PKG_NAME" ]]; then
        echo '  "mcpServers": {'
        echo '    "mymem0ry": {'
        echo '      "command": "mymem0ry-mcp"'
        echo '    }'
        echo '  }'
    else
        local repo_path
        repo_path="$(cd "$(dirname "$0")/.." && pwd)"
        echo '  "mcpServers": {'
        echo '    "mymem0ry": {'
        echo '      "command": "uv",'
        echo "      \"args\": [\"run\", \"--directory\", \"$repo_path\", \"mymem0ry-mcp\"]"
        echo '    }'
        echo '  }'
    fi
}

install_codex() {
    echo "Installing mymem0ry for Codex CLI..."
    if [[ "$SOURCE" == "$_PKG_NAME" ]]; then
        codex mcp add "$_PKG_NAME" -- mymem0ry-mcp
    else
        local repo_path
        repo_path="$(cd "$(dirname "$0")/.." && pwd)"
        codex mcp add "$_PKG_NAME" -- uv run --directory "$repo_path" mymem0ry-mcp
    fi
    echo "Done. Run 'codex mcp list' to verify."
}

install_code() {
    echo "Installing mymem0ry for VS Code..."
    if [[ "$SOURCE" == "$_PKG_NAME" ]]; then
        code --add-mcp '{"name":"mymem0ry","command":"mymem0ry-mcp"}'
    else
        local repo_path
        repo_path="$(cd "$(dirname "$0")/.." && pwd)"
        code --add-mcp "{\"name\":\"mymem0ry\",\"command\":\"uv\",\"args\":[\"run\",\"--directory\",\"$repo_path\",\"mymem0ry-mcp\"]}"
    fi
    echo "Done."
}

install_cursor() {
    echo "Installing mymem0ry for Cursor..."
    if [[ "$SOURCE" == "$_PKG_NAME" ]]; then
        cursor --add-mcp '{"name":"mymem0ry","command":"mymem0ry-mcp"}'
    else
        local repo_path
        repo_path="$(cd "$(dirname "$0")/.." && pwd)"
        cursor --add-mcp "{\"name\":\"mymem0ry\",\"command\":\"uv\",\"args\":[\"run\",\"--directory\",\"$repo_path\",\"mymem0ry-mcp\"]}"
    fi
    echo "Done."
}

AGENT="${1:-}"

if [[ -z "$AGENT" ]]; then
    AGENT="$(detect_agent)"
    if [[ -z "$AGENT" ]]; then
        echo "Could not auto-detect agent. Usage: bin/install.sh <claude|opencode|codex|code|cursor>"
        exit 1
    fi
    echo "Auto-detected: $AGENT"
fi

case "$AGENT" in
    claude)   install_claude   ;;
    opencode) install_opencode ;;
    codex)    install_codex    ;;
    code)     install_code     ;;
    cursor)   install_cursor   ;;
    *)
        echo "Unknown agent: $AGENT"
        echo "Supported: claude, opencode, codex, code, cursor"
        exit 1
        ;;
esac
