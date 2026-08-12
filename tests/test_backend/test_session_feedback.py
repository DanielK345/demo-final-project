import pytest

from src.backend.services.session_service import SessionService


@pytest.mark.asyncio
async def test_submit_feedback_after_successful_booking():
    SessionService.sessions.clear()
    service = SessionService()
    created = service.create_session("usr_demo", "WEB_TEXT", "browser")
    session_id = str(created["session_id"])
    session = service.sessions[session_id]
    session["booking_lifecycle_status"] = "SUCCESS"
    session["booking_id"] = "booking-001"

    result = service.submit_feedback(session_id, 5, "Rất tốt")

    assert result["feedback"]["rating"] == 5
    assert service.sessions[session_id]["feedback"]["rating"] == 5


@pytest.mark.asyncio
async def test_submit_feedback_rejected_without_success():
    SessionService.sessions.clear()
    service = SessionService()
    created = service.create_session("usr_demo", "WEB_TEXT", "browser")
    session_id = str(created["session_id"])

    with pytest.raises(ValueError, match="đánh giá"):
        service.submit_feedback(session_id, 4)
