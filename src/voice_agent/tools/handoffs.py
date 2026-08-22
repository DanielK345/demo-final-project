"""Application boundary for a native LiveKit handoff function tool."""

from __future__ import annotations

import unicodedata
from typing import Protocol

from src.backend.services.handoff_service import HandoffService
from src.voice_agent.session_data import AloSMSessionData


class DurableHandoffService(Protocol):
    async def create_handoff_durable(self, payload: dict[str, object]) -> dict[str, object]: ...


class HandoffToolsService:
    def __init__(self, service: DurableHandoffService | None = None) -> None:
        self._service = service or HandoffService()

    @staticmethod
    def is_handoff_request(text: str) -> bool:
        folded = unicodedata.normalize("NFKD", text.casefold())
        normalized = "".join(char for char in folded if not unicodedata.combining(char))
        normalized = " ".join(normalized.replace("đ", "d").split())
        return any(
            phrase in normalized
            for phrase in (
                "gap nguoi that",
                "gap tong dai vien",
                "tong dai vien that",
                "nhan vien that",
                "chuyen may",
                "chuyen cho toi gap",
                "operator",
                "human agent",
            )
        )

    @staticmethod
    def _classify(reason: str) -> tuple[str, int, str, str, bool]:
        folded = unicodedata.normalize("NFKD", reason.casefold())
        text = "".join(char for char in folded if not unicodedata.combining(char))
        if any(token in text for token in ("tai nan", "nguy hiem", "de doa", "cap cuu", "bi danh")):
            return "EMERGENCY", 100, "CRITICAL", "EMERGENCY_OPERATOR", True
        if any(token in text for token in ("tai xe khong cho", "tai xe khong den", "khong nhan chuyen", "bo khach")):
            return "ACTIVE_TRIP_NO_SHOW", 90, "HIGH", "ACTIVE_TRIP_SUPPORT", True
        if any(token in text for token in ("tru tien sai", "thanh toan", "hoan tien", "khieu nai")):
            return "PAYMENT_DISPUTE", 80, "HIGH", "PAYMENT_OPERATOR", False
        if any(token in text for token in ("khong nghe ro", "nhan dien", "stt", "noi lai nhieu lan")):
            return "LOW_CONFIDENCE", 70, "HIGH", "GENERAL_OPERATOR", False
        if any(token in text for token in ("loi he thong", "khong tao duoc", "bao gia loi")):
            return "PROVIDER_FAILURE", 70, "HIGH", "GENERAL_OPERATOR", False
        return "USER_REQUEST", 60, "NORMAL", "GENERAL_OPERATOR", False

    async def create(
        self,
        userdata: AloSMSessionData,
        *,
        reason: str,
        room_name: str | None = None,
    ) -> dict[str, object]:
        draft = userdata.booking_draft
        summary_parts = [f"Lý do: {reason}"]
        if draft.pickup:
            summary_parts.append(f"Điểm đón: {draft.pickup.display_name}")
        if draft.destination:
            summary_parts.append(f"Điểm đến: {draft.destination.display_name}")
        if draft.vehicle_type:
            summary_parts.append(f"Loại xe: {draft.vehicle_type}")
        if draft.quote:
            summary_parts.append(f"Báo giá: {draft.quote.fare_amount} {draft.quote.currency}")
        if userdata.last_failure:
            summary_parts.append(f"Lỗi gần nhất: {userdata.last_failure.code}")

        context_snapshot = {
            "schema_version": "1",
            "summary": draft.conversation_summary(),
            "booking_state": draft.public_state(),
            "last_failure": userdata.last_failure.model_dump(mode="json") if userdata.last_failure else None,
        }
        reason_code, priority, severity, queue, immediate = self._classify(reason)
        return await self._service.create_handoff_durable(
            {
                "session_id": userdata.app_session_id,
                "reason": reason[:100],
                "reason_code": reason_code,
                # Deliberately excludes raw transcript and account PII; the
                # revisioned booking snapshot keeps only the location context
                # the operator needs to continue the ride request.
                "summary": "; ".join(summary_parts),
                "pending_action": "CONTINUE_BOOKING",
                "priority": priority,
                "severity": severity,
                "queue": queue,
                "requires_immediate_transfer": immediate,
                "room_name": room_name,
                "context_snapshot": context_snapshot,
            }
        )
