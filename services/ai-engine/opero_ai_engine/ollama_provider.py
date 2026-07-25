"""Ollama implementation of ModelProvider (docs/AI_ARCHITECTURE.md §3).

Plain httpx calls against Ollama's REST API — no SDK. Ollama's HTTP surface is
simple enough that a client library would only add an abstraction we'd have to
work around, the same reasoning behind the Gmail integration's direct REST
calls (apps/api/app/services/gmail_client.py).
"""

import json
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from opero_ai_engine.provider import (
    ChatMessage,
    GenerationRequest,
    GenerationResult,
    ModelProvider,
    ModelProviderError,
    ProviderHealth,
    ProviderMetadata,
    StructuredGenerationRequest,
)

T = TypeVar("T", bound=BaseModel)

_MAX_ATTEMPTS = 2


async def _with_retry(coro_fn, *, attempts: int = _MAX_ATTEMPTS):
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return await coro_fn()
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            last_error = exc
            if attempt == attempts:
                break
    raise ModelProviderError(f"Ollama unreachable after {attempts} attempts: {last_error}", retryable=True)


class OllamaProvider(ModelProvider):
    def __init__(
        self,
        base_url: str,
        reasoning_model: str,
        embedding_model: str,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._reasoning_model = reasoning_model
        self._embedding_model = embedding_model
        # Injectable only for tests (httpx.MockTransport) — real deployments never
        # pass this, so behavior against actual Ollama is unaffected.
        self._transport = transport

    def _client(self, timeout: float) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=self._base_url, timeout=timeout, transport=self._transport)

    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(provider_name="ollama", model_name=self._reasoning_model)

    async def health(self) -> ProviderHealth:
        try:
            async with self._client(10.0) as client:
                response = await client.get("/api/tags")
            if response.status_code != 200:
                return ProviderHealth(healthy=False, detail=f"HTTP {response.status_code}")
            return ProviderHealth(healthy=True)
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            return ProviderHealth(healthy=False, detail=str(exc))

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        payload = {
            "model": self._reasoning_model,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "stream": False,
            "options": {"temperature": request.temperature},
        }

        async def _call() -> httpx.Response:
            async with self._client(request.timeout_seconds) as client:
                response = await client.post("/api/chat", json=payload)
                response.raise_for_status()
                return response

        response = await _with_retry(_call)
        data = response.json()
        return GenerationResult(
            content=data["message"]["content"],
            model=data.get("model", self._reasoning_model),
            finish_reason="stop" if data.get("done") else "unknown",
            raw=data,
        )

    async def generate_structured(self, request: StructuredGenerationRequest, schema: type[T]) -> T:
        payload = {
            "model": self._reasoning_model,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "stream": False,
            "format": schema.model_json_schema(),
            "options": {"temperature": request.temperature},
        }

        async def _call() -> httpx.Response:
            async with self._client(request.timeout_seconds) as client:
                response = await client.post("/api/chat", json=payload)
                response.raise_for_status()
                return response

        response = await _with_retry(_call)
        data = response.json()
        raw_content = data["message"]["content"]

        try:
            parsed = json.loads(raw_content)
            return schema.model_validate(parsed)
        except (json.JSONDecodeError, ValidationError) as exc:
            raise ModelProviderError(
                f"Model output did not match schema {schema.__name__}: {exc}", retryable=False
            ) from exc

    async def embed(self, texts: list[str]) -> list[list[float]]:
        payload = {"model": self._embedding_model, "input": texts}

        async def _call() -> httpx.Response:
            async with self._client(30.0) as client:
                response = await client.post("/api/embed", json=payload)
                response.raise_for_status()
                return response

        response = await _with_retry(_call)
        data = response.json()
        return data["embeddings"]


__all__ = ["OllamaProvider", "ChatMessage"]
