import numpy as np
import pytest

from src.voice.audio.vad import EnergyVAD
from src.voice.config import VoiceSettings
from src.voice.gateway import GatewaySessionNotFoundError, VoiceGateway
from src.voice.schemas import ASRResult, TurnStage, WSEventType, WSServerEvent
from src.voice.session_bridge import SessionTurnResult
from tests.test_voice.fake_providers import (
    FailingASRProvider,
    FailingTTSProvider,
    FakeASRProvider,
    FakeTTSProvider,
)


class FakeSessionBridge:
    """Test-double độc lập với `SessionService` thật — dùng để test riêng logic của
    `gateway.py` (RMS gate, BR-001 client-side, xử lý action) mà không phụ thuộc quy
    tắc nghiệp vụ cụ thể của Backend (đã có `test_session_bridge.py` test riêng phần
    tích hợp với `SessionService` thật)."""

    def __init__(self, responses: list[SessionTurnResult] | None = None, current_step: str | None = None):
        self._queue = list(responses) if responses else None
        self.current_step = current_step
        self.sent: list[tuple[str, str, float | None]] = []
        self.started = 0
        self.ended: list[tuple[str, str]] = []

    async def start_session(self, *, channel: str = "WEB_VOICE", device_id: str | None = None):
        self.started += 1
        return {"session_id": f"sess_fake_{self.started}", "status": "ACTIVE", "channel": channel}

    async def get_session(self, session_id: str):
        return {"session_id": session_id, "current_step": self.current_step}

    async def send_message(self, session_id: str, text: str, stt_confidence: float | None = None):
        self.sent.append((session_id, text, stt_confidence))
        if self._queue:
            return self._queue.pop(0)
        return SessionTurnResult(action="ASK_USER", message="Anh/chị muốn đón ở đâu ạ?", state={})

    async def end_session(self, session_id: str, reason: str = "USER_ENDED"):
        self.ended.append((session_id, reason))
        return {"session_id": session_id, "status": "ENDED"}


def _settings(**overrides) -> VoiceSettings:
    defaults = {
        "voice_vad_backend": "energy",
        "voice_vad_silence_ms": 100,
        "voice_min_utterance_rms": 0.01,
        "voice_booking_confirmation_confidence_threshold": 0.80,
    }
    defaults.update(overrides)
    return VoiceSettings(**defaults)


def _make_gateway(asr=None, tts=None, session_bridge=None, tts_formatter=None, tts_pronunciation=None, **settings_overrides):
    settings = _settings(**settings_overrides)
    asr = asr or FakeASRProvider()
    tts = tts or FakeTTSProvider()
    bridge = session_bridge or FakeSessionBridge()
    gateway = VoiceGateway(
        asr=asr,
        tts=tts,
        settings=settings,
        session_bridge=bridge,
        vad_factory=lambda: EnergyVAD(threshold_rms=0.1),
        tts_formatter=tts_formatter,
        tts_pronunciation=tts_pronunciation,
    )
    return gateway, asr, tts, bridge


def _loud_chunk(seconds: float, rate: int = 16000) -> bytes:
    n = int(rate * seconds)
    return (np.ones(n, dtype=np.float32) * 0.5 * 32767).astype("<i2").tobytes()


def _silence_chunk(seconds: float, rate: int = 16000) -> bytes:
    n = int(rate * seconds)
    return np.zeros(n, dtype="<i2").tobytes()


def _events(outputs: list) -> list[WSServerEvent]:
    return [o for o in outputs if isinstance(o, WSServerEvent)]


@pytest.mark.asyncio
async def test_start_session_emits_ready_and_status():
    gateway, *_ = _make_gateway()
    session_id, outputs = await gateway.start_session()
    types = [e.type for e in _events(outputs)]
    assert types == [WSEventType.SESSION_READY, WSEventType.STATUS]
    assert session_id.startswith("sess_fake_")


@pytest.mark.asyncio
async def test_unknown_session_raises():
    gateway, *_ = _make_gateway()
    with pytest.raises(GatewaySessionNotFoundError):
        await gateway.handle_audio_chunk("nope", b"\x00\x00", 16000)


@pytest.mark.asyncio
async def test_full_turn_forwards_transcript_to_session_bridge_and_speaks_reply():
    gateway, asr, tts, bridge = _make_gateway()
    session_id, _ = await gateway.start_session()

    outputs = []
    outputs += await gateway.handle_audio_chunk(session_id, _loud_chunk(1.0), 16000)
    outputs += await gateway.handle_audio_chunk(session_id, _silence_chunk(1.0), 16000)

    types = [e.type for e in _events(outputs)]
    assert WSEventType.TRANSCRIPT in types
    assert WSEventType.AGENT_MESSAGE in types
    assert WSEventType.AUDIO_META in types
    assert any(isinstance(o, bytes) for o in outputs)
    assert len(bridge.sent) == 1
    assert len(tts.calls) == 1


