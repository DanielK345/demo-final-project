from __future__ import annotations

from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

SUPPORTED_VEHICLES = {"MOTORBIKE", "CAR_4", "CAR_7", "LUXURY"}
DEFAULT_PRICING_PATH = Path(__file__).resolve().parents[3] / "data" / "pricing" / "hanoi_demo_2026-08-16.yaml"


class DistanceTier(BaseModel):
    model_config = ConfigDict(extra="forbid")
    up_to_km: float | None = Field(default=None, gt=0)
    per_km: int = Field(ge=0)


class VehiclePricing(BaseModel):
    model_config = ConfigDict(extra="forbid")
    display_name: str = Field(min_length=1)
    capacity: int = Field(ge=1)
    luggage_capacity: int = Field(ge=0)
    source_ref: str = Field(min_length=1)
    base_fare: int = Field(ge=0)
    base_km: float = Field(gt=0)
    tiers: list[DistanceTier] = Field(min_length=1)
    per_minute: int = Field(ge=0)
    min_fare: int = Field(ge=0)
    surcharges: dict[str, int] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_tiers(self) -> VehiclePricing:
        bounded = [tier.up_to_km for tier in self.tiers if tier.up_to_km is not None]
        if any(tier.up_to_km is None for tier in self.tiers[:-1]):
            raise ValueError("only the final distance tier may be unbounded")
        if self.tiers[-1].up_to_km is not None:
            raise ValueError("final distance tier must be unbounded")
        if bounded != sorted(set(bounded)):
            raise ValueError("bounded distance tiers must be strictly increasing")
        if bounded and bounded[0] <= self.base_km:
            raise ValueError("first distance tier must end after base_km")
        if any(amount < 0 for amount in self.surcharges.values()):
            raise ValueError("surcharges cannot be negative")
        return self


class CancellationPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["DEMO"]
    free_cancel_before_accept: bool
    free_cancel_window_seconds: int = Field(ge=0)
    cancellation_fee_vnd: int = Field(ge=0)
    driver_arrived_fee_vnd: int = Field(ge=0)
    driver_no_show_refund_minutes: int = Field(ge=0)


class PricingCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["1.0.0"]
    version: str = Field(min_length=1)
    effective_from: date
    currency: Literal["VND"]
    region: str = Field(min_length=1)
    status: Literal["DEMO"]
    data_quality: Literal["DEMO"]
    owner: str = Field(min_length=1)
    approver: str = Field(min_length=1)
    source_type: Literal["PUBLIC_REFERENCE"]
    imported_from: str = Field(min_length=1)
    source_sha256: str = Field(pattern=r"^[A-F0-9]{64}$")
    source_urls: list[str] = Field(min_length=1)
    vehicles: dict[str, VehiclePricing]
    cancellation_policy: CancellationPolicy

    @model_validator(mode="after")
    def validate_vehicle_catalog(self) -> PricingCatalog:
        unknown = set(self.vehicles) - SUPPORTED_VEHICLES
        if unknown:
            raise ValueError(f"unsupported vehicle types: {sorted(unknown)}")
        missing = SUPPORTED_VEHICLES - set(self.vehicles)
        if missing:
            raise ValueError(f"missing vehicle types: {sorted(missing)}")
        return self


@lru_cache(maxsize=4)
def load_pricing_catalog(path: str | Path = DEFAULT_PRICING_PATH) -> PricingCatalog:
    catalog_path = Path(path)
    if not catalog_path.is_file():
        raise RuntimeError(f"pricing catalog not found: {catalog_path}")
    try:
        raw = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
        return PricingCatalog.model_validate(raw)
    except Exception as exc:
        raise RuntimeError(f"invalid pricing catalog {catalog_path}: {exc}") from exc
