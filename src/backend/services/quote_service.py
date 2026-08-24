from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from src.backend.config import Settings, get_settings
from src.backend.repositories.maps_repository import MapsRepository
from src.backend.repositories.persistence_repository import PersistenceRepository
from src.backend.services.pricing_service import PricingService


class QuoteService:
    """Issues immutable fare quotes from persisted route snapshots."""

    def __init__(
        self,
        repository: PersistenceRepository | None = None,
        pricing: PricingService | None = None,
        settings: Settings | None = None,
        maps_repository: MapsRepository | None = None,
    ) -> None:
        self.repository = repository or PersistenceRepository()
        self.pricing = pricing or PricingService()
        self.settings = settings or get_settings()
        self.maps_repository = maps_repository or (MapsRepository() if self.settings.app_env != "test" else None)

    def _signing_key(self) -> bytes:
        key = self.settings.quote_signing_key
        if not key:
            if self.settings.app_env == "production":
                raise RuntimeError("QUOTE_SIGNING_KEY_REQUIRED")
            key = hashlib.sha256(f"{self.settings.app_name}:development-quote-key".encode()).hexdigest()
        return key.encode()

    @staticmethod
    def _canonical(payload: dict[str, Any]) -> str:
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)

    @staticmethod
    def _canonical_timestamp(value: object) -> str:
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")

    def _integrity(self, payload: dict[str, Any], quote_id: str, expires_at: object) -> tuple[str, str]:
        canonical_expiry = self._canonical_timestamp(expires_at)
        context_hash = hashlib.sha256(self._canonical({**payload, "expires_at": canonical_expiry}).encode()).hexdigest()
        signature = hmac.new(
            self._signing_key(), f"{quote_id}.{context_hash}.{canonical_expiry}".encode(), hashlib.sha256
        ).hexdigest()
        return context_hash, signature

    async def _load_route(
        self, route_id: str | None, pickup_place_id: str | None, destination_place_id: str | None, vehicle_type: str
    ) -> tuple[dict[str, Any], dict[str, object]]:
        if route_id and self.maps_repository is not None:
            route = await self.maps_repository.get_route_snapshot(route_id)
            if route is None:
                raise ValueError("ROUTE_SNAPSHOT_NOT_FOUND")
            expires_at = route.get("expires_at")
            if expires_at:
                expiry = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
                if expiry.tzinfo is None:
                    expiry = expiry.replace(tzinfo=UTC)
                if expiry <= datetime.now(UTC):
                    raise ValueError("ROUTE_SNAPSHOT_EXPIRED")
            draft = self.pricing.estimate_route_fare(
                route_id=route_id,
                distance_meters=float(route["distance_meters"]),
                duration_seconds=float(route["duration_seconds"]),
                vehicle_type=vehicle_type,
            )
            return route, draft
        if self.settings.app_env != "test" or not pickup_place_id or not destination_place_id:
            raise ValueError("PERSISTED_ROUTE_SNAPSHOT_REQUIRED")
        draft = self.pricing.estimate_fare(
            pickup_place_id=pickup_place_id, destination_place_id=destination_place_id, vehicle_type=vehicle_type
        )
        route = {
            "route_id": f"test_{draft['estimate_id']}",
            "pickup_place_id": pickup_place_id,
            "destination_place_id": destination_place_id,
            "distance_meters": round(float(draft["distance_km"]) * 1000),
            "duration_seconds": int(draft["eta_minutes"]) * 60,
            "provider": "TEST_DETERMINISTIC_ONLY",
            "provider_version": "test",
            "source_data_version": "test",
        }
        return route, draft

    async def issue_quote(
        self,
        *,
        user_id: str,
        session_id: str,
        vehicle_type: str,
        route_id: str | None = None,
        pickup_place_id: str | None = None,
        destination_place_id: str | None = None,
    ) -> dict[str, object]:
        route_snapshot, draft = await self._load_route(route_id, pickup_place_id, destination_place_id, vehicle_type)
        pickup_place_id = str(route_snapshot["pickup_place_id"])
        destination_place_id = str(route_snapshot["destination_place_id"])
        route_id = str(route_snapshot["route_id"])
        catalog_snapshot = self.pricing.catalog.model_dump(mode="json")
        catalog_row = await self.repository.ensure_pricing_catalog(catalog_snapshot)
        quote_id = f"quote_{uuid4().hex[:16]}"
        breakdown = dict(draft["fare_breakdown"])
        pricing_snapshot = {
            "pricing_version": draft["pricing_version"],
            "pricing_region": draft["pricing_region"],
            "pricing_status": draft["pricing_status"],
            "vehicle_type": vehicle_type,
            "rate_metadata": draft["rate_metadata"],
            "applied_surcharges": breakdown.get("applied_surcharges", []),
            "rounding_rule": "ROUND_TO_VND",
            "source_sha256": self.pricing.catalog.source_sha256,
            "data_quality": draft["data_quality"],
            "source_type": draft["source_type"],
        }
        promotion_snapshot = {
            "evaluated_vouchers": [],
            "selected_voucher_id": None,
            "selection_reason": "PROMOTION_PROVIDER_NOT_CONFIGURED",
            "discount_amount": 0,
            "promotion_version": None,
        }
        payload = {
            "user_id": user_id,
            "session_id": session_id,
            "pickup_place_id": pickup_place_id,
            "destination_place_id": destination_place_id,
            "vehicle_type": vehicle_type,
            "pricing_version": draft["pricing_version"],
            "total_amount": draft["fare_amount"],
            "currency": draft["currency"],
            "expires_at": draft["expires_at"],
            "route_snapshot": route_snapshot,
            "pricing_snapshot": pricing_snapshot,
            "promotion_snapshot": promotion_snapshot,
        }
        context_hash, signature = self._integrity(payload, quote_id, draft["expires_at"])
        issued_at = datetime.fromisoformat(str(draft["issued_at"]))
        expires_at = datetime.fromisoformat(str(draft["expires_at"]))
        stored = await self.repository.create_quote(
            {
                "id": quote_id,
                "user_id": user_id,
                "session_id": session_id,
                "pricing_catalog_id": catalog_row.id,
                "route_snapshot_id": route_id if self.maps_repository is not None else None,
                "pickup_place_id": pickup_place_id,
                "destination_place_id": destination_place_id,
                "vehicle_type": vehicle_type,
                "route_snapshot": route_snapshot,
                "pricing_snapshot": pricing_snapshot,
                "promotion_snapshot": promotion_snapshot,
                "base_fare": int(breakdown["base_fare"]),
                "distance_fare": int(breakdown["distance_fare"]),
                "time_fare": int(breakdown.get("time_fare", 0)),
                "surcharge_amount": int(breakdown.get("surcharge_amount", 0)),
                "discount_amount": 0,
                "total_amount": int(draft["fare_amount"]),
                "currency": str(draft["currency"]),
                "context_hash": context_hash,
                "signature": signature,
                "status": "ISSUED",
                "issued_at": issued_at,
                "expires_at": expires_at,
            }
        )
        stored.update(
            {
                "pricing_version": draft["pricing_version"],
                "pricing_region": draft["pricing_region"],
                "pricing_status": draft["pricing_status"],
                "eta_minutes": draft["eta_minutes"],
                "distance_km": draft["distance_km"],
                "estimated": True,
                "data_quality": draft["data_quality"],
                "source_type": draft["source_type"],
            }
        )
        return stored

    async def vehicle_options(
        self,
        *,
        user_id: str,
        session_id: str,
        passenger_count: int,
        luggage_count: int | None = None,
        route_id: str | None = None,
        pickup_place_id: str | None = None,
        destination_place_id: str | None = None,
    ) -> list[dict[str, object]]:
        if route_id and self.maps_repository is not None:
            route = await self.maps_repository.get_route_snapshot(route_id)
            if route is None:
                raise ValueError("ROUTE_SNAPSHOT_NOT_FOUND")
            drafts = self.pricing.vehicle_options_for_route(
                route_id=route_id,
                distance_meters=float(route["distance_meters"]),
                duration_seconds=float(route["duration_seconds"]),
                passenger_count=passenger_count,
                luggage_count=luggage_count,
            )
        else:
            if self.settings.app_env != "test" or not pickup_place_id or not destination_place_id:
                raise ValueError("PERSISTED_ROUTE_SNAPSHOT_REQUIRED")
            drafts = self.pricing.vehicle_options(
                pickup_place_id=pickup_place_id,
                destination_place_id=destination_place_id,
                passenger_count=passenger_count,
                luggage_count=luggage_count,
            )
        options = []
        for draft in drafts:
            quote = await self.issue_quote(
                user_id=user_id,
                session_id=session_id,
                route_id=route_id,
                pickup_place_id=pickup_place_id,
                destination_place_id=destination_place_id,
                vehicle_type=str(draft["vehicle_type"]),
            )
            quote.update(
                {
                    key: draft[key]
                    for key in (
                        "option_id",
                        "display_name",
                        "capacity",
                        "luggage_capacity",
                        "available",
                        "vehicle_type",
                    )
                }
            )
            options.append(quote)
        return options

    async def verify_quote(self, quote: dict[str, Any]) -> None:
        payload = {
            "user_id": quote["user_id"],
            "session_id": quote["session_id"],
            "pickup_place_id": quote["pickup_place_id"],
            "destination_place_id": quote["destination_place_id"],
            "vehicle_type": quote["vehicle_type"],
            "pricing_version": quote["pricing_snapshot"]["pricing_version"],
            "total_amount": quote["fare_amount"],
            "currency": quote["currency"],
            "expires_at": quote["expires_at"],
            "route_snapshot": quote["route_snapshot"],
            "pricing_snapshot": quote["pricing_snapshot"],
            "promotion_snapshot": quote["promotion_snapshot"],
        }
        context_hash, signature = self._integrity(payload, str(quote["quote_id"]), quote["expires_at"])
        if not hmac.compare_digest(context_hash, str(quote["context_hash"])) or not hmac.compare_digest(
            signature, str(quote["signature"])
        ):
            raise ValueError("QUOTE_INTEGRITY_INVALID")
