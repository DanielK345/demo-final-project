from datetime import UTC, datetime
from uuid import uuid4

from src.backend.config import get_settings
from src.backend.repositories.handoff_repository import HandoffRepository, get_handoff_repository
from src.backend.repositories.persistence_repository import PersistenceRepository
from src.backend.schemas.handoff import HandoffStatus


class HandoffService:
    def __init__(self, repository: HandoffRepository | None = None) -> None:
        self._repository = repository or get_handoff_repository()
        self._persistence = PersistenceRepository()

    async def create_handoff_durable(self, payload: dict[str, object]) -> dict[str, object]:
        if get_settings().app_env == "test":
            return self.create_handoff(payload)
        values = {
            "session_id": str(payload.get("session_id", "")),
            "reason": str(payload.get("reason", "unknown")),
            "reason_code": str(payload.get("reason_code", "UNABLE_TO_CONTINUE")),
            "summary": str(payload.get("summary", "")),
            "pending_action": payload.get("pending_action"),
            "priority": int(payload.get("priority", 50)),
            "severity": str(payload.get("severity", "NORMAL")),
            "queue": str(payload.get("queue", "GENERAL_OPERATOR")),
            "requires_immediate_transfer": bool(payload.get("requires_immediate_transfer", False)),
            "status": HandoffStatus.PENDING.value,
            "room_name": payload.get("room_name"),
            "context_snapshot": payload.get("context_snapshot"),
        }
        return await self._persistence.create_handoff(values)

    async def list_handoffs_durable(self, status: str) -> list[dict[str, object]]:
        if get_settings().app_env == "test":
            return self.list_handoffs(status)
        return await self._persistence.list_handoffs(HandoffStatus(status).value)

    async def get_handoff_durable(self, handoff_id: str) -> dict[str, object] | None:
        if get_settings().app_env == "test":
            return self._repository.get(handoff_id)
        return await self._persistence.get_handoff(handoff_id)

    async def accept_handoff_durable(self, handoff_id: str, operator_id: str | None = None) -> dict[str, object]:
        if get_settings().app_env == "test":
            return self.accept_handoff(handoff_id, operator_id)
        updated = await self._persistence.accept_handoff(handoff_id, operator_id)
        if updated is None:
            raise KeyError("Không tìm thấy yêu cầu chuyển tổng đài viên")
        return {
            "handoff_id": handoff_id,
            "status": HandoffStatus.ACCEPTED.value,
            "accepted_at": updated["accepted_at"],
            "operator_id": operator_id,
        }

    async def connect_handoff_durable(self, handoff_id: str, operator_id: str) -> dict[str, object]:
        if get_settings().app_env == "test":
            record = self._repository.get(handoff_id)
            if record is None or record.get("status") != "accepted" or record.get("operator_id") != operator_id:
                raise KeyError("Handoff không ở trạng thái accepted")
            return self._repository.update(
                handoff_id, {"status": HandoffStatus.CONNECTED.value, "connected_at": datetime.now(UTC)}
            ) or record
        record = await self._persistence.connect_handoff(handoff_id, operator_id)
        if record is None:
            raise KeyError("Handoff không ở trạng thái accepted")
        return record

    async def resolve_handoff_durable(self, handoff_id: str, operator_id: str) -> dict[str, object]:
        if get_settings().app_env == "test":
            record = self._repository.get(handoff_id)
            if record is None or record.get("operator_id") != operator_id:
                raise KeyError("Không có quyền kết thúc handoff")
            return self._repository.update(
                handoff_id, {"status": HandoffStatus.RESOLVED.value, "resolved_at": datetime.now(UTC)}
            ) or record
        record = await self._persistence.resolve_handoff(handoff_id, operator_id)
        if record is None:
            raise KeyError("Không có quyền kết thúc handoff")
        return record

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
            "connected_at": None,
            "resolved_at": None,
            "operator_id": None,
            "room_name": payload.get("room_name"),
            "context_snapshot": payload.get("context_snapshot"),
        }
        return self._repository.create(record)

    def list_handoffs(self, status: str) -> list[dict[str, object]]:
        normalized = HandoffStatus(status).value
        return self._repository.list_by_status(normalized)

    def accept_handoff(self, handoff_id: str, operator_id: str | None = None) -> dict[str, object]:
        accepted_at = datetime.now(UTC)
        record = self._repository.get(handoff_id)
        if record is None or record.get("status") != HandoffStatus.PENDING.value:
            raise KeyError("Handoff không ở trạng thái pending")
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
