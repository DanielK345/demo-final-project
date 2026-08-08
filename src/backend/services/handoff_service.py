from uuid import uuid4


class HandoffService:
    def create_handoff(self, payload: dict[str, object]) -> dict[str, object]:
        return {
            "handoff_id": f"handoff_{uuid4().hex[:8]}",
            "session_id": payload.get("session_id", ""),
            "reason": payload.get("reason", "unknown"),
            "summary": payload.get("summary", ""),
            "pending_action": payload.get("pending_action"),
            "status": "pending",
        }

    def list_handoffs(self, status: str) -> list[dict[str, object]]:
        return [
            {
                "handoff_id": f"handoff_{uuid4().hex[:8]}",
                "session_id": "sess_demo",
                "reason": status,
                "summary": "Queued handoff placeholder",
                "pending_action": None,
                "status": status,
            }
        ]

    def accept_handoff(self, handoff_id: str) -> dict[str, object]:
        return {"handoff_id": handoff_id, "status": "accepted"}
