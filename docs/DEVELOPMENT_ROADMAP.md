# Development Roadmap

Scoped to get from zero code to a working MVP pilot (per [MVP_SCOPE.md](MVP_SCOPE.md)), on the stack in
[TECHNOLOGY_STACK.md](TECHNOLOGY_STACK.md) and architecture in
[SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md). Timeframes assume a small founding engineering team
(2–4 engineers); adjust if headcount differs.

**Note on phase numbering:** the founder's Phase 2 request ("Project Foundation and Development Scaffolding" —
RBAC, audit logging, the approval workflow, the AI provider abstraction, connector interfaces) cuts across the
phases below rather than mapping to a single one. It has been folded into, and hardens, Phase 0 and the early
part of Phase 1. Current status is tracked in [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md), which is the
authoritative "what's actually done" document — this roadmap is the plan, not the live status.

## Phase 0 — Foundations (Weeks 1–2)

**Goal:** an empty-but-real skeleton every subsequent phase builds on, not a throwaway prototype.

- Sprint 1 (Week 1): repo structure (monorepo: `apps/web`, `apps/api`, `services/ai-engine`, `services/worker`,
  `services/connectors`, `packages/*`), Docker Compose for local dev (Postgres+pgvector, Redis, MinIO, Temporal
  dev server), CI pipeline (lint, type-check, test on PR).
- Sprint 2 (Week 2): AuthN/Z (local email/password for MVP, `Organization`/`Role`/`Permission`/`UserRole` models),
  base OpenTelemetry wiring, AI provider interface with an Ollama implementation.

**Milestone 1:** a developer can run the full stack locally, log in, and hit a health-checked API that round-trips
a call through the model provider.

## Phase 1 — Core Loop: AI Sales & Operations Assistant MVP (Weeks 3–8)

- Sprint 3 (Week 3): Gmail OAuth connection + incremental sync; email data model in Postgres.
- Sprint 4 (Week 4): Knowledge Engine — document upload, chunking, embedding, pgvector storage; basic retrieval
  endpoint.
- Sprint 5 (Week 5): Agent Orchestrator v1 — context assembly (thread + knowledge retrieval), model call with
  structured draft+citation output, confidence flagging.
- Sprint 6 (Week 6): Execution Engine — `HandleIncomingEmail` Temporal workflow with approval-gate signal wait;
  dashboard views for triage inbox + draft approval + send.
- Sprint 7 (Week 7): Lead + Task entities (per
  [SYSTEM_ARCHITECTURE.md §8](SYSTEM_ARCHITECTURE.md#8-core-data-model-mvp-entities)) — lead
  creation/update from thread classification, task creation from detected commitments, dashboard views for both.
- Sprint 8 (Week 8): `CheckStaleThreads` (follow-up reminders) and `GenerateDailyReport` scheduled Temporal
  workflows; dashboard views for follow-ups and the day-end report.

**Milestone 2 (MVP feature-complete):** end-to-end flow from the MVP doc works for a single connected Gmail
account: new mail → triage → grounded draft → human approval → send → lead/task creation where applicable →
follow-up reminders → day-end report, all logged.

## Phase 2 — Memory & Reliability Hardening (Weeks 9–12)

- Sprint 9: Long-term facts memory (episodic table + extraction step that detects statement-worthy facts from
  conversations/rejections).
- Sprint 10: Memory Service unification — single retrieval interface fanning out across short-term/episodic/
  semantic/long-term layers (per architecture doc §2.3).
- Sprint 11: Audit/action-log dashboard view built directly on OpenTelemetry trace data (not a parallel log table).
- Sprint 12: Evaluation pipeline v1 — held-out (email, ideal-reply) set, scoring harness run on every prompt/model
  change.

**Milestone 3:** the metrics in [PRODUCT_REQUIREMENTS.md §8](PRODUCT_REQUIREMENTS.md#8-success-metrics-v1--mvp)
are actually measurable from real data, not anecdote.

## Phase 3 — Pilot & Trust-Building (Weeks 13–16)

- Sprint 13–14: Onboard 3–5 pilot users (target segment per PRD: agencies/real estate/e-commerce/service
  businesses, 5–50 employees); daily monitoring of draft-acceptance rate, error rate, latency.
- Sprint 15: Iterate on prompt/retrieval quality based on pilot rejection-reason data.
- Sprint 16: Decide, with real data, whether to introduce a "trusted sender" approval fast-path (open decision
  from architecture doc §10.2).

**Milestone 4 (MVP validated):** draft-acceptance rate ≥ 90% sustained across pilot users for two consecutive
weeks — the PRD's explicit success bar. This is the gate for moving to Phase 4, not a calendar date.

## Phase 4 — Expansion Wedge #2: External CRM/Calendar Integration (Weeks 17–22, contingent on Milestone 4)

The MVP already ships built-in lead/task/follow-up/report features natively (Phase 1). Phase 4 is specifically
about *syncing outward* to systems pilot customers already use:

- External CRM sync (HubSpot/Salesforce/Pipedrive — whichever the pilot cohort's data shows is most common) —
  read for grounding context, write to push native lead records outward, behind the same approval-gate pattern
  already built.
- Calendar read/write follows the same adapter pattern once CRM sync proves the integration-adapter approach
  scales — this is the payoff of building leads/tasks as native entities behind a clean interface in Phase 1
  rather than hardcoding them to one external system.

## Explicit Non-Milestones (do not schedule until triggered by data, not calendar)

- Kubernetes migration — triggered by measured multi-node scheduling need, not a phase number.
- Owned GPU hardware — triggered by rented-inference utilization data crossing the cost-parity line.
- Multi-agent / Slack-team-communication surface — triggered by pilot users explicitly asking for it.
- Fine-tuning — triggered by the evaluation pipeline (Phase 2) showing retrieval/prompting has plateaued.

## Roadmap Summary

| Phase | Weeks | Milestone |
|---|---|---|
| 0 — Foundations | 1–2 | Local stack running, auth + model router working |
| 1 — Core Loop MVP | 3–8 | Feature-complete AI Sales & Operations Assistant: email, leads, tasks, follow-ups, reports |
| 2 — Memory & Reliability | 9–12 | Metrics measurable, audit log real, eval pipeline live |
| 3 — Pilot | 13–16 | ≥90% draft-acceptance sustained across pilot users |
| 4 — External CRM/Calendar Expansion | 17–22 | Outward sync to external tools, gated on Phase 3 success |

## Open Decisions

1. Confirm team size/composition — the sprint durations above assume 2–4 engineers; fewer people means longer
   phases, not fewer sprints.
2. Confirm pilot user sourcing — do we already have 3–5 candidate users lined up for Phase 3, or does that
   sourcing need to start now, in parallel with Phase 0–1 engineering?
