from fastapi import APIRouter, Header, HTTPException, status

from src.backend.api.routes.sessions import _require_session_access
from src.backend.schemas.quote import QuoteRequestDTO, QuoteResponseDTO
from src.backend.services.quote_service import QuoteService

router = APIRouter(prefix="/quotes", tags=["quotes"])
service = QuoteService()


@router.post("", response_model=QuoteResponseDTO, status_code=status.HTTP_201_CREATED)
async def create_quote(request: QuoteRequestDTO, authorization: str | None = Header(default=None)) -> QuoteResponseDTO:
    user_id = await _require_session_access(request.session_id, authorization)
    try:
        quote = await service.issue_quote(
            user_id=user_id,
            session_id=request.session_id,
            pickup_place_id=request.pickup_place_id,
            destination_place_id=request.destination_place_id,
            vehicle_type=request.vehicle_type,
        )
        return QuoteResponseDTO(**quote)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
