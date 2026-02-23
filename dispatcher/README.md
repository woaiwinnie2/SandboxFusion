# Sandbox Dispatcher

A lightweight Python/FastAPI reverse-proxy that keeps a pool of
`code_sandbox:server` containers running, dispatches incoming HTTP requests to
an idle container, and **recreates** the container after each execution so the
next request always starts from a clean filesystem.

## Why recreate instead of restart?

`docker restart` preserves the container's writable layer, meaning files
written by code execution survive across requests.  Removing and re-creating
the container (`docker rm -f` + `docker run`) gives a truly blank slate every
time at the cost of a few extra seconds.  That delay is hidden from the caller
because the recreation happens **after** the response is already sent.

## Architecture

```
Client  ──→  Dispatcher :8000  ──→  (idle container from pool)
                                         sandbox-pool-0 :8081
                                         sandbox-pool-1 :8082
                                         sandbox-pool-2 :8083
                                         sandbox-pool-3 :8084
              ← response sent immediately
              [ container recreation runs in background ]
```

## Quick start

```bash
# Optional: adjust settings via environment variables
export POOL_SIZE=4
export BASE_HOST_PORT=8081
export DISPATCHER_PORT=8000
export SANDBOX_IMAGE=code_sandbox:server

bash dispatcher/start.sh
```

The script creates a Python venv at `dispatcher/.venv`, installs dependencies,
starts the sandbox containers, and launches the dispatcher.

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `SANDBOX_IMAGE` | `code_sandbox:server` | Docker image for pool containers |
| `POOL_SIZE` | `4` | Number of containers to keep ready |
| `BASE_HOST_PORT` | `8081` | First host port; pool uses BASE … BASE+POOL_SIZE-1 |
| `DISPATCHER_PORT` | `8080` | Port the dispatcher listens on |
| `CONTAINER_PREFIX` | `sandbox-pool-` | Name prefix for pool containers |
| `SANDBOX_PORT` | `8080` | Port inside the container |
| `HEALTH_TIMEOUT` | `60` | Seconds to wait for a container to become healthy |
| `REQUEST_TIMEOUT` | `120` | Seconds to wait for sandbox response |

## Endpoints

| Endpoint | Description |
|---|---|
| `GET /dispatcher/status` | Pool utilisation (idle/busy/container list) |
| `* /*` | Everything else is proxied transparently |

## Stopping

```bash
# Ctrl-C the dispatcher process, then:
bash dispatcher/stop.sh
```

## Testing

```bash
# Pool status
curl http://localhost:8000/dispatcher/status

# Single execution
curl -s -X POST http://localhost:8000/run_code \
  -H "Content-Type: application/json" \
  -d '{"code": "print(42)", "language": "python"}'

# Concurrent executions (exercises the whole pool)
for i in $(seq 1 8); do
  curl -s -X POST http://localhost:8000/run_code \
    -H "Content-Type: application/json" \
    -d "{\"code\": \"import time; time.sleep(2); print($i)\", \"language\": \"python\"}" &
done
wait
```
