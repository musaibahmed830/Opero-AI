# Opero AI Employee OS — Documentation

"Your AI Employee That Gets Work Done."

This folder is the source of truth for product, architecture, and delivery decisions. Read in this order:

1. [PRODUCT_REQUIREMENTS.md](PRODUCT_REQUIREMENTS.md) — what we're building and for whom, and why
2. [MVP_SCOPE.md](MVP_SCOPE.md) — the exact feature cut for v1, and what's deliberately excluded
3. [TECHNOLOGY_STACK.md](TECHNOLOGY_STACK.md) — the stack, with the reasoning and trade-offs behind each pick
4. [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) — components, data flow, memory/execution engine design
5. [AI_ARCHITECTURE.md](AI_ARCHITECTURE.md) — the model-provider interface and memory-schema design
6. [DATABASE_DESIGN.md](DATABASE_DESIGN.md) — full entity list and the reasoning behind each modeling decision
7. [SECURITY_MODEL.md](SECURITY_MODEL.md) — auth, encryption, the approval workflow, and AI-output trust boundaries
8. [DEVELOPMENT_ROADMAP.md](DEVELOPMENT_ROADMAP.md) — phases, milestones, and what "done" means for each
9. [DECISIONS_REQUIRED_FROM_FOUNDER.md](DECISIONS_REQUIRED_FROM_FOUNDER.md) — every open decision, consolidated, with the default in use until it's made
10. [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) — what's actually built right now, kept current every phase

Phase 3 (Knowledge System + Email Intelligence MVP) added:

11. [KNOWLEDGE_SYSTEM.md](KNOWLEDGE_SYSTEM.md) — document ingestion, chunking, embeddings, semantic search
12. [RAG_PIPELINE.md](RAG_PIPELINE.md) — grounded question-answering, confidence heuristic, citations
13. [EMAIL_INTELLIGENCE.md](EMAIL_INTELLIGENCE.md) — mock inbox, classification, lead/task extraction, reply drafting
14. [PROMPT_INJECTION_DEFENCE.md](PROMPT_INJECTION_DEFENCE.md) — the structural + heuristic defenses, verified against the live model
15. [APPROVAL_WORKFLOW.md](APPROVAL_WORKFLOW.md) — the human approval gate, extended with a real (simulated) send
16. [DAILY_REPORT_ENGINE.md](DAILY_REPORT_ENGINE.md) — deterministic metrics first, AI narrative second
17. [TESTING_GUIDE.md](TESTING_GUIDE.md) — deterministic vs. live-model test separation and what's covered
18. [LOCAL_DEMO_GUIDE.md](LOCAL_DEMO_GUIDE.md) — stand up the full slice locally with fictional demo data

## Status

Phase 3 (Knowledge System + Email Intelligence MVP) is in progress. See
[IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) for the live, accurate state of what's built, tested, and
pending — this README is an index, not a status report, and will not be kept in sync line-by-line the way that
file is.
