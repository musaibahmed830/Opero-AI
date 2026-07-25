# Implementation Status

Kept current every phase. This is the authoritative "what's actually built" reference — READMEs and the
roadmap describe intent; this describes reality as of the end of Phase 3 (Knowledge System + Email
Intelligence MVP).

## Completed

### Documentation
All 18 required docs exist: the 9 from Phase 2 (`PRODUCT_REQUIREMENTS.md`, `MVP_SCOPE.md`,
`SYSTEM_ARCHITECTURE.md`, `AI_ARCHITECTURE.md`, `DATABASE_DESIGN.md`, `SECURITY_MODEL.md`,
`DEVELOPMENT_ROADMAP.md`, `DECISIONS_REQUIRED_FROM_FOUNDER.md`, `TECHNOLOGY_STACK.md`) plus 8 new Phase 3
docs: `KNOWLEDGE_SYSTEM.md`, `RAG_PIPELINE.md`, `EMAIL_INTELLIGENCE.md`, `PROMPT_INJECTION_DEFENCE.md`,
`APPROVAL_WORKFLOW.md`, `DAILY_REPORT_ENGINE.md`, `TESTING_GUIDE.md`, `LOCAL_DEMO_GUIDE.md`. This file and
`DECISIONS_REQUIRED_FROM_FOUNDER.md` were both updated with Phase 3 additions rather than replaced.

### Database (24 tables, two migrations)
Phase 2's 21 tables plus Phase 3 additions: `email_classifications`, `rag_query_traces`, and extensions to
`documents` (processing pipeline metadata, checksum dedup), `document_chunks` (token estimates, metadata),
`leads`/`tasks` (source-message links, confidence, priority), `approval_requests` (`resolved_payload`,
`simulated_send_result`), `daily_reports` (`metrics`, `narrative`). Full migration
(`e1b60a1b1bd3_phase_3_knowledge_system_email_.py`) verified via repeated down/up cycles, including several
real Postgres ENUM/foreign-key gotchas hit and fixed along the way (see "Real bugs found and fixed" below).

### Knowledge system (`apps/api/app/services/document_ingestion.py`, `chunking.py`, `text_extraction.py`,
`knowledge_search.py`, `storage.py`)
Upload → checksum dedup → MinIO storage → extract (PDF/DOCX/TXT/MD/CSV, all local open-source libraries) →
clean → chunk → embed (`nomic-embed-text`) → pgvector-backed org-scoped semantic search. Document statuses
(`uploaded/processing/ready/failed/archived`) fully implemented. See
[KNOWLEDGE_SYSTEM.md](KNOWLEDGE_SYSTEM.md).

### RAG pipeline (`apps/api/app/services/rag.py`)
`POST /v1/knowledge/ask` — grounded answering with a zero-model-call short-circuit when no evidence is
retrieved, a transparent (documented, not calibrated) confidence heuristic, citations, and full trace
storage (`RagQueryTrace`). See [RAG_PIPELINE.md](RAG_PIPELINE.md).

### Email intelligence (`apps/api/app/services/email_ingestion.py`, `email_classification.py`,
`lead_extraction.py`, `task_extraction.py`, `draft_generation.py`, `email_processing.py`)
12 fixed mock scenarios via `MockEmailConnector`, idempotent ingestion, full
classify → extract-lead/extract-tasks → draft → propose-approval pipeline, orchestrated end to end by
`email_processing.py::process_email` and dispatched via a real Celery task
(`app/workers/tasks.py::process_email_task`). See [EMAIL_INTELLIGENCE.md](EMAIL_INTELLIGENCE.md).

### Prompt-injection defense (`apps/api/app/services/prompt_injection.py`)
Structural (system/user/retrieved-content separation, no tool-calling surface) plus a 6-pattern regex
detector, applied to every email body and every retrieved knowledge chunk before use. Verified against the
live model with a real planted-secret attack, not simulated — see
[PROMPT_INJECTION_DEFENCE.md](PROMPT_INJECTION_DEFENCE.md).

### Approval workflow extension (`apps/api/app/services/approval_service.py`)
Phase 2's propose→decide loop extended with a real (simulated) execution path: approving a
`send_email_reply` action calls `MockEmailConnector.send_message()` and records the result — never a real
send. Supports approving with an edited payload (the edit, not the original, is what "sends"). Every other
`action_type` remains a no-op on approval — no unrestricted autonomous execution. See
[APPROVAL_WORKFLOW.md](APPROVAL_WORKFLOW.md).

