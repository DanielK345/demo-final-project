"""Database-backed quote boundary for the LiveKit booking task."""

from __future__ import annotations

from typing import Protocol

from src.backend.services.pricing_service import PricingService
from src.backend.services.quote_service import QuoteService
from src.voice_agent.session_data import BookingDraft, QuoteSnapshot


class QuoteIssuer(Protocol):
    async def issue_quote(
        self,
        *,
        user_id: str,
        session_id: str,
        pickup_place_id: str,
        destination_place_id: str,
        vehicle_type: str,
    ) -> dict[str, object]: ...


class QuoteToolsService:
    """Adapt LiveKit's typed draft to the existing durable QuoteService."""

    def __init__(
        self,
        quote_service: QuoteIssuer | None = None,
        pricing_service: PricingService | None = None,
    ) -> None:
        self._quote_service = quote_service
        self._pricing_service = pricing_service or PricingService()

    def estimate(
        self,
        draft: BookingDraft | None = None,
        *,
        user_id: str | None = None,
        app_session_id: str | None = None,
        **kwargs: object,
    ) -> object:
        target_draft = draft or kwargs.get("draft")
        if not isinstance(target_draft, BookingDraft) or target_draft.pickup is None or target_draft.destination is None or target_draft.vehicle_type is None:
            raise ValueError("BOOKING_CONTEXT_INCOMPLETE")

        if self._quote_service is not None:
            async def _run() -> QuoteSnapshot:
                result = await self._quote_service.issue_quote(
                    user_id=user_id or "",
                    session_id=app_session_id or "",
                    pickup_place_id=target_draft.pickup.place_id,
                    destination_place_id=target_draft.destination.place_id,
                    vehicle_type=target_draft.vehicle_type,
                )
                return QuoteSnapshot(
                    quote_id=str(result.get("quote_id") or result["estimate_id"]),
                    pickup_place_id=target_draft.pickup.place_id,
                    destination_place_id=target_draft.destination.place_id,
                    vehicle_type=target_draft.vehicle_type,
                    fare_amount=int(result["fare_amount"]),
                    currency=str(result["currency"]),
                    distance_km=float(result["distance_km"]),
                    eta_minutes=int(result["eta_minutes"]),
                    expires_at=str(result["expires_at"]),
                    estimated=bool(result["estimated"]),
                )
            return _run()

        result = self._pricing_service.estimate_fare(
            pickup_place_id=target_draft.pickup.place_id,
            destination_place_id=target_draft.destination.place_id,
            vehicle_type=target_draft.vehicle_type,
        )
        return QuoteSnapshot(
            quote_id=str(result["estimate_id"]),
            pickup_place_id=target_draft.pickup.place_id,
            destination_place_id=target_draft.destination.place_id,
            vehicle_type=target_draft.vehicle_type,
            fare_amount=int(result["fare_amount"]),
            currency=str(result["currency"]),
            distance_km=float(result["distance_km"]),
            eta_minutes=int(result["eta_minutes"]),
            expires_at=str(result["expires_at"]),
            estimated=bool(result["estimated"]),
        )
