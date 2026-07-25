# Testing Guide

## Running tests

```bash
cd apps/api
source .venv/bin/activate
pytest                          # everything, including live-model tests (slow)
pytest -m "not live_model"      # fast deterministic subset only
pytest -m "live_model"          # only the tests that call the real Ollama model
```

Tests run directly against the host-exposed ports of the `docker compose` stack (Postgres on `:5433`, Redis
on `:6379`, Ollama on `:11434`, MinIO on `:9000`) via `DATABASE_URL`/`REDIS_URL`/`OLLAMA_BASE_URL` in
`apps/api/.env` — the stack must be up (`make dev` or `docker compose up`), but the `api`/`api-worker`
containers themselves don't need to be running; tests exercise the FastAPI app in-process via
`httpx.ASGITransport`, hitting the same real Postgres/Redis/Ollama/MinIO the containers would.

## Deterministic vs. live-model tests

The founder's spec requires these kept separate, since live-model tests are slower and their exact wording
is not reproducible run to run. The split is a pytest marker, registered in `pyproject.toml`:

```toml
markers = [
    "live_model: exercises the real Ollama model — slower and non-deterministic in wording; run `pytest -m \"not live_model\"` for the fast deterministic subset.",
]
```

Any test that calls `ModelProvider.generate()`, `.generate_structured()`, or `.embed()` — directly or via a
service function — is marked `@pytest.mark.live_model` (or, for a whole file where every test does, via a
module-level `pytestmark = pytest.mark.live_model`, e.g. `tests/test_reports.py`, since daily-report
generation always calls the model for its narrative with no zero-model-call path).

Tests are **not** mocked against a fake model. `opero_ai_engine.FakeProvider` exists (used by Phase 2's
provider-interface tests), but every Phase 3 service test that needs a model call uses the real
`OllamaProvider` against the real running `qwen2.5:7b-instruct`/`nomic-embed-text` — this is what makes the
prompt-injection defense test (see below) meaningful: it proves the defense holds against actual inference,
not against a mock that can't misbehave in the first place.

## What's covered

| File | Covers | Live model? |
|---|---|---|
| `test_documents.py` | Upload, dedup (409), type/size validation (400), org isolation, pagination; processing (extraction→chunking→embedding) | Processing test only |
| `test_knowledge.py` | Search org isolation, RAG insufficient-evidence short-circuit (no model call), grounded answer with citation | Grounded-answer test only |
| `test_email_pipeline.py` | Mock ingestion + idempotency, list/detail org isolation, full classify→extract→draft pipeline, injection-email flagging | Pipeline + injection tests |
| `test_leads_and_tasks.py` | List/detail/status-update, org isolation, status filtering | No |
| `test_reports.py` | Metrics correctness with no activity, idempotent generation, org isolation, 404 for missing date | All (narrative always calls the model) |
| `test_approval_simulated_send.py` | `send_email_reply` dispatch, edited-payload precedence, rejection never dispatches, unrecognized action types are a no-op | No |
| `test_prompt_injection_defense.py` | Scanner unit tests (4 patterns), real end-to-end injection attack against the live model | Attack test only |

Plus everything from Phase 2 (`test_approvals.py`, `test_auth.py`, `test_crypto.py`, `test_gmail_sync.py`,
`test_health.py`, `test_oauth_state.py`) — unmodified and still passing (Phase 3 was additive, per the
founder's explicit "do not rebuild the foundation" rule).

## What's not covered

- **Playwright / browser E2E**: no headless browser is available in this development environment (same
  limitation documented in Phase 2's `IMPLEMENTATION_STATUS.md`). Frontend pages are verified by hitting the
  real API endpoints they call and confirming the pages render without runtime errors, not via an actual
  browser session driving the UI.
- **RBAC role differentiation** (member vs. admin vs. owner): there's no invite/add-member endpoint yet —
  every registered user is an org's sole `owner`. Permission *codes* are exercised (every endpoint requires
  one), but there's no test proving a `member`-role user is denied a `.write` action, since no code path
  creates a non-owner user to test with.
- **Celery worker container itself**: `process_document_task`/`process_email_task` are tested by calling the
  underlying service functions directly (`process_document()`, `process_email()`) in the same event loop as
  the test, not by enqueuing through Redis and waiting for a separate worker process to pick them up. The
  idempotency logic inside the Celery task wrapper (`app/workers/tasks.py`) is simple enough (an early-return
  guard) that this is a reasonable trade-off, but it means the actual `api-worker` container's task dispatch
  has only been verified manually, not via automated test.

## Adding a new Phase 3 test

If it calls a service function that ultimately reaches `get_model_provider()`, mark it
`@pytest.mark.live_model` (or module-wide with `pytestmark`). If it only touches the DB/schemas/permission
checks, it's deterministic — no marker needed, and it should run in well under a second.
