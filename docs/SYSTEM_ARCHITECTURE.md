# System Architecture

Scope: architecture sufficient to build the MVP (email agent) described in
[MVP_SCOPE.md](MVP_SCOPE.md), designed so the deferred capabilities (CRM, calendar, multi-agent) are
additive — new tool adapters and workflow definitions, not core rewrites.

## 1. Component Overview

```
                                   ┌─────────────────────┐
                                   │   Web Dashboard      │
                                   │   (Next.js)          │
                                   └──────────┬───────────┘
                                              │ HTTPS/REST + WebSocket (live status)
                                   ┌──────────▼───────────┐
                                   │     API Gateway       │
                                   │  (FastAPI, AuthN/Z)   │
                                   └──────────┬───────────┘
                    ┌─────────────────────────┼─────────────────────────┐
                    │                          │                          │
          ┌─────────▼─────────┐    ┌───────────▼───────────┐   ┌─────────▼─────────┐
          │  Agent Orchestrator │    │   Knowledge Engine     │   │   Memory Service    │
          │  (planning loop)    │◄──►│   (ingestion + RAG)    │◄─►│  (short/long-term)  │
          └─────────┬─────────┘    └───────────┬───────────┘   └─────────┬─────────┘
                    │                          │                          │
          ┌─────────▼─────────┐    ┌───────────▼───────────┐   ┌─────────▼─────────┐
          │   Model Router      │    │   PostgreSQL +         │   │   PostgreSQL       │
          │  (vLLM/Qwen/Llama)  │    │   pgvector             │   │   (facts, episodes)│
          └─────────────────────┘    └────────────────────────┘   └─────────────────────┘
                    │
          ┌─────────▼─────────┐
          │  Execution Engine   │
          │  (Temporal workers) │
          └─────────┬─────────┘
                    │
          ┌─────────▼─────────────────────────────┐
          │   Tool/Integration Adapters              │
          │   Gmail API │ (future: CRM, Calendar)    │
          └─────────────────────────────────────────┘

          Cross-cutting: Audit/Logging (OpenTelemetry) · Notification Service · Secrets Manager
```

## 2. Components in Detail

### 2.1 API Gateway
Single entry point for the dashboard. Owns AuthN (OAuth2/OIDC), request-level AuthZ (organization role check),
rate limiting, and request tracing (injects a trace ID that flows through every downstream call — this is what
makes the "reasoning trace" audit requirement in the PRD possible end to end).

### 2.2 Agent Orchestrator (Planning Engine)
The core loop. Responsibilities:

1. Receive a trigger (new email arrived, scheduled digest time, user asks a question in-dashboard).
2. Assemble context: pull relevant short-term memory (recent thread), query the Knowledge Engine for grounding
   docs, query long-term Memory Service for relevant facts/prior decisions.
3. Call the Model Router with the assembled context + available tools (send_draft, search_knowledge,
   recall_memory, etc.) — this is the **Reasoning Engine** function, expressed as a single well-defined interface
   rather than a separate service, since at MVP scale a distinct microservice for it is unwarranted complexity.
4. Decompose the goal into steps if the model's response indicates multi-step work is needed (**Task
   Decomposition**) — represented as a Temporal workflow definition, not a bespoke in-process state machine, so
   retries/resumption are free.
5. For any step tagged irreversible (send email, delete record), emit an **approval-required** event instead of
   executing directly; execution resumes only after the Execution Engine receives approval.
6. Write the full reasoning trace (inputs, retrieved context, model output, decision) to the audit log before
   taking any action — auditability is not a wrapper around the loop, it's a required step inside it.

**Confidence scoring / hallucination reduction:** every drafted reply must cite which memory/knowledge chunks it
was grounded in. If the model produces a claim not traceable to a retrieved chunk or the raw email thread, the
orchestrator flags the draft as **low-confidence** in the dashboard rather than silently shipping it. This is a
prompt-and-retrieval-design concern in MVP (structured citation requirement in the tool-response schema), with a
dedicated evaluation pipeline (see §2.6) planned for Phase 2 to make this measurable rather than heuristic.

### 2.3 Memory Architecture