### Daily report engine (`apps/api/app/services/daily_report.py`)
Deterministic SQL-computed metrics first, AI narrative written on top of them second — the model has no
path to alter a number. Idempotent per `(organization_id, report_date)`. See
[DAILY_REPORT_ENGINE.md](DAILY_REPORT_ENGINE.md).

### API endpoints (all under `/v1`, all organization-scoped, all behind RBAC permission checks)
`documents` (upload/list/get/archive), `knowledge` (search/ask), `emails` (ingest-mock/list/get/process),
`leads` (list/get/status), `tasks` (list/get/status), `reports` (generate/list/get). Two new RBAC
permission codes added (`reports.read`, `reports.generate`), granted to the appropriate default roles.

### Background jobs (`apps/api/app/workers/`)
A new Celery worker entrypoint (`app.workers.celery_app`), separate from Phase 2's ping-only
`services/worker` skeleton, built from the same image as `apps/api` (needs the full model stack for
document/email processing). `process_document_task` and `process_email_task`, both idempotent and retrying
on failure. Runs as its own `api-worker` compose service.

### Frontend (`apps/web`)
Every page the founder's spec named is now real, not a placeholder: **Knowledge** (upload, search, ask, with
citations), **Inbox** (ingest + classify mock emails, list with category/priority badges, detail panel with
extracted lead/tasks and injection warnings), **Approvals** (extended for edited-payload approval and
simulated-send results), **Leads** (list with status control), **Tasks** (list with a done/open toggle),
**Reports** (metrics + narrative, on-demand generation). **Activity Log** was already fully functional from
Phase 2 and needed no changes. Verified via `npx tsc --noEmit` and `npm run lint` (both clean) and via
HTTP-level checks that every page renders 200 against the real containerized API — no headless browser was
available to drive an actual UI session (same limitation as Phase 2).

### Infrastructure
New `api-worker` service in `infra/docker-compose.yml`. A real, previously-undiscovered `.dockerignore` gap
was found and fixed in this phase (see "Real bugs found and fixed" below) — every image build before this
fix sent the entire monorepo, including `.venv`/`node_modules` (~700MB), as build context on every build.

### Demo data
`apps/api/scripts/seed_demo_org.py` (`make demo-seed`) creates a fictional "Opero Demo Co" organization,
uploads and processes 3 fictional knowledge documents, ingests the 12 mock emails, runs the full pipeline
on all of them against the live model, and generates a daily report. Run against the real stack for this
phase's verification — see "Verified against the real stack" below for actual output.

### Tests
56 tests total in `apps/api` (46 deterministic + 10 live-model, marker-separated per
[TESTING_GUIDE.md](TESTING_GUIDE.md)), all passing, plus all pre-existing Phase 2 tests still passing
unmodified. New coverage: document upload/dedup/validation/org-isolation, knowledge search/RAG (including
the insufficient-evidence short-circuit and a real grounded-answer-with-citation test), the full email
pipeline (including a real prompt-injection attack test against the live model), leads/tasks CRUD and org
isolation, report generation determinism and idempotency, and the approval workflow's simulated-send path
(dispatch, edited-payload precedence, rejection, and unrecognized-action-type no-op).

## Real bugs found and fixed during this phase (not just written around)

