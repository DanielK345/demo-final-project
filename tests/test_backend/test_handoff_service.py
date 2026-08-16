import pytest

from src.backend.repositories.handoff_repository import HandoffRepository
from src.backend.services.handoff_service import HandoffService


def test_handoff_service_persists_lists_and_accepts_real_record():
    service = HandoffService(HandoffRepository())
    created = service.create_handoff(
        {
            "session_id": "sess-1",
            "reason": "Emergency",
            "reason_code": "EMERGENCY",
            "summary": "Customer needs immediate help",
            "priority": 100,
            "severity": "CRITICAL",
            "queue": "SAFETY_OPERATOR",
            "requires_immediate_transfer": True,
        }
    )

    pending = service.list_handoffs("pending")
    assert [item["handoff_id"] for item in pending] == [created["handoff_id"]]
    assert pending[0]["reason_code"] == "EMERGENCY"

    accepted = service.accept_handoff(created["handoff_id"], "operator-1")
    assert accepted["status"] == "accepted"
    assert accepted["operator_id"] == "operator-1"
    assert service.list_handoffs("pending") == []
    assert service.list_handoffs("accepted")[0]["handoff_id"] == created["handoff_id"]


def test_accept_unknown_handoff_is_rejected():
    service = HandoffService(HandoffRepository())

    with pytest.raises(KeyError):
        service.accept_handoff("handoff-missing")


def test_pending_queue_is_sorted_by_priority():
    service = HandoffService(HandoffRepository())
    service.create_handoff({"session_id": "low", "reason": "low", "summary": "low", "priority": 10})
    service.create_handoff({"session_id": "high", "reason": "high", "summary": "high", "priority": 90})

    assert [item["session_id"] for item in service.list_handoffs("pending")] == ["high", "low"]
