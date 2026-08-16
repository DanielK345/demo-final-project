from pydantic import BaseModel, ConfigDict, Field


class QuoteRequestDTO(BaseModel):
    session_id: str = Field(min_length=1)
    pickup_place_id: str = Field(min_length=1)
    destination_place_id: str = Field(min_length=1)
    vehicle_type: str = Field(min_length=1)


class QuoteResponseDTO(BaseModel):
    model_config = ConfigDict(extra="allow")
    quote_id: str
    estimate_id: str
    fare_amount: int
    currency: str
    pricing_version: str
    pricing_status: str
    issued_at: str
    expires_at: str
    context_hash: str
    signature: str
    fare_breakdown: dict[str, object]
    route_snapshot: dict[str, object]
    pricing_snapshot: dict[str, object]
    promotion_snapshot: dict[str, object]
