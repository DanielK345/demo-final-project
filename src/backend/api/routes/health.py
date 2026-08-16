import asyncio

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from src.backend.api.deps import get_app_settings
from src.backend.db.base import get_engine
from src.voice.asr.zipformer.service import get_zipformer_service

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    settings = get_app_settings()
    return {"status": "ok", "env": settings.app_env}


@router.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "alive"}


@router.get("/ready")
@router.get("/health/ready")
async def ready(response: Response) -> dict[str, object]:
    settings = get_app_settings()
    asr = get_zipformer_service()
    config_errors = settings.production_readiness_errors()
    checks: dict[str, str] = {
        "configuration": "ok" if not config_errors else "failed",
        "database": "not_checked" if config_errors else "pending",
        "asr": "ok" if asr.ready else "failed",
    }
    error_codes = list(config_errors)

    if not config_errors:
        try:
            async with asyncio.timeout(settings.database_readiness_timeout_seconds):
                async with get_engine().connect() as connection:
                    await connection.execute(text("SELECT 1"))
        except Exception:
            checks["database"] = "failed"
            error_codes.append("DATABASE_UNAVAILABLE")
        else:
            checks["database"] = "ok"

    if not asr.ready:
        error_codes.append("ASR_NOT_READY")

    is_ready = not error_codes
    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": "ready" if is_ready else "not_ready",
        "model_state": asr.runtime.state,
        "failure_reason": asr.runtime.failure_reason,
        "checks": checks,
        "error_codes": error_codes,
    }
