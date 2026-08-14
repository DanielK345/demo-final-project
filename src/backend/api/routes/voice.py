"""WebSocket + REST route cho Voice AI — file MỚI, thêm additive vào project thật.

Đăng ký trong `src/backend/main.py` (1 import + 1 `include_router`, không đổi route
nào đã có — xem `docs/voice-ai/prompt_voice_integration_real_be_fe.md`). Không dùng chung
`APIRouter` tổng hợp ở `src/backend/api/routes/__init__.py` để tránh phải sửa file đó.

Protocol WS (xem `src/models/voice_schemas.py`):

- Client mở `WebSocket("/api/v1/voice/stream")`.
- Client gửi JSON `WSClientControl` để `start_call` / `end_call` / `ping`.
  `start_call.payload` có thể có `sample_rate` (Hz mic, mặc định 48000).
- Sau `start_call`, client gửi audio PCM16 mono qua **binary WS frame**.
- Server trả JSON `WSServerEvent` cho status/transcript/agent message/handoff/lỗi, và
  **binary WS frame** cho audio TTS (luôn có 1 event `audio_meta` ngay trước).

Route REST `POST /speak`: cho trang nào chỉ cần "đưa text vào, nhận audio ra" mà
không muốn tự quản lý WebSocket (vd. `AssistantPage.tsx` bên frontend — trang đó vốn
dùng `window.speechSynthesis` của trình duyệt, chất lượng/giọng không kiểm soát được
và hay lẫn tiếng Anh/Việt tuỳ máy người dùng — xem
`docs/voice-ai/prompt_voice_integration_real_be_fe.md`).

CẬP NHẬT (13/08/2026): file này từng bị 1 commit khác ("test whisper model", nhánh
`test_speech_model`, tác giả DanielK345) ghi đè hoàn toàn, khiến app không boot được
(`prewarm_tts_cache` bị main.py import nhưng không còn tồn tại). Ban đầu đã khôi phục
lại nguyên bản WS Gateway và gỡ route `/turn` của commit đó — nhưng phát hiện ngay sau
đó: `AssistantPage.tsx` (frontend, cùng commit "test whisper model") ĐÃ được nối thật
vào `POST /voice/turn` cho toàn bộ luồng ghi âm micro (`features/voice/api.ts ->
sendVoiceTurn()`), không phải code thử nghiệm bị bỏ xó — gỡ route đó làm nút micro
trên web bị lỗi 404 thật. Vì vậy giờ CẢ HAI cùng tồn tại trong 1 router này (không đè
nhau nữa vì khác path): `/turn` (OpenAI/Gemini, DanielK345, frontend đang gọi thật) +
`/stream`+`/speak` (Groq/Edge-TTS, hệ thống WS Gateway gốc — hiện frontend CHƯA gọi
`/stream`/`/speak` nữa, giữ lại vì đã test kỹ và có thể cần lại). Xem thêm
`docs/voice-ai/architecture-note-2-voice-systems.md`.
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
from src.voice.schemas import ClientControlType, WSClientControl, WSEventType, WSServerEvent
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

DEFAULT_CLIENT_SAMPLE_RATE = 48000

# pytest set biến này cho mọi test đang chạy — dùng để KHÔNG BAO GIỜ gọi Groq/Edge-TTS
# thật trong test dù `.env` có `GROQ_API_KEY` thật (đúng nguyên tắc test-double). Nếu
# chỉ check `settings.groq_api_key` thôi thì máy dev nào có key thật trong `.env` sẽ
# âm thầm gọi API thật mỗi lần chạy `pytest` — đã tự phát hiện việc này khi viết test.
_RUNNING_UNDER_PYTEST = "PYTEST_CURRENT_TEST" in os.environ


def build_gateway(settings: VoiceSettings | None = None) -> VoiceGateway:
    """Factory — dựng 1 `VoiceGateway`.

    ASR: `GroqASRProvider` thật khi `GROQ_API_KEY` có giá trị VÀ không chạy dưới
    pytest, ngược lại `FakeASRProvider` (pipeline vẫn chạy được không cần key, dùng
    cho demo/dev/CI). TTS: `EdgeTTSProvider` thật (miễn phí, không cần key), bọc
    `CachingTTSProvider`. Dialogue: `SessionBridge` gọi thẳng `SessionService` thật
    của Backend — KHÔNG tạo dialogue engine riêng (xem `session_bridge.py`).
    """
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

    tts = CachingTTSProvider(EdgeTTSProvider(default_voice=settings.voice_tts_voice, rate=settings.voice_tts_rate))

    return VoiceGateway(
        asr=asr,
        tts=tts,
        settings=settings,
        session_bridge=SessionBridge(),
        gazetteer=gazetteer,
        text_corrector=(lambda text: correct_place_names(text, gazetteer)) if len(gazetteer) else None,
        normalizer=normalize_transcript,
        # format_for_speech: số -> chữ đọc tự nhiên. sanitize_for_speech: bỏ dấu ngoặc
        # kép/gạch chéo hay bị Edge-TTS đọc thành lời theo nghĩa đen (phát hiện thật
        # từ câu trả lời của SessionService, vd `“Đúng”`, `Anh/chị`) — xem formatter.py.
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
    """Text -> audio qua đúng pipeline TTS thật (Edge-TTS + format số/tiền tệ +
    override phát âm thương hiệu, cùng cấu hình đã chốt cho WS `/stream`). Dùng cho
    trang nào chỉ cần phát 1 câu, không cần mở WebSocket riêng."""
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
    _require_session_access(session_id, authorization)
    audio_bytes = await audio.read()
    try:
        result = await _voice_turn_service.process_turn(
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
    """Gọi lúc app khởi động (xem `src/backend/main.py`) — pre-render câu tĩnh hay
    dùng để lượt gọi đầu tiên không phải chờ Edge-TTS."""
    gateway = get_gateway()
    if not isinstance(gateway.tts, CachingTTSProvider):
        return
    try:
        await gateway.tts.prewarm(voice=gateway.settings.voice_tts_voice)
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
                        events = await gateway.end_session(session_id, reason=control.payload.get("reason", "USER_ENDED"))
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
