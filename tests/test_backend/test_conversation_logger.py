import json

import pytest

from src.backend.services.conversation_logger import ConversationLogger
from src.backend.services.session_service import SessionService


@pytest.fixture
def logs_dir(tmp_path):
    return tmp_path / "logs"


@pytest.fixture
def logger(logs_dir):
    return ConversationLogger(logs_dir=logs_dir)


def test_start_session_creates_timestamped_json(logger, logs_dir):
    path = logger.start_session(
        session_id="sess_abc123456789",
        user_id="usr_demo",
        channel="WEB_VOICE",
    )

    assert path.parent == logs_dir
    assert path.name.startswith("20")
    assert path.name.endswith(".json")
    assert path.exists()

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["session_id"] == "sess_abc123456789"
    assert payload["messages"] == []
    assert payload["status"] == "ACTIVE"


def test_log_turn_appends_user_and_agent_messages(logger, logs_dir):
    path = logger.start_session(
        session_id="sess_turn001",
        user_id="usr_demo",
        channel="WEB_TEXT",
    )

    logger.log_turn(
        path.name,
        user_message="Tôi muốn đặt xe",
        source="TEXT",
        agent_message="Anh/chị muốn đón ở đâu?",
        message_id="msg_001",
        action="ASK_USER",
        state={"booking_progress": {"missing_field": "pickup"}},
    )

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert len(payload["messages"]) == 2
    assert payload["messages"][0]["role"] == "user"
    assert payload["messages"][0]["text"] == "Tôi muốn đặt xe"
    assert payload["messages"][1]["role"] == "agent"
    assert payload["messages"][1]["action"] == "ASK_USER"
    assert payload["updated_at"] == payload["messages"][1]["timestamp"]


def test_end_session_updates_status(logger):
    path = logger.start_session(
        session_id="sess_end001",
        user_id="usr_demo",
        channel="WEB_VOICE",
    )

    logger.end_session(path.name, reason="USER_ENDED")

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["status"] == "ENDED"
    assert payload["end_reason"] == "USER_ENDED"
    assert payload["ended_at"]


@pytest.mark.asyncio
async def test_session_service_writes_conversation_log(logs_dir, monkeypatch):
    monkeypatch.setattr(
        SessionService,
        "_conversation_logger",
        ConversationLogger(logs_dir=logs_dir),
    )
    SessionService.sessions.clear()

    service = SessionService()
    created = service.create_session("usr_demo", "WEB_TEXT", "browser")
    session_id = str(created["session_id"])
    log_file = logs_dir / str(service.sessions[session_id]["log_file"])

    await service.process_message(session_id, "Tôi muốn đặt xe", source="TEXT")

    payload = json.loads(log_file.read_text(encoding="utf-8"))
    assert len(payload["messages"]) == 2
    assert payload["messages"][0]["role"] == "user"
    assert payload["messages"][1]["role"] == "agent"

    service.end_session(session_id, "USER_ENDED")
    payload = json.loads(log_file.read_text(encoding="utf-8"))
    assert payload["status"] == "ENDED"
