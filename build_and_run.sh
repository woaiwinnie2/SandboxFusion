#!/bin/bash
# Script to build and run the code sandbox

set -e

echo "🚀 Building base image..."
docker build -f ./scripts/Dockerfile.base.us -t code_sandbox:base .

echo "🚀 Building server image..."
docker build -f ./scripts/Dockerfile.server.us -t code_sandbox:server .

echo "🏃 Starting container..."
docker run -d --rm --privileged -p 8080:8080 --name sandbox-server code_sandbox:server

echo "✅ Sandbox is running on http://localhost:8080"
echo "To view logs, run: docker logs -f sandbox-server"
