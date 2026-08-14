"""WebSocket + REST routes for Voice AI.

Registered in `src/backend/main.py` with prefix `/api/v1/voice` (additive — does not
replace existing session/chat routes). WebSocket protocol: see `src/models/voice_schemas.py`.
"""

from __future__ import annotations

import logging
import os

from fastapi import (
    APIRouter,
    File,
    Form,
    Header,
    HTTPException,
    Response,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from pydantic import BaseModel, Field

from src.backend.api.routes.sessions import _require_session_access
from src.backend.integrations.voice_client import VoiceProviderError
from src.backend.schemas.voice import VoiceTurnResponseDTO
from src.backend.services.voice_service import VoiceService
from src.models.voice_schemas import ClientControlType, WSClientControl, WSEventType, WSServerEvent
from src.voice.asr.biasing import correct_place_names
from src.voice.asr.groq_provider import GroqASRProvider
from src.voice.config import VoiceSettings, get_voice_settings
from src.voice.gateway import GatewaySessionNotFoundError, VoiceGateway
from src.voice.session_bridge import SessionBridge
from src.voice.text.gazetteer import Gazetteer
from src.voice.text.normalizer import normalize_transcript
from src.voice.tts.cache import CachingTTSProvider
from src.voice.tts.edge_tts_provider import EdgeTTSProvider
from src.voice.tts.formatter import format_for_speech, sanitize_for_speech
from src.voice.tts.pronunciation import apply_pronunciation_overrides
from tests.test_voice.fake_providers import FakeASRProvider

logger = logging.getLogger(__name__)
router = APIRouter()
_turn_service = VoiceService()

DEFAULT_CLIENT_SAMPLE_RATE = 48000

# pytest sets this for every running test — never call real Groq/Edge-TTS in tests even
# when `.env` contains real API keys.
_RUNNING_UNDER_PYTEST = "PYTEST_CURRENT_TEST" in os.environ


def build_gateway(settings: VoiceSettings | None = None) -> VoiceGateway:
    """Build a `VoiceGateway` with real or fake ASR depending on configuration."""
    settings = settings or get_voice_settings()

    gazetteer = Gazetteer.load()
    if not len(gazetteer):
        logger.info("Gazetteer rỗng (data/gazetteer/place_names.json không có/không đọc được).")

    if settings.groq_api_key and not _RUNNING_UNDER_PYTEST:
        asr = GroqASRProvider(settings.groq_api_key, model=settings.voice_asr_model)
    else:
        if not _RUNNING_UNDER_PYTEST:
            logger.warning("GROQ_API_KEY chưa cấu hình — Voice Gateway đang dùng FakeASR.")
        asr = FakeASRProvider()

    tts = CachingTTSProvider(
        EdgeTTSProvider(default_voice=settings.voice_tts_voice, rate=settings.voice_tts_rate)
    )

    return VoiceGateway(
        asr=asr,
        tts=tts,
        settings=settings,
        session_bridge=SessionBridge(),
        gazetteer=gazetteer,
        text_corrector=(lambda text: correct_place_names(text, gazetteer)) if len(gazetteer) else None,
        normalizer=normalize_transcript,
        tts_formatter=lambda text: sanitize_for_speech(format_for_speech(text)),
        tts_pronunciation=apply_pronunciation_overrides,
    )


_gateway: VoiceGateway | None = None


def get_gateway() -> VoiceGateway:
    global _gateway
    if _gateway is None:
        _gateway = build_gateway()
    return _gateway


@router.get("/health")
async def voice_health() -> dict:
    settings = get_voice_settings()
    return {
        "status": "ok" if settings.voice_enabled else "disabled",
        "vad_backend": settings.voice_vad_backend,
        "asr_provider": "groq" if settings.groq_api_key else "fake",
    }


class SpeakRequestDTO(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)


@router.post("/speak")
async def speak(request: SpeakRequestDTO) -> Response:
    """Text -> audio through the same TTS pipeline used by the WebSocket stream."""
    gateway = get_gateway()
    text = request.text
    if gateway.tts_formatter:
        text = gateway.tts_formatter(text)
    if gateway.tts_pronunciation:
        text = gateway.tts_pronunciation(text)
    try:
        result = await gateway.tts.synthesize(text, voice=gateway.settings.voice_tts_voice)
    except Exception:
        logger.exception("TTS provider raised while synthesizing /speak request")
        return Response(status_code=503, content=b"", media_type="application/octet-stream")
    return Response(content=result.audio, media_type=result.mime_type)


@router.post("/turn", response_model=VoiceTurnResponseDTO)
async def voice_turn(
    session_id: str = Form(...),
    audio: UploadFile = File(...),
    authorization: str | None = Header(default=None),
) -> VoiceTurnResponseDTO:
    """HTTP fallback: upload one audio clip and receive transcript + agent reply."""
    _require_session_access(session_id, authorization)
    audio_bytes = await audio.read()
    try:
        result = await _turn_service.process_turn(
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


async def prewarm_tts_cache() -> None:
    """Pre-render static phrases at startup so the first call is faster."""
    gateway = get_gateway()
    if not isinstance(gateway.tts, CachingTTSProvider):
        return
    try:
        await gateway.tts.prewarm(voice=gateway.settings.voice_tts_voice)
    except Exception:
        logger.exception(
            "Prewarm TTS cache thất bại — bỏ qua, sẽ thử lại ở lượt gọi đầu tiên."
        )


@router.websocket("/stream")
async def voice_stream(websocket: WebSocket) -> None:
    await websocket.accept()
    gateway = get_gateway()
    session_id: str | None = None
    client_sample_rate = DEFAULT_CLIENT_SAMPLE_RATE

    try:
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                break

            if (text := message.get("text")) is not None:
                try:
                    control = WSClientControl.model_validate_json(text)
                except ValueError:
                    await websocket.send_text(
                        WSServerEvent(
                            type=WSEventType.ERROR,
                            session_id=session_id or "",
                            payload={"message": "invalid control message"},
                        ).model_dump_json()
                    )
                    continue

                if control.type == ClientControlType.START_CALL:
                    channel = control.payload.get("channel", "WEB_VOICE")
                    client_sample_rate = int(
                        control.payload.get("sample_rate", DEFAULT_CLIENT_SAMPLE_RATE)
                    )
                    session_id, events = await gateway.start_session(channel=channel)
                    await _send_events(websocket, events)
                elif control.type == ClientControlType.END_CALL:
                    if session_id:
                        events = await gateway.end_session(
                            session_id,
                            reason=control.payload.get("reason", "USER_ENDED"),
                        )
                        await _send_events(websocket, events)
                    break
                elif control.type == ClientControlType.PING:
                    await websocket.send_json({"type": "pong"})

            elif (raw := message.get("bytes")) is not None:
                if session_id is None:
                    await websocket.send_text(
                        WSServerEvent(
                            type=WSEventType.ERROR,
                            session_id="",
                            payload={"message": "gửi start_call trước khi gửi audio"},
                        ).model_dump_json()
                    )
                    continue
                try:
                    events = await gateway.handle_audio_chunk(
                        session_id,
                        raw,
                        client_sample_rate,
                    )
                except GatewaySessionNotFoundError:
                    break
                await _send_events(websocket, events)
    except WebSocketDisconnect:
        pass
    finally:
        if session_id:
            await gateway.end_session(session_id, reason="CONNECTION_CLOSED")


async def _send_events(websocket: WebSocket, events: list) -> None:
    for event in events:
        if isinstance(event, bytes):
            await websocket.send_bytes(event)
        else:
            await websocket.send_text(event.model_dump_json())
