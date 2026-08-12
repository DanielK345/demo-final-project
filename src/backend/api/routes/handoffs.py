from fastapi import APIRouter, Query

from src.backend.controllers.handoff_controller import HandoffController
from src.backend.schemas.handoff import HandoffAcceptanceDTO, HandoffDTO, HandoffResponseDTO

router = APIRouter(prefix="/handoffs", tags=["handoffs"])
controller = HandoffController()


@router.post("", response_model=HandoffResponseDTO)
async def create_handoff(request: HandoffDTO) -> HandoffResponseDTO:
    return await controller.create_handoff(request)


@router.get("", response_model=list[HandoffResponseDTO])
async def list_pending_handoffs(status: str = Query(default="pending")) -> list[HandoffResponseDTO]:
    return await controller.list_handoffs(status)


@router.post("/{handoff_id}/accept", response_model=HandoffAcceptanceDTO)
async def accept_handoff(handoff_id: str) -> HandoffAcceptanceDTO:
    return await controller.accept_handoff(handoff_id)
