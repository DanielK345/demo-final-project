"""Typed per-call business state for the LiveKit-native AloSM agent."""

from __future__ import annotations

import hashlib
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

BookingTarget = Literal["pickup", "destination"]
VehicleType = Literal["MOTORBIKE", "CAR_4", "CAR_7", "LUXURY"]
ConfirmationStatus = Literal["not_requested", "awaiting", "confirmed"]
FailureCode = Literal[
    "ASR_LOW_CONFIDENCE",
    "STT_UNAVAILABLE",
    "LLM_UNAVAILABLE",
    "TTS_UNAVAILABLE",
    "PLACE_NOT_FOUND",
    "QUOTE_UNAVAILABLE",
    "BOOKING_RESULT_UNKNOWN",
    "SESSION_RECOVERY_FAILED",
    "STATE_CONFLICT",
    "HANDOFF_REQUIRED",
]
FallbackAction = Literal["repeat_or_text", "retry", "handoff", "none"]
SessionLifecycle = Literal["active", "completed", "cancelled"]

_VEHICLE_SPOKEN_LABELS: dict[VehicleType, str] = {
    "MOTORBIKE": "xe máy",
    "CAR_4": "xe ô tô bốn chỗ",
    "CAR_7": "xe ô tô bảy chỗ",
    "LUXURY": "xe cao cấp",
}


def vehicle_spoken_label(vehicle_type: VehicleType | None) -> str | None:
    """Return a Vietnamese label suitable for TTS, never a domain enum."""

    return _VEHICLE_SPOKEN_LABELS.get(vehicle_type) if vehicle_type else None


