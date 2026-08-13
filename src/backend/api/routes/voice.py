from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile, status

from src.backend.api.routes.sessions import _require_session_access
from src.backend.integrations.voice_client import VoiceProviderError
from src.backend.schemas.voice import VoiceTurnResponseDTO
from src.backend.services.voice_service import VoiceService


router = APIRouter(prefix="/voice", tags=["voice"])
service = VoiceService()


@router.post("/turn", response_model=VoiceTurnResponseDTO)
async def voice_turn(
    session_id: str = Form(...),
    audio: UploadFile = File(...),
    authorization: str | None = Header(default=None),
) -> VoiceTurnResponseDTO:
    _require_session_access(session_id, authorization)
    audio_bytes = await audio.read()
    try:
        result = await service.process_turn(
            session_id,
            audio_bytes,
            mime_type=audio.content_type,
        )
        return VoiceTurnResponseDTO(**result)
    except VoiceProviderError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
