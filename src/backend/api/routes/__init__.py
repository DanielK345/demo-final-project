from fastapi import APIRouter, HTTPException

from src.backend.api.deps import get_app_settings
from src.backend.api.routes.auth import router as auth_router
from src.backend.api.routes.bookings import router as bookings_router
from src.backend.api.routes.calls import router as calls_router
from src.backend.api.routes.handoffs import router as handoffs_router
from src.backend.api.routes.health import router as health_router
from src.backend.api.routes.livekit import router as livekit_router
from src.backend.api.routes.maps import maps_router as maps_standard_router
from src.backend.api.routes.maps import route_router as maps_route_router
from src.backend.api.routes.maps import router as maps_places_router
from src.backend.api.routes.policies import router as policies_router
from src.backend.api.routes.quotes import router as quotes_router
from src.backend.api.routes.sessions import router as sessions_router
from src.backend.api.routes.settings import router as settings_router
from src.backend.api.routes.trips import router as trips_router
from src.backend.integrations.voice_client import resolve_voice_provider
from src.backend.models.schemas import ChatRequest, ChatResponse
from src.voice_agent.config import get_livekit_voice_settings

router = APIRouter()

router.include_router(auth_router)
router.include_router(calls_router)
router.include_router(sessions_router)
router.include_router(bookings_router)
router.include_router(handoffs_router)
router.include_router(livekit_router)
router.include_router(policies_router)
router.include_router(quotes_router)
router.include_router(trips_router)
router.include_router(settings_router)
router.include_router(maps_places_router)
router.include_router(maps_route_router)
router.include_router(maps_standard_router)


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """Legacy chat route kept for compatibility with the current test suite."""
    try:
        # Keep the legacy text agent out of the LiveKit backend startup path.
        # Importing it eagerly constructs its configured LLM even though native
        # LiveKit voice sessions never call this compatibility endpoint.
        from src.agents.graph import agent

        result = await agent.ainvoke({"query": request.message, "turn_id": request.turn_id})
        return ChatResponse(
            response=result.get("response", ""),
            analysis=result.get("analysis", ""),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/status")
async def agent_status():
    """Agent readiness and language-understanding configuration."""
    settings = get_app_settings()
    livekit_settings = get_livekit_voice_settings()
    llm_ready = settings.agent_llm_enabled and bool(
        settings.llm_api_key_for(settings.agent_llm_base_url)
    )
    voice_provider = None
    try:
        voice_provider = resolve_voice_provider(settings)
    except Exception:
        voice_provider = None
    legacy_stt_model = {
        "openai": settings.voice_stt_model,
        "gemini": settings.voice_gemini_model,
        "zipformer": "sherpa-onnx ZipFormer Vietnamese",
    }.get(voice_provider)
    return {
        "status": "ready",
        "agent": "Core Agent v1.0",
        "llm_enabled": settings.agent_llm_enabled,
        "llm_provider": settings.agent_llm_provider,
        "llm_model": settings.agent_llm_model,
        "understanding_mode": "openai" if llm_ready else "rules",
        "conversation_backend": "core_agent",
        "voice_provider": voice_provider,
        "voice_stt_model": legacy_stt_model,
        "voice_tts_enabled": (
            settings.voice_tts_provider == "edge"
            or bool(settings.openai_api_key)
        ),
        "voice_tts_provider": settings.voice_tts_provider,
        "voice_tts_model": settings.voice_tts_model if settings.voice_tts_provider == "openai" else "edge-tts",
        "voice_tts_voice": settings.openai_tts_voice if settings.voice_tts_provider == "openai" else None,
        "livekit_runtime": livekit_settings.voice_runtime,
        "livekit_configured": not livekit_settings.configuration_errors(),
        "livekit_agent_name": livekit_settings.livekit_agent_name,
        "livekit_stt_model": livekit_settings.livekit_stt_model,
        "livekit_llm_model": livekit_settings.livekit_llm_model,
        "livekit_tts_model": livekit_settings.livekit_tts_model,
    }

__all__ = ["health_router", "router"]
