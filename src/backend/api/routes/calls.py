from fastapi import APIRouter, WebSocket

from src.backend.controllers.call_controller import CallController
from src.backend.schemas.call import CallResponseDTO, CreateCallDTO

router = APIRouter(prefix="/calls", tags=["calls"])
controller = CallController()


@router.post("", response_model=CallResponseDTO)
async def create_call(request: CreateCallDTO) -> CallResponseDTO:
    return await controller.start_call(request)


@router.websocket("/{call_id}/stream")
async def stream_call(websocket: WebSocket, call_id: str) -> None:
    await websocket.accept()
    await websocket.send_json({"call_id": call_id, "status": "connected"})
    await websocket.close()
