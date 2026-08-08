from uuid import uuid4


class SessionService:
    def get_session(self, session_id: str) -> dict[str, object]:
        return {
            "session_id": session_id,
            "call_id": f"call_{uuid4().hex[:8]}",
            "intent": None,
            "pickup": None,
            "destination": None,
            "vehicle_type": None,
            "confirmation_status": "pending",
            "failed_count": 0,
            "booking_id": None,
            "handoff_triggered": False,
        }

    def update_session(self, session_id: str, payload: dict[str, object]) -> dict[str, object]:
        session = self.get_session(session_id)
        session.update(payload)
        return session

    def resume_session(self, session_id: str) -> dict[str, str]:
        return {"session_id": session_id, "status": "resumed"}
