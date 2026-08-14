import pytest

from src.agents.context import (
    CandidateField,
    ContextSessionMismatchError,
    ConversationContextBuilder,
)
from src.agents.history import build_message_id
from src.agents.schemas import AgentInput, WorkflowType
from src.agents.state import (
    AgentState,
    ConversationMessage,
    ConversationMessageType,
    ConversationRole,
    ConversationSummary,
    DeliveryStatus,
)
from src.agents.tools.schemas import PlaceCandidate
from src.agents.workflows.booking_models import BookingData


def context_input(
    *,
    session_id: str = "session-001",
    transcript: str = "Cái thứ hai",
) -> AgentInput:
    return AgentInput(
        session_id=session_id,
        turn_id="turn-current",
        transcript=transcript,
    )


def user_message(turn_id: str, content: str) -> ConversationMessage:
    return ConversationMessage(
        message_id=build_message_id(turn_id, ConversationRole.USER),
        turn_id=turn_id,
        role=ConversationRole.USER,
        message_type=ConversationMessageType.USER_TRANSCRIPT,
        content=content,
        delivery_status=DeliveryStatus.FINAL,
    )


def assistant_message(
    turn_id: str,
    content: str,
    status: DeliveryStatus,
    *,
    spoken_content: str | None = None,
) -> ConversationMessage:
    return ConversationMessage(
        message_id=build_message_id(turn_id, ConversationRole.ASSISTANT),
        turn_id=turn_id,
        role=ConversationRole.ASSISTANT,
        message_type=ConversationMessageType.ASSISTANT_SPEECH,
        content=content,
        delivery_status=status,
        spoken_content=spoken_content,
    )


def tool_summary(turn_id: str, content: str) -> ConversationMessage:
    return ConversationMessage(
        message_id=build_message_id(turn_id, ConversationRole.TOOL, sequence=1),
        turn_id=turn_id,
        role=ConversationRole.TOOL,
        message_type=ConversationMessageType.TOOL_SUMMARY,
        content=content,
        delivery_status=DeliveryStatus.FINAL,
    )


def test_context_uses_only_user_and_audible_assistant_messages():
    history = [
        user_message("turn-001", "Tôi muốn đặt xe"),
        assistant_message(
            "turn-001",
            "Bạn muốn đón ở đâu?",
            DeliveryStatus.DELIVERED,
            spoken_content="Bạn muốn đón ở đâu?",
        ),
        assistant_message(
            "turn-002",
            "Câu này chưa được phát",
            DeliveryStatus.PENDING,
        ),
        assistant_message(
            "turn-003",
            "Tôi tìm thấy hai địa điểm. Bạn chọn địa điểm nào?",
            DeliveryStatus.INTERRUPTED,
            spoken_content="Tôi tìm thấy hai địa điểm.",
        ),
        assistant_message(
            "turn-004",
            "TTS thất bại",
            DeliveryStatus.FAILED,
        ),
        tool_summary("turn-005", "search_place returned SUCCESS."),
    ]

    context = ConversationContextBuilder().build(
        context_input(),
        AgentState(session_id="session-001", conversation_history=history),
    )

    assert [message.turn_id for message in context.recent_messages] == [
        "turn-001",
        "turn-001",
        "turn-003",
    ]
    assert context.recent_messages[-1].content == "Tôi tìm thấy hai địa điểm."
    assert context.last_assistant_message == context.recent_messages[-1]
    assert all(message.role is not ConversationRole.TOOL for message in context.recent_messages)


def test_context_excludes_arbitrary_data_and_masks_sensitive_values():
    booking = BookingData(
        pickup_query="Hồ Gươm",
        phone_number="0901234567",
        booking_id="BOOKING-SECRET",
    )
    state = AgentState(
        session_id="session-001",
        current_workflow=WorkflowType.RIDE_BOOKING,
        current_step="COLLECT_DESTINATION",
        collected_data={
            "booking": booking.model_dump(mode="json"),
            "raw_tool_payload": {"provider_token": "provider-secret"},
            "handoff_context": {"error": "internal-provider-error"},
        },
        conversation_history=[
            user_message("turn-001", "Số của tôi là 0901234567"),
        ],
        conversation_summary=ConversationSummary(
            content="Khách 0901234567 đang đặt xe từ một địa chỉ cũ.",
            summarized_through_turn_id="turn-001",
            source_message_ids=["turn-001:user"],
        ),
    )

    context = ConversationContextBuilder().build(context_input(), state)
    serialized = context.model_dump_json()

    assert context.raw_transcript == "Cái thứ hai"
    assert "0901234567" not in serialized
    assert "BOOKING-SECRET" not in serialized
    assert "provider-secret" not in serialized
    assert "internal-provider-error" not in serialized
    assert "[REDACTED_PHONE]" in serialized
    assert "[REDACTED_BOOKING_ID]" in serialized


