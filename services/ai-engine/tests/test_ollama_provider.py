import httpx
import pytest
from pydantic import BaseModel

from opero_ai_engine.ollama_provider import OllamaProvider
from opero_ai_engine.provider import (
    ChatMessage,
    GenerationRequest,
    ModelProviderError,
    StructuredGenerationRequest,
)


class _DraftReply(BaseModel):
    reply: str
    citations: list[str]


def _provider(handler) -> OllamaProvider:
    transport = httpx.MockTransport(handler)
    return OllamaProvider(
        base_url="http://fake-ollama:11434",
        reasoning_model="qwen2.5:14b-instruct",
        embedding_model="nomic-embed-text",
        transport=transport,
    )


async def test_health_reports_healthy_on_200() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/tags"
        return httpx.Response(200, json={"models": []})

    provider = _provider(handler)
    health = await provider.health()

    assert health.healthy is True


async def test_health_reports_unhealthy_on_non_200() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    provider = _provider(handler)
    health = await provider.health()

    assert health.healthy is False
    assert "500" in health.detail


async def test_health_reports_unhealthy_on_connection_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    provider = _provider(handler)
    health = await provider.health()

    assert health.healthy is False


async def test_generate_returns_message_content() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/chat"
        return httpx.Response(
            200, json={"message": {"content": "hello there"}, "model": "qwen2.5:14b-instruct", "done": True}
        )

    provider = _provider(handler)
    result = await provider.generate(GenerationRequest(messages=[ChatMessage(role="user", content="hi")]))

    assert result.content == "hello there"
    assert result.finish_reason == "stop"


async def test_generate_retries_transient_failure_then_succeeds() -> None:
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise httpx.TimeoutException("timed out", request=request)
        return httpx.Response(200, json={"message": {"content": "ok on retry"}, "done": True})

    provider = _provider(handler)
    result = await provider.generate(GenerationRequest(messages=[ChatMessage(role="user", content="hi")]))

    assert call_count["n"] == 2
    assert result.content == "ok on retry"


async def test_generate_raises_retryable_error_after_exhausting_attempts() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("still down", request=request)

    provider = _provider(handler)

    with pytest.raises(ModelProviderError) as exc_info:
        await provider.generate(GenerationRequest(messages=[ChatMessage(role="user", content="hi")]))

    assert exc_info.value.retryable is True


async def test_generate_structured_parses_valid_json_into_schema() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/chat"
        return httpx.Response(
            200,
            json={
                "message": {"content": '{"reply": "Sure, here is the info.", "citations": ["doc-1"]}'},
                "done": True,
            },
        )

    provider = _provider(handler)
    result = await provider.generate_structured(
        StructuredGenerationRequest(messages=[ChatMessage(role="user", content="hi")]), _DraftReply
    )

    assert result.reply == "Sure, here is the info."
    assert result.citations == ["doc-1"]


async def test_generate_structured_raises_non_retryable_error_on_malformed_json() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"message": {"content": "not json at all"}, "done": True})

    provider = _provider(handler)

    with pytest.raises(ModelProviderError) as exc_info:
        await provider.generate_structured(
            StructuredGenerationRequest(messages=[ChatMessage(role="user", content="hi")]), _DraftReply
        )

    assert exc_info.value.retryable is False


async def test_embed_returns_vectors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/embed"
        return httpx.Response(200, json={"embeddings": [[0.1, 0.2, 0.3]]})

    provider = _provider(handler)
    vectors = await provider.embed(["hello world"])

    assert vectors == [[0.1, 0.2, 0.3]]
