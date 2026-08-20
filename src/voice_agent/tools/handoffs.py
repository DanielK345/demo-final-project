"""Application boundary for a native LiveKit handoff function tool."""

from __future__ import annotations

from typing import Protocol

from src.backend.services.handoff_service import HandoffService
from src.voice_agent.session_data import AloSMSessionData


class DurableHandoffService(Protocol):
    async def create_handoff_durable(self, payload: dict[str, object]) -> dict[str, object]: ...


class HandoffToolsService:
    def __init__(self, service: DurableHandoffService | None = None) -> None:
        self._service = service or HandoffService()

    async def create(self, userdata: AloSMSessionData, *, reason: str) -> dict[str, object]:
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

        return await self._service.create_handoff_durable(
            {
                "session_id": userdata.app_session_id,
                "reason": reason[:100],
                "reason_code": "LIVEKIT_VOICE_HANDOFF",
                # Deliberately excludes transcript, raw query, full address and PII.
                "summary": "; ".join(summary_parts),
                "pending_action": "CONTINUE_BOOKING",
                "priority": 60,
                "severity": "NORMAL",
                "queue": "GENERAL_OPERATOR",
                "requires_immediate_transfer": False,
            }
        )
