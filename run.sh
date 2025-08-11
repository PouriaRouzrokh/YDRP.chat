#!/usr/bin/env bash
set -euo pipefail

# Root-relative paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$SCRIPT_DIR"
ENGINE_DIR="$ROOT_DIR/ydrp_engine"
UI_DIR="$ROOT_DIR/ydrp_ui"

# Session names
SESSION_MCP="mcp_server"
SESSION_AGENT="agent_server"
SESSION_UI="ui_next"
SESSION_CF="cf_tunnel"
SESSION_CF_API="cf_tunnel_api"

# Configurable ports and envs
MCP_HOST="${MCP_HOST:-0.0.0.0}"
MCP_PORT="${MCP_PORT:-8001}"
API_HOST="${API_HOST:-0.0.0.0}"
API_PORT="${API_PORT:-8000}"
NEXT_PORT="${NEXT_PORT:-3000}"
# Frontend will call backend at this URL
NEXT_PUBLIC_API_URL="${NEXT_PUBLIC_API_URL:-http://localhost:${API_PORT}}"
# Optional public defaults for production via Cloudflare
NEXT_PUBLIC_ADMIN_MODE="${NEXT_PUBLIC_ADMIN_MODE:-false}"
NEXT_PUBLIC_TYPING_INDICATOR_DELAY_MS="${NEXT_PUBLIC_TYPING_INDICATOR_DELAY_MS:-3000}"

# Cloudflare tunnel target (defaults to the UI)
CF_TARGET="${CF_TARGET:-http://localhost:${NEXT_PORT}}"
# Optional: hostname to bind the tunnel to (requires cloudflared login and domain in your CF account)
# Default to ydrp.chat per deployment
CF_HOSTNAME="${CF_HOSTNAME:-ydrp.chat}"
CLOUDFLARED_BIN="${CLOUDFLARED_BIN:-cloudflared}"
# Prefer a named tunnel if provided (recommended for custom domains)
CF_TUNNEL_ID="${CF_TUNNEL_ID:-}"
CF_TUNNEL_NAME="${CF_TUNNEL_NAME:-}"
CF_CONFIG="${CF_CONFIG:-}"
# Secondary hostname for API exposure
CF_API_HOSTNAME="${CF_API_HOSTNAME:-api.ydrp.chat}"
CF_API_TARGET="${CF_API_TARGET:-http://localhost:${API_PORT}}"
# Auto-configure DNS routes for CF_HOSTNAME and CF_API_HOSTNAME when using a named tunnel
CF_AUTOCONFIG_DNS="${CF_AUTOCONFIG_DNS:-true}"

usage() {
  cat <<EOF
Usage: $0 <command> [component]

Commands:
  start-all           Start MCP, Agent, UI, and Cloudflare tunnel (kills existing sessions first)
  start <name>        Start one: mcp | agent | ui | tunnel (kills existing session first)
  kill-all            Kill all managed tmux sessions
  kill <name>         Kill one session: mcp | agent | ui | tunnel
  status              Show tmux session status for managed sessions
  help                Show this help

Environment variables (optional):
  MCP_HOST, MCP_PORT            Default: 0.0.0.0, 8001
  API_HOST, API_PORT            Default: 0.0.0.0, 8000
  NEXT_PORT                     Default: 3000
  NEXT_PUBLIC_API_URL           Default: http://localhost:
  CF_TARGET                     Default: http://localhost:
  CF_HOSTNAME                   Default: ydrp.chat (override to bind tunnel to a different hostname)
  CF_TUNNEL_ID                  If set, runs this named tunnel (uses dashboard routes/public hostnames)
  CF_TUNNEL_NAME                Alternative to CF_TUNNEL_ID; runs by tunnel name
  CF_CONFIG                     Optional path to cloudflared config.yml to use with named tunnel
  CLOUDFLARED_BIN               Default: cloudflared
  CF_API_HOSTNAME               Default: api.ydrp.chat
  CF_API_TARGET                 Default: http://localhost:
  CF_AUTOCONFIG_DNS             Default: true (adds/updates DNS routes for hostnames when using named tunnel)

Paths auto-detected:
  ENGINE_DIR: $ENGINE_DIR
  UI_DIR:     $UI_DIR
EOF
}

ensure_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Error: required command '$1' not found in PATH" >&2
    exit 1
  fi
}

has_session() {
  tmux has-session -t "$1" 2>/dev/null
}

kill_session_if_exists() {
  local name="$1"
  if has_session "$name"; then
    tmux kill-session -t "$name" || true
  fi
}

new_session_run() {
  local name="$1"
  local cmd="$2"
  tmux new-session -d -s "$name" "bash -lc '$cmd'"
}

