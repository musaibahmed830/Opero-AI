from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter(tags=["version"])

API_VERSION = "0.1.0"


@router.get("/version")
async def version() -> dict[str, str]:
    settings = get_settings()
    return {"version": API_VERSION, "environment": settings.environment}