@pytest.mark.asyncio
async def test_near_silent_utterance_skips_asr_and_backend_entirely():
    gateway, asr, tts, bridge = _make_gateway()
    session_id, _ = await gateway.start_session()

    outputs = await gateway._handle_utterance(
        gateway._connections[session_id], np.zeros(16000, dtype="<i2").tobytes()
    )

    assert asr.calls == []
    assert bridge.sent == []  # không gửi lên SessionService — chỉ tự re-prompt
    types = [e.type for e in _events(outputs)]
    assert WSEventType.AGENT_MESSAGE in types


@pytest.mark.asyncio
async def test_asr_provider_exception_handled_gracefully_and_not_forwarded():
    asr = FailingASRProvider(RuntimeError("Groq tạm thời sập"))
    gateway, asr, tts, bridge = _make_gateway(asr=asr)
    session_id, _ = await gateway.start_session()

    outputs = await gateway._handle_utterance(gateway._connections[session_id], _loud_chunk(1.0))

    types = [e.type for e in _events(outputs)]
    assert WSEventType.ERROR in types
    assert asr.calls == 1
    assert bridge.sent == []  # text rỗng -> không gửi lên SessionService


@pytest.mark.asyncio
async def test_tts_provider_exception_handled_gracefully():
    tts = FailingTTSProvider(RuntimeError("Edge-TTS tạm thời sập"))
    gateway, asr, tts, bridge = _make_gateway(tts=tts)
    session_id, _ = await gateway.start_session()

    outputs = await gateway._speak(gateway._connections[session_id], "xin chào")

    types = [e.type for e in outputs if isinstance(e, WSServerEvent)]
    assert WSEventType.ERROR in types
    assert tts.calls == 1
    assert not any(isinstance(o, bytes) for o in outputs)


@pytest.mark.asyncio
async def test_confirmation_step_low_confidence_is_not_forwarded_to_backend():
    """BR-001: lớp thận trọng riêng của Voice — confidence 0.70 đủ cho ngưỡng phẳng
    0.55 của SessionService nhưng KHÔNG đủ cho bước CONFIRM (ngưỡng riêng 0.80)."""
    asr = FakeASRProvider(responses=[ASRResult(text="đúng rồi", confidence=0.70)])
    bridge = FakeSessionBridge(current_step="CONFIRM")
    gateway, asr, tts, bridge = _make_gateway(asr=asr, session_bridge=bridge)
    session_id, _ = await gateway.start_session()

    outputs = await gateway._handle_utterance(gateway._connections[session_id], _loud_chunk(1.0))

    assert bridge.sent == []  # không được gửi lên backend
    types = [e.type for e in _events(outputs)]
    assert WSEventType.AGENT_MESSAGE in types


@pytest.mark.asyncio
async def test_confirmation_step_high_confidence_is_forwarded():
    asr = FakeASRProvider(responses=[ASRResult(text="đúng rồi", confidence=0.95)])
    bridge = FakeSessionBridge(current_step="CONFIRM")
    gateway, asr, tts, bridge = _make_gateway(asr=asr, session_bridge=bridge)
    session_id, _ = await gateway.start_session()

    await gateway._handle_utterance(gateway._connections[session_id], _loud_chunk(1.0))

    assert len(bridge.sent) == 1
    assert bridge.sent[0][1] == "đúng rồi"


@pytest.mark.asyncio
async def test_non_confirmation_step_low_confidence_is_still_forwarded():
    """Ngoài bước CONFIRM, Voice KHÔNG tự áp ngưỡng riêng — tin tưởng hoàn toàn
    ngưỡng 0.55 phẳng của SessionService."""
    asr = FakeASRProvider(responses=[ASRResult(text="tôi muốn đặt xe", confidence=0.60)])
    bridge = FakeSessionBridge(current_step="COLLECT_PICKUP")
    gateway, asr, tts, bridge = _make_gateway(asr=asr, session_bridge=bridge)
    session_id, _ = await gateway.start_session()

    await gateway._handle_utterance(gateway._connections[session_id], _loud_chunk(1.0))

    assert len(bridge.sent) == 1


@pytest.mark.asyncio
async def test_brief_ambiguous_sound_is_not_forwarded_to_backend():
    asr = FakeASRProvider(responses=[ASRResult(text="ừm", confidence=0.95)])
    gateway, asr, tts, bridge = _make_gateway(asr=asr)
    session_id, _ = await gateway.start_session()

    outputs = await gateway._handle_utterance(
        gateway._connections[session_id],
        _loud_chunk(0.25),
    )

    assert bridge.sent == []
    assert WSEventType.AGENT_MESSAGE in [event.type for event in _events(outputs)]