detect_named_tunnel() {
  # Populate CF_TUNNEL_ID if empty by picking the first available tunnel
  if [ -z "$CF_TUNNEL_ID" ] && [ -z "$CF_TUNNEL_NAME" ]; then
    if command -v "$CLOUDFLARED_BIN" >/dev/null 2>&1; then
      local first_id
      first_id="$($CLOUDFLARED_BIN tunnel list 2>/dev/null | awk 'NR>1 && $1 ~ /^[0-9a-f-]{36}$/ {print $1; exit}')"
      if [[ "$first_id" =~ ^[0-9a-f\-]{36}$ ]]; then
        CF_TUNNEL_ID="$first_id"
      fi
    fi
  fi
}

ensure_dns_route() {
  # $1 = hostname to route to named tunnel
  local h="$1"
  [ -z "$h" ] && return 0
  if [ -n "$CF_TUNNEL_ID" ]; then
    $CLOUDFLARED_BIN tunnel route dns "$CF_TUNNEL_ID" "$h" >/dev/null 2>&1 || true
  elif [ -n "$CF_TUNNEL_NAME" ]; then
    $CLOUDFLARED_BIN tunnel route dns "$CF_TUNNEL_NAME" "$h" >/dev/null 2>&1 || true
  fi
}

start_mcp() {
  ensure_cmd tmux
  ensure_cmd uv
  kill_session_if_exists "$SESSION_MCP"
  local cmd="cd '$ENGINE_DIR' && uv run python main.py mcp --transport http --host '$MCP_HOST' --port '$MCP_PORT'"
  new_session_run "$SESSION_MCP" "$cmd"
  echo "Started MCP server in tmux session: $SESSION_MCP (http/sse on ${MCP_HOST}:${MCP_PORT})"
}

start_agent() {
  ensure_cmd tmux
  ensure_cmd uv
  kill_session_if_exists "$SESSION_AGENT"
  local cmd="cd '$ENGINE_DIR' && uv run python main.py agent --host '$API_HOST' --port '$API_PORT'"
  new_session_run "$SESSION_AGENT" "$cmd"
  echo "Started Agent API in tmux session: $SESSION_AGENT (on ${API_HOST}:${API_PORT})"
}

start_ui() {
  ensure_cmd tmux
  ensure_cmd npm
  kill_session_if_exists "$SESSION_UI"
  # Build then start Next.js, exposing API URL to the frontend
  local api_url="$NEXT_PUBLIC_API_URL"
  # If named tunnel detected and API hostname configured, default UI API to public host unless explicitly overridden
  if { [ -n "$CF_TUNNEL_ID" ] || [ -n "$CF_TUNNEL_NAME" ]; } && [ "$NEXT_PUBLIC_API_URL" = "http://localhost:${API_PORT}" ]; then
    api_url="https://$CF_API_HOSTNAME"
  fi
  local cmd="cd '$UI_DIR' && npm ci && npm run build && NEXT_PUBLIC_API_URL='$api_url' NEXT_PUBLIC_ADMIN_MODE='$NEXT_PUBLIC_ADMIN_MODE' NEXT_PUBLIC_TYPING_INDICATOR_DELAY_MS='$NEXT_PUBLIC_TYPING_INDICATOR_DELAY_MS' npm start -- --port '$NEXT_PORT'"
  new_session_run "$SESSION_UI" "$cmd"
  echo "Started Next.js UI in tmux session: $SESSION_UI (on port ${NEXT_PORT})"
}

start_tunnel() {
  ensure_cmd tmux
  if ! command -v "$CLOUDFLARED_BIN" >/dev/null 2>&1; then
    echo "Error: cloudflared not found. Install it or set CLOUDFLARED_BIN to its path." >&2
    exit 1
  fi
  kill_session_if_exists "$SESSION_CF"
  local cmd
  detect_named_tunnel
  if [ -n "$CF_TUNNEL_ID" ] || [ -n "$CF_TUNNEL_NAME" ]; then
    if [ "$CF_AUTOCONFIG_DNS" = "true" ]; then
      ensure_dns_route "$CF_HOSTNAME"
      ensure_dns_route "$CF_API_HOSTNAME"
    fi
    # Run existing named tunnel; relies on routes/public hostnames configured in Cloudflare dashboard
    if [ -n "$CF_CONFIG" ]; then
      if [ -n "$CF_TUNNEL_ID" ]; then
        cmd="${CLOUDFLARED_BIN} tunnel --config '$CF_CONFIG' --no-autoupdate run '$CF_TUNNEL_ID'"
      else
        cmd="${CLOUDFLARED_BIN} tunnel --config '$CF_CONFIG' --no-autoupdate run '$CF_TUNNEL_NAME'"
      fi
    else
      if [ -n "$CF_TUNNEL_ID" ]; then
        cmd="${CLOUDFLARED_BIN} tunnel --no-autoupdate run '$CF_TUNNEL_ID'"
      else
        cmd="${CLOUDFLARED_BIN} tunnel --no-autoupdate run '$CF_TUNNEL_NAME'"
      fi
    fi
  elif [ -n "$CF_HOSTNAME" ]; then
    # Named hostname route (requires 'cloudflared login' completed and domain under your account)
    cmd="${CLOUDFLARED_BIN} tunnel --hostname '$CF_HOSTNAME' --url '$CF_TARGET' --no-autoupdate"
  else
    # Quick tunnel (random *.trycloudflare.com URL)
    cmd="${CLOUDFLARED_BIN} tunnel --url '$CF_TARGET' --no-autoupdate"
  fi
  new_session_run "$SESSION_CF" "$cmd"
  if [ -n "$CF_TUNNEL_ID" ] || [ -n "$CF_TUNNEL_NAME" ]; then
    local ref="$CF_TUNNEL_ID"
    [ -n "$CF_TUNNEL_NAME" ] && ref="$CF_TUNNEL_NAME"
    echo "Started named Cloudflare tunnel in tmux session: $SESSION_CF (tunnel $ref)"
  elif [ -n "$CF_HOSTNAME" ]; then
    echo "Started Cloudflare tunnel in tmux session: $SESSION_CF (hostname ${CF_HOSTNAME} -> ${CF_TARGET})"
  else
    echo "Started Cloudflare quick tunnel in tmux session: $SESSION_CF (target ${CF_TARGET}). URL will appear in the tmux log."
  fi
}