1. **Postgres ENUM value case bug**: a migration added the `MOCK` email/integration provider value as
   lowercase `'mock'` (the enum's `.value`), but SQLAlchemy's `Enum` type actually stores the Python member
   **name** (`'MOCK'`), matching the existing `GMAIL` pattern — caused a real
   `InvalidTextRepresentationError` on first live query. Fixed non-destructively via a corrected `ALTER
   TYPE` against the live dev DB (real test data existed) plus a fix to the migration file for fresh
   installs.
2. **`add_column` doesn't auto-create a referenced Postgres ENUM type** the way `create_table` does — two
   new columns (`documents.processing_status`, `tasks.priority`) failed with `UndefinedObjectError` until
   the migration explicitly created the enum type first.
3. **Unnamed foreign-key constraints can't be dropped by name** — three `create_foreign_key(None, ...)`
   calls left Postgres to auto-name the constraint, which then couldn't be referenced in `downgrade()`.
   Fixed by naming both directions explicitly; required a manual `RENAME CONSTRAINT` against the already-
   migrated dev DB to reconcile state.
4. **Model returns confidence as 0–100 instead of 0–1**: a live `qwen2.5:7b-instruct` call returned
   `confidence: 95` despite the schema and prompt specifying a 0.0–1.0 float — a real, live-observed model
   quirk. Fixed with a shared, reusable Pydantic `Confidence` type
   (`app/schemas/common.py`) that normalizes >1 values, still bounded so genuinely invalid values fail
   loudly rather than being silently coerced.
5. **Model unreliably omits already-known sender info**: `LeadExtractionModelResponse` originally asked the
   model to "extract" `contact_name`/`contact_email` from the email; a live test showed it correctly
   extracted `company` and `requested_service` while returning both contact fields `null` — even though the
   sender's name/email were literally given in the prompt. Root-caused as a design flaw (asking a model to
   re-derive data already deterministically available), not a prompting problem — fixed by parsing the
   sender header deterministically (`app/services/email_headers.py`) and removing the fields from the
   model's schema entirely.
6. **Celery worker cross-task event-loop bug**: the same "attached to a different loop" class of bug
   documented in Phase 2's `tests/conftest.py` resurfaced in the long-running `api-worker` process — the
   *second* document/email processed by the same worker process failed, because the module-level DB engine's
   connection pool persisted across `asyncio.run()` calls. Fixed with the same disposal pattern, wrapped
   around every task (`app/workers/tasks.py::_run_and_dispose`).
7. **Missing repo-root `.dockerignore`**: every `docker compose build` for `api`/`api-worker`/`dashboard`
   was sending the *entire* monorepo — including `apps/api/.venv` (227MB) and `apps/web/node_modules`
   (441MB) — as build context, since `infra/docker-compose.yml`'s `api`/`api-worker` services build from
   the repo root (needed to `pip install -e ../../services/*`). This is what made the first `api-worker`
   build look hung rather than merely slow (700MB+ over the Docker socket into the Colima VM on every
   build). Root-caused by literally watching `docker compose build --progress=plain`'s "Sending build
   context to Docker daemon" counter climb past 260MB and continuing, then confirming no `.dockerignore`
   existed anywhere in the repo. Fixed by adding one at the repo root; a subsequent `docker compose build
   api` after this fix completed instantly (fully cached layers, correct minimal context).
8. **Transient pip network timeouts inside the build VM**: even after the context-size fix, one build
   attempt failed outright with `ReadTimeoutError` from `files.pythonhosted.org` mid-download after ~27
   minutes. Made the Dockerfile's `pip install` resilient (`--retries 10 --timeout 120`) rather than just
   retrying blindly; the next attempt succeeded in a few minutes.
