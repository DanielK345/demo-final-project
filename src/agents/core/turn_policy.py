"""Deterministic checks that run before a user turn reaches the LLM."""

from hashlib import sha256
from unicodedata import category, normalize

from src.agents.contracts.schemas import ActionType, AgentAction, AgentInput, ToolName, ToolStatus, WorkflowType
from src.agents.contracts.state import AgentState, ConfirmationStatus
from src.agents.core.booking.actions import request_cancel_booking_action, request_create_booking_action
from src.agents.core.booking.messages import format_fare, passenger_confirmation, vehicle_label
from src.agents.core.booking.state import BookingData, BookingStep
from src.agents.core.handoff import HandoffReason, classify_handoff, deterministic_handoff_action
from src.agents.core.policy import AgentPolicy
from src.agents.tools.builders import CancelBookingTool, CreateBookingTool
from src.agents.tools.schemas import CancelBookingResult, CreateBookingResult

_AFFIRMATIONS = {
    "co",
    "co nhe",
    "co dung",
    "dung",
    "dung roi",
    "ok",
    "okay",
    "oke",
    "xac nhan",
    "toi xac nhan",
    "uh",
    "u",
    "ua",
    "vang",
    "duoc",
    "duoc nhe",
    "dat di",
    "dat xe",
    "dat xe di",
}
_NEGATIONS = {
    "khong",
    "khong dung",
    "chua",
    "thoi",
    "huy",
    "huy di",
    "huy chuyen",
    "khong dat",
    "khong dat nua",
}
_CONTINUE_BOOKING = {
    "khong huy",
    "khong huy chuyen",
    "khong huy dau",
    "dat xe",
    "dat xe di",
    "dat di",
    "tiep tuc",
    "tiep tuc dat",
    "van dat",
}


class TurnPolicy:
    def __init__(self, policy: AgentPolicy | None = None) -> None:
        self.policy = policy or AgentPolicy()

    def evaluate(self, agent_input: AgentInput, state: AgentState) -> AgentAction | None:
        replay = self._completed_side_effect_replay(agent_input, state)
        if replay is not None:
            return replay
        immediate_handoff = classify_handoff(agent_input.transcript)
        if immediate_handoff is not None and immediate_handoff is not HandoffReason.USER_REQUEST:
            return deterministic_handoff_action(
                state,
                reason_code=immediate_handoff,
                reason=f"Deterministic handoff trigger: {immediate_handoff.value}",
            )
        if agent_input.tool_result is not None:
            return None
        if state.pending_tool_name is not None:
            return AgentAction(
                action_type=ActionType.ASK_USER,
                message="Tôi đang chờ hệ thống xử lý yêu cầu trước. Bạn đợi tôi một chút nhé?",
                reason="A backend tool result is still pending.",
            )
        confirmation_action = self._pending_confirmation_action(agent_input, state)
        if confirmation_action is not None:
            return confirmation_action
        confidence = agent_input.stt_confidence
        if confidence is None or confidence >= self.policy.low_confidence_threshold:
            return None
        repeated = (
            state.last_stt_confidence is not None
            and state.last_stt_confidence < self.policy.low_confidence_threshold
        )
        if repeated:
            return deterministic_handoff_action(
                state,
                reason_code=HandoffReason.LOW_STT_CONFIDENCE,
                reason="Repeated low STT confidence requires human assistance.",
            )
        return AgentAction(
            action_type=ActionType.ASK_USER,
            message="Tôi chưa nghe rõ. Bạn vui lòng nói lại ngắn và chậm hơn nhé?",
            reason="Low STT confidence requires clarification before LLM processing.",
        )

    def _pending_confirmation_action(
        self,
        agent_input: AgentInput,
        state: AgentState,
    ) -> AgentAction | None:
        if state.confirmation is not ConfirmationStatus.AWAITING_CONFIRMATION:
            return None
        normalized = _normalize_vietnamese(agent_input.transcript)
        if not normalized:
            return None

        if state.current_step == BookingStep.CONFIRM.value:
            return self._booking_confirmation_action(normalized, state)
        if state.current_step == BookingStep.CONFIRM_CANCEL.value:
            return self._cancellation_confirmation_action(normalized, state)
        if state.current_step == "CONFIRM_ABANDON":
            return self._abandon_confirmation_action(normalized, state)
        return None

    @staticmethod
    def _booking_confirmation_action(normalized: str, state: AgentState) -> AgentAction | None:
        booking = _load_booking(state)
        if booking is None:
            return None
        if _matches(normalized, _AFFIRMATIONS):
            missing = _missing_booking_fields(booking)
            if missing:
                return AgentAction(
                    action_type=ActionType.ASK_USER,
                    message=f"Thông tin đặt xe còn thiếu: {', '.join(missing)}. Bạn bổ sung giúp tôi nhé?",
                    state_updates={"confirmation": ConfirmationStatus.NOT_REQUESTED, "current_step": None},
                    reason="Booking confirmation was received but required state is incomplete.",
                )
            key = sha256(f"{state.session_id}:create:{booking.fare_estimate_id}:{booking.phone_number}".encode()).hexdigest()
            return request_create_booking_action(state, booking, CreateBookingTool(), idempotency_key=key)
        if _matches(normalized, _NEGATIONS):
            return AgentAction(
                action_type=ActionType.ASK_USER,
                message="Bạn muốn sửa thông tin nào: điểm đón, điểm đến, loại xe hay số người?",
                state_updates={"confirmation": ConfirmationStatus.NOT_REQUESTED, "current_step": None},
                reason="User rejected the booking confirmation; collect the correction.",
            )
        return None

    @staticmethod
    def _cancellation_confirmation_action(normalized: str, state: AgentState) -> AgentAction | None:
        booking = _load_booking(state)
        if booking is None:
            return None
        if _matches(normalized, _AFFIRMATIONS):
            if not booking.booking_id:
                return AgentAction(
                    action_type=ActionType.ASK_USER,
                    message="Chưa có chuyến nào đã đặt để hủy. Bạn muốn tiếp tục đặt xe hiện tại không?",
                    state_updates={"confirmation": ConfirmationStatus.NOT_REQUESTED, "current_step": None},
                    reason="Cancellation was confirmed without a completed booking.",
                )
            key = sha256(f"{state.session_id}:cancel:{booking.booking_id}".encode()).hexdigest()
            return request_cancel_booking_action(state, booking, CancelBookingTool(), idempotency_key=key)
        if _matches(normalized, _NEGATIONS) or _matches(normalized, _CONTINUE_BOOKING):
            return _continue_booking_action(state, booking)
        return None

    @staticmethod
    def _abandon_confirmation_action(normalized: str, state: AgentState) -> AgentAction | None:
        booking = _load_booking(state)
        if booking is None:
            return None
        if _matches(normalized, _CONTINUE_BOOKING):
            return _continue_booking_action(state, booking)
        if _matches(normalized, _AFFIRMATIONS) or _matches(normalized, _NEGATIONS):
            collected = dict(state.collected_data)
            collected.pop("booking", None)
            return AgentAction(
                action_type=ActionType.RESPOND,
                message="Được, tôi đã dừng yêu cầu đặt xe này. Khi nào cần bạn cứ nói nhé.",
                state_updates={
                    "current_workflow": None,
                    "current_step": None,
                    "collected_data": collected,
                    "confirmation": ConfirmationStatus.NOT_REQUESTED,
                    "retry_count": 0,
                },
                reason="User confirmed abandoning the draft booking.",
            )
        return None

    @staticmethod
    def _completed_side_effect_replay(
        agent_input: AgentInput,
        state: AgentState,
    ) -> AgentAction | None:
        result = agent_input.tool_result
        if (
            result is None
            or state.pending_tool_name is not None
            or result.status is not ToolStatus.SUCCESS
        ):
            return None
        try:
            booking = BookingData.model_validate(state.collected_data.get("booking", {}))
            if (
                result.tool_name is ToolName.CREATE_BOOKING
                and result.call_id == booking.completed_booking_call_id
            ):
                payload = CreateBookingResult.model_validate(result.data)
                if payload.booking_id == booking.booking_id:
                    return AgentAction(
                        action_type=ActionType.RESPOND,
                        message="Chuyến xe này đã được đặt thành công trước đó.",
                        reason="A completed create_booking result was replayed.",
                    )
            if (
                result.tool_name is ToolName.CANCEL_BOOKING
                and result.call_id == booking.completed_cancellation_call_id
            ):
                payload = CancelBookingResult.model_validate(result.data)
                if payload.booking_id == booking.booking_id:
                    return AgentAction(
                        action_type=ActionType.RESPOND,
                        message="Chuyến xe này đã được hủy trước đó.",
                        reason="A completed cancel_booking result was replayed.",
                    )
        except ValueError:
            return None
        return None


