"""Test `SessionBridge` — verify nó gọi đúng `SessionService` thật (không mock), vì
đây chính là điểm tích hợp quan trọng nhất với Backend (xem
docs/voice-ai/prompt_voice_integration_real_be_fe.md). Dùng instance `SessionService()` riêng
cho mỗi test để không rò rỉ state qua `sessions` (class attribute dùng chung)."""

import pytest

from src.backend.services.session_service import SessionService
from src.voice.session_bridge import SessionBridge


def _bridge() -> tuple[SessionBridge, SessionService]:
    service = SessionService()
    return SessionBridge(service), service


@pytest.mark.asyncio
async def test_start_session_creates_real_session_in_session_service():
    bridge, service = _bridge()
    created = await bridge.start_session(channel="WEB_VOICE")

    assert created["channel"] == "WEB_VOICE"
    assert created["status"] == "ACTIVE"
    # Session phải thật sự tồn tại trong SessionService (không phải id giả).
    assert service.get_session(created["session_id"])["session_id"] == created["session_id"]


@pytest.mark.asyncio
async def test_get_session_returns_none_for_unknown_id():
    bridge, _ = _bridge()
    assert await bridge.get_session("does-not-exist") is None


@pytest.mark.asyncio
async def test_send_message_drives_real_booking_flow():
    bridge, _ = _bridge()
    created = await bridge.start_session()
    session_id = created["session_id"]

    turn = await bridge.send_message(session_id, "tôi muốn đặt xe", stt_confidence=0.95)
    assert turn is not None
    assert turn.action == "ASK_USER"
    assert "đón" in turn.message.lower()


@pytest.mark.asyncio
async def test_send_message_low_confidence_triggers_immediate_handoff():
    """Trước đây (SessionService rule-based cũ): 1 lượt confidence thấp chỉ tăng
    `failed_count`, phải 2 lượt liên tiếp mới handoff. Sau khi Core Agent thật
    (`src.agents.agent.LLMAgent` + `AgentGuardrails`) được nối vào làm dialogue
    engine, hành vi đã đổi — xác nhận bằng cách gọi trực tiếp
    `SessionService.process_message` thật: confidence=0.2 handoff ngay từ lượt đầu.
    Test này verify `SessionBridge` phản ánh đúng hành vi THẬT hiện tại của
    SessionService, không phải giả định cũ."""
    bridge, service = _bridge()
    created = await bridge.start_session()
    session_id = created["session_id"]

    turn = await bridge.send_message(session_id, "ừm gì đó", stt_confidence=0.2)
    assert turn is not None
    assert turn.action == "HANDOFF"
    assert service.get_session(session_id)["handoff_triggered"] is True


@pytest.mark.asyncio
async def test_send_message_two_low_confidence_turns_triggers_handoff():
    bridge, service = _bridge()
    created = await bridge.start_session()
    session_id = created["session_id"]

    await bridge.send_message(session_id, "ừm", stt_confidence=0.2)
    turn = await bridge.send_message(session_id, "ờ", stt_confidence=0.2)

    assert turn is not None
    assert turn.action == "HANDOFF"
    assert service.get_session(session_id)["handoff_triggered"] is True


@pytest.mark.asyncio
async def test_send_message_returns_none_for_unknown_session():
    bridge, _ = _bridge()
    assert await bridge.send_message("unknown", "xin chào", stt_confidence=0.9) is None


@pytest.mark.asyncio
async def test_send_message_returns_none_after_session_ended():
    bridge, _ = _bridge()
    created = await bridge.start_session()
    session_id = created["session_id"]
    await bridge.end_session(session_id)

    assert await bridge.send_message(session_id, "xin chào", stt_confidence=0.9) is None


@pytest.mark.asyncio
async def test_end_session_marks_ended_in_real_service():
    bridge, service = _bridge()
    created = await bridge.start_session()
    session_id = created["session_id"]

    result = await bridge.end_session(session_id, reason="USER_ENDED")
    assert result is not None
    assert result["status"] == "ENDED"
    assert service.get_session(session_id)["status"] == "ENDED"


@pytest.mark.asyncio
async def test_end_session_unknown_id_returns_none():
    bridge, _ = _bridge()
    assert await bridge.end_session("unknown") is None
