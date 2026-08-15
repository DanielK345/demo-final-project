from uuid import uuid4


class CallService:
    def create_call(self, customer_phone: str) -> dict[str, str]:
        return {
            "call_id": f"call_{uuid4().hex[:8]}",
            "session_id": f"sess_{uuid4().hex[:8]}",
            "status": "active",
        }
