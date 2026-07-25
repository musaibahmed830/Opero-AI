from pydantic import BaseModel, Field


class RagModelResponse(BaseModel):
    """The schema the model must fill in — validated before anything downstream
    trusts it (docs/RAG_PIPELINE.md, docs/SECURITY_MODEL.md §16 "Safe JSON
    schema validation").
    """

    answer: str = Field(description="The answer, grounded only in the numbered context chunks provided.")
    insufficient_evidence: bool = Field(
        description="True if the provided context does not contain enough information to answer confidently."
    )
    supporting_chunk_indices: list[int] = Field(
        default_factory=list,
        description="Which numbered context chunks (0-based) were actually used to produce the answer.",
    )
