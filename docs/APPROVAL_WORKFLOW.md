# Approval Workflow

The single gate every irreversible action passes through. Phase 2 built the full loop with no downstream
execution; Phase 3 wires exactly one real-but-simulated action on top of it.

## Loop

```
AI proposes an action -> ApprovalRequest(status=pending) created, audit-logged
    -> human reviews (list/get)
    -> human decides: approve (optionally with edits) | reject
    -> decision audit-logged
    -> only on approval: the action executes (simulated)
    -> execution result + audit log recorded
```

`app/services/approval_service.py`. `ApprovalRequest.payload` is always the original, unmodified AI-generated
proposal — the code never mutates it after creation, so "what did the AI actually produce" stays inspectable
even after a human edits and approves. `resolved_payload` is null until a decision is made; on approval (with
or without edits) it holds the exact content that was "sent" — this is what actually gets executed, never
`payload` directly.

## What Phase 3 actually wires up

Exactly one action type executes anything: `send_email_reply`. Approving it calls
`MockEmailConnector.send_message()` (`services/connectors`) and records the result in
`simulated_send_result` — **never a real send**, per the founder's explicit instruction not to send real
email yet. Every other `action_type` is approved/rejected and audit-logged like normal, but nothing
downstream executes for it (`_execute_approved_action` returns `None` for anything else). This is a
deliberate, hard-coded allow-list of one — not a general "execute whatever the AI proposed" mechanism. There
is no unrestricted autonomous execution anywhere in this codebase.

Verified in `tests/test_approval_simulated_send.py`:
- Approving `send_email_reply` produces a `simulated_send_result` and an `email.sent` audit log.
- Rejecting it produces neither.
- An edited payload is what gets "sent," not the original AI draft — and the original `payload` is
  confirmed unchanged afterward.
- An unrecognized `action_type` (e.g. `delete_account`) is approved but dispatches nothing.

## Statuses

`pending -> approved | rejected`, plus three Phase 3 additions to the enum for future use:
`edited` (a saved edit not yet approved/rejected), `expired` (left pending past a TTL — nothing is
auto-approved), `cancelled` (withdrawn, e.g. the underlying email thread went stale). Only
`pending/approved/rejected` are actually reachable through the current API; the other three exist in the
schema for a future editing/expiry feature and aren't set by any code path yet (see Known Limitations).

## Where proposals come from

- **Manual** (`POST /v1/approvals`, unchanged from Phase 2): stands in for "the AI proposes an action" for
  any caller that wants to test the loop directly.
- **The real pipeline** (Phase 3): `app/services/email_processing.py::_propose_reply` calls the same
  `propose_action()` service function after generating a reply draft — one code path, two callers, never
  a special-cased "real" version vs. a "test" version.

## Security

- Every approval is organization-scoped — verified cross-org in `tests/test_approvals.py` (Phase 2) and
  unchanged in Phase 3.
- Deciding an already-decided approval is rejected with `409`, not silently overwritten
  (`ApprovalAlreadyDecidedError`).
- The decision audit log records whether the payload was edited (`{"edited": true/false}`) and the reason,
  if given — never the full email body/document content, per the audit log's own no-sensitive-payload rule
  (`docs/SECURITY_MODEL.md` §7).

## Known limitations

- `edited`/`expired`/`cancelled` statuses exist in the schema but have no code path that sets them yet — no
  TTL-based expiry job, no separate "save edit without deciding" endpoint (edits currently only happen
  atomically with an approve decision via `edited_payload` on `POST /decide`).
- No "trusted sender" or auto-approval fast path exists or is planned for MVP — 100% human-in-the-loop,
  per `docs/DECISIONS_REQUIRED_FROM_FOUNDER.md` #12.
