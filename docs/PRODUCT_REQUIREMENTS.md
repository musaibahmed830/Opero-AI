# Product Requirements Document (PRD)

**Product:** Opero AI
**Tagline:** The world's first autonomous AI employee that actually works instead of chatting.
**Status:** Draft v0.1 — pending founder review
**Owner:** Founding team

---

## 1. Problem Statement

Knowledge-work software today falls into two buckets:

- **Chat assistants** (ChatGPT, Claude.ai, Gemini) — great at answering questions, bad at *doing* the work. They have
  no persistent access to a company's systems, no memory of what happened yesterday, and every session starts cold.
- **Automation tools** (Zapier, n8n, RPA) — can execute steps reliably but have no judgment. They break the moment a
  workflow deviates from the exact recipe they were configured for.

Nobody has shipped the overlap: a system with the judgment of a chat assistant and the persistence/reliability of an
automation engine — something that behaves like an employee you can hand a goal to, not a prompt.

## 2. Vision

Opero AI is an autonomous AI employee: a system that reads its inbox, understands company context, plans multi-step
work, executes it against real systems (email, CRM, calendar, documents), and remembers what it did — improving over
time instead of resetting every session.

This is **not** a chatbot with plugins bolted on. The planning, memory, and execution engines are core product
surface, not middleware. See [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md).

## 3. Target Users

**Decision (founder-confirmed):** initial target customers are small software houses, marketing agencies, real
estate companies, e-commerce businesses, and service-based companies with **5–50 employees** — SMBs with real
email/lead volume but no dedicated ops hire to manage it.

| Segment | Why | MVP priority |
|---|---|---|
| Small software houses / agencies (5–50 employees) | High client-email + lead volume, no dedicated ops/sales-ops hire, price-sensitive | **Primary — MVP target** |
| Real estate businesses | Lead follow-up is the core of the job; a missed follow-up is a lost commission — high willingness to pay for reliability | **Primary — MVP target** |
| E-commerce / service-based businesses | Repetitive customer-email patterns (order status, policy questions) — good draft-acceptance conditions | **Primary — MVP target** |
| Enterprise back-office | Highest contract value, but requires SSO, compliance, audit trail we don't have yet | Later — after v1 proves reliability |

## 3a. First AI Role (founder-confirmed)

The MVP does not ship a generic "email agent" — it ships one named, hireable role: the
**AI Sales & Operations Assistant**. Framing it as a role (not a feature list) matters for the product story: a
customer is evaluating whether to "hire" this the way they'd hire a junior ops person, not whether to turn on a
feature toggle. See [MVP_SCOPE.md](MVP_SCOPE.md) for the concrete job description this role fulfills.

## 4. Goals

- G1: An agent that can autonomously triage, summarize, and draft replies to a real inbox with >90% draft-acceptance
  rate (user sends with zero or minor edit) within the target user's first week of use.
- G2: Persistent memory — the agent recalls prior conversations, decisions, and company-specific facts across
  sessions without being re-told.
- G3: A model-agnostic execution core — swapping the underlying LLM (open-weight or otherwise) does not require
  rewriting the planning, memory, or tool layers.
- G4: Auditability — every autonomous action the agent takes is logged, attributable, and reversible or approvable
  before execution for anything irreversible (e.g., sending an email, deleting a record).

## 5. Non-Goals (v1)

- Full CRM replacement — we integrate with existing CRMs, we do not build one.
- General-purpose "do anything" agent — scope is explicitly the workflows in
  [MVP_SCOPE.md](MVP_SCOPE.md).
- On-device / offline inference — v1 assumes a network-connected inference backend (self-hosted or cloud-rented
  GPU), not local laptop inference.
- Enterprise SSO/compliance certifications (SOC 2, HIPAA) — required before enterprise sales, not before MVP.

## 6. Key Differentiators

1. **Executes, not just chats** — actions land in real systems (send email, update CRM record), with an
   approval gate for irreversible ones.
2. **Persistent, structured memory** — not a longer context window; a real memory architecture with short-term,
   episodic, and semantic/company-knowledge layers (detailed in
   [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md)).
3. **Model-agnostic core** — the product's value is the orchestration, memory, and execution layers, not a
   wrapper around one vendor's API. This is a defensibility argument, not just a cost argument: if the moat were
   "we call GPT-4 well," it wouldn't be a moat.
4. **Auditable autonomy** — every decision and action is logged with the reasoning trace that produced it.

## 7. Constraints Set by Leadership

- **Inference:** default to self-hostable open-weight models (Llama, Qwen, Mistral, DeepSeek, GLM family) behind
  a swappable model-router abstraction — no hard dependency on a single closed-source vendor API.
  **CTO note (push-back, on record):** self-hosting a 70B+ class model to match closed frontier-model tool-use
  reliability is a GPU-ops project on its own, with real latency/quality/cost trade-offs versus renting inference.
  The architecture must make the model swappable so this is a per-environment config choice, not a rewrite.
  See [TECHNOLOGY_STACK.md §Model Serving](TECHNOLOGY_STACK.md#model-serving--inference) for the concrete
  recommendation and fallback path.
- **Modularity:** every engine (planning, memory, execution, notification) must be independently replaceable.
  No component may assume the identity of any other component's implementation.

## 8. Success Metrics (v1 / MVP)

| Metric | Target |
|---|---|
| Draft-acceptance rate (email replies sent with ≤ minor edits) | ≥ 90% by week 4 of use |
| Time-to-first-value (signup → first autonomous action taken) | < 15 minutes |
| Autonomous action error rate requiring manual correction | < 5% |
| Memory recall accuracy (does it correctly recall a fact stated >7 days prior) | ≥ 95% |
| p95 end-to-end latency for a single agent turn (plan + tool call + response) | < 8s |

## 9. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Self-hosted open-weight models underperform on tool-use/planning vs. closed frontier models | Core product quality suffers, users churn | Model-router abstraction; benchmark before committing; allow per-deployment override |
| Users don't trust autonomous email sending | Adoption stalls at "just a drafting tool" | Approval gate for irreversible actions is a v1 requirement, not a v2 nice-to-have |
| Scope creep into "does everything" | Ships nothing | MVP wedge is enforced in [MVP_SCOPE.md](MVP_SCOPE.md); anything else is explicitly out |
| GPU inference cost at scale | Margins collapse before enterprise pricing kicks in | Start on rented GPU inference (RunPod/Lambda/Together), only build owned GPU infra once utilization justifies it |

## 10. Decisions Log

**Resolved:**

- Target segment: small software houses, agencies, real estate, e-commerce, service businesses, 5–50 employees
  (§3).
- MVP is one named role — **AI Sales & Operations Assistant** — not a generic feature list (§3a).
- Deployment model: **single-company, self-hosted deployment first**; SaaS multi-tenant is a later, separate
  product mode (see [SYSTEM_ARCHITECTURE.md §7](SYSTEM_ARCHITECTURE.md#7-deployment-model)).

**Still open:**

1. Confirm self-hosted-only is a hard requirement, or whether a closed-model fallback is acceptable during MVP
   validation while the open-weight router matures (recommendation: allow it behind the router, disabled by
   default, so validation isn't blocked on inference quality).
2. Pricing model (seat-based vs. usage/action-based) — not yet decided, needed before a Phase 1 business-model doc.
3. For self-hosted single-company deployments: does Opero AI operate the deployment (managed self-hosted) or does
   the customer's own infra team run it? This materially affects support burden and is worth deciding before
   the first pilot, not after.
