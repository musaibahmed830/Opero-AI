# MVP Scope

**Role: AI Sales & Operations Assistant** (founder-confirmed, see
[PRODUCT_REQUIREMENTS.md §3a](PRODUCT_REQUIREMENTS.md#3a-first-ai-role-founder-confirmed)).

**Principle:** the brief asks for an employee that reads email, manages CRM, handles calendars, reads documents,
generates reports, and talks to the team — all at once. A real employee doesn't onboard into six departments in
their first week, and neither should this. The MVP is one role, done reliably, with an architecture that doesn't
have to be rewritten to add the rest.

The founder-confirmed job description for this role is broader than "read email, draft replies": it also owns
lightweight lead tracking, follow-up reminders, task management, and a day-end report — because for the target
segment (agencies, real estate, e-commerce, 5–50 employees) a missed follow-up or forgotten task is the actual
pain, not just slow replies. The distinction that keeps this scoped, not scope-creeping back into "do everything":
**these are built-in, native features of the Assistant — not integrations with a third-party CRM/task tool.**
Syncing to HubSpot/Salesforce/Asana is still deferred (see "Explicitly out of scope" below); a customer's leads
and tasks live in Opero AI itself for v1.

## 1. MVP Feature List

### In scope

| # | Feature | Detail |
|---|---|---|
| 1 | **Inbox ingestion** | Connects to Gmail/Google Workspace via OAuth; syncs inbox incrementally (not full re-read every poll) |
| 2 | **Triage & summarization** | Classifies incoming mail (needs-reply / FYI / spam-like / urgent); produces a daily digest |
| 3 | **Draft generation** | Drafts replies grounded in (a) the thread, (b) company knowledge base, (c) prior similar replies in memory |
| 4 | **Approval gate** | User approves/edits/rejects drafts before send — v1 default is human-in-the-loop for all sends |
| 5 | **Company knowledge ingestion** | User uploads docs (PDF/Markdown/Google Docs) that get chunked, embedded, and used as grounding context |
| 6 | **Long-term memory** | Facts learned from conversations/documents persist and are recalled in later sessions (e.g., "our refund policy is X") |
| 7 | **Built-in lead record** | When an email thread looks like a lead/prospect (heuristic + model classification), a lightweight lead record (name, contact, source thread, status) is created/updated natively — not synced to an external CRM |
| 8 | **Follow-up reminders** | Scheduled workflow that flags leads/threads with no reply after N days and surfaces a "needs follow-up" item in the dashboard |
| 9 | **Task management** | Simple task list (create/assign/complete) that the Assistant can populate from email content ("customer asked for a callback Tuesday" → task) and the user can manage directly |
| 10 | **Day-end report** | End-of-day scheduled workflow summarizing: emails handled, drafts pending approval, new leads, overdue follow-ups, tasks completed/outstanding |
| 11 | **Task/action log** | Every action the agent took or proposed is visible in an audit view with the reasoning trace |
| 12 | **Basic web dashboard** | Inbox-style view of triaged mail, pending drafts, leads, tasks, follow-ups, and the action log |

### Explicitly out of scope for MVP

| Feature (from original brief) | Why deferred |
|---|---|
| External CRM read/write (HubSpot/Salesforce/Pipedrive sync) | Requires integration work per-CRM; the built-in lead record (feature 7) covers the MVP job-to-be-done without picking a CRM integration first |
| Calendar management | Second integration; scheduling conflict-resolution is a planning-engine problem best solved after the simpler email/lead loop is proven |
| Full autonomous send (no approval) | Trust hasn't been earned yet; this is a Phase 2+ toggle once draft-acceptance metrics justify it |
| Multi-agent / team communication (Slack etc.) | Adds a whole notification surface; not needed to prove the core loop |
| External task-tool sync (Asana/Trello/Linear) | Built-in task management (feature 9) covers MVP; syncing outward is additive later |
| Fine-tuning / continual learning from feedback | Requires a working feedback-collection pipeline (built in MVP) before there's data to learn from |

## 2. MVP User Story (end to end)

1. User signs up, connects Gmail, uploads 3–5 company docs (FAQ, pricing sheet, policies).
2. Agent ingests inbox history, builds initial memory of recurring contacts/topics.
3. New email arrives → agent triages it, retrieves relevant memory + knowledge base context, drafts a reply, and
   — if the thread matches lead-like patterns (new contact asking about pricing/services) — creates or updates a
   lead record.
4. Draft appears in dashboard with the reasoning trace ("replied using refund policy from `policies.pdf`, sec. 3").
5. User approves as-is, edits, or rejects with a reason.
6. Rejection reason is stored and influences future drafts on similar threads (feedback loop, not fine-tuning —
   retrieved as context, not used to retrain weights in v1).
7. If a lead thread goes quiet for N days, a follow-up reminder appears in the dashboard; if the thread mentions
   a concrete commitment ("call me Tuesday"), a task is created.
8. At end of day, a report is generated summarizing the day's email/lead/task/follow-up activity.

## 3. Acceptance Criteria (MVP "done")

- A new user can go from signup to first approved draft in under 15 minutes with no engineering support.
- Draft-acceptance rate ≥ 90% by the end of a pilot user's first two weeks (see PRD success metrics).
- Every autonomous action (draft created, lead created/updated, task created, memory fact stored, doc ingested)
  has a corresponding audit-log entry with a timestamp, trigger, and reasoning summary.
- Swapping the underlying LLM (e.g., Qwen2.5-72B → Llama-3.3-70B) requires only a config change, not a code change
  in the planning/memory/tool layers — this is a hard architectural acceptance criterion, not a nice-to-have.
- A day-end report generates automatically without manual triggering and reflects that day's actual activity.

## 4. Deployment Model (founder-confirmed)

**v1 ships as a single-company, self-hosted deployment** — one Opero AI instance per customer, not a shared
multi-tenant SaaS. A SaaS multi-tenant version is a deliberate later product mode, not part of MVP. This is
compatible with the architecture as designed: every table already carries a `organization_id` (see
[SYSTEM_ARCHITECTURE.md §7](SYSTEM_ARCHITECTURE.md#7-deployment-model)) so the later move to multi-tenant
SaaS is a deployment-topology change, not a schema rewrite.

## 5. Open Decisions

1. Confirm Gmail-first (not Outlook/Microsoft 365) for MVP — Gmail's API is simpler and the target segment
   skews Google Workspace. Recommend yes.
2. Confirm human-in-the-loop send is acceptable for the pilot, vs. wanting fully autonomous send from day one
   (recommendation: human-in-the-loop — it's also the safer story for the trust-building goal in the PRD).
3. Who operates the self-hosted instance for pilot customers — Opero AI (managed) or the customer's own infra —
   carried over from the PRD's decisions log.