class PlaceCandidate(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    place_id: str
    display_name: str
    address: str
    provider: str
    city: str | None = None


class QuoteSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    quote_id: str
    pickup_place_id: str
    destination_place_id: str
    vehicle_type: VehicleType
    fare_amount: int = Field(ge=0)
    currency: str = "VND"
    distance_km: float = Field(ge=0)
    eta_minutes: int = Field(ge=0)
    expires_at: str
    estimated: bool = True

    @property
    def fingerprint(self) -> str:
        raw = ":".join(
            (
                self.quote_id,
                self.pickup_place_id,
                self.destination_place_id,
                self.vehicle_type,
                str(self.fare_amount),
            )
        )
        return hashlib.sha256(raw.encode()).hexdigest()


class BookingResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    booking_id: str
    status: str
    estimated_fare: int = Field(ge=0)
    currency: str = "VND"
    eta_minutes: int = Field(ge=0)


class VoiceFailure(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: FailureCode
    message: str
    retryable: bool = True
    fallback_action: FallbackAction = "retry"


class HandoffState(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    handoff_id: str
    status: Literal["pending", "accepted", "resolved"] = "pending"
    reason_code: str


class BookingDraft(BaseModel):
    """Mutable draft with deterministic dependent-field invalidation."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    pickup_query: str | None = None
    pickup: PlaceCandidate | None = None
    pickup_candidates: list[PlaceCandidate] = Field(default_factory=list)
    destination_query: str | None = None
    destination: PlaceCandidate | None = None
    destination_candidates: list[PlaceCandidate] = Field(default_factory=list)
    vehicle_type: VehicleType | None = None
    quote: QuoteSnapshot | None = None
    confirmation_status: ConfirmationStatus = "not_requested"
    confirmation_fingerprint: str | None = None
    booking: BookingResult | None = None
    revision: int = 0

    def _invalidate_quote_and_confirmation(self) -> None:
        self.quote = None
        self.confirmation_status = "not_requested"
        self.confirmation_fingerprint = None
        self.booking = None

    def set_candidates(
        self,
        target: BookingTarget,
        query: str,
        candidates: list[PlaceCandidate],
    ) -> None:
        if target == "pickup":
            self.pickup_query = query
            self.pickup = None
            self.pickup_candidates = candidates
        else:
            self.destination_query = query
            self.destination = None
            self.destination_candidates = candidates
        self._invalidate_quote_and_confirmation()
        self.revision += 1

    def select_place(self, target: BookingTarget, place_id: str) -> PlaceCandidate:
        candidates = self.pickup_candidates if target == "pickup" else self.destination_candidates
        selected = next((candidate for candidate in candidates if candidate.place_id == place_id), None)
        if selected is None:
            raise ValueError("PLACE_CANDIDATE_NOT_IN_CURRENT_SEARCH")
        current = self.pickup if target == "pickup" else self.destination
        if current != selected:
            if target == "pickup":
                self.pickup = selected
            else:
                self.destination = selected
            self._invalidate_quote_and_confirmation()
            self.revision += 1
        return selected

    def set_vehicle_type(self, vehicle_type: VehicleType) -> None:
        if self.vehicle_type != vehicle_type:
            self.vehicle_type = vehicle_type
            self._invalidate_quote_and_confirmation()
            self.revision += 1

    def set_quote(self, quote: QuoteSnapshot) -> None:
        if self.pickup is None or self.destination is None or self.vehicle_type is None:
            raise ValueError("BOOKING_CONTEXT_INCOMPLETE")
        expected = (self.pickup.place_id, self.destination.place_id, self.vehicle_type)
        actual = (quote.pickup_place_id, quote.destination_place_id, quote.vehicle_type)
        if actual != expected:
            raise ValueError("QUOTE_CONTEXT_MISMATCH")
        self.quote = quote
        self.confirmation_status = "not_requested"
        self.confirmation_fingerprint = None
        self.booking = None
        self.revision += 1

    def request_confirmation(self) -> None:
        if self.quote is None:
            raise ValueError("QUOTE_REQUIRED_BEFORE_CONFIRMATION")
        self.confirmation_status = "awaiting"
        self.confirmation_fingerprint = self.quote.fingerprint
        self.revision += 1

    def confirm(self) -> None:
        if self.quote is None or self.confirmation_status != "awaiting":
            raise ValueError("BOOKING_NOT_AWAITING_CONFIRMATION")
        if self.confirmation_fingerprint != self.quote.fingerprint:
            raise ValueError("BOOKING_CONTEXT_CHANGED")
        self.confirmation_status = "confirmed"
        self.revision += 1

    def quote_or_raise(self) -> QuoteSnapshot:
        if self.quote is None:
            raise ValueError("QUOTE_REQUIRED")
        return self.quote

    def require_creatable(self) -> QuoteSnapshot:
        quote = self.quote_or_raise()
        if self.confirmation_status != "confirmed":
            raise ValueError("EXPLICIT_CONFIRMATION_REQUIRED")
        if self.confirmation_fingerprint != quote.fingerprint:
            raise ValueError("BOOKING_CONTEXT_CHANGED")
        return quote

    def set_booking(self, booking: BookingResult) -> None:
        self.require_creatable()
        if self.booking is not None and self.booking.booking_id != booking.booking_id:
            raise ValueError("BOOKING_ALREADY_CREATED")
        self.booking = booking
        self.revision += 1

    def public_state(self) -> dict[str, object]:
        return {
            "schema_version": "1",
            "revision": self.revision,
            "pickup": self.pickup.model_dump() if self.pickup else None,
            "destination": self.destination.model_dump() if self.destination else None,
            "vehicle_type": self.vehicle_type,
            "quote": self.quote.model_dump() if self.quote else None,
            "confirmation_status": self.confirmation_status,
            "booking": self.booking.model_dump() if self.booking else None,
        }

    def conversation_summary(self) -> str:
        """Return the minimum booking context needed by the conversational agent."""

        details: list[str] = []
        if self.pickup is not None:
            details.append(f"điểm đón {self.pickup.display_name}")
        elif self.pickup_query:
            details.append(f"điểm đón chưa xác nhận từ lời nói {self.pickup_query}")
        if self.destination is not None:
            details.append(f"điểm đến {self.destination.display_name}")
        elif self.destination_query:
            details.append(f"điểm đến chưa xác nhận từ lời nói {self.destination_query}")
        vehicle_label = vehicle_spoken_label(self.vehicle_type)
        if vehicle_label:
            details.append(f"loại xe {vehicle_label}")
        if self.booking is not None:
            details.append(f"đã tạo chuyến mã {self.booking.booking_id}")
        elif self.confirmation_status == "confirmed":
            details.append("khách đã xác nhận và đang chờ tạo chuyến")
        elif self.confirmation_status == "awaiting":
            details.append("đang chờ khách xác nhận đặt chuyến")
        elif self.quote is not None:
            details.append("đã có báo giá nhưng chưa yêu cầu xác nhận")

        return "; ".join(details) if details else "chưa có thông tin đặt xe"


class AloSMSessionData(BaseModel):
    """Business userdata owned by one LiveKit ``AgentSession``."""

    model_config = ConfigDict(extra="forbid")

    app_session_id: str
    call_id: str
    user_id: str
    participant_identity: str
    consent_granted: bool = True
    recording_enabled: bool = False
    booking_draft: BookingDraft = Field(default_factory=BookingDraft)
    last_asr_confidence: float | None = None
    handoff_requested: bool = False
    critical_confidence_threshold: float = Field(default=0.65, ge=0, le=1)
    persistence_revision: int = Field(default=0, ge=0)
    persistence_enabled: bool = True
    recovered: bool = False
    last_failure: VoiceFailure | None = None
    handoff: HandoffState | None = None
    lifecycle_status: SessionLifecycle = "active"

    def durable_state(self) -> dict[str, object]:
        """Return only resumable business state; never transcript or raw audio."""

        return {
            "schema_version": "1",
            "booking_draft": self.booking_draft.model_dump(mode="json"),
            "last_failure": (self.last_failure.model_dump(mode="json") if self.last_failure else None),
            "handoff": self.handoff.model_dump(mode="json") if self.handoff else None,
            "lifecycle_status": self.lifecycle_status,
        }

    def restore(self, state: dict[str, object], revision: int) -> None:
        if state.get("schema_version") != "1":
            raise ValueError("VOICE_STATE_SCHEMA_UNSUPPORTED")
        self.booking_draft = BookingDraft.model_validate(state.get("booking_draft") or {})
        self.last_failure = VoiceFailure.model_validate(state["last_failure"]) if state.get("last_failure") else None
        self.handoff = HandoffState.model_validate(state["handoff"]) if state.get("handoff") else None
        self.handoff_requested = self.handoff is not None
        lifecycle = state.get("lifecycle_status") or "active"
        if lifecycle not in {"active", "completed", "cancelled"}:
            raise ValueError("VOICE_SESSION_LIFECYCLE_UNSUPPORTED")
        self.lifecycle_status = lifecycle
        self.persistence_revision = revision
        self.recovered = True

    def record_failure(
        self,
        code: FailureCode,
        message: str,
        *,
        retryable: bool = True,
        fallback_action: FallbackAction = "retry",
    ) -> None:
        self.last_failure = VoiceFailure(
            code=code,
            message=message,
            retryable=retryable,
            fallback_action=fallback_action,
        )

    def clear_failure(self) -> None:
        self.last_failure = None

    def public_state(self) -> dict[str, object]:
        return {
            **self.booking_draft.public_state(),
            "failure": self.last_failure.model_dump(mode="json") if self.last_failure else None,
            "handoff": self.handoff.model_dump(mode="json") if self.handoff else None,
            "recovered": self.recovered,
        }