def test_booking_context_includes_vehicle_and_current_fare_estimate():
    booking = BookingData.model_validate(
        {
            "vehicle_type": "CAR_7",
            "fare_estimate_id": "fare-001",
            "estimated_fare_amount": 105000,
            "estimated_currency": "VND",
            "estimated_eta_minutes": 8,
            "estimated_distance_km": 15.5,
        }
    )
    state = AgentState(
        session_id="session-001",
        current_workflow=WorkflowType.RIDE_BOOKING,
        current_step="COLLECT_PHONE",
        collected_data={"booking": booking.model_dump(mode="json")},
    )

    context = ConversationContextBuilder().build(context_input(), state)
    snapshot = {field.path: field.value for field in context.business_snapshot}

    assert snapshot["booking.vehicle_type"] == "CAR_7"
    assert snapshot["booking.fare_estimate_id"] == "fare-001"
    assert snapshot["booking.estimated_fare_amount"] == "105000.0"


def test_context_exposes_typed_booking_candidates_without_extra_payload():
    booking = BookingData(
        pickup_candidates=[
            PlaceCandidate(
                place_id="place-1",
                display_name="Hồ Gươm",
                address="Hoàn Kiếm",
                provider_payload="must-not-leak",
            ),
            PlaceCandidate(
                place_id="place-2",
                display_name="Phố đi bộ Hồ Gươm",
                address="Đinh Tiên Hoàng",
            ),
        ],
        destination_candidates=[
            PlaceCandidate(
                place_id="place-3",
                display_name="Times City",
            )
        ],
    )
    state = AgentState(
        session_id="session-001",
        current_workflow=WorkflowType.RIDE_BOOKING,
        current_step="SELECT_PICKUP_CANDIDATE",
        collected_data={"booking": booking.model_dump(mode="json")},
    )

    context = ConversationContextBuilder().build(context_input(), state)

    assert [(candidate.field, candidate.index) for candidate in context.available_candidates] == [
        (CandidateField.PICKUP, 1),
        (CandidateField.PICKUP, 2),
        (CandidateField.DESTINATION, 1),
    ]
    assert context.available_candidates[1].display_name == "Phố đi bộ Hồ Gươm"
    assert "place-1" not in context.model_dump_json()
    assert "must-not-leak" not in context.model_dump_json()


def test_business_snapshot_stays_separate_from_untrusted_summary():
    booking = BookingData(pickup_query="Hồ Gươm")
    state = AgentState(
        session_id="session-001",
        current_workflow=WorkflowType.RIDE_BOOKING,
        current_step="COLLECT_DESTINATION",
        collected_data={"booking": booking.model_dump(mode="json")},
        conversation_summary=ConversationSummary(
            content="Điểm đón là Times City.",
            summarized_through_turn_id="turn-001",
            source_message_ids=["turn-001:user"],
        ),
    )

    context = ConversationContextBuilder().build(context_input(), state)

    snapshot = {field.path: field.value for field in context.business_snapshot}
    assert snapshot["booking.pickup_query"] == "Hồ Gươm"
    assert context.conversation_summary is not None
    assert context.conversation_summary.content == "Điểm đón là Times City."


def test_context_budget_keeps_latest_messages_and_bounds_supplementary_text():
    history = [user_message(f"turn-{index:03d}", f"message-{index}-" + "x" * 40) for index in range(6)]
    context = ConversationContextBuilder(max_context_characters=70).build(
        context_input(transcript="raw-" + "z" * 200),
        AgentState(session_id="session-001", conversation_history=history),
    )

    assert context.context_character_count <= context.character_budget
    assert context.recent_messages[-1].turn_id == "turn-005"
    assert context.raw_transcript == "raw-" + "z" * 200


def test_context_rejects_state_from_another_session():
    with pytest.raises(ContextSessionMismatchError, match="same session"):
        ConversationContextBuilder().build(
            context_input(session_id="session-001"),
            AgentState(session_id="session-002"),
        )


def test_context_ignores_invalid_or_inactive_business_namespaces():
    context = ConversationContextBuilder().build(
        context_input(),
        AgentState(
            session_id="session-001",
            current_workflow=WorkflowType.RIDE_BOOKING,
            current_step="COLLECT_PICKUP",
            collected_data={
                "booking": {"eta_minutes": -1},
                "trip_lookup": {"trip_status": "ACTIVE"},
            },
        ),
    )

    assert context.business_snapshot == []
    assert context.available_candidates == []
    assert context.known_fields == []
