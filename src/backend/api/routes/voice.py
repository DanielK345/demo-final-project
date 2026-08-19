"""Voice REST/WebSocket routes mounted once at `/api/v1/voice`.

Transports:
- `POST /turn`: complete utterance -> ASR/rewrite -> Agent -> reviewed TTS.
- `POST /speak`: reviewed text -> TTS orchestrator -> validated audio.
- `WS /stream`: PCM16/VAD streaming -> session events and binary TTS audio.

All transports share Backend session/Agent contracts. TTS paths use
`TTSOrchestrator`; transcript paths use the same deterministic rewrite guards.
See `docs/voice-ai/voice-runtime-architecture.md` for current ownership.
"""

from __future__ import annotations

import logging

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

from src.backend.api.routes.auth import service as auth_service
from src.backend.api.routes.sessions import _require_session_access, _token_from_header
from src.backend.integrations.voice_client import VoiceProviderError
from src.backend.schemas.voice import VoiceTurnResponseDTO
from src.backend.services.transcript_rewriter import build_transcript_rewriter
from src.backend.services.voice_service import VoiceService
from src.config import get_settings as get_app_settings
from src.voice.asr.biasing import correct_place_names
from src.voice.asr.groq_provider import GroqASRProvider
from src.voice.asr.unavailable_provider import UnavailableASRProvider
from src.voice.asr.zipformer.provider import ZipformerASRProvider
from src.voice.asr.zipformer.service import get_zipformer_service
from src.voice.config import VoiceSettings, get_voice_settings
from src.voice.gateway import GatewaySessionNotFoundError, VoiceGateway
from src.voice.schemas import ClientControlType, WSClientControl, WSEventType, WSServerEvent
from src.voice.session_bridge import SessionBridge
from src.voice.text.gazetteer import Gazetteer
from src.voice.text.normalizer import normalize_transcript
from src.voice.text.place_aliases import PlaceAliasCatalog
from src.voice.tts.cache import STATIC_PHRASES
from src.voice.tts.errors import TTSError
from src.voice.tts.orchestrator import get_tts_orchestrator

logger = logging.getLogger(__name__)
router = APIRouter()

DEFAULT_CLIENT_SAMPLE_RATE = 48000


def build_gateway(settings: VoiceSettings | None = None) -> VoiceGateway:
    """Factory — dựng 1 `VoiceGateway`.

    ASR: `GroqASRProvider` thật khi `GROQ_API_KEY` có giá trị; ngược lại
    `UnavailableASRProvider` trả lỗi cấu hình rõ ràng, không giả lập transcript. TTS: `EdgeTTSProvider` thật (miễn phí, không cần key), bọc
    `CachingTTSProvider`. Dialogue: `SessionBridge` gọi thẳng `SessionService` thật
    của Backend — KHÔNG tạo dialogue engine riêng (xem `session_bridge.py`).
    """
    settings = settings or get_voice_settings()

    gazetteer = Gazetteer.load()
    place_aliases = PlaceAliasCatalog.load()
    if not len(gazetteer):
        logger.info("Gazetteer rỗng (data/gazetteer/place_names.json không có/không đọc được).")

    if get_zipformer_service().ready:
        asr = ZipformerASRProvider()
    elif settings.groq_api_key:
        asr = GroqASRProvider(settings.groq_api_key, model=settings.voice_asr_model)
    else:
        logger.error("GROQ_API_KEY chưa cấu hình — WebSocket ASR sẽ trả lỗi cấu hình.")
        asr = UnavailableASRProvider()

    tts = get_tts_orchestrator()

    return VoiceGateway(
        asr=asr,
        tts=tts,
        settings=settings,
        session_bridge=SessionBridge(),
        gazetteer=gazetteer,
        text_corrector=(
            lambda text: correct_place_names(place_aliases.correct(text), gazetteer)
        )
        if len(gazetteer)
        else place_aliases.correct,
        transcript_rewriter=build_transcript_rewriter(get_app_settings(), gazetteer),
        normalizer=normalize_transcript,
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
        "asr_provider": (
            "zipformer" if get_zipformer_service().ready else "groq" if settings.groq_api_key else "unavailable"
        ),
        "transcript_rewrite": "configured"
        if get_app_settings().voice_transcript_rewrite_enabled
        and get_app_settings().llm_api_key_for(get_app_settings().voice_transcript_rewrite_base_url)
        else "disabled_or_unconfigured",
        "tts": get_tts_orchestrator().health(),
    }


