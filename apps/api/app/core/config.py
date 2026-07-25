from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_nested_delimiter="__", extra="ignore")

    environment: str = "development"

    database_url: str = Field(
        default="postgresql+asyncpg://opero:opero@localhost:5432/opero",
        description="Async SQLAlchemy connection string.",
    )
    redis_url: str = Field(default="redis://localhost:6379/0")

    # Local email/password session auth — the MVP AuthN mechanism (docs/SECURITY_MODEL.md §3).
    # No default — see the same rationale as token_encryption_key below.
    session_signing_key: str = Field(description="HMAC secret for signing local-auth session JWTs.")

    # OIDC — a *future* SSO login path (app/core/oidc.py), not wired into any route yet.
    auth_issuer: str = Field(default="", description="OIDC issuer URL, e.g. https://tenant.auth0.com/")
    auth_audience: str = Field(default="", description="Expected JWT audience for this API.")

    # AI provider — Ollama for local dev (docs/AI_ARCHITECTURE.md §3). Swapping the model,
    # or swapping Ollama for vLLM entirely, is a config change (services/ai-engine).
    # qwen2.5:14b-instruct (9GB) was the original default but doesn't reliably load
    # alongside the rest of the stack (Postgres/Temporal/etc.) in an 8GB Docker VM —
    # verified by actually trying it, not assumed. 7b (4.7GB) is the confirmed-working
    # default; bump it back up on hardware with more headroom via this env var.
    ollama_base_url: str = Field(default="http://localhost:11434")
    model_reasoning_name: str = Field(default="qwen2.5:7b-instruct")
    model_embedding_name: str = Field(default="nomic-embed-text")

    otel_exporter_otlp_endpoint: str = Field(default="")
    otel_service_name: str = Field(default="opero-api")

    cors_allowed_origins: str = Field(
        default="http://localhost:3000,http://localhost:3001,http://localhost:3002,http://localhost:3010",
        description="Comma-separated dashboard origins allowed to call this API.",
    )

    @property
    def cors_allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]

    # Rate limiting foundation (docs/SECURITY_MODEL.md §9) — hook exists, thresholds not yet tuned.
    rate_limit_per_minute: int = Field(default=120)

    # Secret-at-rest encryption (docs/SYSTEM_ARCHITECTURE.md §4). Must be a
    # urlsafe-base64-encoded 32-byte key, e.g. `Fernet.generate_key()`. No default —
    # a shared, checked-in key would defeat the point of encrypting tokens at rest,
    # so a deployment that forgets to set this fails to start rather than silently
    # using a key every reader of this source tree also has.
    token_encryption_key: str = Field(
        description="Fernet key for encrypting connected-account OAuth tokens at rest."
    )

    # Gmail OAuth (docs/MVP_SCOPE.md, MVP feature 1).
    google_oauth_client_id: str = Field(default="")
    google_oauth_client_secret: str = Field(default="")
    google_oauth_redirect_uri: str = Field(default="http://localhost:8000/integrations/gmail/callback")

    # Signs the short-lived OAuth `state` param (app/core/oauth_state.py). Deliberately
    # separate from token_encryption_key — different cryptographic purpose (signing vs.
    # encrypting), so a compromise of one doesn't automatically compromise the other.
    oauth_state_secret: str = Field(description="HMAC secret for signing OAuth state tokens.")

    # Document storage (docs/KNOWLEDGE_SYSTEM.md) — MinIO, already part of the compose stack.
    minio_endpoint: str = Field(default="localhost:9000")
    minio_access_key: str = Field(default="opero")
    minio_secret_key: str = Field(default="opero-dev-secret")
    minio_bucket: str = Field(default="opero-documents")
    minio_secure: bool = Field(default=False)

    # Document ingestion limits (docs/KNOWLEDGE_SYSTEM.md "Validate file size").
    max_document_size_bytes: int = Field(default=25 * 1024 * 1024, description="25MB default cap.")

    # Chunking defaults (docs/KNOWLEDGE_SYSTEM.md "Chunking") — character-based, not
    # token-based, to avoid a tokenizer dependency; token_estimate on each chunk is a
    # rough len()/4 approximation, documented as such wherever it's used.
    chunk_size_chars: int = Field(default=1000)
    chunk_overlap_chars: int = Field(default=150)
    min_chunk_length_chars: int = Field(default=50)

    # RAG defaults (docs/RAG_PIPELINE.md).
    rag_top_k: int = Field(default=5)
    rag_similarity_threshold: float = Field(default=0.5)


@lru_cache
def get_settings() -> Settings:
    return Settings()
