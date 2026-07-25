# Decisions Required From Founder

Every open decision currently scattered across the other docs, consolidated here. None of these block starting
or finishing Phase 2 — reasonable defaults are recorded and used, per the instruction not to stop for non-critical
missing information. This is the list to work through when there's founder bandwidth, not a blocker list.

## Genuinely blocking (nothing to fall back on)

None. Every decision below has a working default already in place in the code and docs.

## Product

| # | Decision | Default in use | Source |
|---|---|---|---|
| 1 | Pricing model (seat-based vs. usage-based) | Not decided; not needed until a business-model doc exists | [PRODUCT_REQUIREMENTS.md](PRODUCT_REQUIREMENTS.md) §10 |
| 2 | Who operates self-hosted pilot deployments — Opero AI (managed) or the customer's infra team | Assumed customer/founder-operated for now | [PRODUCT_REQUIREMENTS.md](PRODUCT_REQUIREMENTS.md) §10, [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) §7 |
| 3 | Whether a closed-model provider tier is ever permitted as an opt-in, disabled-by-default option | Not implemented in Phase 2; the provider interface doesn't forbid adding one later | [TECHNOLOGY_STACK.md](TECHNOLOGY_STACK.md) §1 |

## AI / Infrastructure

| # | Decision | Default in use | Source |
|---|---|---|---|
| 4 | Ollama model tag for **production** deployments — `14b`/`32b` may be worth it on hardware with more RAM than an 8GB dev VM | `qwen2.5:7b-instruct` confirmed working for local dev (14b tested and OOM'd in an 8GB Docker VM — see AI_ARCHITECTURE.md §3); configurable per deployment via `MODEL_REASONING_NAME` | [AI_ARCHITECTURE.md](AI_ARCHITECTURE.md) §8 |
| 5 | Whether embeddings run through Ollama or a separate embedding server | Ollama for both generation and embeddings in Phase 2 | [AI_ARCHITECTURE.md](AI_ARCHITECTURE.md) §8 |
| 6 | Rented GPU inference provider, if/when self-hosted moves beyond a single local Ollama instance | Not applicable yet — Phase 2 runs Ollama locally/single-node | [TECHNOLOGY_STACK.md](TECHNOLOGY_STACK.md) |

## Auth & Security

| # | Decision | Default in use | Source |
|---|---|---|---|
| 7 | Session token lifetime for local email/password auth | 24h access token, re-authenticate on expiry | [SECURITY_MODEL.md](SECURITY_MODEL.md) §12 |
| 8 | When (if ever) to add OIDC/SSO as a second login method | Interface supports it; not built until a customer requires it | [SECURITY_MODEL.md](SECURITY_MODEL.md) §3 |
| 9 | Rate-limit thresholds | Hook exists, no tuned numbers yet | [SECURITY_MODEL.md](SECURITY_MODEL.md) §12 |

## Database

| # | Decision | Default in use | Source |
|---|---|---|---|
| 10 | Whether `user_roles.organization_id` redundancy is acceptable, or multi-organization user membership should be designed now | Redundant column kept, enforced at application layer, not a DB constraint | [DATABASE_DESIGN.md](DATABASE_DESIGN.md) §5 |

## Deployment

| # | Decision | Default in use | Source |
|---|---|---|---|
| 11 | Push (Gmail Pub/Sub webhook) vs. poll for new-mail detection | Polling, per existing Gmail sync implementation | [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) §10 |
| 12 | Whether the approval gate ever gets a "trusted sender" fast-path | No — 100% human-in-the-loop until draft-acceptance data justifies otherwise | [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) §10 |
| 13 | Team size/composition, affecting roadmap sprint pacing | Assumed 2–4 engineers | [DEVELOPMENT_ROADMAP.md](DEVELOPMENT_ROADMAP.md) |
| 14 | Pilot user sourcing — lined up yet, or needs to start now | Not addressed yet | [DEVELOPMENT_ROADMAP.md](DEVELOPMENT_ROADMAP.md) |

## Phase 3 additions

| # | Decision | Default in use | Source |
|---|---|---|---|
| 15 | When to connect a real mailbox (Gmail/Outlook) to the classification/extraction/drafting pipeline built in Phase 3 | Not connected — mock connector only, per the founder's explicit "no real Gmail/Outlook yet" instruction. The pipeline is provider-agnostic (`EmailAccount.provider`), so wiring in Phase 2's existing `gmail_sync.py` means adding a second producer of `EmailMessage` rows, not rewriting anything downstream | [EMAIL_INTELLIGENCE.md](EMAIL_INTELLIGENCE.md) |
| 16 | Whether/when the approval gate gets a real (non-simulated) send path | Not built — `send_email_reply` approval always calls `MockEmailConnector`, never a real SMTP/API send, per the founder's explicit instruction | [APPROVAL_WORKFLOW.md](APPROVAL_WORKFLOW.md) |
| 17 | Whether report generation should be scheduled automatically (e.g. nightly per organization) rather than triggered on demand | On-demand only via `POST /v1/reports/generate`; the underlying function is idempotent per (org, date) so a scheduled Celery Beat job could be added without any other change | [DAILY_REPORT_ENGINE.md](DAILY_REPORT_ENGINE.md) |
| 18 | Whether member-role users should be creatable (currently every registered user is their org's sole owner) | Not built — no invite/add-member endpoint exists yet; RBAC roles/permissions exist and are enforced, but there's no way to populate a non-owner user via the API | [TESTING_GUIDE.md](TESTING_GUIDE.md) |
| 19 | Whether the prompt-injection regex scanner should be expanded (more languages, more patterns) or replaced with a model-based classifier | Regex scanner kept as a lightweight detector; the real defense is structural (system/user/retrieved-content separation + approval gate), so the scanner's coverage is not currently a priority investment | [PROMPT_INJECTION_DEFENCE.md](PROMPT_INJECTION_DEFENCE.md) |

## How to Use This Document

When a decision here changes from "default in use" to an actual founder call, update the source document directly
(not just this list) and remove or check off the row here. This file is a routing table to the real documents,
not a duplicate source of truth — if it ever disagrees with the document it points to, the document wins and this
file is stale and needs fixing.
