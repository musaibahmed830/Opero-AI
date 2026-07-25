import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import AuthenticatedUser
from app.schemas.knowledge import AskRequest, RagAnswerResponse, SearchResultResponse
from app.services.knowledge_search import search_knowledge
from app.services.rag import answer_question
from app.services.rbac import require_permission

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.get("/search", response_model=list[SearchResultResponse])
async def search(
    query: str = Query(min_length=1, max_length=2000),
    top_k: int | None = Query(default=None, ge=1, le=50),
    similarity_threshold: float | None = Query(default=None, ge=0.0, le=1.0),
    document_id: uuid.UUID | None = Query(default=None),
    mime_type: str | None = Query(default=None),
    uploaded_after: datetime | None = Query(default=None),
    uploaded_before: datetime | None = Query(default=None),
    current_user: AuthenticatedUser = Depends(require_permission("documents.read")),
    db: AsyncSession = Depends(get_db),
) -> list[SearchResultResponse]:
    settings = get_settings()
    threshold = (
        similarity_threshold if similarity_threshold is not None else settings.rag_similarity_threshold
    )
    results = await search_knowledge(
        db,
        organization_id=uuid.UUID(current_user.organization_id),
        query_text=query,
        top_k=top_k or settings.rag_top_k,
        similarity_threshold=threshold,
        document_id=document_id,
        mime_type=mime_type,
        uploaded_after=uploaded_after,
        uploaded_before=uploaded_before,
    )
    return [SearchResultResponse(**r.__dict__) for r in results]


@router.post("/ask", response_model=RagAnswerResponse)
async def ask(
    payload: AskRequest,
    current_user: AuthenticatedUser = Depends(require_permission("documents.read")),
    db: AsyncSession = Depends(get_db),
) -> RagAnswerResponse:
    result = await answer_question(
        db,
        organization_id=uuid.UUID(current_user.organization_id),
        user_id=uuid.UUID(current_user.subject),
        question=payload.question,
    )
    return RagAnswerResponse(
        answer=result.answer,
        confidence=result.confidence,
        citations=result.citations,
        retrieved_chunks=[SearchResultResponse(**c.__dict__) for c in result.retrieved_chunks],
        insufficient_evidence=result.insufficient_evidence,
        model_name=result.model_name,
        generation_time_ms=result.generation_time_ms,
        trace_id=result.trace_id,
        prompt_injection_flags=[
            {"pattern_name": f.pattern_name, "matched_text": f.matched_text}
            for f in result.prompt_injection_flags
        ],
    )
