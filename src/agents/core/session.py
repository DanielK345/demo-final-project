from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field

from src.agents.contracts.state import AgentState
from src.agents.core.booking.state import BookingData
from src.agents.tools.schemas import TripMatch


class TripLookupState(BaseModel):
    booking_id: str | None = None
    phone_number: str | None = None
    candidates: list[TripMatch] = Field(default_factory=list)
    selected_booking_id: str | None = None
    status: str | None = None
    eta_minutes: int | None = None
    completed_call_id: str | None = None


class FAQState(BaseModel):
    question: str | None = None
    answer: str | None = None
    sources: list[str] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)


class HandoffState(BaseModel):
    reason_code: str = "UNABLE_TO_CONTINUE"
    reason: str
    priority: int = Field(default=50, ge=0, le=100)
    severity: str = "NORMAL"
    queue: str = "GENERAL_OPERATOR"
    source_workflow: str | None = None
    summary: str
    pending_tool: str | None = None
    requires_immediate_transfer: bool = False


@dataclass
class TurnSession:
    """Mutable working projection for one model/tool loop only."""

    state: AgentState
    booking: BookingData
    trip: TripLookupState
    faq: FAQState
    updates: dict[str, Any] = field(default_factory=dict)
    event: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, state: AgentState, *, event: dict[str, Any]) -> "TurnSession":
        return cls(
            state=state,
            booking=BookingData.model_validate(state.collected_data.get("booking", {})),
            trip=TripLookupState.model_validate(state.collected_data.get("trip_lookup", {})),
            faq=FAQState.model_validate(state.collected_data.get("faq", {})),
            event=event,
        )

    def persist(self, *names: str) -> None:
        collected = dict(self.updates.get("collected_data", self.state.collected_data))
        for name in names:
            value = getattr(self, name)
            collected[name if name != "trip" else "trip_lookup"] = value.model_dump(mode="json")
        self.updates["collected_data"] = collected

    def working_state(self) -> AgentState:
        values = self.state.model_dump()
        values.update(self.updates)
        return AgentState.model_validate(values)

    def public_context(self) -> dict[str, Any]:
        booking = self.booking.model_dump(mode="json")
        if booking.get("phone_number"):
            booking["phone_number"] = "đã có và hợp lệ"
        return {
            "event": self.event,
            "state": {
                "active_capability": (
                    self.updates.get("current_workflow", self.state.current_workflow)
                ),
                "confirmation": self.updates.get("confirmation", self.state.confirmation),
                "booking": booking,
                "trip_lookup": self.trip.model_dump(mode="json"),
                "faq": self.faq.model_dump(mode="json"),
            },
            "conversation_history": [
                {"role": item.role.value, "content": item.content}
                for item in self.state.conversation_history[-8:]
            ],
        }
