"""Constructs the configured ModelProvider (docs/AI_ARCHITECTURE.md §2).

The only place in apps/api that imports a concrete provider implementation —
everything else depends on `opero_ai_engine.ModelProvider`. Swapping Ollama for
another provider is a change to this one function, not to any caller.
"""

from functools import lru_cache

from opero_ai_engine import ModelProvider, OllamaProvider

from app.core.config import get_settings


@lru_cache
def get_model_provider() -> ModelProvider:
    settings = get_settings()
    return OllamaProvider(
        base_url=settings.ollama_base_url,
        reasoning_model=settings.model_reasoning_name,
        embedding_model=settings.model_embedding_name,
    )
