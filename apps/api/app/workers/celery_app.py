"""Celery app for background jobs that need the full app stack (DB models,
AI provider, etc.) — document processing, email classification, draft
generation, daily reports (docs/DEVELOPMENT_ROADMAP.md Phase 3, "Background
Jobs").

`services/worker` (Phase 2) proved the broker connection with a minimal
`ping` task and has no dependency on `apps/api`'s models/DB session. Real
Phase 3 jobs need that full stack, so they're defined here and run via a
worker container built from the `apps/api` image (see
infra/docker-compose.yml `worker` service) rather than duplicating models
into the separate `services/worker` package. `services/worker`'s code and
tests are untouched and still valid — just no longer what the `worker`
compose service runs.
"""

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

app = Celery("opero_api_worker", broker=settings.redis_url, backend=settings.redis_url)
app.conf.task_serializer = "json"
app.conf.result_serializer = "json"
app.conf.accept_content = ["json"]
app.conf.broker_connection_retry_on_startup = True

# Retry policy (docs/DEVELOPMENT_ROADMAP.md Phase 3, "Background Jobs"): every
# task gets a bounded number of automatic retries with backoff by default;
# individual tasks can override via their own `max_retries`/`retry_backoff`.
app.conf.task_acks_late = True
app.conf.task_reject_on_worker_lost = True

from app.workers import tasks  # noqa: E402,F401
