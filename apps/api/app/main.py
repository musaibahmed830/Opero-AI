from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.middleware.error_handling import register_exception_handlers
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.request_id import RequestIDMiddleware
from app.routers import (
    ai_employees,
    approvals,
    audit_logs,
    auth,
    documents,
    emails,
    gmail,
    health,
    knowledge,
    leads,
    reports,
    tasks,
    version,
)

settings = get_settings()
configure_logging()

app = FastAPI(
    title="Opero AI API",
    description="AI Sales & Operations Assistant — core API and agent orchestrator.",
    version=version.API_VERSION,
)

register_exception_handlers(app)

# Middleware executes in reverse of registration order (last added = outermost),
# so CORS wraps everything, then request-ID tagging, then rate limiting closest
# to the route handlers.
app.add_middleware(RateLimitMiddleware)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# /healthz, /readyz, /version are unversioned — infra probes and clients alike
# hit these directly without an API version prefix.
app.include_router(health.router)
app.include_router(version.router)

# Everything else is versioned (docs/DEVELOPMENT_ROADMAP.md Phase 2 backend
# foundation: "API versioning").
app.include_router(auth.router, prefix="/v1")
app.include_router(gmail.router, prefix="/v1")
app.include_router(approvals.router, prefix="/v1")
app.include_router(ai_employees.router, prefix="/v1")
app.include_router(audit_logs.router, prefix="/v1")
app.include_router(documents.router, prefix="/v1")
app.include_router(knowledge.router, prefix="/v1")
app.include_router(emails.router, prefix="/v1")
app.include_router(leads.router, prefix="/v1")
app.include_router(tasks.router, prefix="/v1")
app.include_router(reports.router, prefix="/v1")

FastAPIInstrumentor.instrument_app(app)
