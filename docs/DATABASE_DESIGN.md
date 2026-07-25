# Database Design

PostgreSQL 16 + pgvector. Every table is scoped by `organization_id` (see
[SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) §7) even though Phase 2's single-company self-hosted deployment
only ever has one organization per running instance — this is what makes the later move to multi-tenant SaaS a
topology change instead of a schema rewrite.

## 1. Naming Decision: `Organization`, not `Workspace`

Earlier drafts of this documentation used `Workspace` as the tenant boundary. This document renames it to
`Organization` to match the founder's explicit model list. Purely a naming change — the role of the entity (one
row per deployed customer) is unchanged.

## 2. Entity Overview

```
organizations
  └─ users ──────────┬─ user_roles ─── roles ─── role_permissions ─── permissions
                      │
                      ├─ ai_employees
                      │     ├─ tasks
                      │     ├─ approval_requests
                      │     ├─ conversations
                      │     └─ memory_records
                      │
                      ├─ integrations ─── email_accounts ─── email_threads ─── email_messages
                      ├─ documents ─── document_chunks
                      ├─ contacts ─── leads
                      ├─ daily_reports
                      └─ audit_logs
```

## 3. Tables

### `organizations`
One row per deployed customer (or, in a future SaaS mode, per tenant). `id`, `name`, `created_at`.

### `users`
`id`, `organization_id` (FK), `email` (unique), `hashed_password` (nullable — null for a user who only
authenticates via a future SSO provider), `oidc_subject` (nullable — populated only for SSO-authenticated users),
`created_at`.

**Design decision:** the earlier `User.role` enum column is removed. Role is now assigned entirely through
`user_roles`, so a user's permissions are queryable/auditable data, not a hardcoded three-value enum. This is
more normalized than the MVP strictly needs today, but it's the one piece of "design for later" that's cheap to
get right now and expensive to retrofit once permission checks are scattered through the codebase.

### `roles`
`id`, `organization_id` (FK — roles are per-organization so an org can eventually define custom roles),
`name` (e.g. `owner`, `admin`, `member`), `description`.

### `permissions`
`id`, `code` (unique, e.g. `email.send`, `leads.write`, `approvals.decide`), `description`. Global, not
per-organization — the set of things the system *can* check permission for is fixed by the codebase, not
customer-configurable.

### `role_permissions`
Join table: `role_id`, `permission_id`. Composite primary key, no surrogate `id` — this table has no attributes
of its own, just the association.

### `user_roles`
Join table: `id`, `user_id`, `role_id`, `organization_id`. Carries `organization_id` redundantly (derivable from
`user_id`) so that a future shared-account-across-organizations model doesn't require a schema change — currently
always consistent with the user's own `organization_id`, and enforced as such at the application layer rather
than a DB constraint (over-constraining this now would need loosening later; documented as a known simplification).

### `ai_employees`
`id`, `organization_id`, `name` (e.g. "Sales & Ops Assistant"), `role_type` (enum — currently only
`sales_ops_assistant`), `status` (enum: `active`/`paused`), `created_at`. One row per configured AI employee
instance in an organization. Only one role type exists today (per
[PRODUCT_REQUIREMENTS.md](PRODUCT_REQUIREMENTS.md) §3a); the table exists as its own entity now because `Task`,
`ApprovalRequest`, `Conversation`, and `MemoryRecord` all need to record *which* AI employee did something —
retrofitting that attribution later, after audit logs already exist without it, would be worse than modeling it
now.

### `tasks`
`id`, `organization_id`, `ai_employee_id` (nullable — a task can be user-created directly), `title`,
`description`, `source_thread_id` (nullable FK → `email_threads`), `assignee_user_id` (nullable FK → `users`),
`category` (enum: `general`/`follow_up`), `due_at` (nullable), `status` (enum: `open`/`done`), `created_at`.

**Consolidation decision:** an earlier architecture draft had a separate `follow_up` table. It's folded into
`tasks` with `category = follow_up` instead — the founder's required model list doesn't include a distinct
follow-up entity, and a follow-up genuinely is just a task with a source and a due date. Two tables that differ
only by one enum value would be over-normalization.

