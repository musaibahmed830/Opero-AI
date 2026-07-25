"""The ModelProvider interface (docs/AI_ARCHITECTURE.md §2).

Every call into the model layer goes through this interface. No orchestration/
memory/execution code should import a provider implementation directly —
callers depend on `ModelProvider`, and a factory (app/services/ai_provider.py
in the API service) decides which concrete implementation to construct from
config.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class ModelProviderError(Exception):
    """Raised by any provider implementation instead of a raw transport exception.

    `retryable` distinguishes transient failures (connection refused, timeout)
    from non-transient ones (schema validation failure) — callers above the
    provider layer never need to know the transport to decide whether retrying
    makes sense.
    """

    def __init__(self, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.retryable = retryable


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str


@dataclass(frozen=True)
class GenerationRequest:
    messages: list[ChatMessage]
    temperature: float = 0.2
    timeout_seconds: float = 60.0


@dataclass(frozen=True)
class StructuredGenerationRequest:
    messages: list[ChatMessage]
    temperature: float = 0.0
    timeout_seconds: float = 60.0


@dataclass(frozen=True)
class GenerationResult:
    content: str
    model: str
    finish_reason: str
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderHealth:
    healthy: bool
    detail: str = ""


@dataclass(frozen=True)
class ProviderMetadata:
    provider_name: str
    model_name: str
    context_window: int | None = None


class ModelProvider(ABC):
    @abstractmethod
    async def health(self) -> ProviderHealth: ...

    @abstractmethod
    async def generate(self, request: GenerationRequest) -> GenerationResult: ...

    @abstractmethod
    async def generate_structured(self, request: StructuredGenerationRequest, schema: type[T]) -> T: ...

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]: ...

    @abstractmethod
    def metadata(self) -> ProviderMetadata: ...
