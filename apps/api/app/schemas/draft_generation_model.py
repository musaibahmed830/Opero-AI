from pydantic import BaseModel, Field

from app.schemas.common import Confidence


class DraftGenerationModelResponse(BaseModel):
    """docs/EMAIL_INTELLIGENCE.md Part 4 "Reply Draft Generation" — rules
    enforced by the system prompt, not just this schema: never invent price,
    policy, timeline, discount, refund, commitment, or legal statement; never
    disclose internal documents; never promise work without authorization.
    `missing_information` is how the model tells a human reviewer what it
    couldn't answer from available context, instead of guessing.
    """

    subject: str
    body: str
    tone: str = Field(description="A short label, e.g. 'professional', 'empathetic', 'formal'.")
    referenced_chunk_indices: list[int] = Field(
        default_factory=list, description="Which numbered knowledge chunks (if any) were used."
    )
    missing_information: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    confidence: Confidence