@pytest.mark.asyncio
async def test_meaningful_brief_confirmation_is_still_forwarded():
    asr = FakeASRProvider(responses=[ASRResult(text="ừ", confidence=0.95)])
    gateway, asr, tts, bridge = _make_gateway(asr=asr)
    session_id, _ = await gateway.start_session()

    await gateway._handle_utterance(
        gateway._connections[session_id],
        _loud_chunk(0.25),
    )

    assert len(bridge.sent) == 1
    assert bridge.sent[0][1] == "ừ"


@pytest.mark.asyncio
async def test_handoff_action_sets_stage_and_emits_handoff_event():
    bridge = FakeSessionBridge(responses=[SessionTurnResult(action="HANDOFF", message="Chuyển tổng đài viên.")])
    gateway, asr, tts, bridge = _make_gateway(session_bridge=bridge)
    session_id, _ = await gateway.start_session()

    outputs = await gateway._handle_utterance(gateway._connections[session_id], _loud_chunk(1.0))

    types = [e.type for e in _events(outputs)]
    assert WSEventType.HANDOFF in types
    assert gateway._connections[session_id].stage == TurnStage.HANDED_OFF


@pytest.mark.asyncio
async def test_end_session_action_sets_ended_stage():
    bridge = FakeSessionBridge(responses=[SessionTurnResult(action="END_SESSION", message="Đã huỷ yêu cầu.")])
    gateway, asr, tts, bridge = _make_gateway(session_bridge=bridge)
    session_id, _ = await gateway.start_session()

    await gateway._handle_utterance(gateway._connections[session_id], _loud_chunk(1.0))

    assert gateway._connections[session_id].stage == TurnStage.ENDED


@pytest.mark.asyncio
async def test_session_not_found_response_emits_error():
    class _NoneBridge(FakeSessionBridge):
        async def send_message(self, session_id, text, stt_confidence=None):
            self.sent.append((session_id, text, stt_confidence))
            return None

    bridge = _NoneBridge()
    gateway, asr, tts, bridge = _make_gateway(session_bridge=bridge)
    session_id, _ = await gateway.start_session()

    outputs = await gateway._handle_utterance(gateway._connections[session_id], _loud_chunk(1.0))

    types = [e.type for e in _events(outputs)]
    assert WSEventType.ERROR in types


@pytest.mark.asyncio
async def test_tts_formatter_and_pronunciation_hooks_applied_before_synthesize():
    tts = FakeTTSProvider()
    gateway, asr, tts, bridge = _make_gateway(
        tts=tts,
        tts_formatter=lambda text: text.replace("20.000", "hai mươi nghìn"),
        tts_pronunciation=lambda text: text.replace("AloSM", "Alo Ét Em"),
    )
    session_id, _ = await gateway.start_session()

    outputs = await gateway._speak(gateway._connections[session_id], "Giá chuyến AloSM là 20.000 đồng")

    assert tts.calls == ["Giá chuyến Alo Ét Em là hai mươi nghìn đồng"]
    audio_meta = next(e for e in outputs if isinstance(e, WSServerEvent) and e.type == WSEventType.AUDIO_META)
    assert audio_meta.payload["text"] == "Giá chuyến AloSM là 20.000 đồng"


@pytest.mark.asyncio
async def test_pronunciation_hook_runs_before_formatter_hook():
    """Regression thật: nếu formatter (số -> chữ) chạy trước pronunciation, nó "ăn"
    mất số trong tên riêng (vd "Landmark 81" -> "Landmark tám mươi mốt") trước khi
    pronunciation kịp khớp chuỗi gốc để override. `_speak()` phải gọi
    tts_pronunciation TRƯỚC tts_formatter — xem src/voice/gateway.py."""
    tts = FakeTTSProvider()
    gateway, asr, tts, bridge = _make_gateway(
        tts=tts,
        tts_formatter=lambda text: text.replace("81", "tám mươi mốt"),
        tts_pronunciation=lambda text: text.replace("Landmark 81", "Len Mác Tám Mươi Mốt"),
    )
    session_id, _ = await gateway.start_session()

    await gateway._speak(gateway._connections[session_id], "Xe đang tới Landmark 81")

    assert tts.calls == ["Xe đang tới Len Mác Tám Mươi Mốt"]


@pytest.mark.asyncio
async def test_end_session_calls_bridge_and_cleans_up_connection():
    gateway, *_rest = _make_gateway()
    bridge = gateway.session_bridge
    session_id, _ = await gateway.start_session()

    outputs = await gateway.end_session(session_id, reason="USER_ENDED")

    assert bridge.ended == [(session_id, "USER_ENDED")]
    assert any(isinstance(e, WSServerEvent) and e.type == WSEventType.SESSION_ENDED for e in outputs)
    with pytest.raises(GatewaySessionNotFoundError):
        await gateway.handle_audio_chunk(session_id, _loud_chunk(0.1), 16000)
