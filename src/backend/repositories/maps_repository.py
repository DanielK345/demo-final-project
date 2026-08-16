"""Durable repository for resolved places and immutable route snapshots."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.backend.db.base import get_session_factory
from src.backend.db.models import Place as PlaceModel
from src.backend.db.models import RouteSnapshot as RouteSnapshotModel
from src.backend.maps.contracts import ResolvedPlace, RouteResult


class MapsRepository:
    """Short-lived transactions; safe to share through a singleton service."""

    def __init__(self, factory: async_sessionmaker[AsyncSession] | None = None) -> None:
        self._factory = factory or get_session_factory()

    async def create_place(self, place: ResolvedPlace) -> ResolvedPlace:
        async with self._factory() as db, db.begin():
            existing = (
                await db.execute(
                    select(PlaceModel).where(
                        PlaceModel.provider == place.provider,
                        PlaceModel.provider_place_id == place.provider_place_id,
                    )
                )
            ).scalar_one_or_none()
            if existing is not None:
                return self._to_resolved_place(existing)
            row = PlaceModel(
                id=place.place_id,
                provider=place.provider,
                provider_place_id=place.provider_place_id,
                display_name=place.display_name,
                formatted_address=place.formatted_address,
                latitude=place.latitude,
                longitude=place.longitude,
                types=place.types,
                serviceable=place.serviceable,
                service_area_id=place.service_area_id,
                source_version=place.source_version,
                resolved_at=place.resolved_at or datetime.now(UTC),
            )
            db.add(row)
            await db.flush()
            return self._to_resolved_place(row)

    async def get_place(self, place_id: str) -> ResolvedPlace | None:
        async with self._factory() as db:
            row = await db.get(PlaceModel, place_id)
            return self._to_resolved_place(row) if row is not None else None

    async def find_place_by_provider(self, provider: str, provider_place_id: str) -> ResolvedPlace | None:
        async with self._factory() as db:
            row = (
                await db.execute(
                    select(PlaceModel).where(
                        PlaceModel.provider == provider,
                        PlaceModel.provider_place_id == provider_place_id,
                    )
                )
            ).scalar_one_or_none()
            return self._to_resolved_place(row) if row is not None else None

    @staticmethod
    def _to_resolved_place(row: PlaceModel) -> ResolvedPlace:
        return ResolvedPlace(
            place_id=row.id,
            provider=row.provider,
            provider_place_id=row.provider_place_id,
            display_name=row.display_name,
            formatted_address=row.formatted_address,
            latitude=float(row.latitude),
            longitude=float(row.longitude),
            types=row.types if isinstance(row.types, list) else [],
            serviceable=row.serviceable,
            service_area_id=row.service_area_id,
            source_version=row.source_version,
            resolved_at=row.resolved_at,
        )

    async def create_route_snapshot(self, route: RouteResult) -> dict[str, Any]:
        async with self._factory() as db, db.begin():
            existing = await db.get(RouteSnapshotModel, route.route_id)
            if existing is not None:
                return self._route_dict(existing)
            row = RouteSnapshotModel(
                id=route.route_id,
                pickup_place_id=route.pickup_place_id,
                destination_place_id=route.destination_place_id,
                distance_meters=route.distance_meters,
                duration_seconds=route.duration_seconds,
                geometry=route.geometry,
                provider=route.provider,
                provider_version=route.provider_version,
                source_data_version=route.source_data_version or "",
                created_at=route.created_at or datetime.now(UTC),
            )
            db.add(row)
            await db.flush()
            return self._route_dict(row)

    async def get_route_snapshot(self, route_id: str) -> dict[str, Any] | None:
        async with self._factory() as db:
            row = await db.get(RouteSnapshotModel, route_id)
            return self._route_dict(row) if row is not None else None

    @staticmethod
    def _route_dict(row: RouteSnapshotModel) -> dict[str, Any]:
        return {
            "route_id": row.id,
            "pickup_place_id": row.pickup_place_id,
            "destination_place_id": row.destination_place_id,
            "distance_meters": float(row.distance_meters),
            "duration_seconds": float(row.duration_seconds),
            "geometry": row.geometry,
            "provider": row.provider,
            "provider_version": row.provider_version,
            "source_data_version": row.source_data_version,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "expires_at": row.expires_at.isoformat() if row.expires_at else None,
        }
