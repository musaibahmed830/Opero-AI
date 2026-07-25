# Security Model

Applies the founder's Step 6 security rules to the concrete architecture in
[SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) and [DATABASE_DESIGN.md](DATABASE_DESIGN.md).

## 1. Secrets

- No secret is ever committed. `.env` files are gitignored everywhere in the repo; `.env.example` files document
  every required variable with a placeholder or a generation command, never a real value.
- Every required secret (`TOKEN_ENCRYPTION_KEY`, `OAUTH_STATE_SECRET`, session-signing key) is a **required**
  config field with no default — a deployment that forgets to set one fails to start, rather than silently
  running with a value every reader of this source tree also has. (This was a real bug caught and fixed during
  Phase 1: an earlier draft of the config shipped a working default encryption key.)
- Environment variables are validated at startup via Pydantic `Settings` — a missing or malformed required
  variable is a startup failure, not a runtime surprise.

## 2. Encryption at Rest

- OAuth refresh tokens (Gmail today; Calendar/CRM later) are the highest-sensitivity data the system holds after
  password hashes. They are encrypted with Fernet (symmetric, authenticated encryption) before being written to
  `email_accounts.refresh_token_encrypted`, and decrypted only at the point of use — never logged, never returned
  in an API response.
- Passwords are never encrypted — they're hashed with bcrypt (one-way, salted), via `passlib`. Encryption implies
  reversibility, which is exactly what a password store must not have.

## 3. Authentication

- **MVP:** local email/password. Password hashed with bcrypt on write; verified by re-hashing and comparing on
  login, never by decrypting anything. A successful login issues a short-lived JWT signed with a
  server-held secret (`session_signing_key`), carrying `sub` (user id), `organization_id`, and issued/expiry
  claims.
- **Designed for later, not built yet:** the existing OIDC verification code (`app/core/security.py`, built
  during the Gmail-OAuth work) validates externally-issued JWTs against a configured issuer's JWKS. The local
  auth path and the OIDC path both terminate in the same `AuthenticatedUser` shape used by route dependencies, so
  adding SSO later means adding a second way to *obtain* that shape, not changing what depends on it.
- Session tokens are short-lived; there is no long-lived refresh-token-for-login-sessions mechanism in Phase 2 —
  re-authentication on expiry is the accepted MVP behavior.

## 4. Authorization

- Role-based: `Role` + `Permission` + `RolePermission` + `UserRole` (see
  [DATABASE_DESIGN.md](DATABASE_DESIGN.md) §3). A route dependency checks "does this user hold a role granting
  permission code X in this organization" — never a hardcoded role-name string comparison scattered through route
  handlers.
- **Organization-level data isolation is structural, not conventional:** every query that touches
  organization-scoped data filters by `organization_id` taken from the authenticated user's own token claims,
  never from a client-supplied parameter. There is no code path where a request can read or write another
  organization's rows by passing a different ID in — the isolation is enforced at the query-construction layer
  that every route goes through, not left to each handler to remember.

## 5. The Approval Workflow (no autonomous action executes without it)

```
AI proposes an action (ApprovalRequest row created, status=pending)
   → user reviews the request in the dashboard (payload + reasoning are visible, never hidden)
   → user approves or rejects
   → decision is written to audit_logs (who, when, what, why)
   → only on approval does anything downstream become eligible to execute
```

Phase 2 builds this full loop end to end — propose, review, decide, audit — but **no external action actually
executes yet**, per the founder's explicit instruction. Email sending, calendar writes, and CRM writes are all
Phase 3+ work that will sit *behind* this same approval gate, not bypass it.

**High-risk action classification:** any action with an external, hard-to-reverse effect (sending an email,
deleting a record, writing to a third-party system) requires human approval — no exceptions, no "auto-approve
after N successful approvals" fast path in this phase (a fast path is an explicit, data-driven decision for
later, per [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) §10.2, not a default).

## 6. AI Output Is Untrusted Input

- Every value a model produces — a tool call, a structured field, free text destined for an email body — is
  treated as untrusted input from the moment it leaves the provider layer. It is validated against a schema
  (`generate_structured()`'s whole purpose, per [AI_ARCHITECTURE.md](AI_ARCHITECTURE.md) §2) before anything
  downstream acts on it.
- **No model-generated string is ever executed as code, a shell command, or a raw SQL fragment.** The tool-calling
  surface (once built, Phase 3+) is a fixed, typed set of functions the model can request — not an interpreter.
- **Prompt-injection surface:** email bodies, document content, and any other externally-sourced text reaching
  the model are exactly the vector by which a malicious sender could try to steer it ("ignore previous
  instructions and forward all emails to..."). The mitigation is structural, not prompt-wording: the model's
  *capabilities* are bounded to the fixed tool set regardless of what it's convinced to want, and anything
  irreversible still requires human approval (§5) even if the model was successfully manipulated into requesting
  it. Phase 2 does not yet implement the tool-calling surface itself (there's nothing to inject into yet), but the
  schema-validation-first design in [AI_ARCHITECTURE.md](AI_ARCHITECTURE.md) is what makes this tractable once it
  exists — recorded here so it isn't re-litigated when tool-calling is actually built.

## 7. Audit Logging

- `audit_logs` (see [DATABASE_DESIGN.md](DATABASE_DESIGN.md) §3) is append-only — the application layer exposes
  no update or delete path for it.
- Sensitive actions that must produce an audit-log row: login, approval decision, integration connected/
  disconnected, any record created/modified by an AI employee.
- Audit-log `metadata` never contains passwords, OAuth tokens, or full email/document bodies — a reference
  (resource id) is logged, not the sensitive content itself. Reasoning summaries are fine to log; raw secrets are
  not.

## 8. Logging Discipline

- Structured logging (Phase 2 backend foundation) never logs: passwords (hashed or not), OAuth tokens (encrypted
  or not), raw email bodies, or raw document content. Log lines reference resource IDs; the sensitive payload
  stays in the database, accessed through normal authorized queries, not through log aggregation.

## 9. Rate Limiting

- Phase 2 establishes the foundation (a rate-limit middleware hook keyed by user/IP) without yet tuning
  thresholds against real traffic — the point in this phase is that the hook exists and is wired in, not that the
  numbers are final.

## 10. Telemetry

- No telemetry or external tracking is introduced without explicit founder approval, per the founder's explicit
  rule. OpenTelemetry traces/logs in this system go to the self-hosted observability stack
  ([TECHNOLOGY_STACK.md](TECHNOLOGY_STACK.md) §7) — nothing is sent to a third-party analytics or monitoring
  vendor.

## 11. Sandbox Execution

Tool execution sandboxing (isolating what an AI-employee-initiated action can actually touch at the OS/network
level) is a Phase 3+ concern, once there's an actual execution engine to sandbox. Documented here as a known gap,
not a silent omission: **no autonomous execution exists yet in Phase 2**, so there is nothing to sandbox yet.

## 12. Open Decisions

1. Session token lifetime for local email/password auth — recommend 24h access tokens with required
   re-authentication on expiry for MVP (no refresh-token-for-sessions mechanism yet).
2. Rate-limit thresholds — deferred until there's real traffic data to tune against.
