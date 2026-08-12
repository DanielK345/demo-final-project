"""Voice Gateway — điều phối pipeline audio ↔ dialogue engine thật của Backend.

    audio browser --codec--> VAD/EndpointScorer --utterance--> ASR (Groq)
        --(bias/normalize)--> SessionBridge (SessionService thật) --> (format/pronounce)
        --> TTS (Edge-TTS) --> audio trả về browser

`VoiceGateway` không biết gì về WebSocket — chỉ nhận audio chunk qua
`handle_audio_chunk()` và trả về list output đã chuẩn hoá (`WSServerEvent` JSON hoặc
`bytes` audio nhị phân). `src/backend/api/routes/voice.py` là nơi duy nhất dịch
sang/từ WebSocket thật.

**Không tự giữ dialogue state** (không Redis, không state machine riêng) — mọi quyết
định nghiệp vụ (đặt xe tới bước nào, đã xác nhận chưa, đếm thất bại, khi nào handoff)
đều do `SessionBridge` (tức `SessionService` thật của Backend) quyết định, để tránh 2
nguồn sự thật. Gateway chỉ giữ state DSP thuần audio (resampler, VAD) theo từng kết
nối, sống trong RAM, mất khi disconnect — chấp nhận được vì `SessionService` cũng
in-memory, không ai kỳ vọng audio pipeline bền hơn dialogue state của chính nó.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.models.voice_schemas import (
    ASRResult,
    HandoffReason,
    TurnStage,
    WSEventType,
    WSServerEvent,
)
from src.voice.audio.codec import PCM16Resampler, utterance_rms
from src.voice.audio.vad import EndpointScorer, VADProvider, build_vad_provider
from src.voice.session_bridge import SessionBridge, SessionTurnResult

if TYPE_CHECKING:
    from src.voice.asr.base import ASRProvider
    from src.voice.config import VoiceSettings
    from src.voice.text.gazetteer import Gazetteer
    from src.voice.tts.base import TTSProvider

logger = logging.getLogger(__name__)

GatewayOutput = WSServerEvent | bytes

REPROMPT_MESSAGE = "Xin lỗi, tôi chưa nghe rõ. Bạn có thể nói lại được không?"


class GatewaySessionNotFoundError(Exception):
    """`handle_audio_chunk`/`end_session` gọi với session_id chưa `start_session`."""


@dataclass
class _ConnectionState:
    """State DSP thuần audio cho 1 kết nối WS — không phải dialogue state."""

    session_id: str
    resampler: PCM16Resampler
    scorer: EndpointScorer
    stage: TurnStage = TurnStage.LISTENING


class VoiceGateway:
    def __init__(
        self,
        *,
        asr: ASRProvider,
        tts: TTSProvider,
        settings: VoiceSettings,
        session_bridge: SessionBridge | None = None,
        vad_factory: Callable[[], VADProvider] | None = None,
        gazetteer: Gazetteer | None = None,
        text_corrector: Callable[[str], str] | None = None,
        normalizer: Callable[[str], str] | None = None,
        tts_formatter: Callable[[str], str] | None = None,
        tts_pronunciation: Callable[[str], str] | None = None,
    ) -> None:
        self.asr = asr
        self.tts = tts
        self.settings = settings
        self.session_bridge = session_bridge or SessionBridge()
        self._vad_factory = vad_factory or (
            lambda: build_vad_provider(
                settings.voice_vad_backend,
                silero_model_path=settings.voice_silero_model_path,
            )
        )
        self.gazetteer = gazetteer
        self.text_corrector = text_corrector
        self.normalizer = normalizer
        self.tts_formatter = tts_formatter
        self.tts_pronunciation = tts_pronunciation
        self._connections: dict[str, _ConnectionState] = {}
        self._seq: dict[str, int] = {}

    # -- session lifecycle -------------------------------------------------

    async def start_session(self, channel: str = "WEB_VOICE") -> tuple[str, list[GatewayOutput]]:
        created = await self.session_bridge.start_session(channel=channel)
        session_id = str(created["session_id"])
        self._connections[session_id] = _ConnectionState(
            session_id=session_id,
            resampler=PCM16Resampler(target_rate=self.settings.voice_vad_sample_rate),
            scorer=EndpointScorer(
                vad=self._vad_factory(),
                sample_rate=self.settings.voice_vad_sample_rate,
                silence_ms=self.settings.voice_vad_silence_ms,
                max_utterance_ms=self.settings.voice_max_utterance_seconds * 1000,
            ),
        )
        self._seq[session_id] = 0
        return session_id, [
            self._event(session_id, WSEventType.SESSION_READY),
            self._status_event(session_id, TurnStage.LISTENING),
        ]

    async def end_session(self, session_id: str, reason: str = "USER_ENDED") -> list[GatewayOutput]:
        self._connections.pop(session_id, None)
        result = await self.session_bridge.end_session(session_id, reason)
        if result is None:
            return []
        return [
            WSServerEvent(
                type=WSEventType.SESSION_ENDED,
                session_id=session_id,
                payload={"reason": reason},
            )
        ]

    # -- audio ingestion -----------------------------------------------------

    async def handle_audio_chunk(
        self,
        session_id: str,
        chunk: bytes,
        src_sample_rate: int,
    ) -> list[GatewayOutput]:
        conn = self._connections.get(session_id)
        if conn is None:
            raise GatewaySessionNotFoundError(session_id)

        resampled = conn.resampler.process(chunk, src_sample_rate)
        outputs: list[GatewayOutput] = []
        for endpoint_result in conn.scorer.push(resampled):
            if endpoint_result.event == "speech_start":
                conn.stage = TurnStage.LISTENING
                outputs.append(self._status_event(session_id, conn.stage))
            elif endpoint_result.event == "speech_end" and endpoint_result.utterance_pcm16:
                outputs.extend(await self._handle_utterance(conn, endpoint_result.utterance_pcm16))
        return outputs

    # -- one utterance: ASR -> (SessionService thật) -> TTS -------------------

    async def _handle_utterance(self, conn: _ConnectionState, pcm16_audio: bytes) -> list[GatewayOutput]:
        session_id = conn.session_id
        conn.stage = TurnStage.PROCESSING
        outputs: list[GatewayOutput] = [self._status_event(session_id, conn.stage)]

        asr_result = await self._transcribe(session_id, pcm16_audio, outputs)
        outputs.append(
            self._event(
                session_id,
                WSEventType.TRANSCRIPT,
                {"text": asr_result.text, "confidence": asr_result.confidence, "is_final": asr_result.is_final},
            )
        )

        if not asr_result.text.strip():
            # Không có gì để gửi lên SessionService (message min_length=1) — tự
            # re-prompt, KHÔNG đụng failed_count của backend (audio không đủ để
            # coi là "1 lần thử" thật sự — có thể chỉ là VAD false-positive).
            outputs.extend(await self._reprompt(conn, REPROMPT_MESSAGE))
            return outputs

        normalized_text = asr_result.text
        if self.text_corrector:
            normalized_text = self.text_corrector(normalized_text)
        if self.normalizer:
            normalized_text = self.normalizer(normalized_text)
        if not normalized_text.strip():
            outputs.extend(await self._reprompt(conn, REPROMPT_MESSAGE))
            return outputs

        # BR-001 — lớp thận trọng THÊM riêng của Voice khi đang ở bước xác nhận đặt
        # xe: KHÔNG gửi lên SessionService nếu confidence thấp hơn ngưỡng riêng của
        # Voice (mặc định 0.80, cao hơn ngưỡng phẳng 0.55 của SessionService) — vì
        # xác nhận sai ở bước này tạo booking ngoài ý muốn. Các bước khác tin tưởng
        # hoàn toàn ngưỡng 0.55 của SessionService, không tự áp thêm ngưỡng.
        current = await self.session_bridge.get_session(session_id)
        is_confirmation_step = bool(current and current.get("current_step") == "CONFIRM")
        if is_confirmation_step and asr_result.confidence < self.settings.voice_booking_confirmation_confidence_threshold:
            outputs.extend(await self._reprompt(conn, "Xin lỗi, bạn xác nhận là \"đúng\" hay \"thôi\" ạ?"))
            return outputs

        turn = await self.session_bridge.send_message(session_id, normalized_text, asr_result.confidence)
        if turn is None:
            outputs.append(
                self._event(
                    session_id,
                    WSEventType.ERROR,
                    {"message": "Phiên hội thoại không còn hợp lệ, vui lòng gọi lại.", "code": "SESSION_NOT_FOUND"},
                )
            )
            return outputs

        outputs.extend(await self._apply_turn_result(conn, turn))
        return outputs

    async def _transcribe(self, session_id: str, pcm16_audio: bytes, outputs: list[GatewayOutput]) -> ASRResult:
        if utterance_rms(pcm16_audio) < self.settings.voice_min_utterance_rms:
            # Utterance quá nhỏ để có khả năng là tiếng nói thật — KHÔNG gọi ASR.
            # Phát hiện qua test tay với GROQ_API_KEY thật: audio gần như im lặng
            # khiến Whisper "bịa" ra câu hoàn chỉnh với confidence CAO — xem
            # docs/voice-ai/mustdo_voice.md.
            logger.info("Utterance RMS quá thấp, bỏ qua ASR (session=%s)", session_id)
            return ASRResult(text="", confidence=0.0)

        prompt_hint = self.gazetteer.as_prompt_hint() if self.gazetteer else ""
        try:
            return await self.asr.transcribe(
                pcm16_audio,
                sample_rate=self.settings.voice_vad_sample_rate,
                language=self.settings.voice_asr_language,
                prompt_hint=prompt_hint,
            )
        except Exception:
            logger.exception("ASR provider raised while transcribing session=%s", session_id)
            outputs.append(
                self._event(
                    session_id,
                    WSEventType.ERROR,
                    {"message": "Nhận dạng giọng nói tạm thời lỗi, vui lòng thử lại.", "code": "ASR_PROVIDER_ERROR"},
                )
            )
            return ASRResult(text="", confidence=0.0)

    async def _apply_turn_result(self, conn: _ConnectionState, turn: SessionTurnResult) -> list[GatewayOutput]:
        session_id = conn.session_id
        outputs: list[GatewayOutput] = []
        if turn.message:
            outputs.append(self._event(session_id, WSEventType.AGENT_MESSAGE, {"text": turn.message}))
            outputs.extend(await self._speak(conn, turn.message))

        if turn.action == "HANDOFF":
            conn.stage = TurnStage.HANDED_OFF
            outputs.append(
                self._event(
                    session_id,
                    WSEventType.HANDOFF,
                    {"reason": HandoffReason.ASR_LOW_CONFIDENCE.value, "summary": turn.message},
                )
            )
        elif turn.action == "END_SESSION":
            conn.stage = TurnStage.ENDED
            outputs.append(self._status_event(session_id, conn.stage))
        else:
            conn.stage = TurnStage.LISTENING

        return outputs

    async def _reprompt(self, conn: _ConnectionState, text: str) -> list[GatewayOutput]:
        outputs: list[GatewayOutput] = [self._event(conn.session_id, WSEventType.AGENT_MESSAGE, {"text": text})]
        outputs.extend(await self._speak(conn, text))
        return outputs

    async def _speak(self, conn: _ConnectionState, text: str) -> list[GatewayOutput]:
        if not text.strip():
            return []
        session_id = conn.session_id
        conn.stage = TurnStage.SPEAKING

        # Pronunciation TRƯỚC formatter — cố ý, không phải tuỳ ý. Địa danh/thương hiệu
        # override (vd "Landmark 81" -> "Len Mác Tám Mươi Mốt") match theo đúng chuỗi
        # số gốc; nếu formatter (số -> chữ) chạy trước, nó "ăn mất" con số đó thành chữ
        # ("Landmark tám mươi mốt") và pronunciation không còn tìm thấy chuỗi để khớp
        # nữa — bug thật đã tự phát hiện qua test, xem docs/voice-ai/mustdo_voice.md.
        spoken_text = text
        if self.tts_pronunciation:
            spoken_text = self.tts_pronunciation(spoken_text)
        if self.tts_formatter:
            spoken_text = self.tts_formatter(spoken_text)

        try:
            tts_result = await self.tts.synthesize(spoken_text, voice=self.settings.voice_tts_voice)
        except Exception:
            logger.exception("TTS provider raised while synthesizing session=%s", session_id)
            conn.stage = TurnStage.LISTENING
            return [
                self._event(
                    session_id,
                    WSEventType.ERROR,
                    {"message": "Tổng hợp giọng nói tạm thời lỗi.", "code": "TTS_PROVIDER_ERROR"},
                ),
                self._status_event(session_id, conn.stage),
            ]

        events: list[GatewayOutput] = [
            self._event(
                session_id,
                WSEventType.AUDIO_META,
                {"mime_type": tts_result.mime_type, "sample_rate": tts_result.sample_rate, "text": text},
            ),
            tts_result.audio,
        ]
        conn.stage = TurnStage.LISTENING
        events.append(self._status_event(session_id, conn.stage))
        return events

    # -- event helpers -----------------------------------------------------

    def _next_seq(self, session_id: str) -> int:
        self._seq[session_id] = self._seq.get(session_id, 0) + 1
        return self._seq[session_id]

    def _event(self, session_id: str, event_type: WSEventType, payload: dict | None = None) -> WSServerEvent:
        return WSServerEvent(
            type=event_type,
            session_id=session_id,
            seq=self._next_seq(session_id),
            payload=payload or {},
        )

    def _status_event(self, session_id: str, stage: TurnStage) -> WSServerEvent:
        return self._event(session_id, WSEventType.STATUS, {"stage": stage.value})
