.PHONY: setup dev dev-down migrate create-admin demo-seed test test-api test-web lint lint-api lint-web \
        typecheck db-reset logs

COMPOSE = docker compose -f infra/docker-compose.yml

## Initial setup: install all local dependencies (for running services outside Docker).
setup:
	cd apps/api && python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
	cd apps/web && npm install
	cd services/ai-engine && python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements-dev.txt
	cd services/connectors && python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements-dev.txt
	cd services/worker && python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements-dev.txt
	@echo "Setup complete. Copy apps/api/.env.example to apps/api/.env and fill in secrets, then run 'make dev'."

## Start every service (Postgres, Redis, MinIO, Ollama, Temporal, API, worker, dashboard).
dev:
	$(COMPOSE) up --build

## Stop and remove all containers (data volumes are preserved).
dev-down:
	$(COMPOSE) down

## Apply database migrations (also runs automatically on API container start).
migrate:
	cd apps/api && . .venv/bin/activate && alembic upgrade head

## Create the first organization + owner user: make create-admin ORG="Acme" EMAIL=owner@acme.com PASSWORD=...
create-admin:
	cd apps/api && . .venv/bin/activate && python scripts/create_admin.py --org "$(ORG)" --email "$(EMAIL)" --password "$(PASSWORD)"

## Seed a fictional demo organization: knowledge docs, 12 mock emails, full
## pipeline run, and today's daily report (docs/LOCAL_DEMO_GUIDE.md).
demo-seed:
	cd apps/api && . .venv/bin/activate && python scripts/seed_demo_org.py

## Run every test suite in the monorepo.
test: test-api test-web

test-api:
	cd apps/api && . .venv/bin/activate && python -m pytest -q
	cd services/ai-engine && . .venv/bin/activate && python -m pytest -q
	cd services/connectors && . .venv/bin/activate && python -m pytest -q
	cd services/worker && . .venv/bin/activate && python -m pytest -q

test-web:
	cd apps/web && npm run lint && npx tsc --noEmit && npm run build

## Lint everything.
lint: lint-api lint-web

lint-api:
	cd apps/api && . .venv/bin/activate && ruff check .
	cd services/ai-engine && . .venv/bin/activate && ruff check .
	cd services/connectors && . .venv/bin/activate && ruff check .
	cd services/worker && . .venv/bin/activate && ruff check .

lint-web:
	cd apps/web && npm run lint

typecheck:
	cd apps/web && npx tsc --noEmit

## Drop and recreate the local database schema. Destructive — confirms first.
db-reset:
	@echo "This will drop every table in the local database. Ctrl-C to cancel."
	@sleep 3
	cd apps/api && . .venv/bin/activate && alembic downgrade base && alembic upgrade head

## Tail logs from every running service.
logs:
	$(COMPOSE) logs -f
