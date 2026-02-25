# AGENTS.md

## Cursor Cloud specific instructions

### Project Overview

MGX Demo is a PaaS platform where AI agents generate web apps. See `README.md` for architecture and `docs/project_description.md` for full details.

### Running Services (Docker Compose)

All infrastructure services are defined in `infra/docker-compose.yml`. Start with:

```bash
docker compose -f infra/docker-compose.yml up -d --build
```

This starts: MongoDB (27017), Redis (6379), etcd (2379), Apisix (9080/9180), OAuth2 Provider (8001), MGX API (8000), Frontend (8080), Celery Worker.

### Non-obvious Gotchas

- **Python tests require `REDIS_URL=redis://localhost:6379/0`** when running outside Docker. The `.env` default `redis://redis:6379/0` uses the Docker-internal hostname which is unreachable from the host. Run tests with: `REDIS_URL=redis://localhost:6379/0 uv run python -m pytest tests/ -v`
- **Frontend esbuild**: `frontend/package.json` includes `pnpm.onlyBuiltDependencies: ["esbuild"]` to allow esbuild's postinstall script to run non-interactively. Without this, Vite and vitest will fail.
- **Frontend lint has pre-existing errors** (31 errors, 1 warning) — these are in the existing codebase and are not regressions.
- **Docker-in-Docker**: This cloud environment runs inside a container. Docker requires `fuse-overlayfs` storage driver and `iptables-legacy`. These are configured during initial setup.

### Standard Commands

See `Makefile` for all commands (`make help`). Key ones:

| Task | Command |
|---|---|
| Install all deps | `make install` (runs `uv sync --all-extras` + `cd frontend && pnpm install`) |
| Start all services | `docker compose -f infra/docker-compose.yml up -d --build` |
| Run Python tests | `REDIS_URL=redis://localhost:6379/0 uv run python -m pytest tests/ -v` |
| Run frontend tests | `cd frontend && pnpm test:run` |
| Run frontend lint | `cd frontend && pnpm lint` |
| Frontend dev server | `cd frontend && pnpm dev` (port 5173) |
| Build MGX image | `make build-mgx` |

### Login Credentials

Default: `admin` / `admin123`
