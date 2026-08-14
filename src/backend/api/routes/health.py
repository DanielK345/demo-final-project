from fastapi import APIRouter

from src.backend.api.deps import get_app_settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    settings = get_app_settings()
    return {"status": "ok", "env": settings.app_env}


@router.get("/ready")
async def ready() -> dict[str, str]:
    return {"status": "ready"}
