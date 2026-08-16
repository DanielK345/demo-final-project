from fastapi import APIRouter, HTTPException

from src.agents.graph import agent
from src.backend.api.deps import get_app_settings
from src.backend.api.routes.auth import router as auth_router
from src.backend.api.routes.bookings import router as bookings_router
from src.backend.api.routes.calls import router as calls_router
from src.backend.api.routes.handoffs import router as handoffs_router
from src.backend.api.routes.health import router as health_router
from src.backend.api.routes.sessions import router as sessions_router
from src.backend.api.routes.settings import router as settings_router
from src.backend.api.routes.trips import router as trips_router
from src.backend.integrations.voice_client import resolve_voice_provider
from src.backend.models.schemas import ChatRequest, ChatResponse

router = APIRouter()

router.include_router(auth_router)
router.include_router(calls_router)
router.include_router(sessions_router)
router.include_router(bookings_router)
router.include_router(handoffs_router)
router.include_router(trips_router)
router.include_router(settings_router)


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """Legacy chat route kept for compatibility with the current test suite."""
    try:
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
    llm_ready = settings.agent_llm_enabled and bool(
        settings.llm_api_key_for(settings.agent_llm_base_url)
    )
    voice_provider = None
    try:
        voice_provider = resolve_voice_provider(settings)
    except Exception:
        voice_provider = None
    return {
        "status": "ready",
        "agent": "Core Agent v1.0",
        "llm_enabled": settings.agent_llm_enabled,
        "llm_provider": settings.agent_llm_provider,
        "llm_model": settings.agent_llm_model,
        "understanding_mode": "openai" if llm_ready else "rules",
        "conversation_backend": "core_agent",
        "voice_provider": voice_provider,
        "voice_stt_model": settings.voice_stt_model if voice_provider == "openai" else settings.voice_gemini_model,
        "voice_tts_enabled": voice_provider == "openai",
    }

__all__ = ["health_router", "router"]