9. **`MINIO_ENDPOINT` wrong inside the container network**: both `api` and `api-worker` inherited
   `MINIO_ENDPOINT=localhost:9000` from the host-oriented `apps/api/.env` via `env_file:`, but neither
   service's `environment:` override block set it to the in-network hostname the way `DATABASE_URL`/
   `REDIS_URL`/`OLLAMA_BASE_URL` already were. Every document upload through the real containerized stack
   was silently retrying forever (`MaxRetryError: Connection refused` to `localhost:9000`, which inside a
   container is the container's own loopback, not the host). Caught by watching `docker logs
   opero-ai-api-worker-1` during Docker Compose health verification, not by unit tests (which run against
   the host venv, where `localhost:9000` is correct). Fixed by adding `MINIO_ENDPOINT: minio:9000` to both
   services' `environment:` blocks in `infra/docker-compose.yml`; re-verified with a real document upload
   through the running container going `uploaded → ready` end to end.

## Verified against the real stack, not just unit-tested

- Every new service was smoke-tested against live Postgres+pgvector, live Redis, live MinIO, and live
  Ollama (`qwen2.5:7b-instruct` + `nomic-embed-text`) throughout development — not mocked.
- **Full containerized stack**, not just host-venv tests: rebuilt `api`, `api-worker`, and `dashboard`
  images; brought up the real `docker compose` stack; registered a fresh organization through the real
  containerized API; ingested the mock inbox; enqueued a real `process_email` Celery task through Redis;
  confirmed the real `api-worker` container picked it up, called the real Ollama model twice, and completed
  in ~11 seconds — verified via `docker logs`, not inferred. The processed message was the deliberate
  prompt-injection scenario, and it was correctly classified `category=spam, possible_prompt_injection=true,
  confidence=0.95, requires_reply=false` (so no reply was proposed) through the real containerized path.
- **Demo organization fully seeded against the real stack**: "Opero Demo Co" — 3 knowledge documents
  uploaded and embedded, all 12 mock emails ingested and classified, 1 lead and 2 tasks extracted, 7 reply
  drafts proposed as pending approvals, one approved end-to-end (confirmed `simulated_send_result`
  populated), and a daily report generated with correct deterministic metrics and a coherent AI narrative.
  A `POST /v1/knowledge/ask` question against the seeded refund-policy document returned the correct answer
  ("30 days") with a correctly-ranked citation.
- **A real prompt-injection attack, not simulated**: a document containing a planted secret value and an
  embedded instruction to leak it was uploaded, retrieved into RAG context by the real pipeline, and the
  live model did not comply — verified by an automated test
  (`tests/test_prompt_injection_defense.py`), not a one-off manual check.
- All 7 new/updated frontend pages render (200) against the real containerized dashboard and call the real
  containerized API.

## In Progress

Nothing left mid-implementation — every item started in this phase was either finished and verified, or
explicitly deferred (below), not left half-built.

## Pending (explicitly deferred, not forgotten)

- **Real Gmail/Outlook connection to the Phase 3 pipeline**: mock connector only, per the founder's explicit
  instruction. The pipeline is provider-agnostic, so wiring in Phase 2's existing `gmail_sync.py` is
  additive, not a rewrite.
- **Real (non-simulated) email sending**: `send_email_reply` approval always calls `MockEmailConnector`.
- **RBAC role differentiation testing**: every registered user is currently their org's sole `owner` — no
  invite/add-member endpoint exists, so there's no code path to test a `member`-role user being correctly
  denied a `.write` action, even though the permission checks themselves are enforced everywhere.
- **Scheduled/automatic daily report generation**: currently on-demand only; the underlying function is
  already idempotent per (org, date), so a Celery Beat job is a small addition, not built this phase.
- **Playwright/browser E2E tests**: no headless browser available in this development environment (same
  limitation as Phase 2). Frontend correctness verified via typecheck/lint (clean) and real HTTP-level
  checks against the containerized stack, not an actual browser session.
- **Document versioning**: a re-uploaded changed file creates an independent `Document` row rather than a
  new version of the same logical document; `Document.version` exists in the schema but nothing increments
  it yet.
- **Task completion timestamps**: `Task` has no `completed_at` column, so the daily report's
  `tasks_completed` metric is a point-in-time snapshot of all currently-done tasks, not "completed today" —
  documented as a known limitation rather than silently treated as date-scoped.

## Known Issues / Technical Debt

- The `test_oauth_state.py::test_state_rejects_tampered_token` test (Phase 2, unmodified in Phase 3) failed
  once during a full-suite run in this phase but passed both in isolation and on an immediate full-suite
  rerun — order-dependent or timing-sensitive flake, not a reproducing bug. Not chased further without more
  evidence; noted here rather than hidden.
- Classification/extraction quality is real live-model output from a 7B local model, not scripted — occasionally
  imperfect (see [EMAIL_INTELLIGENCE.md](EMAIL_INTELLIGENCE.md) "Known limitations"). This is an honest
  capability limit, not a bug.
- The prompt-injection regex scanner is English-only and pattern-based — a detector, not the primary
  defense (see [PROMPT_INJECTION_DEFENCE.md](PROMPT_INJECTION_DEFENCE.md)).
- `token_estimate` on document chunks is a `len // 4` heuristic, not a real tokenizer count.
- Carried over from Phase 2, still true: rate-limit threshold untuned, dashboard auth guard is client-side
  only, Ollama's model isn't bundled in the image (manual pull required on first run).

## Next Milestone

Per the founder's phased plan: connecting a real mailbox (Gmail/Outlook) to the Phase 3 pipeline as a
second producer of `EmailMessage` rows alongside the mock connector, a real (non-simulated) send path once
that's trusted, member-role user management (invite/add-member), and scheduled daily report generation.
