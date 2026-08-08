from fastapi import APIRouter, HTTPException

from src.backend.agents.graph import agent
from src.backend.api.routes.bookings import router as bookings_router
from src.backend.api.routes.calls import router as calls_router
from src.backend.api.routes.handoffs import router as handoffs_router
from src.backend.api.routes.health import router as health_router
from src.backend.api.routes.sessions import router as sessions_router
from src.backend.api.routes.trips import router as trips_router
from src.backend.models.schemas import ChatRequest, ChatResponse


router = APIRouter()

router.include_router(calls_router)
router.include_router(sessions_router)
router.include_router(bookings_router)
router.include_router(trips_router)
router.include_router(handoffs_router)


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """Legacy chat route kept for compatibility with the current test suite."""
    try:
        result = await agent.ainvoke({"query": request.message})
        return ChatResponse(
            response=result.get("response", ""),
            analysis=result.get("analysis", ""),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/status")
async def agent_status():
    """Legacy status route kept for compatibility with the current test suite."""
    return {"status": "ready", "agent": "LangGraph Agent v1.0"}
