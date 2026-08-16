from src.backend.services.session_service import SessionService


class _Logger:
    def __init__(self) -> None:
        self.reset_log_file: str | None = None

    def reset_conversation(self, log_file: str) -> None:
        self.reset_log_file = log_file


def test_reset_conversation_keeps_active_session_but_clears_agent_memory(monkeypatch):
    logger = _Logger()
    monkeypatch.setattr(SessionService, "_conversation_logger", logger)
    SessionService.sessions.clear()
    SessionService.sessions["sess_reset"] = {
        "session_id": "sess_reset",
        "status": "ACTIVE",
        "log_file": "reset.json",
        "intent": "RIDE_BOOKING",
        "pickup": {"label": "VinUni"},
        "destination": {"label": "Hồ Gươm"},
        "vehicle_type": "CAR_4",
        "confirmation_status": "confirmed",
        "failed_count": 2,
        "booking_id": "book_old",
        "handoff_triggered": True,
        "handoff_id": "handoff_old",
        "booking_lifecycle_status": "PENDING",
        "feedback": {"rating": 5},
        "current_workflow": "RIDE_BOOKING",
        "current_step": "CONFIRM",
        "agent_state": {"conversation_history": [{"content": "old memory"}]},
        "turn_sequence": 4,
    }

    result = SessionService().reset_conversation("sess_reset")
    session = SessionService.sessions["sess_reset"]

    assert result["session_id"] == "sess_reset"
    assert result["status"] == "ACTIVE"
    assert logger.reset_log_file == "reset.json"
    assert session["session_id"] == "sess_reset"
    assert session["status"] == "ACTIVE"
    assert session["agent_state"] is None
    assert session["turn_sequence"] == 0
    assert session["pickup"] is None
    assert session["destination"] is None
    assert session["booking_id"] is None
