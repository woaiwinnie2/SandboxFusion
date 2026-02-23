"""
Dispatcher configuration — all values can be overridden via environment variables.
"""
import os

# Docker image used for pool containers
IMAGE: str = os.environ.get("SANDBOX_IMAGE", "code_sandbox:server")

# Number of containers to keep in the pool
POOL_SIZE: int = int(os.environ.get("POOL_SIZE", "4"))

# Docker name prefix for pool containers (e.g. sandbox-pool-0, sandbox-pool-1 …)
CONTAINER_PREFIX: str = os.environ.get("CONTAINER_PREFIX", "sandbox-pool-")

# Port that the sandbox server listens on *inside* the container
SANDBOX_PORT: int = int(os.environ.get("SANDBOX_PORT", "8080"))

# First host port to map; pool containers will use BASE_HOST_PORT … BASE_HOST_PORT+POOL_SIZE-1
BASE_HOST_PORT: int = int(os.environ.get("BASE_HOST_PORT", "8081"))

# Port the dispatcher itself listens on
DISPATCHER_PORT: int = int(os.environ.get("DISPATCHER_PORT", "8080"))

# Seconds to wait for a container to become healthy after (re)creation
HEALTH_TIMEOUT: int = int(os.environ.get("HEALTH_TIMEOUT", "60"))

# Seconds to wait for the sandbox to respond to a proxied request
REQUEST_TIMEOUT: float = float(os.environ.get("REQUEST_TIMEOUT", "120"))
