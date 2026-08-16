from datetime import UTC, datetime
from uuid import uuid4

from src.backend.repositories.handoff_repository import HandoffRepository, get_handoff_repository
from src.backend.schemas.handoff import HandoffStatus


class HandoffService:
    def __init__(self, repository: HandoffRepository | None = None) -> None:
        self._repository = repository or get_handoff_repository()

    def create_handoff(self, payload: dict[str, object]) -> dict[str, object]:
        record = {
            "handoff_id": f"handoff_{uuid4().hex[:8]}",
            "session_id": payload.get("session_id", ""),
            "reason": payload.get("reason", "unknown"),
            "reason_code": payload.get("reason_code", "UNABLE_TO_CONTINUE"),
            "summary": payload.get("summary", ""),
            "pending_action": payload.get("pending_action"),
            "priority": payload.get("priority", 50),
            "severity": payload.get("severity", "NORMAL"),
            "queue": payload.get("queue", "GENERAL_OPERATOR"),
            "requires_immediate_transfer": payload.get("requires_immediate_transfer", False),
            "status": HandoffStatus.PENDING.value,
            "created_at": datetime.now(UTC),
            "accepted_at": None,
            "operator_id": None,
        }
        return self._repository.create(record)

    def list_handoffs(self, status: str) -> list[dict[str, object]]:
        normalized = HandoffStatus(status).value
        return self._repository.list_by_status(normalized)

    def accept_handoff(self, handoff_id: str, operator_id: str | None = None) -> dict[str, object]:
        accepted_at = datetime.now(UTC)
        updated = self._repository.update(
            handoff_id,
            {
                "status": HandoffStatus.ACCEPTED.value,
                "accepted_at": accepted_at,
                "operator_id": operator_id,
            },
        )
        if updated is None:
            raise KeyError("Không tìm thấy yêu cầu chuyển tổng đài viên")
        return {
            "handoff_id": handoff_id,
            "status": HandoffStatus.ACCEPTED.value,
            "accepted_at": accepted_at,
            "operator_id": operator_id,
        }
