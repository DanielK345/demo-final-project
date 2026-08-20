"""Idempotent deterministic booking boundary for the Phase-2 demo."""

from __future__ import annotations

import hashlib

from src.voice_agent.session_data import BookingDraft, BookingResult


class BookingToolsService:
    """Create stable demo outcomes without pretending to call a real fleet backend."""

    def create(self, *, app_session_id: str, draft: BookingDraft) -> BookingResult:
        quote = draft.require_creatable()
        idempotency_key = f"{app_session_id}:create_booking:{quote.fingerprint}"
        booking_id = f"demo_{hashlib.sha256(idempotency_key.encode()).hexdigest()[:12]}"
        return BookingResult(
            booking_id=booking_id,
            status="DEMO_SEARCHING_DRIVER",
            estimated_fare=quote.fare_amount,
            currency=quote.currency,
            eta_minutes=quote.eta_minutes,
        )
