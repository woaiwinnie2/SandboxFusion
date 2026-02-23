"""
Sandbox Dispatcher — transparent HTTP proxy with container pool.

Every request (any path, any method) is:
  1. Held until an idle sandbox container is available.
  2. Forwarded verbatim to that container.
  3. The response is returned to the caller immediately.
  4. The container is recreated in the background (clean state for next request).

Special routes
--------------
  GET /dispatcher/status  — pool health / busy count (not proxied)
"""
import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import BackgroundTasks, FastAPI, Request, Response
from fastapi.responses import JSONResponse

import config
from pool import ContainerPool

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
log = logging.getLogger(__name__)

pool = ContainerPool()


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Starting sandbox pool (%d containers, image=%s) …", config.POOL_SIZE, config.IMAGE)
    await pool.start()
    log.info("Dispatcher ready on port %d.", config.DISPATCHER_PORT)
    yield
    log.info("Shutting down …")
    await pool.shutdown()


app = FastAPI(title="Sandbox Dispatcher", lifespan=lifespan)


# --------------------------------------------------------------------------- #
#  Status endpoint                                                             #
# --------------------------------------------------------------------------- #

@app.get("/dispatcher/status", tags=["dispatcher"])
async def dispatcher_status():
    """Return pool utilisation info — never proxied to a sandbox."""
    return JSONResponse(pool.status)


# --------------------------------------------------------------------------- #
#  Catch-all transparent proxy                                                 #
# --------------------------------------------------------------------------- #

_HOP_BY_HOP = frozenset({
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade", "host",
})


@app.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
    tags=["proxy"],
)
async def proxy(path: str, request: Request, background_tasks: BackgroundTasks):
    entry = await pool.acquire()
    log.info("→  %s %-6s /%s  via  %s", request.client.host, request.method, path, entry.name)

    target_url = f"{entry.base_url}/{path}"
    if request.url.query:
        target_url = f"{target_url}?{request.url.query}"

    headers = {k: v for k, v in request.headers.items() if k.lower() not in _HOP_BY_HOP}
    body = await request.body()

    try:
        async with httpx.AsyncClient(timeout=config.REQUEST_TIMEOUT) as client:
            resp = await client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                content=body,
            )
        log.info("←  %s %d  (%d bytes)", entry.name, resp.status_code, len(resp.content))

        # Release the container in the background so the client doesn't wait
        background_tasks.add_task(pool.release, entry)

        # Strip hop-by-hop headers from the upstream response before forwarding
        resp_headers = {k: v for k, v in resp.headers.items() if k.lower() not in _HOP_BY_HOP}
        return Response(
            content=resp.content,
            status_code=resp.status_code,
            headers=resp_headers,
            media_type=resp.headers.get("content-type"),
        )

    except Exception as exc:
        # Still recycle even on error
        background_tasks.add_task(pool.release, entry)
        log.exception("Proxy error: %s → %s", entry.name, target_url)
        return JSONResponse({"error": str(exc)}, status_code=502)
