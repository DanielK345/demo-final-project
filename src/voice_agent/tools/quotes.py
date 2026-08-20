"""Deterministic quote application boundary for the LiveKit booking task."""

from __future__ import annotations

from src.backend.services.pricing_service import PricingService
from src.voice_agent.session_data import BookingDraft, QuoteSnapshot


class QuoteToolsService:
    def __init__(self, pricing_service: PricingService | None = None) -> None:
        self._pricing_service = pricing_service or PricingService()

    def estimate(self, draft: BookingDraft) -> QuoteSnapshot:
        if draft.pickup is None or draft.destination is None or draft.vehicle_type is None:
            raise ValueError("BOOKING_CONTEXT_INCOMPLETE")
        result = self._pricing_service.estimate_fare(
            pickup_place_id=draft.pickup.place_id,
            destination_place_id=draft.destination.place_id,
            vehicle_type=draft.vehicle_type,
        )
        return QuoteSnapshot(
            quote_id=str(result["estimate_id"]),
            pickup_place_id=draft.pickup.place_id,
            destination_place_id=draft.destination.place_id,
            vehicle_type=draft.vehicle_type,
            fare_amount=int(result["fare_amount"]),
            currency=str(result["currency"]),
            distance_km=float(result["distance_km"]),
            eta_minutes=int(result["eta_minutes"]),
            expires_at=str(result["expires_at"]),
            estimated=bool(result["estimated"]),
        )
