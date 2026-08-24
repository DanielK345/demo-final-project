from pydantic import ValidationError

from src.agents.contracts.schemas import AgentInput, WorkflowType
from src.agents.contracts.state import (
    AgentState,
    ConversationMessage,
    ConversationRole,
    DeliveryStatus,
)
from src.agents.core.booking import BookingData
from src.agents.core.guardrails import redact_pii
from src.agents.legacy.context_models import (
    BusinessContextField,
    CandidateField,
    ContextCandidate,
    ContextMessage,
    ContextSummary,
    ConversationContext,
)
from src.agents.legacy.workflows.faq_models import FAQData
from src.agents.legacy.workflows.trip_lookup_models import TripLookupData


class ContextError(ValueError):
    pass


class ContextSessionMismatchError(ContextError):
    pass


class ConversationContextBuilder:
    def __init__(self, *, max_context_characters: int = 6000) -> None:
        if max_context_characters < 1:
            raise ValueError("max_context_characters must be positive")
        self.max_context_characters = max_context_characters

    def build(
        self,
        agent_input: AgentInput,
        state: AgentState,
    ) -> ConversationContext:
        if agent_input.session_id != state.session_id:
            raise ContextSessionMismatchError("agent input and context state must belong to the same session")

        business_snapshot, available_candidates = _business_context(state)
        known_fields = [field.path for field in business_snapshot]
        recent_messages = _usable_messages(state.conversation_history)
        summary = _context_summary(state)

        (
            known_fields,
            business_snapshot,
            available_candidates,
            recent_messages,
            summary,
        ) = _fit_context_budget(
            known_fields=known_fields,
            business_snapshot=business_snapshot,
            available_candidates=available_candidates,
            recent_messages=recent_messages,
            summary=summary,
            character_budget=self.max_context_characters,
        )

        return ConversationContext(
            session_id=state.session_id,
            raw_transcript=agent_input.transcript,
            current_workflow=state.current_workflow,
            current_step=state.current_step,
            known_fields=known_fields,
            business_snapshot=business_snapshot,
            available_candidates=available_candidates,
            recent_messages=recent_messages,
            conversation_summary=summary,
            character_budget=self.max_context_characters,
        )


def _usable_messages(history: list[ConversationMessage]) -> list[ContextMessage]:
    messages: list[ContextMessage] = []
    for message in history:
        content: str | None = None
        if message.role is ConversationRole.USER:
            content = message.content
        elif message.role is ConversationRole.ASSISTANT:
            if message.delivery_status is DeliveryStatus.DELIVERED:
                content = message.spoken_content or message.content
            elif message.delivery_status is DeliveryStatus.INTERRUPTED:
                content = message.spoken_content

        sanitized = redact_pii(content) if content else None
        if not sanitized:
            continue
        messages.append(
            ContextMessage(
                message_id=message.message_id,
                turn_id=message.turn_id,
                role=message.role,
                content=sanitized,
                delivery_status=message.delivery_status,
            )
        )
    return messages


def _business_context(
    state: AgentState,
) -> tuple[list[BusinessContextField], list[ContextCandidate]]:
    if state.current_workflow is WorkflowType.RIDE_BOOKING:
        return _booking_context(state.collected_data.get("booking", {}))
    if state.current_workflow is WorkflowType.TRIP_LOOKUP:
        return _trip_lookup_context(state.collected_data.get("trip_lookup", {})), []
    if state.current_workflow is WorkflowType.FAQ:
        return _faq_context(state.collected_data.get("faq", {})), []
    return [], []


def _booking_context(value: object) -> tuple[list[BusinessContextField], list[ContextCandidate]]:
    try:
        data = BookingData.model_validate(value)
    except ValidationError:
        return [], []

    fields = _fields(
        {
            "booking.pickup_query": data.pickup_query,
            "booking.pickup": data.pickup.display_name if data.pickup else None,
            "booking.destination_query": data.destination_query,
            "booking.destination": data.destination.display_name if data.destination else None,
            "booking.phone_number": "[REDACTED_PHONE]" if data.phone_number else None,
            "booking.vehicle_type": data.vehicle_type,
            "booking.passenger_count": data.passenger_count,
            "booking.luggage_count": data.luggage_count,
            "booking.vehicle_preference": data.vehicle_preference,
            "booking.fare_estimate_id": data.fare_estimate_id,
            "booking.estimated_fare_amount": data.estimated_fare_amount,
            "booking.estimated_currency": data.estimated_currency,
            "booking.estimated_eta_minutes": data.estimated_eta_minutes,
            "booking.estimated_distance_km": data.estimated_distance_km,
            "booking.booking_id": "[REDACTED_BOOKING_ID]" if data.booking_id else None,
            "booking.booking_status": data.booking_status,
            "booking.eta_minutes": data.eta_minutes,
            "booking.fare_amount": data.fare_amount,
            "booking.currency": data.currency,
        }
    )
    candidates = [
        *_candidates(CandidateField.PICKUP, data.pickup_candidates),
        *_candidates(CandidateField.DESTINATION, data.destination_candidates),
        *[
            ContextCandidate(
                field=CandidateField.VEHICLE,
                index=index,
                display_name=option.display_name,
            )
            for index, option in enumerate(data.vehicle_options, start=1)
        ],
    ]
    return fields, candidates


