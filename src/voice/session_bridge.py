"""Seam duy nhất giữa Voice Gateway và dialogue engine thật của Backend.

Dialogue engine thật của project này là
`src.backend.services.session_service.SessionService` (rule-based state machine:
COLLECT_PICKUP → COLLECT_DESTINATION → CONFIRM → BOOKED, xử lý `stt_confidence`,
BR-003-tương-đương qua `failed_count`) — **không phải** `src/agents/graph.py`
(LangGraph agent đó chỉ còn phục vụ route `/chat` legacy, xem
`src/backend/api/routes/__init__.py`). Xác nhận bằng cách đọc code thật, không đoán
— xem `docs/prompt_voice_integration_real_be_fe.md`.

Gọi thẳng `SessionService()` bằng Python (cùng process) — không qua HTTP, không cần
token auth: `SessionService.sessions` là **class attribute**, mọi instance
`SessionService()` (kể cả instance Voice tự tạo) đọc/ghi chung 1 dict, nên tương tác
đúng với session được tạo qua REST `/api/v1/sessions` (nếu có) và ngược lại. Token
auth chỉ nằm ở route handler (`_user_id_from_header`), không nằm trong
`SessionService` — Voice bỏ qua auth, tự cấp `user_id` dạng khách ẩn danh.

Đây là module DUY NHẤT trong `src/voice/` import từ `src.backend.*` — nếu sau này
dialogue engine đổi (vd. dùng Core Agent thật ở `src/agents/`), chỉ cần sửa file
này, không đụng `gateway.py`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from src.backend.services.session_service import SessionService


@dataclass
class SessionTurnResult:
    action: str
    message: str
    state: dict[str, Any] = field(default_factory=dict)
    booking: dict[str, Any] | None = None


class SessionBridge:
    def __init__(self, service: SessionService | None = None) -> None:
        self._service = service or SessionService()

    async def start_session(
        self,
        *,
        channel: str = "WEB_VOICE",
        device_id: str | None = None,
    ) -> dict[str, Any]:
        user_id = f"voice_guest_{uuid4().hex[:8]}"
        return self._service.create_session(user_id, channel, device_id)

    async def get_session(self, session_id: str) -> dict[str, Any] | None:
        try:
            return self._service.get_session(session_id)
        except KeyError:
            return None

    async def send_message(
        self,
        session_id: str,
        text: str,
        stt_confidence: float | None = None,
    ) -> SessionTurnResult | None:
        """Trả None nếu session không tồn tại hoặc đã kết thúc — gateway tự xử lý
        (không raise để khỏi ép gateway phải try/except riêng cho từng loại lỗi)."""
        try:
            result = await self._service.process_message(session_id, text, stt_confidence)
        except (KeyError, ValueError):
            return None
        return SessionTurnResult(
            action=str(result.get("action", "RESPOND")),
            message=str(result.get("message", "")),
            state=dict(result.get("state") or {}),
            booking=result.get("booking"),
        )

    async def end_session(self, session_id: str, reason: str = "USER_ENDED") -> dict[str, Any] | None:
        try:
            return self._service.end_session(session_id, reason)
        except KeyError:
            return None
