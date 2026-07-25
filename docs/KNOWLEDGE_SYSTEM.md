# Knowledge System

Phase 3's document ingestion pipeline: company documents in, searchable, embedded, org-isolated knowledge
chunks out. This is the foundation both the RAG `/knowledge/ask` endpoint (see
[RAG_PIPELINE.md](RAG_PIPELINE.md)) and reply-draft generation ground themselves in — no other part of the
system is allowed to answer from a model's general knowledge about the organization.

## Pipeline

```
upload (multipart) -> validate type/size -> checksum -> dedupe -> store in MinIO -> Document row (uploaded)
    -> [background job] extract text -> clean -> chunk -> embed -> DocumentChunk rows -> Document row (ready)
```

Upload (`app/services/document_ingestion.py::create_document`) and processing (`::process_document`) are
deliberately separate steps. Upload must respond quickly and reject duplicates before anything expensive
happens; processing (extraction, chunking, embedding — the slow part) runs as a Celery task
(`app/workers/tasks.py::process_document_task`) so a slow or failed extraction never blocks the HTTP
request that created the document.

## Supported document types

PDF (`pypdf`), DOCX (`python-docx`), TXT, Markdown, CSV — all local, open-source libraries
(`app/services/text_extraction.py`). No third-party document-processing API is used anywhere, per the
founder's explicit constraint. CSV is reconstructed as header-aware `key: value` blocks per row rather than
raw comma-separated text, since that reads far better as retrieval context than a literal CSV dump.

## Document statuses

`uploaded -> processing -> ready` (happy path), or `-> failed` (extraction/chunking/embedding threw — the
error is recorded in `processing_error` and the document stays queryable/re-processable, never silently
dropped), or `-> archived` (soft-delete via `POST /documents/{id}/archive` — archived documents are excluded
from search but the row and chunks are kept for audit purposes).

## Required metadata

Every `Document` row (`app/models/document.py`) tracks: `uploaded_by`, `original_filename` (as given by the
client — display only), `safe_filename` (a UUID-generated name actually used for storage, so a
path-traversal or special-character filename from a user can never reach the filesystem/object-store path —
see `app/services/document_validation.py::generate_safe_filename`), `mime_type`, `file_size`, `checksum`,
`storage_path`, `version`, and the processing-status fields above.

## Duplicate prevention

SHA-256 checksum of the raw file bytes, unique per `(organization_id, checksum)`
(`uq_document_org_checksum`). Re-uploading the exact same file to the same organization is rejected with a
`409` and the existing document's ID, never silently re-ingested or duplicated
(`DuplicateDocumentError` in `document_ingestion.py`). Re-uploading a *changed* version of a document is
not deduplicated (different checksum) — creates a new `Document` row; there is no "supersedes" link between
versions yet (see Known Limitations).

## Chunking

`app/services/chunking.py::chunk_text` — paragraph-aware greedy packing with character-based overlap.
Configurable via `CHUNK_SIZE_CHARS` (default 1000), `CHUNK_OVERLAP_CHARS` (default 150),
`MIN_CHUNK_LENGTH_CHARS` (default 50, drops trailing scraps too short to be useful context). Token counts
stored per chunk (`DocumentChunk.token_estimate`) are a `len(text) // 4` heuristic, not a real tokenizer —
documented as such in the code, good enough for the retrieval bookkeeping it's used for (nothing enforces a
hard token budget from it yet).

## Embeddings

`nomic-embed-text` via the same `ModelProvider.embed()` interface used everywhere else
(`app/services/ai_provider.py`) — 768-dimensional vectors, stored in `DocumentChunk.embedding`
(`pgvector`'s `Vector(768)` type, `EMBEDDING_DIM` constant shared with `MemoryRecord` from Phase 2).

## Semantic search

`app/services/knowledge_search.py::search_knowledge` — cosine similarity (`embedding.cosine_distance()`)
against `DocumentChunk.embedding`, always filtered by `organization_id` and `processing_status == ready`
(archived/failed/still-processing documents never surface in search results). Supports `top_k`,
`similarity_threshold`, and optional `document_id` / `mime_type` / `uploaded_after` / `uploaded_before`
filters. Exposed directly at `GET /v1/knowledge/search` and used internally by both the RAG service and
reply-draft generation.

## Security

- Every query is scoped by `organization_id` — verified in `tests/test_documents.py` and
  `tests/test_knowledge.py` (`test_document_not_visible_across_organizations`,
  `test_search_not_visible_across_organizations`).
- Uploaded content is never trusted: document text is treated as untrusted input the moment it's
  extracted, scanned for prompt-injection patterns before being used as RAG/draft context (see
  [PROMPT_INJECTION_DEFENCE.md](PROMPT_INJECTION_DEFENCE.md)), and never executed or interpreted as
  instructions.
- File type is validated by extension against a fixed allow-list (not by trusting the client-supplied
  `Content-Type` header) and size is capped (`MAX_DOCUMENT_SIZE_BYTES`, default 25MB) before any bytes are
  read into memory for processing.

## Known limitations

- No document-version "supersedes" relationship — a re-upload of a changed file creates an independent
  `Document` row rather than a new version of the same logical document (`Document.version` exists in the
  schema for this but nothing increments it yet).
- `token_estimate` is a heuristic, not a real tokenizer count.
- No OCR — a scanned/image-only PDF will extract no text and the document will land in `failed` with a
  clear `processing_error`, not silently produce empty chunks.
