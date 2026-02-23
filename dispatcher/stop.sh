#!/usr/bin/env bash
# stop.sh — stop and remove all pool containers created by the dispatcher
set -euo pipefail

PREFIX="${CONTAINER_PREFIX:-sandbox-pool-}"
POOL_SIZE="${POOL_SIZE:-4}"

echo "🛑 Stopping dispatcher pool containers (prefix: $PREFIX) …"

for (( i=0; i<POOL_SIZE; i++ )); do
  name="${PREFIX}${i}"
  if docker inspect "$name" &>/dev/null; then
    docker rm -f "$name" && echo "  Removed $name"
  else
    echo "  $name not found, skipping."
  fi
done

echo "✅ Done."
