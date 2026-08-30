#!/bin/sh
set -eu

export TRVL_MCP_TOKEN="${TRVL_INTERNAL_TOKEN:?TRVL_INTERNAL_TOKEN is required}"
export UPSTREAM_BEARER_TOKEN="$TRVL_INTERNAL_TOKEN"
export UPSTREAM_BASE_URL="${UPSTREAM_BASE_URL:-http://127.0.0.1:9090}"

trvl mcp --http --host 127.0.0.1 --port 9090 &
TRVL_PID="$!"

cleanup() {
  kill "$TRVL_PID" 2>/dev/null || true
}
trap cleanup INT TERM EXIT

python app.py &
BRIDGE_PID="$!"

wait "$BRIDGE_PID"
