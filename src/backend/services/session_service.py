from __future__ import annotations

from datetime import UTC, datetime
import re
from uuid import uuid4

from src.backend.services.booking_service import BookingService


class SessionService:
    sessions: dict[str, dict[str, object]] = {}

    def create_session(self, user_id: str, channel: str, device_id: str | None = None) -> dict[str, object]:
        session_id = f"sess_{uuid4().hex[:12]}"
        now = datetime.now(UTC).isoformat()
        self.sessions[session_id] = {
            "session_id": session_id, "call_id": f"call_{uuid4().hex[:8]}", "user_id": user_id,
            "status": "ACTIVE", "channel": channel, "device_id": device_id, "created_at": now,
            "intent": None, "pickup": None, "destination": None, "vehicle_type": "4_SEAT",
            "confirmation_status": "pending", "failed_count": 0, "booking_id": None,
            "handoff_triggered": False, "current_workflow": None, "current_step": "START",
        }
        return {"session_id": session_id, "status": "ACTIVE", "channel": channel, "created_at": now}

    def get_session(self, session_id: str) -> dict[str, object]:
        session = self.sessions.get(session_id)
        if session is None:
            raise KeyError("Không tìm thấy phiên hội thoại")
        return session.copy()

    def update_session(self, session_id: str, payload: dict[str, object]) -> dict[str, object]:
        session = self.sessions.get(session_id)
        if session is None:
            raise KeyError("Không tìm thấy phiên hội thoại")
        session.update(payload)
        return session.copy()

    def resume_session(self, session_id: str) -> dict[str, str]:
        session = self.sessions.get(session_id)
        if session is None:
            raise KeyError("Không tìm thấy phiên hội thoại")
        session["status"] = "ACTIVE"
        return {"session_id": session_id, "status": "resumed"}

    def end_session(self, session_id: str, reason: str) -> dict[str, str]:
        session = self.sessions.get(session_id)
        if session is None:
            raise KeyError("Không tìm thấy phiên hội thoại")
        session.update({"status": "ENDED", "end_reason": reason})
        return {"session_id": session_id, "status": "ENDED", "ended_at": datetime.now(UTC).isoformat()}

    def process_message(self, session_id: str, message: str, confidence: float | None = None) -> dict[str, object]:
        session = self.sessions.get(session_id)
        if session is None:
            raise KeyError("Không tìm thấy phiên hội thoại")
        if session["status"] != "ACTIVE":
            raise ValueError("Phiên hội thoại đã kết thúc")
        text = message.strip()
        normalized = text.lower()
        if confidence is not None and confidence < 0.55:
            session["failed_count"] = int(session["failed_count"]) + 1
            if session["failed_count"] >= 2:
                session.update({"handoff_triggered": True, "current_step": "HANDOFF"})
                return self._reply(session, "HANDOFF", "Em xin phép chuyển cuộc gọi đến tổng đài viên ạ.")
            return self._reply(session, "ASK_USER", "Em chưa nghe rõ. Anh/chị vui lòng nói lại hoặc nhắn tin giúp em.")
        session["failed_count"] = 0
        if any(term in normalized for term in ("gặp người", "tổng đài viên", "khiếu nại", "tai nạn", "thanh toán", "hoàn tiền")):
            session.update({"handoff_triggered": True, "current_step": "HANDOFF"})
            return self._reply(session, "HANDOFF", "Em xin phép chuyển cuộc gọi đến tổng đài viên ạ.")
        if any(term in normalized for term in ("thôi", "hủy", "không đặt")):
            session.update({"status": "ENDED", "current_step": "CANCELLED"})
            return self._reply(session, "END_SESSION", "Em đã hủy yêu cầu đặt xe. Khi cần, anh/chị cứ nhắn em nhé.")
        if session["current_step"] == "CONFIRM":
            if normalized in {"đúng", "dong", "đồng ý", "xac nhan", "xác nhận", "ok", "oke"}:
                session["confirmation_status"] = "confirmed"
                booking = BookingService().create_booking_from_session(session)
                session.update({"booking_id": booking["booking_id"], "current_step": "BOOKED"})
                return self._reply(session, "RESPOND", "Đặt xe thành công. Hệ thống đang tìm tài xế cho anh/chị.", booking)
            return self._reply(session, "ASK_USER", "Anh/chị vui lòng nói “Đúng” để xác nhận, hoặc “Thôi” để hủy.")
        if session["current_step"] == "COLLECT_PICKUP":
            session["pickup"] = self._location(text)
            session["current_step"] = "COLLECT_DESTINATION"
            return self._reply(session, "ASK_USER", "Anh/chị muốn đến đâu ạ?")
        if session["current_step"] == "COLLECT_DESTINATION":
            session["destination"] = self._location(text)
            return self._confirm(session)
        route = self._extract_route(text)
        if route:
            session.update({"intent": "RIDE_BOOKING", "current_workflow": "RIDE_BOOKING", "pickup": self._location(route[0]), "destination": self._location(route[1])})
            return self._confirm(session)
        if any(term in normalized for term in ("đặt xe", "gọi xe", "đi xe", "muốn đi")):
            session.update({"intent": "RIDE_BOOKING", "current_workflow": "RIDE_BOOKING", "current_step": "COLLECT_PICKUP"})
            return self._reply(session, "ASK_USER", "Anh/chị muốn đón ở đâu ạ?")
        return self._reply(session, "RESPOND", "Em có thể giúp đặt xe. Anh/chị nói “đặt xe từ A đến B” nhé.")

    def _confirm(self, session: dict[str, object]) -> dict[str, object]:
        session["current_step"] = "CONFIRM"
        pickup = session["pickup"]["name"]  # type: ignore[index]
        destination = session["destination"]["name"]  # type: ignore[index]
        return self._reply(session, "ASK_USER", f"Xe 4 chỗ từ {pickup} đến {destination}, giá dự kiến 85.000 ₫. Anh/chị xác nhận “Đúng” nhé?")

    @staticmethod
    def _extract_route(text: str) -> tuple[str, str] | None:
        match = re.search(r"(?:từ|đón(?: tôi)? ở)\s+(.+?)\s+(?:đến|tới|ra)\s+(.+)", text, re.IGNORECASE)
        return (match.group(1).strip(" .,"), match.group(2).strip(" .,")) if match else None

    @staticmethod
    def _location(name: str) -> dict[str, object]:
        return {"name": name, "lat": 10.7769, "lng": 106.7009, "place_id": f"place_{uuid4().hex[:8]}"}

    @staticmethod
    def _reply(session: dict[str, object], action: str, message: str, booking: dict[str, object] | None = None) -> dict[str, object]:
        state = {key: session.get(key) for key in ("current_workflow", "current_step", "pickup", "destination", "vehicle_type", "confirmation_status", "booking_id")}
        return {"message_id": f"msg_{uuid4().hex[:10]}", "action": action, "message": message, "state": state, "booking": booking}
