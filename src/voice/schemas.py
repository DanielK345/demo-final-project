"""Shared data contracts for the Voice AI pipeline.

Mọi module trong `src/voice/` (audio, asr, tts, text) và route trong
`src/backend/api/routes/voice.py` dùng các model ở đây.
"""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# ASR / TTS turn results
# ---------------------------------------------------------------------------


class ASRResult(BaseModel):
    """Kết quả một lượt nhận dạng giọng nói (utterance đã cắt xong bởi VAD)."""

    text: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    is_final: bool = True
    language: str = "vi"
    duration_ms: int | None = Field(default=None, ge=0)
    raw: dict[str, Any] = Field(default_factory=dict)


class TTSResult(BaseModel):
    """Audio đã tổng hợp cho một câu/đoạn trả lời."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    audio: bytes = b""
    mime_type: str = "audio/mpeg"
    sample_rate: int = 24000
    text: str = ""
    duration_ms: int | None = Field(default=None, ge=0)
    provider: str | None = None
    voice: str | None = None
    fallback_used: bool = False
    review_decision: str | None = None
    review_reason_codes: list[str] = Field(default_factory=list)
    spoken_text: str | None = None
    audio_metrics: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Session / turn state
# ---------------------------------------------------------------------------


class HandoffReason(StrEnum):
    ASR_LOW_CONFIDENCE = "ASR_LOW_CONFIDENCE"  # BR-003: 2 lần ASR liên tiếp thất bại
    USER_REQUESTED = "USER_REQUESTED"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"
    AGENT_ERROR = "AGENT_ERROR"
    TOOL_ERROR = "TOOL_ERROR"


class TurnStage(StrEnum):
    """Trạng thái hiển thị cho UI."""

    IDLE = "IDLE"
    LISTENING = "LISTENING"  # 🎙️ Đang nghe
    PROCESSING = "PROCESSING"  # ⚙️ Đang xử lý (ASR → agent → TTS)
    SPEAKING = "SPEAKING"  # 🔊 AI đang nói
    HANDED_OFF = "HANDED_OFF"
    ENDED = "ENDED"


class SessionStatus(StrEnum):
    ACTIVE = "ACTIVE"
    HANDED_OFF = "HANDED_OFF"
    ENDED = "ENDED"


class VoiceTurnState(BaseModel):
    """Trạng thái theo từng lượt nói — phần thay đổi nhiều nhất mỗi turn."""

    turn_index: int = Field(default=0, ge=0)
    stage: TurnStage = TurnStage.IDLE
    consecutive_asr_failures: int = Field(default=0, ge=0)
    last_transcript: str = ""
    last_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    handoff_reason: HandoffReason | None = None


def _new_session_id() -> str:
    return f"sess_{uuid.uuid4().hex[:20]}"


class VoiceSession(BaseModel):
    """Toàn bộ state của một cuộc gọi voice, lưu trong Redis / Memory.

    `agent_state` là opaque blob truyền thẳng vào/nhận về từ Core Agent
    (`AgentState.model_dump()` phía agentic — Voice không diễn giải nội
    dung bên trong, chỉ lưu và trả lại nguyên vẹn ở turn kế tiếp).
    """

    session_id: str = Field(default_factory=_new_session_id)
    channel: str = "WEB_VOICE"  # khớp SessionDTO.channel bên Backend (WEB_VOICE | WEB_TEXT)
    status: SessionStatus = SessionStatus.ACTIVE
    turn: VoiceTurnState = Field(default_factory=VoiceTurnState)
    agent_state: dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def touch(self) -> None:
        self.updated_at = time.time()


# ---------------------------------------------------------------------------
# WebSocket protocol
# ---------------------------------------------------------------------------
#
# Kênh nhị phân (binary WS frame):
#   client -> server : audio thô PCM16 mono từ mic (bất kỳ sample rate nào,
#                       codec.py sẽ resample về 16kHz).
#   server -> client : audio đã TTS (mime theo TTSResult.mime_type, xem
#                       event AUDIO_META ngay trước đó để biết cách phát).
#
# Kênh JSON (text WS frame): mọi thứ còn lại đi qua WSServerEvent /
# WSClientControl bên dưới.


class WSEventType(StrEnum):
    SESSION_READY = "session_ready"
    STATUS = "status"  # payload: {"stage": TurnStage}
    TRANSCRIPT = "transcript"  # payload: {"text", "confidence", "is_final"}
    AGENT_MESSAGE = "agent_message"  # payload: {"text"} — câu agent sắp/đang nói
    AUDIO_META = "audio_meta"  # payload: {"mime_type", "sample_rate", "text"} — báo trước binary frame TTS
    HANDOFF = "handoff"  # payload: {"reason", "summary"}
    ERROR = "error"  # payload: {"message", "code"}
    SESSION_ENDED = "session_ended"  # payload: {"reason"}


class WSServerEvent(BaseModel):
    """Mọi message JSON server gửi cho client đều bọc trong shape này."""

    type: WSEventType
    session_id: str
    seq: int = Field(default=0, ge=0)
    payload: dict[str, Any] = Field(default_factory=dict)


class ClientControlType(StrEnum):
    START_CALL = "start_call"
    END_CALL = "end_call"
    PING = "ping"


class WSClientControl(BaseModel):
    """Message JSON client gửi lên (audio đi qua binary frame riêng)."""

    type: ClientControlType
    payload: dict[str, Any] = Field(default_factory=dict)