| Layer | Storage | Lifetime | Example |
|---|---|---|---|
| Short-term (working) | In-process/Redis, scoped to current thread | Duration of the conversation/thread | Last 10 messages in the current email thread |
| Episodic | Postgres table (structured: actor, action, outcome, timestamp) | Persistent | "On 2026-06-01, agent drafted a refund reply, user rejected it because policy had changed" |
| Semantic / company knowledge | pgvector (embeddings) + Postgres (source metadata) | Persistent, versioned | Ingested policy docs, FAQ, pricing sheet |
| Long-term facts | Postgres, structured key-facts table, populated by the orchestrator when it detects a stated fact worth retaining | Persistent | "Our refund window is 30 days" |

Retrieval at inference time is a single Memory Service call that fans out to all four layers and returns a ranked,
deduplicated context bundle — the orchestrator does not know or care which layer a fact came from, which is what
keeps this swappable (e.g., pgvector → Qdrant later touches only the Memory Service's internals).

### 2.4 Knowledge Engine
Ingestion pipeline: upload → parse (`unstructured` library) → chunk (semantic chunking, ~512 tokens) → embed
(BGE-M3) → store (pgvector) with source + version metadata. Re-ingestion on document update creates a new version
rather than overwriting, so the audit trail can show which document version grounded a given past decision.

### 2.5 Execution Engine
Built on Temporal. Each unit of external-world work (send an email, ingest a document, run a scheduled digest) is
a workflow with explicit retry policy, timeout, and a durable execution history. This directly satisfies the
brief's requirement for retry logic and error recovery without hand-rolled state machines. Tool adapters (Gmail
today; CRM/Calendar later) are plain activities registered with the workflow — adding a new tool is adding a new
activity + a router entry, not touching the orchestrator's core loop.

### 2.6 Evaluation Pipeline (Phase 2, designed for now)
A held-out set of historical (email, ideal-reply) pairs used to score draft quality on every model/prompt change,
so "we changed the prompt" doesn't ship on vibes. Not required to build MVP v1's first working loop, but the
audit-log schema and citation requirement above are designed so this pipeline can be built directly on top of
existing data — it is not a bolt-on data-collection project later.