@router.get("/tts/health")
async def tts_health() -> dict[str, object]:
    return get_tts_orchestrator().health()


@router.get("/tts/metrics")
async def tts_metrics() -> Response:
    return Response(
        get_tts_orchestrator().metrics.render_prometheus(),
        media_type="text/plain; version=0.0.4",
    )


class SpeakRequestDTO(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)
    booking_confirmed: bool = False
    action: str | None = None


@router.post("/speak")
async def speak(request: SpeakRequestDTO) -> Response:
    """Text -> audio qua đúng pipeline TTS thật (Edge-TTS + format số/tiền tệ +
    override phát âm thương hiệu, cùng cấu hình đã chốt cho WS `/stream`). Dùng cho
    trang nào chỉ cần phát 1 câu, không cần mở WebSocket riêng."""
    try:
        result = await get_tts_orchestrator().synthesize(
            request.text,
            review_context={"booking_confirmed": request.booking_confirmed, "action": request.action},
        )
    except TTSError as exc:
        logger.warning("TTS /speak failed code=%s", exc.code)
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": str(exc)}) from exc
    return Response(
        content=result.audio,
        media_type=result.mime_type,
        headers={
            "X-TTS-Provider": result.provider or "unknown",
            "X-TTS-Voice": result.voice or "unknown",
            "X-TTS-Fallback": str(result.fallback_used).lower(),
            "X-TTS-Duration-Ms": str(result.duration_ms or 0),
            "X-TTS-Review": result.review_decision or "unknown",
        },
    )


_voice_turn_service = VoiceService()


@router.post("/turn", response_model=VoiceTurnResponseDTO)
async def voice_turn(
    session_id: str = Form(...),
    audio: UploadFile = File(...),
    authorization: str | None = Header(default=None),
) -> VoiceTurnResponseDTO:
    """Ghi âm 1 lượt trọn vẹn -> transcript + phản hồi text + audio (base64) trong
    1 lần gọi. Đây là cơ chế micro THẬT mà `AssistantPage.tsx` đang dùng
    (`features/voice/api.ts::sendVoiceTurn`) — khác `/stream` (WS streaming theo thời
    gian thực, Groq+Edge-TTS). Dùng OpenAI/Gemini (`src/backend/integrations/
    voice_client.py`), cấu hình qua `VOICE_PROVIDER`/`OPENAI_API_KEY`/`GEMINI_API_KEY`."""
    await _require_session_access(session_id, authorization)
    audio_bytes = await audio.read()
    try:
        result = await _voice_turn_service.process_turn(
            session_id,
            audio_bytes,
            mime_type=audio.content_type,
        )
        if result.get("action") == "END_SESSION":
            await auth_service.revoke_token_durable(_token_from_header(authorization))
        return VoiceTurnResponseDTO(**result)
    except TTSError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": str(exc)}) from exc
    except VoiceProviderError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


async def prewarm_tts_cache() -> None:
    """Gọi lúc app khởi động (xem `src/backend/main.py`) — pre-render câu tĩnh hay
    dùng để lượt gọi đầu tiên không phải chờ Edge-TTS."""
    try:
        await get_tts_orchestrator().prewarm(STATIC_PHRASES)
    except Exception:
        logger.exception("Prewarm TTS cache thất bại — bỏ qua, sẽ thử lại ở lượt gọi đầu tiên.")


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
                    client_sample_rate = int(control.payload.get("sample_rate", DEFAULT_CLIENT_SAMPLE_RATE))
                    session_id, events = await gateway.start_session(channel=channel)
                    await _send_events(websocket, events)
                elif control.type == ClientControlType.END_CALL:
                    if session_id:
                        events = await gateway.end_session(
                            session_id, reason=control.payload.get("reason", "USER_ENDED")
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
                    events = await gateway.handle_audio_chunk(session_id, raw, client_sample_rate)
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
