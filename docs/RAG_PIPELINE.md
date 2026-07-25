# RAG Pipeline

How `POST /v1/knowledge/ask` answers a question grounded in an organization's own documents, and nothing
else.

## Flow

```
question -> embed -> pgvector similarity search (org-scoped, top_k, threshold)
    -> zero chunks? -> insufficient_evidence=true, model never called
    -> else -> scan chunks for prompt injection -> build numbered context block
    -> generate_structured() with system/user/retrieved-content separation
    -> compute confidence -> build citations -> store RagQueryTrace -> respond
```

(`app/services/rag.py::answer_question`)

## The model is never allowed to answer from its own knowledge

If retrieval returns zero chunks, the model is **not called at all** — the service returns
`insufficient_evidence=true` directly with a fixed honest answer. This is a deliberate zero-model-call
short-circuit, not just a prompt instruction: there is no code path where an unanswerable question reaches
the model and it "helpfully" answers from general knowledge instead of the company's actual documents.
Verified in `tests/test_knowledge.py::test_ask_with_no_documents_returns_insufficient_evidence` (a fast,
deterministic test — no live model call happens).

## Response shape

`RagAnswerResponse` (`app/schemas/knowledge.py`): `answer`, `confidence`, `citations` (document/chunk
references the model says it used), `retrieved_chunks` (everything actually retrieved, not just cited),
`insufficient_evidence`, `model_name`, `generation_time_ms`, `trace_id`, `prompt_injection_flags`.

## Confidence heuristic — transparent, not calibrated

`app/services/rag.py::_compute_confidence` is a documented heuristic, not a calibrated probability of
factual correctness:

```
confidence = 0.6 * avg_similarity(cited chunks) + 0.2 * coverage + 0.2 * agreement
```

- **avg_similarity**: mean cosine similarity of the chunks the model actually cited (0 if it cited none).
- **coverage**: fraction of retrieved chunks the model used — citing 1 of 5 retrieved chunks scores lower
  than citing 4 of 5, on the theory that broader use of the retrieved evidence is (weakly) more reassuring.
- **agreement**: 1 minus the variance of the cited chunks' similarity scores — if the cited evidence is all
  similarly relevant, that's a (weak) positive signal; wildly differing similarity among cited chunks isn't.

If the model itself flags `insufficient_evidence=true`, confidence is forced to `0.0` regardless of what
was retrieved. This is a heuristic proxy for "how well-grounded does this look," not a statistically
validated confidence score — documented here and in the code so it's never mistaken for one.

## Prompt-injection defense

Every retrieved chunk is scanned (`app/services/prompt_injection.py`) before being trusted as context, and
the system prompt explicitly tells the model the retrieved context is DATA, not instructions, and to ignore
anything that looks like an embedded instruction. See
[PROMPT_INJECTION_DEFENCE.md](PROMPT_INJECTION_DEFENCE.md) for the real (not simulated) attack test that
verifies this against the live model.

## Citations

Built from `supporting_chunk_indices` — the model's own list of which numbered context chunks it actually
used — mapped back to `{document_id, document_title, chunk_id, chunk_index}`. Indices outside the retrieved
range are dropped defensively rather than causing an error (a model returning an out-of-range index is a
plausible failure mode of any structured generation call, not treated as a security event).

## Trace storage

Every call — successful or `insufficient_evidence` — writes a `RagQueryTrace` row: question, answer,
confidence, citations, retrieved chunk IDs, `insufficient_evidence`, model name, generation time, and any
prompt-injection flags. This is the audit trail for "why did the AI say that" — every answer is
reconstructable after the fact without re-running the model.

## Security

Retrieval is always scoped by `organization_id` before anything reaches the model (`search_knowledge`, see
[KNOWLEDGE_SYSTEM.md](KNOWLEDGE_SYSTEM.md)) — there is no code path where one organization's documents can
appear in another organization's answer.

## Known limitations

- `generation_time_ms` measures wall-clock time for the whole retrieval+generation call, not model-only
  inference time (retrieval is fast relative to generation, so this is a reasonable proxy, not a precise
  breakdown).
- No answer caching — identical questions re-embed and re-retrieve every time. Acceptable at MVP scale;
  worth revisiting if `/ask` becomes a hot path.
