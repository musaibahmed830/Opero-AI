# Local Demo Guide

How to stand up the full Phase 3 vertical slice locally and see it work end to end, with fictional data.

## 1. Start the stack

```bash
make dev
```

Brings up Postgres (pgvector), Redis, MinIO, Ollama, Temporal, the API, the Phase 3 background-job worker
(`api-worker`), and the web dashboard. First run also needs the model pulled once (not bundled in the image
— multi-GB download):

```bash
docker compose -f infra/docker-compose.yml exec ollama ollama pull qwen2.5:7b-instruct
docker compose -f infra/docker-compose.yml exec ollama ollama pull nomic-embed-text
```

## 2. Seed the demo organization

```bash
make demo-seed
```

This creates (or reuses, if run again) a fictional organization, **Opero Demo Co**
(login: `demo@opero.ai` / `DemoPass123!`), and:

1. Uploads and processes three fictional company documents — a refund policy, a service catalog, and
   support hours — through the real ingestion pipeline (extraction, chunking, embedding).
2. Ingests the 12 fixed mock inbox scenarios (sales enquiry, complaint, refund request, spam, a
   prompt-injection attempt, etc. — see [EMAIL_INTELLIGENCE.md](EMAIL_INTELLIGENCE.md)).
3. Runs the full classification → lead/task extraction → reply-draft → approval-proposal pipeline on every
   one of those 12 messages, against the real model.
4. Generates today's daily report.

This calls the real Ollama model close to 20 times (12 emails × classification/extraction/drafting + 3
documents' embeddings + 1 report narrative), so it takes a few minutes — this is real inference happening,
not instant because nothing is actually being computed.

## 3. Log in and look around

Open the web dashboard (`http://localhost:3010`), sign in as `demo@opero.ai`, and:

- **Knowledge**: search for "refund" or "support hours" — see real semantic search results against the
  seeded documents. Ask a question via the knowledge-ask panel (e.g. "How many days do customers have to
  return something?") and see a grounded answer with citations back to the actual document.
- **Inbox**: see the 12 classified emails with category/priority/sentiment badges. Open the prompt-injection
  scenario and confirm it's flagged.
- **Approvals**: at least one pending `send_email_reply` approval should exist (the pipeline proposes a
  reply for every email the model judged `requires_reply=true`). Approve one, edit one's text before
  approving, reject one — confirm the simulated send result and audit trail update accordingly.
- **Leads / Tasks**: see the leads and tasks the pipeline extracted from the sales enquiry, project update,
  and other action-implying messages.
- **Reports**: see today's report — real computed metrics plus an AI-written narrative summarizing them.
- **Activity**: the full audit log of everything above — every upload, classification, extraction, proposal,
  and decision is a row here.

## 4. Re-running the seed script

`make demo-seed` is safe to run again: the organization/user lookup is get-or-create (won't create a
duplicate org), document uploads are checksum-deduplicated (a re-run skips documents already uploaded), and
email ingestion is idempotent (a re-run ingests zero new messages). It will, however, attempt to re-run the
classification pipeline on messages that already have one — `process_email_task`'s idempotency guard means
calling the underlying task again is a no-op, but the seed script itself calls `process_email()` directly
rather than through that guard, so a second run **will** re-classify and may propose a second draft for
each message. If you want a clean re-seed, drop and recreate the schema first (`make db-reset`, destructive)
before re-running `make demo-seed`.

## What's real vs. simulated in this demo

- **Real**: document extraction/chunking/embedding, semantic search, RAG answers, email classification,
  lead/task extraction, reply drafting — all live model inference against real stored data.
- **Simulated, by explicit design**: the mock inbox (no real Gmail/Outlook connection exists) and the
  "sent" email on approval (calls `MockEmailConnector`, never a real SMTP/API send). Both are clearly
  labeled as such throughout the code and UI — never presented as a real integration.
