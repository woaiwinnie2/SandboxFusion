#!/usr/bin/env bash
# start.sh — set up venv, start dispatcher (which will spin up pool containers)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$SCRIPT_DIR/.venv"

# ── venv ──────────────────────────────────────────────────────────────────────
if [[ ! -d "$VENV" ]]; then
  echo "🐍 Creating virtual environment at $VENV …"
  python3 -m venv "$VENV"
fi

echo "📦 Installing / updating dependencies …"
"$VENV/bin/pip" install --quiet --upgrade pip
"$VENV/bin/pip" install --quiet -r "$SCRIPT_DIR/requirements.txt"

# ── env ───────────────────────────────────────────────────────────────────────
export SANDBOX_IMAGE="${SANDBOX_IMAGE:-code_sandbox:server}"
export POOL_SIZE="${POOL_SIZE:-4}"
export BASE_HOST_PORT="${BASE_HOST_PORT:-8081}"
export DISPATCHER_PORT="${DISPATCHER_PORT:-8080}"
export HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-60}"
export REQUEST_TIMEOUT="${REQUEST_TIMEOUT:-120}"

echo ""
echo "🚀 Starting Sandbox Dispatcher"
echo "   Image       : $SANDBOX_IMAGE"
echo "   Pool size   : $POOL_SIZE"
echo "   Pool ports  : $BASE_HOST_PORT … $(( BASE_HOST_PORT + POOL_SIZE - 1 ))"
echo "   Dispatcher  : http://localhost:$DISPATCHER_PORT"
echo ""

cd "$SCRIPT_DIR"
exec "$VENV/bin/uvicorn" dispatcher:app \
  --host 0.0.0.0 \
  --port "$DISPATCHER_PORT" \
  --log-level info
