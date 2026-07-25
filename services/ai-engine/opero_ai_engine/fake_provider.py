"""A deterministic, in-memory ModelProvider — for tests, and for running the
rest of the stack without a live Ollama daemon. Never used by default in a real
deployment; wired in only where a caller explicitly asks for it (docs/AI_ARCHITECTURE.md).
"""

from typing import TypeVar

from pydantic import BaseModel

from opero_ai_engine.provider import (
    GenerationRequest,
    GenerationResult,
    ModelProvider,
    ModelProviderError,
    ProviderHealth,
    ProviderMetadata,
    StructuredGenerationRequest,
)

T = TypeVar("T", bound=BaseModel)


class FakeProvider(ModelProvider):
    def __init__(
        self,
        *,
        fixed_response: str = "This is a fake provider response.",
        healthy: bool = True,
        embedding_dim: int = 8,
    ) -> None:
        self._fixed_response = fixed_response
        self._healthy = healthy
        self._embedding_dim = embedding_dim

    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(provider_name="fake", model_name="fake-model")

    async def health(self) -> ProviderHealth:
        detail = "" if self._healthy else "fake provider set unhealthy"
        return ProviderHealth(healthy=self._healthy, detail=detail)

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        if not self._healthy:
            raise ModelProviderError("Fake provider is unhealthy", retryable=True)
        return GenerationResult(content=self._fixed_response, model="fake-model", finish_reason="stop")

    async def generate_structured(self, request: StructuredGenerationRequest, schema: type[T]) -> T:
        if not self._healthy:
            raise ModelProviderError("Fake provider is unhealthy", retryable=True)
        try:
            return schema.model_construct()
        except Exception as exc:  # pragma: no cover - only if schema has no defaults
            raise ModelProviderError(
                f"Cannot construct {schema.__name__} without input: {exc}", retryable=False
            ) from exc

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not self._healthy:
            raise ModelProviderError("Fake provider is unhealthy", retryable=True)
        return [[float(len(text) % 7)] * self._embedding_dim for text in texts]