def _trip_lookup_context(value: object) -> list[BusinessContextField]:
    try:
        data = TripLookupData.model_validate(value)
    except ValidationError:
        return []
    return _fields(
        {
            "trip_lookup.booking_id": "[REDACTED_BOOKING_ID]" if data.booking_id else None,
            "trip_lookup.phone_number": "[REDACTED_PHONE]" if data.phone_number else None,
            "trip_lookup.found_booking_id": ("[REDACTED_BOOKING_ID]" if data.found_booking_id else None),
            "trip_lookup.trip_status": data.trip_status,
            "trip_lookup.eta_minutes": data.eta_minutes,
        }
    )


def _faq_context(value: object) -> list[BusinessContextField]:
    try:
        data = FAQData.model_validate(value)
    except ValidationError:
        return []
    return _fields(
        {
            "faq.question": data.question,
            "faq.answer": data.answer,
        }
    )


def _fields(values: dict[str, object]) -> list[BusinessContextField]:
    result: list[BusinessContextField] = []
    for path, value in values.items():
        if value in (None, "", [], {}):
            continue
        sanitized = redact_pii(str(value)) or str(value)
        result.append(BusinessContextField(path=path, value=sanitized))
    return result


def _candidates(field: CandidateField, candidates: list) -> list[ContextCandidate]:
    return [
        ContextCandidate(
            field=field,
            index=index,
            display_name=redact_pii(candidate.display_name) or candidate.display_name,
            address=redact_pii(candidate.address) if candidate.address else None,
        )
        for index, candidate in enumerate(candidates, start=1)
    ]


def _context_summary(state: AgentState) -> ContextSummary | None:
    if state.conversation_summary is None:
        return None
    content = redact_pii(state.conversation_summary.content)
    if not content:
        return None
    return ContextSummary(
        content=content,
        summarized_through_turn_id=state.conversation_summary.summarized_through_turn_id,
        source_message_ids=list(state.conversation_summary.source_message_ids),
    )


def _fit_context_budget(
    *,
    known_fields: list[str],
    business_snapshot: list[BusinessContextField],
    available_candidates: list[ContextCandidate],
    recent_messages: list[ContextMessage],
    summary: ContextSummary | None,
    character_budget: int,
) -> tuple[
    list[str],
    list[BusinessContextField],
    list[ContextCandidate],
    list[ContextMessage],
    ContextSummary | None,
]:
    remaining = character_budget

    bounded_messages: list[ContextMessage] = []
    for message in reversed(recent_messages):
        content, remaining = _take_text(message.content, remaining)
        if not content:
            break
        bounded_messages.append(message.model_copy(update={"content": content}))
    bounded_messages.reverse()

    bounded_candidates: list[ContextCandidate] = []
    for candidate in available_candidates:
        fixed_cost = len(candidate.field.value)
        display_name, after_display = _take_text(candidate.display_name, remaining - fixed_cost)
        if not display_name:
            break
        address, after_address = _take_text(candidate.address, after_display)
        bounded_candidates.append(
            candidate.model_copy(
                update={"display_name": display_name, "address": address},
            )
        )
        remaining = after_address

    bounded_fields: list[BusinessContextField] = []
    for field in business_snapshot:
        value, after_value = _take_text(field.value, remaining - len(field.path))
        if not value:
            break
        bounded_fields.append(field.model_copy(update={"value": value}))
        remaining = after_value

    bounded_known_fields: list[str] = []
    for field in known_fields:
        if len(field) > remaining:
            break
        bounded_known_fields.append(field)
        remaining -= len(field)

    bounded_summary = None
    if summary is not None:
        content, remaining = _take_text(summary.content, remaining)
        if content:
            bounded_summary = summary.model_copy(update={"content": content})

    return (
        bounded_known_fields,
        bounded_fields,
        bounded_candidates,
        bounded_messages,
        bounded_summary,
    )


def _take_text(value: str | None, remaining: int) -> tuple[str | None, int]:
    if not value or remaining < 1:
        return None, max(remaining, 0)
    if len(value) <= remaining:
        return value, remaining - len(value)
    if remaining <= 3:
        return value[:remaining], 0
    return f"{value[: remaining - 3].rstrip()}...", 0
