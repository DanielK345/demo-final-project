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
        "nominatim": "not_configured",
        "osrm": "not_configured",
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

    # Maps provider health checks (§37) — non-blocking, informational
    if settings.maps_provider:
        try:
            from src.backend.services.maps_service import MapsService
            maps = MapsService(settings=settings)
            maps_health = await maps.health_check()
            geo_status = maps_health.get("geocoding", {}).get("status", "not_checked")
            route_status = maps_health.get("routing", {}).get("status", "not_checked")
            checks["nominatim"] = geo_status
            checks["osrm"] = route_status
            if geo_status == "failed":
                error_codes.append("NOMINATIM_UNAVAILABLE")
            if route_status == "failed":
                error_codes.append("OSRM_UNAVAILABLE")
        except Exception:
            checks["nominatim"] = "check_error"
            checks["osrm"] = "check_error"

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
