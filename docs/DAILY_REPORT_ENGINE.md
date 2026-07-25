# Daily Report Engine

A once-per-day, read-only-after-generation summary of what the AI employee did, with every number computed
before the model ever writes a word of prose.

## Deterministic metrics first

`app/services/daily_report.py::_compute_metrics` runs plain SQL aggregates against already-stored rows —
`EmailMessage`/`EmailClassification`, `ApprovalRequest`, `Lead`, `Task` — and returns a plain dict. Only
*after* that dict exists is the model ever called (`_generate_narrative`), and the model is given the
metrics as read-only data with an explicit instruction: use ONLY these numbers, never invent, estimate, or
restate one differently than given. There is no code path where the model computes or alters a count — it
writes prose on top of numbers it cannot touch.

## Metrics computed

Top-level columns on `DailyReport` (`emails_handled`, `drafts_pending`, `leads_created`,
`follow_ups_overdue`, `tasks_completed`) plus a `metrics` JSONB blob with the full breakdown: emails by
category/priority/sentiment, count flagged for possible prompt injection, approvals pending/approved-today/
rejected-today, leads created today, follow-ups overdue, and total completed tasks. The JSONB blob exists
because this report's exact shape is still evolving; the well-established top-level counters have real
columns for simple querying/filtering, matching `docs/DATABASE_DESIGN.md` §3's original design for this
table.

## Generation is idempotent per (organization, date)

`generate_daily_report` checks for an existing row for `(organization_id, report_date)` first and returns it
unchanged if found — a report is generated once and is read-only afterward, per the model's own docstring.
Calling `POST /v1/reports/generate` twice for the same date never recomputes or overwrites; it returns the
same report both times (verified in
`tests/test_reports.py::test_generating_the_same_day_twice_is_idempotent`).

## The narrative always calls the live model

Unlike RAG's `insufficient_evidence` short-circuit, there is no zero-model-call path here — every report
generation asks the model to write 2-3 short paragraphs of prose on top of the metrics, even for a day with
zero activity (in which case the model is expected to say so plainly). This is a deliberate scope choice:
the founder's spec asks for an AI-written narrative unconditionally, not only on "interesting" days. It
does mean every report-generation test is a live-model test, not a fast deterministic one — see
[TESTING_GUIDE.md](TESTING_GUIDE.md).

If the model call itself fails (`ModelProviderError`), the report still generates with the real metrics and
a plain fallback narrative string — a model outage never blocks the deterministic half of the report.

## Security

Reports are organization-scoped everywhere (`tests/test_reports.py::test_report_not_visible_across_organizations`).
Generation requires `reports.generate`; viewing requires `reports.read` — both new RBAC permission codes
added in Phase 3 (`app/services/rbac.py::PERMISSION_CODES`), granted to owner/admin (generate) and all three
default roles (read).

## Known limitations

- `tasks_completed` is a point-in-time snapshot of all currently-`done` tasks for the organization, not
  "completed on report_date" — `Task` has no completed-at timestamp in the schema
  (`docs/DATABASE_DESIGN.md` §3 didn't call for one). Documented rather than silently treated as
  date-scoped; a real fix would add `Task.completed_at` in a future migration.
- No scheduled/automatic daily generation yet (e.g. a Celery Beat job firing at midnight per organization) —
  generation is currently triggered on demand via the API or the demo seed script. Wiring a scheduled job is
  straightforward on top of the existing idempotent `generate_daily_report()` but wasn't built in Phase 3.
