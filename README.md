# Opero AI Employee OS

Your AI Employee That Gets Work Done.

Opero AI is an autonomous **AI Sales & Operations Assistant** — not a chatbot. It reads and triages email, drafts
replies grounded in your company's own documents, tracks leads and follow-ups, manages tasks, and reports on what
it did, with a human approval gate on anything irreversible. See [docs/](docs/) for the full product/architecture
docs — start with [docs/README.md](docs/README.md) — and [docs/IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md)
for what's actually built right now. This file covers running the code.

## Repository layout

```
apps/
  web/                Next.js dashboard (sign-in, approvals, activity log, and placeholder pages)
  api/                 FastAPI backend: auth, RBAC, approvals, Gmail integration, audit log
services/
  ai-engine/           Model-provider interface + Ollama implementation (docs/AI_ARCHITECTURE.md)
  connectors/          Email/Calendar/CRM/Document connector interfaces + safe mocks
  worker/              Celery background-job worker
infra/                 docker-compose stack for local dev / self-hosted deployment
docs/                  Product, architecture, database, security, and roadmap documentation
```

**Note on `infra/`:** kept as-is rather than renamed to `infrastructure/docker/` — this directory already had a
working, verified `docker-compose.yml` before this phase, and a pure rename with no functional difference wasn't
worth the churn. Documented here rather than silently deviating from the suggested structure.

**Note on `packages/`:** the suggested structure included `packages/shared-types`, `packages/ui`, and
`packages/config`. None were created — there is exactly one frontend app (`apps/web`) and no second TypeScript
codebase to share types or config with yet, so these would have been empty directories with no defined purpose,
which the founder's own instructions explicitly call out to avoid. Create them when a second consumer actually
needs to share code with `apps/web`, not before.

## Prerequisites

- Docker (for `infra/docker-compose.yml`)
- Python 3.12+ (if running services outside Docker)
- Node.js 20+ (if running the dashboard outside Docker)

## Running locally

### One command (recommended)

```bash
make dev
```

Equivalent to `docker compose -f infra/docker-compose.yml up --build`. Brings up Postgres+pgvector, Redis, MinIO,
Ollama, Temporal, the API, the Celery worker, and the dashboard.

- Dashboard: http://localhost:3010 — register your organization at `/register`, then sign in
- API: http://localhost:8000 (`/healthz`, `/readyz`, `/version`, `/docs` for OpenAPI)
- Temporal UI: http://localhost:8080
- MinIO console: http://localhost:9001
- Postgres: localhost:5433 (host-side; services talk to it over the internal Docker network on 5432)

Host ports for Postgres (5433) and the dashboard (3010) are intentionally non-default — adjust
`infra/docker-compose.yml` if your machine doesn't have the same conflicts (a pre-existing local Postgres on 5432
and another project's dev server on 3000).

**Pull an Ollama model after first `up`** (docs/AI_ARCHITECTURE.md §3) — not bundled in the image:

```bash
docker compose -f infra/docker-compose.yml exec ollama ollama pull qwen2.5:7b-instruct
docker compose -f infra/docker-compose.yml exec ollama ollama pull nomic-embed-text
```

`qwen2.5:7b-instruct` (4.7GB) is the confirmed-working default — it's what's actually configured
(`MODEL_REASONING_NAME`) and what's been verified to load and generate correctly. The larger
`qwen2.5:14b-instruct` (9GB) was tried first and failed to load in an 8GB Docker VM alongside the rest of the
stack; use it instead only if your Docker VM has more memory to spare.

### `make` targets

```bash
make setup          # install local dependencies for every service (for running outside Docker)
make dev             # docker compose up --build
make dev-down        # stop everything
make migrate         # apply DB migrations (also runs automatically on API container start)
make create-admin ORG="Acme" EMAIL=owner@acme.com PASSWORD=...   # bootstrap the first org + owner
make test            # run every test suite in the monorepo
make lint            # lint every service
make typecheck       # frontend type-check
make db-reset        # drop and recreate the local schema (destructive, asks first)
make logs            # tail all container logs
```

### Running services natively (faster iteration)

Bring up just the infra dependencies, then run each service directly:

```bash
docker compose -f infra/docker-compose.yml up postgres redis ollama temporal -d
```

**API:**

```bash
cd apps/api
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt   # includes an editable install of services/ai-engine
cp .env.example .env              # fill in generated secrets — see comments in the file
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

**Dashboard:**

```bash
cd apps/web
npm install
cp .env.local.example .env.local
npm run dev
```

If port 3000 is already in use by another project on your machine, Next.js picks the next free port automatically
— the dashboard reads the API's base URL from `NEXT_PUBLIC_API_BASE_URL`, so it works from any port.

## Testing & linting

```bash
make test   # or individually:

cd apps/api && source .venv/bin/activate && ruff check . && pytest -q
cd services/ai-engine && source .venv/bin/activate && ruff check . && pytest -q
cd services/connectors && source .venv/bin/activate && ruff check . && pytest -q
cd services/worker && source .venv/bin/activate && ruff check . && pytest -q
cd apps/web && npm run lint && npx tsc --noEmit && npm run build
```

CI (`.github/workflows/ci.yml`) runs the API and dashboard suites on every PR.

## Current status

See [docs/IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md) — kept current every phase, this is the
authoritative "what's actually built" reference, not this README.