def _continue_booking_action(state: AgentState, booking: BookingData) -> AgentAction:
    updates = {
        "current_workflow": WorkflowType.RIDE_BOOKING,
        "current_step": BookingStep.CONFIRM.value if not _missing_booking_fields(booking) else None,
        "confirmation": (
            ConfirmationStatus.AWAITING_CONFIRMATION
            if not _missing_booking_fields(booking)
            else ConfirmationStatus.NOT_REQUESTED
        ),
    }
    if _missing_booking_fields(booking):
        return AgentAction(
            action_type=ActionType.ASK_USER,
            message="Được, mình tiếp tục giữ yêu cầu đặt xe. Bạn bổ sung thông tin còn thiếu giúp mình nhé?",
            state_updates=updates,
            reason="User chose to keep the draft booking.",
        )
    return AgentAction(
        action_type=ActionType.ASK_USER,
        message=(
            f"Mình tiếp tục giữ yêu cầu này. Bạn xác nhận đặt xe đón tại {booking.pickup.display_name} "
            f"và đến {booking.destination.display_name}, loại {vehicle_label(booking)}, giá dự kiến "
            f"{format_fare(booking)}{passenger_confirmation(booking)}, đúng không?"
        ),
        state_updates=updates,
        reason="User chose to keep the draft; deterministic policy asks for booking confirmation again.",
    )


def _load_booking(state: AgentState) -> BookingData | None:
    try:
        return BookingData.model_validate(state.collected_data.get("booking", {}))
    except ValueError:
        return None


def _missing_booking_fields(data: BookingData) -> list[str]:
    fields = {
        "điểm đón": data.pickup,
        "điểm đến": data.destination,
        "loại xe": data.vehicle_type,
        "báo giá": data.fare_estimate_id,
        "số điện thoại": data.phone_number,
    }
    return [label for label, value in fields.items() if not value]


def _matches(text: str, phrases: set[str]) -> bool:
    return text in phrases


def _normalize_vietnamese(value: str) -> str:
    decomposed = normalize("NFD", value.strip().casefold()).replace("đ", "d")
    without_marks = "".join(ch for ch in decomposed if category(ch) != "Mn")
    return " ".join("".join(ch if ch.isalnum() or ch.isspace() else " " for ch in without_marks).split())
