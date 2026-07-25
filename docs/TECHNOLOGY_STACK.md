# Technology Stack

Every pick below states the alternative considered and why it lost, per the "challenge the decision" mandate. Every
component is chosen to be replaceable — no pick here should require rewriting another layer if it's swapped later.

## 1. Model Serving & Inference

**Decision (founder-confirmed):** self-hosted, open-weight models only — no paid closed-inference APIs (no
OpenAI, Anthropic, Gemini) — served behind an internal **model-provider interface**
(see [AI_ARCHITECTURE.md](AI_ARCHITECTURE.md)) that the rest of the system calls through a single interface:
`generate()`, `generate_structured()`, `embed()`, `health()`. No orchestration/memory/execution code talks to a
model SDK directly — only the provider layer does, and the provider implementation is swappable per deployment.

| Layer | Choice | Alternative considered | Why |
|---|---|---|---|
| Local inference runtime (MVP) | **Ollama** | vLLM, TGI | Founder-mandated starting runtime: zero-ops local serving (single binary, model pulls via `ollama pull`), ideal for a single-company self-hosted deployment where standing up a GPU-serving cluster is out of scope for Phase 2. |
| Reasoning/planning model | Qwen2.5 (14B or 32B, whichever the deployment's hardware fits) served via Ollama | Llama 3.x, Mistral, DeepSeek, GLM | Ollama's library has well-maintained Qwen2.5-instruct quantizations; the provider interface makes this a config value, not a code dependency |
| Embeddings | `nomic-embed-text` or `bge-m3` via Ollama | OpenAI/Voyage embeddings (rejected — paid, closed) | Open-weight, self-hostable via the same Ollama runtime as generation, no second serving stack needed for MVP |
| Future inference runtime | vLLM (OpenAI-compatible API surface) behind the same provider interface | — | Ollama is right for single-company self-hosted MVP; vLLM's throughput/concurrency story matters once serving many organizations or many concurrent agents — the provider interface is what makes that swap a config change, not a rewrite (docs/AI_ARCHITECTURE.md). |

**Provider-interface requirement:** every call into the model layer goes through the abstract `ModelProvider`
interface (`services/ai-engine`). Swapping Ollama for vLLM, or swapping the specific open-weight model, is a
config change — this is a hard architectural acceptance criterion for Phase 2, not a nice-to-have.

**Standing decision:** a closed-model provider tier is **not** implemented in Phase 2. The provider interface
does not forbid one being added later (that's the point of an interface), but per the founder's explicit AI model
policy, no closed/paid inference is wired up in this phase.

## 2. Backend / Orchestration

| Layer | Choice | Alternative | Why |
|---|---|---|---|
| Core API + orchestration language | Python 3.12, FastAPI | Node/NestJS | Agent orchestration, RAG, and model-serving tooling (LangGraph-equivalent patterns, vLLM client, embedding pipelines) are Python-native; avoids a translation layer between "AI code" and "product code" |
| Background jobs (embedding a doc, sending a digest, polling for mail) | **Redis + Celery** | RQ, Dramatiq | Founder-specified default; Celery's task routing, retries, and periodic-task (`celery beat`) support cover the MVP's background-job needs (`services/worker`) without a bespoke queue |
| Durable, multi-step, approval-gated workflows (send email → wait for human approval → send → confirm) | Temporal | Doing this in Celery | **Kept, with justification, per the "explain why before changing it" rule:** Celery tasks are fire-and-forget with no first-class "pause and wait for an external signal for days" primitive — building approval-gate semantics on top of Celery means hand-rolling the durable-state-machine behavior Temporal already provides (retry policy, resumable wait, full execution history). This is a different problem shape than "run this background job," so both are kept: Celery for jobs, Temporal for the approval-gated execution engine described in [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md). |

## 3. Data Layer

| Layer | Choice | Alternative | Why |
|---|---|---|---|
| Primary datastore | PostgreSQL 16 | MongoDB | Relational integrity matters for audit logs, permissions, and structured memory facts; Postgres also gives us... |
| Vector store | **pgvector** (on the same Postgres instance) for MVP | Dedicated vector DB (Qdrant/Weaviate) | One less service to operate at MVP scale; pgvector is sufficient until embedding volume/query latency proves otherwise. Migration path to Qdrant is isolated behind the memory service's retrieval interface — not a rewrite. |
| Object storage | MinIO (self-hosted, S3-compatible) | AWS S3 directly | Keeps "self-hosted, no vendor lock-in" consistent with the model-serving philosophy; API is S3-compatible so a managed S3 swap later is trivial |
| Cache | Redis | — | Session state, rate limiting, hot memory reads |

## 4. Frontend

| Layer | Choice | Alternative | Why |
|---|---|---|---|
| Framework | Next.js (React, TypeScript) | Remix, plain Vite SPA | Team familiarity assumption + SSR for the dashboard's data-heavy views; large ecosystem for auth/dashboard components |
| Styling/UI | Tailwind CSS + shadcn/ui | MUI | Fast to build a clean, non-generic dashboard without fighting a heavy component library's theming |
| State/data fetching | TanStack Query | Redux | Server-state-heavy app (inbox, drafts, audit log) — TanStack Query fits better than a global client store |

## 5. Integrations (MVP)

| Integration | Method |
|---|---|
| Gmail | Gmail API via OAuth 2.0, incremental sync using `historyId` (not full re-poll) |
| Document ingestion | Direct upload (PDF/Markdown/Docx) parsed via `unstructured` library → chunked → embedded via BGE-M3 |

## 6. Auth & Security

**Decision (founder-confirmed, supersedes the earlier Auth0-first draft of this document):** local email/password
authentication is the primary AuthN mechanism for the MVP. This is a deliberate change from this document's
original recommendation (OIDC via Auth0) — the founder's rationale is that a single-company self-hosted
deployment shouldn't have a hard external dependency (Auth0 account, network reachability to a third-party IdP)
just to log in on day one. The auth layer is designed so OIDC/SSO can be added as an **additional** login method
later without a rewrite (see [SECURITY_MODEL.md](SECURITY_MODEL.md) for the concrete interface).

| Layer | Choice | Why |
|---|---|---|
| AuthN (MVP) | Local email/password, bcrypt-hashed, JWT session tokens issued by our own API | No external dependency to stand up a single self-hosted deployment; standard, well-understood |
| AuthN (future) | OIDC/SSO (Auth0 or self-hosted Keycloak) as an additional login method | Enterprise customers will require SSO; the auth layer is interface-shaped so this is additive, not a replacement |
| AuthZ | Role-based access control: `Role` + `Permission` + `UserRole` as first-class tables (not a hardcoded enum) — see [DATABASE_DESIGN.md](DATABASE_DESIGN.md) | Normalized RBAC scales to per-resource permissions later without a schema rewrite; still seeded with only 2-3 simple roles for MVP so this isn't over-engineered in practice |
| Secrets | Environment-based + a secrets manager (Doppler or self-hosted Vault) before any production deploy | Never commit secrets; OAuth tokens for connected Gmail accounts and user password hashes are the most sensitive data in this system |

**Superseded open decision:** the original "Auth0 vs. Keycloak" question is moot for Phase 2 — neither is wired
up yet. It becomes live again whenever SSO is actually prioritized (see
[DECISIONS_REQUIRED_FROM_FOUNDER.md](DECISIONS_REQUIRED_FROM_FOUNDER.md)).

## 7. Observability & Ops

| Layer | Choice | Why |
|---|---|---|
| Logging/tracing | OpenTelemetry → Grafana + Loki + Tempo | Standard, open-source, and every agent "reasoning trace" required by the PRD's auditability goal is a trace/span, not a bespoke logging table |
| Metrics | Prometheus + Grafana | Standard pairing with the above |
| Deployment | Docker Compose for MVP → Kubernetes when multi-node/GPU-scheduling need appears | **CTO push-back:** standing up Kubernetes before there's more than one service instance to schedule is pure overhead. Compose first; the containers are the same either way, so this isn't a rewrite later, just an orchestrator swap. |
| CI/CD | GitHub Actions | Ubiquitous, sufficient for MVP; revisit only if build/deploy complexity outgrows it |

## 8. Summary Table (at a glance)

```
Frontend:      Next.js + TypeScript + Tailwind + shadcn/ui
Backend:       Python 3.12 + FastAPI
Orchestration: Temporal (durable, approval-gated workflows) + Celery/Redis (background jobs)
Models:        Qwen2.5 via Ollama (local), behind an internal model-provider interface (services/ai-engine)
Embeddings:    nomic-embed-text / bge-m3 via Ollama
Data:          PostgreSQL 16 + pgvector, Redis (cache/queue), MinIO (object storage)
Auth:          Local email/password (MVP) + OIDC/SSO interface for later
Observability: OpenTelemetry + Grafana/Loki/Tempo/Prometheus
Infra:         Docker Compose (MVP) -> Kubernetes (post-MVP scale trigger)
CI/CD:         GitHub Actions
```

## 9. Open Decisions

See [DECISIONS_REQUIRED_FROM_FOUNDER.md](DECISIONS_REQUIRED_FROM_FOUNDER.md) for the current, consolidated list —
this section previously duplicated it and drifted out of sync as decisions were made.
