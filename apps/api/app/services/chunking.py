"""Configurable text chunking (docs/KNOWLEDGE_SYSTEM.md "Chunking").

Character-based (not token-based) sizing, with paragraph-aware packing:
paragraphs are packed greedily up to `chunk_size`, and a chunk that would
otherwise start mid-thought instead carries the tail of the previous chunk
forward as overlap. The whole strategy is one function behind a stable
signature — swapping it for a smarter (e.g. sentence-embedding-aware) chunker
later doesn't touch any caller.
"""

from dataclasses import dataclass

DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 150
DEFAULT_MIN_CHUNK_LENGTH = 50


@dataclass(frozen=True)
class Chunk:
    text: str
    token_estimate: int


def estimate_tokens(text: str) -> int:
    """A rough, deliberately-labeled-as-a-heuristic estimate (~4 chars/token for
    English) — good enough for reporting/context-budget purposes, not an
    actual tokenizer count.
    """
    return max(1, len(text) // 4)


def chunk_text(
    text: str,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    min_chunk_length: int = DEFAULT_MIN_CHUNK_LENGTH,
) -> list[Chunk]:
    if not text.strip():
        return []

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        paragraphs = [text.strip()]

    raw_chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}" if current else paragraph

        if len(candidate) <= chunk_size:
            current = candidate
            continue

        if current:
            raw_chunks.append(current)

        if len(paragraph) <= chunk_size:
            current = paragraph
        else:
            # A single paragraph longer than chunk_size: hard-split it.
            for start in range(0, len(paragraph), chunk_size):
                raw_chunks.append(paragraph[start : start + chunk_size])
            current = ""

    if current:
        raw_chunks.append(current)

    # Apply overlap: each chunk after the first carries the tail of the
    # previous *raw* chunk forward, so retrieval near a chunk boundary still
    # has surrounding context.
    overlapped_chunks: list[str] = []
    for i, raw in enumerate(raw_chunks):
        if i == 0 or chunk_overlap <= 0:
            overlapped_chunks.append(raw)
        else:
            tail = raw_chunks[i - 1][-chunk_overlap:]
            overlapped_chunks.append(f"{tail}{raw}")

    return [
        Chunk(text=c, token_estimate=estimate_tokens(c))
        for c in overlapped_chunks
        if len(c) >= min_chunk_length
    ]
