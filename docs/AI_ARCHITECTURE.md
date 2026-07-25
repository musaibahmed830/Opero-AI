# AI Architecture

Scope: the model-provider abstraction and the memory/reasoning concepts it supports. This document defines the
**interface** the rest of the system programs against; it does not describe the full reasoning/planning engine
(that's [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) §2.2), which is Phase 3+ work per
[DEVELOPMENT_ROADMAP.md](DEVELOPMENT_ROADMAP.md). Phase 2 builds the provider interface and one working
implementation — it explicitly does not implement autonomous task execution.

## 1. Why an Interface, Not a Client Library

The founder's AI model policy is a product-defensibility argument, not just a cost argument (see
[PRODUCT_REQUIREMENTS.md](PRODUCT_REQUIREMENTS.md) §6): if the product's value were "we call a vendor's API well,"
it wouldn't be a moat, and it would be trivially cloned. Every call into a model — for generation, structured
output, or embeddings — goes through one interface, implemented in `services/ai-engine`. No other service imports
an inference SDK directly.

## 2. The `ModelProvider` Interface

```python
class ModelProvider(Protocol):
    async def health(self) -> ProviderHealth: ...
    async def generate(self, request: GenerationRequest) -> GenerationResult: ...
    async def generate_structured(self, request: StructuredGenerationRequest, schema: type[T]) -> T: ...
    async def embed(self, texts: list[str]) -> list[list[float]]: ...
    def metadata(self) -> ProviderMetadata: ...
```

| Method | Purpose | Notes |
|---|---|---|
| `health()` | Liveness/readiness check against the underlying runtime | Used by the API's own `/readyz`-equivalent for the AI layer and by ops monitoring |
| `generate()` | Free-text completion given messages | Timeout + retry policy applied uniformly (see §4) |
| `generate_structured()` | Completion constrained to a caller-supplied schema (Pydantic model) | Backs anything that needs a reliable shape — draft+citation objects, classification labels — rather than parsing free text |
| `embed()` | Text → vector, for pgvector-backed retrieval | Same interface regardless of whether the embedding model is served by Ollama or a future dedicated embedding server |
| `metadata()` | Model name, context window, provider identity | For logging/audit — every generation is traceable to *which* model produced it |

**Design consequence:** swapping the provider (Ollama → vLLM, or one open-weight model → another) is a
configuration change (which provider class gets constructed, and with what model name/endpoint), never a change
to calling code. This is the same shape as the model-router concept already in
[TECHNOLOGY_STACK.md](TECHNOLOGY_STACK.md) §1, formalized as an actual interface in Phase 2.

## 3. First Implementation: Ollama

- Runtime: Ollama, running as a local process/container, exposing an HTTP API on `localhost:11434` by default.
- Model: **`qwen2.5:7b-instruct` (confirmed default)**, pulled via `ollama pull` — no training or fine-tuning
  in this phase, per the founder's explicit instruction. `qwen2.5:14b-instruct` (9GB) was the original
  default but was hardware-tested, not just assumed, and failed to load in an 8GB Docker VM alongside the
  rest of the stack (Postgres/Temporal/etc.) — `ggml_aligned_malloc: insufficient memory`. 7B (4.7GB)
  confirmed working end to end. Bump this back up via `MODEL_REASONING_NAME` on hardware with more headroom.
- `OllamaProvider` implements `ModelProvider` using plain HTTP calls against Ollama's REST API
  (`/api/chat` for generation, `/api/embed` for embeddings) — no heavier SDK, consistent with how the Gmail
  integration avoids `google-api-python-client` in favor of direct REST calls
  (see `apps/api/app/services/gmail_client.py`).
- Structured output: Ollama supports a `format` parameter constraining output to a JSON schema; `generate_structured()`
  passes the caller's Pydantic schema through as that constraint and validates the response against it, raising a
  typed error if the model's output doesn't parse — callers never receive an unvalidated dict.

## 4. Reliability Behavior (all providers, not just Ollama)

- **Timeouts:** every provider call has an explicit timeout (config-driven, default 60s for generation, 30s for
  embeddings) — a hung local model must not hang the calling request indefinitely.
- **Retries:** transient failures (connection refused during Ollama startup, timeout) get a bounded retry (2
  attempts, short backoff) at the provider layer. Non-transient failures (schema validation failure, 4xx-shaped
  errors) do not retry — retrying a malformed request just wastes time.
- **Errors:** provider failures surface as a typed `ModelProviderError` (with a `retryable: bool` flag), not a
  raw `httpx` exception — callers above the provider layer never need to know the transport.

## 5. Confidence and Hallucination Reduction (design note, not yet implemented)

Per [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) §2.2, drafts must cite the memory/knowledge chunks that
grounded them. `generate_structured()` is what makes this enforceable: the response schema for a draft reply
requires a `citations: list[str]` field, so a response that doesn't cite anything is a schema validation failure,
not a silent quality problem. The actual grounding/retrieval pipeline that populates context for this is Phase 3+
(Knowledge Engine) — Phase 2 only guarantees the interface can carry citations end to end.

## 6. Memory Architecture (schema now, engine later)

[SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) §2.3 describes four memory layers (short-term, episodic,
semantic/company-knowledge, long-term facts). Phase 2 creates the `MemoryRecord` table
(see [DATABASE_DESIGN.md](DATABASE_DESIGN.md)) that all four layers will be persisted through, distinguished by a
`memory_type` column — but the retrieval/ranking logic that fans out across layers (the "Memory Service" in the
architecture doc) is not built in this phase. Storing memory and reasoning over memory are deliberately separated
so the schema can exist and be tested before the reasoning engine that consumes it is built.

## 7. What Phase 2 Explicitly Does Not Include

- Autonomous task execution (the model proposing and then itself executing an action) — approval-gated execution
  is Phase 3+ (Execution Engine), and even then requires human approval for irreversible actions per
  [SECURITY_MODEL.md](SECURITY_MODEL.md).
- Multi-agent communication — only one AI employee role (`AIEmployee` model) exists in the schema; there's
  nothing yet for it to communicate with.
- Fine-tuning or any model training.
- A closed-model provider tier (see [TECHNOLOGY_STACK.md](TECHNOLOGY_STACK.md) §1).

## 8. Open Decisions

1. **Resolved for local dev:** `qwen2.5:7b-instruct`, confirmed by actually loading it (§3). Production
   deployments on beefier hardware may want `14b` or `32b` instead — still an open call, now with a real
   memory data point to size against instead of a guess. See
   [DECISIONS_REQUIRED_FROM_FOUNDER.md](DECISIONS_REQUIRED_FROM_FOUNDER.md).
2. Confirm whether embeddings run through Ollama (`nomic-embed-text`) or a separate lightweight embedding server —
   Phase 2 defaults to Ollama for both to minimize moving parts; revisit if embedding throughput becomes a
   bottleneck once the Knowledge Engine (Phase 3+) is doing real document ingestion volume.
