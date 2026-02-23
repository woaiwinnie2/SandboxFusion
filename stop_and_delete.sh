#!/bin/bash
# Script to stop the container and delete sandbox images

echo "🛑 Stopping sandbox container..."
docker stop sandbox-server 2>/dev/null || echo "No running sandbox-server found."

echo "🗑️ Removing sandbox images..."
docker rmi code_sandbox:server code_sandbox:base 2>/dev/null || echo "Sandbox images already removed."

echo "🧹 Cleaning up dangling images..."
docker image prune -f

echo "✅ Cleanup complete."