### `approval_requests`
`id`, `organization_id`, `ai_employee_id`, `action_type` (string code, e.g. `send_email`, `update_lead`),
`payload` (JSONB — the proposed action's parameters), `status` (enum: `pending`/`approved`/`rejected`),
`requested_at`, `decided_at` (nullable), `decided_by_user_id` (nullable FK → `users`), `decision_reason`
(nullable). This is the schema for the approval workflow in [SECURITY_MODEL.md](SECURITY_MODEL.md) §4 — no
external action executes without a row here reaching `approved`.

### `audit_logs`
`id`, `organization_id`, `actor_type` (enum: `user`/`ai_employee`/`system`), `actor_id` (nullable UUID — the
user or AI employee responsible), `action` (string code, e.g. `approval.approved`, `email.sent`,
`integration.connected`), `resource_type`, `resource_id` (nullable), `metadata` (JSONB), `created_at`. Append-only
— no update or delete path is exposed anywhere in the application layer.

### `integrations`
`id`, `organization_id`, `provider` (enum: `gmail`/`outlook`/`google_calendar`/`slack`/`crm`, extensible),
`status` (enum: `connected`/`disconnected`/`error`), `config` (JSONB — non-secret settings only), `connected_at`,
`last_synced_at` (nullable).

**Design decision:** `Integration` is a generic registry row; `email_accounts` (already built in an earlier
session) holds the Gmail-specific detail — encrypted refresh token, `history_cursor` — and gets an
`integration_id` FK to its parent registry row. This keeps `integrations` genuinely generic (a Calendar or CRM
connector adds a new provider value and its own detail table, not new columns bolted onto `integrations`) without
forcing a rewrite of the already-working, already-tested `EmailAccount` model.

### `email_accounts`, `email_threads`, `email_messages`
Unchanged from the existing schema except `workspace_id` → `organization_id` and the new `integration_id` FK on
`email_accounts`.

### `conversations`
`id`, `organization_id`, `ai_employee_id`, `channel` (enum: `email`; extensible to `dashboard_chat` etc. later),
`email_thread_id` (nullable FK — populated when `channel = email`), `started_at`, `last_message_at`. Represents
"the AI employee is engaged in this exchange," independent of which channel it's happening over.

### `memory_records`
`id`, `organization_id`, `ai_employee_id`, `memory_type` (enum: `short_term`/`episodic`/`semantic`/`long_term_fact`
— the four layers from [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) §2.3), `content` (text), `embedding`
(`vector`, nullable — not every memory type needs a vector; a long-term fact might be looked up by structured
query instead), `source_reference` (JSONB — e.g. `{"conversation_id": ...}` or `{"document_id": ...}`),
`created_at`.

### `documents`
`id`, `organization_id`, `title`, `source_type` (enum: `upload`/`gmail_attachment`), `storage_path` (MinIO
object key), `version` (int — re-ingesting a changed document creates a new version row rather than overwriting,
per the audit requirement that a past decision's grounding document version stays inspectable), `uploaded_at`.

### `document_chunks`
`id`, `document_id` (FK), `organization_id`, `chunk_index`, `content` (text), `embedding` (`vector`),
`created_at`.

### `contacts`
`id`, `organization_id`, `name`, `email`, `phone` (nullable), `company` (nullable), `created_at`,
`last_interaction_at`.

### `leads`
`id`, `organization_id`, `contact_id` (FK), `source_thread_id` (nullable FK → `email_threads`), `status`
(enum: `new`/`contacted`/`awaiting_reply`/`stale`/`won`/`lost`), `created_at`, `last_activity_at`.

**Design decision:** `Contact` and `Lead` are split (a contact can exist without being a sales lead; a lead
always points at exactly one contact) rather than the single denormalized `lead` table sketched in an earlier
architecture draft — this matches the founder's explicit model list and is the more normalized shape once both
are first-class.

### `daily_reports`
`id`, `organization_id`, `report_date`, `emails_handled`, `drafts_pending`, `leads_created`,
`follow_ups_overdue`, `tasks_completed`, `generated_at`. Generated once per day, read-only after generation.

## 4. What This Phase Does Not Model

- Per-resource ACLs (e.g. "this user can only see leads they're assigned to") — `role_permissions` is
  action-level (`leads.write`), not row-level. Row-level scoping is organization-level only for now
  (see [SECURITY_MODEL.md](SECURITY_MODEL.md)).
- Calendar/CRM-specific detail tables — `integrations` has the provider enum values reserved, but only the Gmail
  detail table (`email_accounts`) exists; Calendar/CRM detail tables are built when those connectors are (Phase
  4+ per [DEVELOPMENT_ROADMAP.md](DEVELOPMENT_ROADMAP.md)).

## 5. Open Decisions

1. Confirm the `user_roles.organization_id` redundancy (§3, `user_roles`) is acceptable simplification, or
   whether multi-organization user membership should be designed for now instead of later.
