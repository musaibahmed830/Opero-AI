import uuid

from pydantic import BaseModel, Field


class SearchResultResponse(BaseModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_title: str
    chunk_index: int
    content: str
    similarity: float


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class InjectionFlagResponse(BaseModel):
    pattern_name: str
    matched_text: str


class RagAnswerResponse(BaseModel):
    answer: str
    confidence: float
    citations: list[dict]
    retrieved_chunks: list[SearchResultResponse]
    insufficient_evidence: bool
    model_name: str
    generation_time_ms: int
    trace_id: uuid.UUID
    prompt_injection_flags: list[InjectionFlagResponse]