start_tunnel_api() {
  # Only start this secondary mapping when not using a named tunnel (named tunnels should be configured in dashboard)
  if [ -n "$CF_TUNNEL_ID" ] || [ -n "$CF_TUNNEL_NAME" ]; then
    echo "Named tunnel mode active. Please add public hostname ${CF_API_HOSTNAME} -> ${CF_API_TARGET} in Cloudflare dashboard. Skipping local secondary tunnel." >&2
    return 0
  fi
  ensure_cmd tmux
  if ! command -v "$CLOUDFLARED_BIN" >/dev/null 2>&1; then
    echo "Error: cloudflared not found. Install it or set CLOUDFLARED_BIN to its path." >&2
    exit 1
  fi
  kill_session_if_exists "$SESSION_CF_API"
  local cmd="${CLOUDFLARED_BIN} tunnel --hostname '$CF_API_HOSTNAME' --url '$CF_API_TARGET' --no-autoupdate"
  new_session_run "$SESSION_CF_API" "$cmd"
  echo "Started Cloudflare API tunnel in tmux session: $SESSION_CF_API (hostname ${CF_API_HOSTNAME} -> ${CF_API_TARGET})"
}

kill_one() {
  local name="$1"
  case "$name" in
    mcp) kill_session_if_exists "$SESSION_MCP" ;;
    agent) kill_session_if_exists "$SESSION_AGENT" ;;
    ui) kill_session_if_exists "$SESSION_UI" ;;
    tunnel) kill_session_if_exists "$SESSION_CF" ;;
    tunnel-api) kill_session_if_exists "$SESSION_CF_API" ;;
    *) echo "Unknown component to kill: $name" >&2; exit 1 ;;
  esac
}

start_one() {
  local name="$1"
  case "$name" in
    mcp) start_mcp ;;
    agent) start_agent ;;
    ui) start_ui ;;
    tunnel) start_tunnel ;;
    tunnel-api) start_tunnel_api ;;
    *) echo "Unknown component to start: $name" >&2; exit 1 ;;
  esac
}

start_all() {
  # Start in order so dependencies are available; sessions run concurrently once launched
  start_mcp
  start_agent
  start_ui
  start_tunnel
  start_tunnel_api
}

kill_all() {
  kill_session_if_exists "$SESSION_CF"
  kill_session_if_exists "$SESSION_CF_API"
  kill_session_if_exists "$SESSION_UI"
  kill_session_if_exists "$SESSION_AGENT"
  kill_session_if_exists "$SESSION_MCP"
  echo "Killed all managed tmux sessions (if any existed)."
}

status() {
  for s in "$SESSION_MCP" "$SESSION_AGENT" "$SESSION_UI" "$SESSION_CF" "$SESSION_CF_API"; do
    if has_session "$s"; then
      echo "$s: RUNNING"
    else
      echo "$s: not running"
    fi
  done
}

main() {
  local cmd="${1:-help}"
  case "$cmd" in
    start-all) start_all ;;
    start) shift || true; [ "${1:-}" ] || { echo "Specify component: mcp|agent|ui|tunnel" >&2; exit 1; }; start_one "$1" ;;
    kill-all) kill_all ;;
    kill) shift || true; [ "${1:-}" ] || { echo "Specify component: mcp|agent|ui|tunnel" >&2; exit 1; }; kill_one "$1" ;;
    status) status ;;
    help|*) usage ;;
  esac
}

main "$@"


