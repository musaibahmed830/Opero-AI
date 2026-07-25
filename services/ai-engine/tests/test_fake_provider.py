from pydantic import BaseModel

from opero_ai_engine.fake_provider import FakeProvider
from opero_ai_engine.provider import (
    GenerationRequest,
    ModelProviderError,
    StructuredGenerationRequest,
)


class _Classification(BaseModel):
    label: str = "unclassified"


async def test_healthy_fake_provider_generates() -> None:
    provider = FakeProvider(fixed_response="canned answer")
    result = await provider.generate(GenerationRequest(messages=[]))

    assert result.content == "canned answer"


async def test_unhealthy_fake_provider_raises_retryable_error_on_generate() -> None:
    provider = FakeProvider(healthy=False)

    try:
        await provider.generate(GenerationRequest(messages=[]))
        raised = False
    except ModelProviderError as exc:
        raised = True
        assert exc.retryable is True

    assert raised


async def test_fake_provider_health_reflects_configured_state() -> None:
    healthy_provider = FakeProvider(healthy=True)
    unhealthy_provider = FakeProvider(healthy=False)

    assert (await healthy_provider.health()).healthy is True
    assert (await unhealthy_provider.health()).healthy is False


async def test_fake_provider_embed_returns_consistent_dimension() -> None:
    provider = FakeProvider(embedding_dim=5)
    vectors = await provider.embed(["a", "bb"])

    assert len(vectors) == 2
    assert all(len(v) == 5 for v in vectors)


async def test_fake_provider_generate_structured_constructs_schema() -> None:
    provider = FakeProvider()
    result = await provider.generate_structured(StructuredGenerationRequest(messages=[]), _Classification)

    assert isinstance(result, _Classification)
