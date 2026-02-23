"""
ContainerPool — manages a fixed pool of sandbox Docker containers.

Each container in the pool is assigned a dedicated host port. When a container
finishes serving a request it is *recreated* from scratch (not just restarted)
so that the filesystem is wiped clean, eliminating any residual state left by
the previous execution.

Thread-safety model
--------------------
Docker SDK calls are blocking; we run them in the default thread executor to
avoid blocking the asyncio event loop.  The asyncio.Queue provides back-pressure
— callers that `acquire()` when the pool is fully busy will simply await until
a container becomes available again.
"""
import asyncio
import logging
import time
from dataclasses import dataclass

import docker
import httpx

import config

log = logging.getLogger(__name__)


@dataclass
class PoolEntry:
    """Represents one sandbox container slot in the pool."""
    name: str        # Docker container name, e.g. "sandbox-pool-2"
    host_port: int   # Host-side port mapped to SANDBOX_PORT inside the container
    base_url: str    # http://localhost:<host_port>


class ContainerPool:
    def __init__(self) -> None:
        self._client = docker.from_env()
        self._queue: asyncio.Queue[PoolEntry] = asyncio.Queue()
        self._entries: list[PoolEntry] = []
        self._busy: int = 0
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Create all pool containers and wait until each is healthy."""
        loop = asyncio.get_event_loop()
        tasks = []
        for i in range(config.POOL_SIZE):
            port = config.BASE_HOST_PORT + i
            name = f"{config.CONTAINER_PREFIX}{i}"
            entry = PoolEntry(name=name, host_port=port, base_url=f"http://localhost:{port}")
            self._entries.append(entry)
            tasks.append(self._init_entry(loop, entry))
        await asyncio.gather(*tasks)
        log.info("All %d sandbox containers are ready.", config.POOL_SIZE)

    async def _init_entry(self, loop: asyncio.AbstractEventLoop, entry: PoolEntry) -> None:
        await loop.run_in_executor(None, self._create_container, entry)
        await loop.run_in_executor(None, self._wait_healthy, entry)
        await self._queue.put(entry)
        log.info("  [ready] %s  →  localhost:%d", entry.name, entry.host_port)

    async def shutdown(self) -> None:
        """Stop and remove all pool containers."""
        loop = asyncio.get_event_loop()
        tasks = [loop.run_in_executor(None, self._remove_container, e) for e in self._entries]
        await asyncio.gather(*tasks, return_exceptions=True)
        log.info("Container pool shut down.")

    # ------------------------------------------------------------------
    # Acquire / release
    # ------------------------------------------------------------------

    async def acquire(self) -> PoolEntry:
        """Block until an idle container is available, then mark it busy."""
        entry = await self._queue.get()
        async with self._lock:
            self._busy += 1
        log.debug("Acquired %s  (busy=%d)", entry.name, self._busy)
        return entry

    async def release(self, entry: PoolEntry) -> None:
        """Recreate the container to wipe state, then return it to the pool."""
        loop = asyncio.get_event_loop()
        log.info("Recycling %s …", entry.name)
        try:
            await loop.run_in_executor(None, self._create_container, entry)
            await loop.run_in_executor(None, self._wait_healthy, entry)
            log.info("  [ready] %s recycled successfully.", entry.name)
        except Exception:
            log.exception("Failed to recycle %s — attempting one more time.", entry.name)
            try:
                await loop.run_in_executor(None, self._create_container, entry)
                await loop.run_in_executor(None, self._wait_healthy, entry)
            except Exception:
                log.exception(
                    "Container %s could not be recovered. Dropping it from pool.", entry.name
                )
                async with self._lock:
                    self._busy -= 1
                return  # don't re-enqueue a broken container

        async with self._lock:
            self._busy -= 1
        await self._queue.put(entry)

    # ------------------------------------------------------------------
    # Docker helpers (blocking — run in thread executor)
    # ------------------------------------------------------------------

    def _create_container(self, entry: PoolEntry) -> None:
        """Remove any existing container with the same name, then create a fresh one."""
        self._remove_container(entry)
        log.debug("Creating container %s on host port %d …", entry.name, entry.host_port)
        self._client.containers.run(
            config.IMAGE,
            detach=True,
            name=entry.name,
            ports={f"{config.SANDBOX_PORT}/tcp": entry.host_port},
            privileged=True,   # SandboxFusion requires --privileged
            remove=False,       # we manage lifecycle manually
        )

    def _remove_container(self, entry: PoolEntry) -> None:
        try:
            c = self._client.containers.get(entry.name)
            c.remove(force=True)
            log.debug("Removed old container %s.", entry.name)
        except docker.errors.NotFound:
            pass

    def _wait_healthy(self, entry: PoolEntry, timeout: int | None = None) -> None:
        """Poll the sandbox HTTP root until it responds or timeout expires."""
        timeout = timeout or config.HEALTH_TIMEOUT
        deadline = time.monotonic() + timeout
        url = f"{entry.base_url}/"
        last_exc: Exception | None = None
        while time.monotonic() < deadline:
            try:
                httpx.get(url, timeout=2.0)
                return  # any HTTP response → server is up
            except Exception as exc:
                last_exc = exc
                time.sleep(0.5)
        raise TimeoutError(
            f"{entry.name} did not become healthy within {timeout}s. Last error: {last_exc}"
        )

    # ------------------------------------------------------------------
    # Observability
    # ------------------------------------------------------------------

    @property
    def status(self) -> dict:
        busy = self._busy
        return {
            "pool_size": config.POOL_SIZE,
            "idle": config.POOL_SIZE - busy,
            "busy": busy,
            "containers": [
                {"name": e.name, "host_port": e.host_port, "base_url": e.base_url}
                for e in self._entries
            ],
        }
