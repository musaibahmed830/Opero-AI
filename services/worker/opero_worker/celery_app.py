"""Celery application (docs/TECHNOLOGY_STACK.md §2): background jobs — embedding
a document, sending a digest, polling for mail — as opposed to the
durable/approval-gated workflows Temporal owns (docs/SYSTEM_ARCHITECTURE.md §2.5).

Phase 2 ships the foundation (broker connection, one real task proving the
loop) — real background jobs (email polling, embedding generation) land with
the features that need them in Phase 1+.
"""

import os

from celery import Celery

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

app = Celery("opero_worker", broker=REDIS_URL, backend=REDIS_URL)
app.conf.task_serializer = "json"
app.conf.result_serializer = "json"
app.conf.accept_content = ["json"]
# Explicit per Celery's deprecation notice — retains today's default retry-on-startup
# behavior instead of silently changing when Celery 6.0 flips the default.
app.conf.broker_connection_retry_on_startup = True

# Imported for its side effect of registering tasks with `app`.
from opero_worker import tasks  # noqa: E402,F401