### 2.7 Model Router
Single internal interface every other component calls through. Config maps a task tier
(`reasoning` / `fast` / `embedding`) to a concrete backend (model + endpoint + auth). Swapping models, or adding a
closed-model tier per the PRD's open decision, is a config change. See
[TECHNOLOGY_STACK.md §1](TECHNOLOGY_STACK.md#1-model-serving--inference).

### 2.8 Notification Service
Delivers "draft ready for review" / "approval needed" notifications. MVP: in-dashboard + email digest. Slack/Teams
are additive channels behind the same interface — not built for MVP per [MVP_SCOPE.md](MVP_SCOPE.md).

### 2.9 Audit & Observability
Every orchestrator decision, tool call, and Temporal workflow step emits an OpenTelemetry span. The dashboard's
"action log" (MVP feature 7) is a read view over these traces, not a separate hand-maintained log table — this
guarantees the audit view can never drift from what actually executed.

## 3. Data Flow: "New Email Arrives" (concrete walkthrough)

1. Gmail push notification (or poll fallback) → API Gateway → enqueues a Temporal workflow: `HandleIncomingEmail`.
2. Workflow activity 1: fetch full thread via Gmail adapter.
3. Workflow activity 2: call Memory Service for context bundle (short-term thread history + relevant semantic
   knowledge + relevant long-term facts).
4. Workflow activity 3: call Agent Orchestrator with (thread, context bundle) → Orchestrator calls Model Router →
   model returns a structured response: `{draft_reply, citations[], confidence, requires_approval: true}`.
5. Workflow activity 4: persist draft + reasoning trace; emit notification.
6. Workflow pauses (Temporal signal wait) until user approves/edits/rejects in dashboard.
7. On approval: workflow activity 5 sends via Gmail adapter, records outcome in episodic memory, closes workflow.
8. On rejection: reason captured, stored in episodic memory, workflow closes without sending.

## 4. Security Model (MVP-relevant subset; full treatment is a Phase 7 deliverable)

- OAuth tokens for connected Gmail accounts are the highest-sensitivity secret in the system — encrypted at rest,
  scoped to minimum required Gmail API scopes, never logged.
- All irreversible actions (send, delete) require the approval gate described above — this is a security control
  as much as a trust-building one.
- Every request is tenant-scoped at the database-query level (organization_id on every row) — no cross-tenant data
  path exists structurally, not just by application-logic convention.
- Prompt-injection surface: email content is untrusted input reaching the model. The tool-calling schema
  constrains what the model can *do* (a fixed set of typed tools, not arbitrary code execution), which bounds the
  blast radius of injected instructions in an email body regardless of what the model is convinced to "want" to do.

## 7. Deployment Model

**v1 target: single-company, self-hosted deployment** (founder-confirmed, see
[MVP_SCOPE.md §4](MVP_SCOPE.md#4-deployment-model-founder-confirmed)). One full stack (per
[TECHNOLOGY_STACK.md](TECHNOLOGY_STACK.md)) per customer, not a shared multi-tenant cluster. Practically:

- Every table still carries a `organization_id` column and every query is organization-scoped, even though v1 only
  ever has one organization per deployed instance. This costs nothing now and means the later move to multi-tenant
  SaaS is a hosting/topology change (many customers' organization rows in one shared database/cluster) rather than
  an application rewrite.
- Configuration (model endpoints, Gmail OAuth client, secrets) is per-deployment via environment variables /
  the secrets manager — no hardcoded assumption of a single global instance.
- Deployment artifact is the same Docker Compose stack used in local dev (see
  [TECHNOLOGY_STACK.md §7](TECHNOLOGY_STACK.md#7-observability--ops)); "self-hosted" for a pilot customer
  means standing up that same Compose stack on infrastructure they or Opero AI control.

**Open decision (carried from PRD):** whether Opero AI operates these self-hosted instances on the customer's
behalf (managed self-hosted) or the customer's own infra team runs them — affects support tooling (e.g., whether
we need remote upgrade/monitoring tooling from day one) and should be settled before the first pilot deploy.

## 8. Core Data Model (MVP entities)

Beyond the email/knowledge/memory entities described above, the AI Sales & Operations Assistant role requires
these first-class, organization-scoped tables:

| Entity | Key fields | Notes |
|---|---|---|
| `lead` | organization_id, contact_name, contact_email, source_thread_id, status (new/contacted/awaiting_reply/stale/won/lost), last_activity_at | Created/updated by the orchestrator when a thread is classified as lead-like; a native record, not a synced copy of an external CRM object |
| `follow_up` | organization_id, lead_id or thread_id, due_at, reason, resolved_at | Produced by a scheduled Temporal workflow (`CheckStaleThreads`) that scans for leads/threads with no reply after N days |
| `task` | organization_id, title, source_thread_id (nullable), assignee, due_at, status (open/done) | Created either by the orchestrator (detected commitment in an email) or directly by the user in the dashboard |
| `daily_report` | organization_id, report_date, emails_handled, drafts_pending, leads_created, follow_ups_overdue, tasks_completed | Generated by a scheduled Temporal workflow (`GenerateDailyReport`) at a configurable end-of-day time; read-only once generated, stored rather than recomputed on view |

These follow the same pattern as email handling: a Temporal workflow per generating event (new thread classified,
daily cron fire), writing to Postgres, with every write emitting the same audit trace used elsewhere in the
system. No separate "CRM engine" or "reporting engine" service exists at MVP scale — these are workflows and
tables inside the same Execution Engine and data layer already described, which is what keeps the system
modular without being over-decomposed into services nobody needs yet.

## 9. What This Architecture Deliberately Defers

- Multi-agent inter-agent communication protocol — not needed until there's more than one specialized agent role;
  premature to design now per [MVP_SCOPE.md](MVP_SCOPE.md).
- Kubernetes / multi-region — Docker Compose is sufficient until real load data says otherwise (see
  [TECHNOLOGY_STACK.md §7](TECHNOLOGY_STACK.md#7-observability--ops)).
- Fine-tuning / continual learning — feedback (rejections + reasons) is captured from day one specifically so
  this is a data-availability non-issue whenever it's prioritized.

## 10. Open Decisions

1. Push (Gmail Pub/Sub webhook) vs. poll for new-mail detection — recommend starting with polling (simpler,
   no public webhook endpoint needed for MVP) and moving to push once latency requirements demand it.
2. Whether the approval gate is per-message or has a "trusted sender" fast-path — recommend deferring: start
   100% human-in-the-loop, introduce fast-path once draft-acceptance data supports it.
3. Who operates self-hosted pilot deployments — carried from §7 above.
