"""Contracts for the authenticated LiveKit token endpoint."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class LiveKitTokenRequestDTO(BaseModel):
    """Subset of LiveKit's standard TokenSource request we explicitly govern."""

    model_config = ConfigDict(extra="ignore")

    room_name: str | None = None
    participant_name: str | None = None
    participant_identity: str | None = None
    participant_metadata: str | None = None
    participant_attributes: dict[str, str] | None = None
    agent_name: str | None = None
    agent_metadata: str | None = None
    deployment: str | None = None


class LiveKitTokenResponseDTO(BaseModel):
    server_url: str
    participant_token: str


class LiveKitPrepareRequestDTO(BaseModel):
    call_instance_id: str


class LiveKitPrepareResponseDTO(LiveKitTokenResponseDTO):
    agent_prepared: bool


class LiveKitOperatorTokenRequestDTO(BaseModel):
    handoff_id: str


class LiveKitOperatorTokenResponseDTO(BaseModel):
    server_url: str
    participant_token: str
    handoff_id: str
    room_name: str
