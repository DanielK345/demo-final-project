from typing import Any

from pydantic import BaseModel, Field


class CreateCallDTO(BaseModel):
    customer_phone: str = Field(..., min_length=1, max_length=32)


class CallResponseDTO(BaseModel):
    call_id: str
    session_id: str
    status: str


class CallStreamEventDTO(BaseModel):
    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
