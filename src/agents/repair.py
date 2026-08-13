import re
from collections.abc import Iterable, Mapping

from src.agents.repair_models import DialogueAct, DialogueActResult
from src.agents.schemas import ActionType, AgentAction, AgentInput, ToolName, WorkflowType
from src.agents.state import (
    AgentState,
    ConfirmationStatus,
    ConversationMessageType,
    ConversationRole,
    DeliveryStatus,
)
from src.agents.state_types import InterruptedWorkflow, InterruptionReason
from src.agents.tools.lifecycle import clear_pending_tool_updates
from src.agents.understanding.models import CorrectionField
from src.agents.workflows.booking_models import BookingData, BookingStep
from src.agents.workflows.trip_lookup_models import TripLookupStep

_START_OVER_PATTERNS = (
    re.compile(r"\b(?:làm|bắt đầu|đặt)\s+lại\s+(?:từ\s+)?đầu\b", re.IGNORECASE),
    re.compile(r"\bkhởi động lại(?:\s+quy trình)?\b", re.IGNORECASE),
)
_REPEAT_PATTERNS = (
    re.compile(r"\b(?:nói|đọc|nhắc)\s+lại\b", re.IGNORECASE),
    re.compile(r"\b(?:bạn|anh|chị)\s+vừa\s+nói\s+gì\b", re.IGNORECASE),
)
_CANCEL_PATTERNS = (
    re.compile(r"\b(?:hủy|huỷ|bỏ)\s+(?:yêu\s+cầu|đặt\s+xe|chuyến|việc\s+đặt\s+xe)\b", re.IGNORECASE),
    re.compile(r"\b(?:thôi\s+)?(?:tôi\s+)?không\s+(?:cần|đặt)\s+(?:xe\s+)?nữa\b", re.IGNORECASE),
)
_GOODBYE_PATTERNS = (re.compile(r"\b(?:tạm biệt|chào nhé|kết thúc cuộc gọi|dừng cuộc gọi)\b", re.IGNORECASE),)
_PAUSE_PATTERNS = (re.compile(r"\b(?:tạm dừng|khoan đã|đợi đã|chờ một chút)\b", re.IGNORECASE),)
_RESUME_PATTERNS = (
    re.compile(r"\b(?:tiếp tục|quay lại)(?:\s+(?:việc\s+)?(?:đặt xe|tra cứu chuyến|hỏi đáp))?\b", re.IGNORECASE),
)
_HELP_PATTERNS = (re.compile(r"\b(?:tôi cần trợ giúp|hướng dẫn cho tôi|bạn giúp được gì)\b", re.IGNORECASE),)
_CORRECTION_PATTERNS = (
    (
        CorrectionField.PICKUP,
        re.compile(r"\b(?:đổi|sửa|thay)\s+(?:lại\s+)?(?:điểm\s+)?đón\b", re.IGNORECASE),
    ),
    (
        CorrectionField.DESTINATION,
        re.compile(r"\b(?:đổi|sửa|thay)\s+(?:lại\s+)?(?:điểm\s+)?(?:đến|đích)\b", re.IGNORECASE),
    ),
    (
        CorrectionField.PHONE_NUMBER,
        re.compile(
            r"\b(?:(?:đổi|sửa|thay)\s+(?:lại\s+)?(?:số\s+)?điện\s+thoại|"
            r"(?:số\s+)?điện\s+thoại\s+(?:đúng\s+)?là)\b",
            re.IGNORECASE,
        ),
    ),
    (
        None,
        re.compile(r"\b(?:tôi\s+muốn\s+)?sửa\s+(?:lại\s+)?thông\s+tin\b", re.IGNORECASE),
    ),
)
_CHANGE_INTENT_PATTERN = re.compile(
    r"\b(?:chuyển|đổi)\s+sang\s+"
    r"(?P<target>đặt\s+xe|tra\s+cứu(?:\s+chuyến)?|hỏi\s+đáp|faq)\b",
    re.IGNORECASE,
)

_EXACT_CANCEL_COMMANDS = {"hủy", "huỷ", "bỏ đi"}
_WORKFLOW_TARGETS = {
    "đặt xe": WorkflowType.RIDE_BOOKING,
    "tra cứu": WorkflowType.TRIP_LOOKUP,
    "tra cứu chuyến": WorkflowType.TRIP_LOOKUP,
    "hỏi đáp": WorkflowType.FAQ,
    "faq": WorkflowType.FAQ,
}
_WORKFLOW_NAMESPACES = {
    WorkflowType.RIDE_BOOKING: "booking",
    WorkflowType.TRIP_LOOKUP: "trip_lookup",
    WorkflowType.FAQ: "faq",
    WorkflowType.HUMAN_HANDOFF: "handoff_context",
}
_SIDE_EFFECT_TOOLS = {ToolName.CREATE_BOOKING, ToolName.CREATE_HANDOFF}
_START_OVER_PROMPTS = {
    WorkflowType.RIDE_BOOKING: (
        "COLLECT_PICKUP",
        "Bạn muốn đón ở đâu?",
    ),
    WorkflowType.TRIP_LOOKUP: (
        "COLLECT_IDENTIFIER",
        "Bạn vui lòng cung cấp mã chuyến hoặc số điện thoại đặt xe.",
    ),
    WorkflowType.FAQ: (
        None,
        "Bạn muốn hỏi thông tin gì về dịch vụ?",
    ),
}


class DialogueActDetector:
    """Recognize explicit conversation commands without changing state."""

    def detect(self, transcript: str) -> DialogueActResult:
        normalized = " ".join(transcript.casefold().split())
        if not normalized:
            return DialogueActResult()

        match = _first_match(_START_OVER_PATTERNS, transcript)
        if match:
            return _recognized(DialogueAct.START_OVER, match)

        match = _first_match(_REPEAT_PATTERNS, transcript)
        if match:
            return _recognized(DialogueAct.REPEAT, match)

        if normalized.strip(" .!?") in _EXACT_CANCEL_COMMANDS:
            return _recognized(DialogueAct.CANCEL, transcript.strip())
        match = _first_match(_CANCEL_PATTERNS, transcript)
        if match:
            return _recognized(DialogueAct.CANCEL, match)

        match = _first_match(_GOODBYE_PATTERNS, transcript)
        if match:
            return _recognized(DialogueAct.GOODBYE, match)

        match = _first_match(_PAUSE_PATTERNS, transcript)
        if match:
            return _recognized(DialogueAct.PAUSE, match)

        match = _first_match(_RESUME_PATTERNS, transcript)
        if match:
            return _recognized(
                DialogueAct.RESUME,
                match,
                target_workflow=_workflow_from_text(match),
            )

        for correction_field, pattern in _CORRECTION_PATTERNS:
            correction_match = pattern.search(transcript)
            if correction_match:
                return _recognized(
                    DialogueAct.CORRECT,
                    correction_match.group(),
                    correction_field=correction_field,
                )

        change_match = _CHANGE_INTENT_PATTERN.search(transcript)
        if change_match:
            target = " ".join(change_match.group("target").casefold().split())
            return _recognized(
                DialogueAct.CHANGE_INTENT,
                change_match.group(),
                target_workflow=_WORKFLOW_TARGETS[target],
            )

        match = _first_match(_HELP_PATTERNS, transcript)
        if match:
            return _recognized(DialogueAct.HELP, match)

        return DialogueActResult()


class ConversationRepairHandler:
    """Build repair actions without mutating state or executing side effects."""

    _HANDLED_ACTS = {
        DialogueAct.REPEAT,
        DialogueAct.CORRECT,
        DialogueAct.CANCEL,
        DialogueAct.START_OVER,
        DialogueAct.HELP,
        DialogueAct.CHANGE_INTENT,
        DialogueAct.PAUSE,
        DialogueAct.RESUME,
        DialogueAct.GOODBYE,
    }

    def handle(
        self,
        command: DialogueActResult,
        agent_input: AgentInput,
        state: AgentState,
    ) -> AgentAction | None:
        if agent_input.session_id != state.session_id:
            raise ValueError("agent input and repair state must belong to the same session")
        if command.act not in self._HANDLED_ACTS:
            return None
        if command.act is DialogueAct.REPEAT:
            return self._repeat(state)
        if command.act in {
            DialogueAct.CORRECT,
            DialogueAct.CANCEL,
            DialogueAct.START_OVER,
            DialogueAct.CHANGE_INTENT,
            DialogueAct.PAUSE,
            DialogueAct.GOODBYE,
        } and _requires_reconciliation(state):
            return _reconciliation_action(command.act)
        if command.act is DialogueAct.CORRECT:
            return self._correction(state)
        if command.act is DialogueAct.CANCEL:
            return self._cancel(agent_input, state)
        if command.act is DialogueAct.START_OVER:
            return self._start_over(state)
        if command.act is DialogueAct.HELP:
            return self._help(state)
        if command.act is DialogueAct.CHANGE_INTENT:
            return self._change_intent(command, state)
        if command.act is DialogueAct.PAUSE:
            return self._pause(state)
        if command.act is DialogueAct.RESUME:
            return self._resume(command, state)
        return self._goodbye(state)

    @staticmethod
    def prepare_faq_interruption(
        state: AgentState,
    ) -> InterruptedWorkflow | None:
        if (
            state.current_workflow
            not in {WorkflowType.RIDE_BOOKING, WorkflowType.TRIP_LOOKUP}
            or state.current_step is None
            or state.pending_tool_name is not None
            or state.interrupted_workflow is not None
        ):
            return None
        try:
            return _snapshot_workflow(state, InterruptionReason.FAQ)
        except ValueError:
            return None

    @staticmethod
    def faq_resume_invitation(state: AgentState) -> str | None:
        frame = state.interrupted_workflow
        if frame is None:
            return None
        return f"Bạn có muốn tiếp tục {_workflow_label(frame.workflow)} đang dở không?"

    @staticmethod
    def nested_interruption_action() -> AgentAction:
        return _nested_interruption_action()

    @staticmethod
    def _correction(state: AgentState) -> AgentAction | None:
        if state.current_workflow is WorkflowType.RIDE_BOOKING:
            return None
        return AgentAction(
            action_type=ActionType.ASK_USER,
            message=(
                "Hiện không có yêu cầu đặt xe đang xử lý để sửa. "
                "Bạn có muốn bắt đầu đặt xe không?"
            ),
            reason="Booking correction requires an active ride-booking workflow.",
        )

    @staticmethod
    def _repeat(state: AgentState) -> AgentAction:
        content = _last_audible_assistant_content(state)
        if content is None:
            return AgentAction(
                action_type=ActionType.ASK_USER,
                message=("Tôi chưa có nội dung trước đó để nhắc lại. Bạn cần hỗ trợ gì?"),
                reason="No audible assistant message is available to repeat.",
            )
        return AgentAction(
            action_type=ActionType.RESPOND,
            message=content,
            reason="The user requested the last audible assistant message.",
        )

    @staticmethod
    def _cancel(agent_input: AgentInput, state: AgentState) -> AgentAction:
        interrupted = state.interrupted_workflow
        targets_interrupted = interrupted is not None and (
            state.current_workflow is None
            or _mentions_workflow(agent_input.transcript, interrupted.workflow)
        )
        if targets_interrupted:
            collected_data = _without_workflow_namespace(
                state.collected_data,
                interrupted.workflow,
            )
            return AgentAction(
                action_type=ActionType.RESPOND,
                message="Tôi đã hủy yêu cầu đang tạm dừng.",
                state_updates={
                    "collected_data": collected_data,
                    "interrupted_workflow": None,
                },
                reason="The explicitly targeted interrupted workflow was cancelled.",
            )
        if state.current_workflow is None and state.pending_tool_name is None:
            return AgentAction(
                action_type=ActionType.RESPOND,
                message="Hiện không có yêu cầu nào đang xử lý.",
                reason="There is no active workflow to cancel.",
            )
        return AgentAction(
            action_type=ActionType.RESPOND,
            message="Tôi đã hủy yêu cầu hiện tại.",
            state_updates=_clear_active_workflow_updates(state),
            reason="The active workflow was cancelled before a side effect.",
        )

    @staticmethod
    def _start_over(state: AgentState) -> AgentAction:
        prompt = _START_OVER_PROMPTS.get(state.current_workflow)
        if prompt is None:
            return AgentAction(
                action_type=ActionType.ASK_USER,
                message="Bạn cần đặt xe, tra cứu chuyến đi hay hỗ trợ vấn đề khác?",
                state_updates=_clear_active_workflow_updates(state),
                reason="No restartable workflow is active.",
            )

        step, message = prompt
        updates = _clear_active_workflow_updates(state)
        updates.update(
            {
                "current_workflow": state.current_workflow,
                "current_step": step,
            }
        )
        return AgentAction(
            action_type=ActionType.ASK_USER,
            message=message,
            state_updates=updates,
            reason="The active workflow was reset to its initial step.",
        )

    @staticmethod
    def _help(state: AgentState) -> AgentAction:
        return AgentAction(
            action_type=ActionType.RESPOND,
            message=_help_message(state),
            reason="Contextual help was requested without changing workflow state.",
        )

    @staticmethod
    def _pause(state: AgentState) -> AgentAction:
        if state.pending_tool_name is not None:
            return AgentAction(
                action_type=ActionType.ASK_USER,
                message="Tôi đang chờ kết quả xử lý. Bạn vui lòng đợi một chút.",
                reason="A workflow cannot be paused while a tool result is pending.",
            )
        if state.current_workflow is None:
            message = (
                "Yêu cầu trước đó đã được tạm dừng."
                if state.interrupted_workflow is not None
                else "Hiện không có yêu cầu nào đang xử lý để tạm dừng."
            )
            return AgentAction(
                action_type=ActionType.RESPOND,
                message=message,
                reason="There is no active workflow to pause.",
            )
        if state.interrupted_workflow is not None:
            return _nested_interruption_action()
        if state.current_workflow not in {
            WorkflowType.RIDE_BOOKING,
            WorkflowType.TRIP_LOOKUP,
        } or state.current_step is None:
            return AgentAction(
                action_type=ActionType.RESPOND,
                message="Workflow hiện tại không thể tạm dừng ở bước này.",
                reason="The active workflow is not at a resumable step.",
            )
        try:
            frame = _snapshot_workflow(state, InterruptionReason.USER_PAUSE)
        except ValueError:
            return _not_resumable_action()
        return AgentAction(
            action_type=ActionType.RESPOND,
            message=f"Tôi đã tạm dừng {_workflow_label(frame.workflow)}.",
            state_updates={
                "current_workflow": None,
                "current_step": None,
                "confirmation": ConfirmationStatus.NOT_REQUESTED,
                "retry_count": 0,
                "interrupted_workflow": frame,
            },
            reason="The active workflow was paused at a stable step.",
        )

    @staticmethod
    def _resume(
        command: DialogueActResult,
        state: AgentState,
    ) -> AgentAction:
        frame = state.interrupted_workflow
        if frame is None:
            return AgentAction(
                action_type=ActionType.RESPOND,
                message="Hiện không có yêu cầu nào đang tạm dừng để tiếp tục.",
                reason="There is no interrupted workflow to resume.",
            )
        if command.target_workflow is not None and command.target_workflow is not frame.workflow:
            return AgentAction(
                action_type=ActionType.ASK_USER,
                message=(
                    f"Yêu cầu đang tạm dừng là {_workflow_label(frame.workflow)}. "
                    "Bạn muốn tiếp tục yêu cầu này không?"
                ),
                reason="The requested resume target does not match the saved workflow.",
            )
        if state.pending_tool_name is not None:
            return AgentAction(
                action_type=ActionType.ASK_USER,
                message="Tôi đang chờ kết quả xử lý. Bạn vui lòng đợi một chút.",
                reason="A workflow cannot resume while a tool result is pending.",
            )
        if state.current_workflow is not None:
            return AgentAction(
                action_type=ActionType.ASK_USER,
                message="Bạn vui lòng hoàn tất hoặc hủy yêu cầu hiện tại trước.",
                reason="Nested workflow resume is not allowed.",
            )
        return AgentAction(
            action_type=ActionType.ASK_USER,
            message=_resume_prompt(frame, state),
            state_updates={
                "current_workflow": frame.workflow,
                "current_step": frame.step,
                "collected_data": _without_workflow_namespace(
                    state.collected_data,
                    WorkflowType.FAQ,
                ),
                "confirmation": frame.confirmation,
                "retry_count": frame.retry_count,
                "interrupted_workflow": None,
            },
            reason="The interrupted workflow was restored to its saved step.",
        )

    @staticmethod
    def _change_intent(
        command: DialogueActResult,
        state: AgentState,
    ) -> AgentAction:
        target = command.target_workflow
        assert target is not None
        if state.pending_tool_name is not None:
            return AgentAction(
                action_type=ActionType.ASK_USER,
                message="Tôi đang chờ kết quả xử lý. Bạn vui lòng đợi một chút.",
                reason="Intent cannot change while a read-only tool is pending.",
            )
        if target is state.current_workflow:
            return AgentAction(
                action_type=ActionType.ASK_USER,
                message=_active_prompt(state),
                reason="The requested workflow is already active.",
            )
        if (
            state.current_workflow is None
            and state.interrupted_workflow is not None
            and target is state.interrupted_workflow.workflow
        ):
            frame = state.interrupted_workflow
            return AgentAction(
                action_type=ActionType.ASK_USER,
                message=_resume_prompt(frame, state),
                state_updates={
                    "current_workflow": frame.workflow,
                    "current_step": frame.step,
                    "confirmation": frame.confirmation,
                    "retry_count": frame.retry_count,
                    "interrupted_workflow": None,
                },
                reason="The requested workflow matches the paused workflow.",
            )
        if state.current_workflow is not None and state.interrupted_workflow is not None:
            return _nested_interruption_action()

        frame = state.interrupted_workflow
        if state.current_workflow in {
            WorkflowType.RIDE_BOOKING,
            WorkflowType.TRIP_LOOKUP,
        } and state.current_step is not None:
            try:
                frame = _snapshot_workflow(
                    state,
                    InterruptionReason.CHANGE_INTENT,
                )
            except ValueError:
                return _not_resumable_action()

        step, message = _START_OVER_PROMPTS[target]
        collected_data = _without_workflow_namespace(state.collected_data, target)
        return AgentAction(
            action_type=ActionType.ASK_USER,
            message=message,
            state_updates={
                "current_workflow": target,
                "current_step": step,
                "collected_data": collected_data,
                "confirmation": ConfirmationStatus.NOT_REQUESTED,
                "retry_count": 0,
                "interrupted_workflow": frame,
            },
            reason="The user explicitly changed to another workflow.",
        )

    @staticmethod
    def _goodbye(state: AgentState) -> AgentAction:
        updates = _clear_active_workflow_updates(state)
        interrupted = state.interrupted_workflow
        if interrupted is not None:
            updates["collected_data"] = _without_workflow_namespace(
                updates["collected_data"],
                interrupted.workflow,
            )
            updates["interrupted_workflow"] = None
        return AgentAction(
            action_type=ActionType.END_SESSION,
            message="Cảm ơn bạn đã liên hệ. Xin chào và hẹn gặp lại.",
            state_updates=updates,
            reason="The user explicitly ended the conversation.",
        )


def _last_audible_assistant_content(state: AgentState) -> str | None:
    for message in reversed(state.conversation_history):
        if (
            message.role is not ConversationRole.ASSISTANT
            or message.message_type is not ConversationMessageType.ASSISTANT_SPEECH
        ):
            continue
        if message.delivery_status is DeliveryStatus.DELIVERED:
            return message.spoken_content or message.content
        if message.delivery_status is DeliveryStatus.INTERRUPTED and message.spoken_content:
            return message.spoken_content
    return None


def _clear_active_workflow_updates(state: AgentState) -> dict[str, object]:
    collected_data = _without_workflow_namespace(
        state.collected_data,
        state.current_workflow,
    )
    return {
        "current_workflow": None,
        "current_step": None,
        "collected_data": collected_data,
        "confirmation": ConfirmationStatus.NOT_REQUESTED,
        "retry_count": 0,
        **clear_pending_tool_updates(),
    }


def _requires_reconciliation(state: AgentState) -> bool:
    return state.pending_tool_name in _SIDE_EFFECT_TOOLS


def _reconciliation_action(act: DialogueAct) -> AgentAction:
    operation = {
        DialogueAct.CORRECT: "sửa thông tin",
        DialogueAct.CANCEL: "hủy",
        DialogueAct.START_OVER: "bắt đầu lại",
        DialogueAct.CHANGE_INTENT: "chuyển yêu cầu",
        DialogueAct.PAUSE: "tạm dừng",
        DialogueAct.GOODBYE: "kết thúc cuộc gọi",
    }[act]
    return AgentAction(
        action_type=ActionType.HANDOFF,
        message=(
            "Tôi cần kiểm tra trạng thái yêu cầu đang xử lý trước khi "
            f"{operation} và sẽ chuyển bạn tới tổng đài viên."
        ),
        state_updates={
            "current_workflow": WorkflowType.HUMAN_HANDOFF,
            "current_step": "RECONCILIATION_REQUIRED",
        },
        reason=("A pending side effect requires Backend or human reconciliation."),
    )


def _snapshot_workflow(
    state: AgentState,
    reason: InterruptionReason,
) -> InterruptedWorkflow:
    assert state.current_workflow is not None
    assert state.current_step is not None
    return InterruptedWorkflow(
        workflow=state.current_workflow,
        step=state.current_step,
        confirmation=state.confirmation,
        retry_count=state.retry_count,
        reason=reason,
    )


def _without_workflow_namespace(
    collected_data: Mapping[str, object],
    workflow: WorkflowType | None,
) -> dict[str, object]:
    result = dict(collected_data)
    namespace = _WORKFLOW_NAMESPACES.get(workflow)
    if namespace is not None:
        result.pop(namespace, None)
    return result


def _workflow_label(workflow: WorkflowType) -> str:
    return {
        WorkflowType.RIDE_BOOKING: "việc đặt xe",
        WorkflowType.TRIP_LOOKUP: "việc tra cứu chuyến",
        WorkflowType.FAQ: "phần hỏi đáp",
        WorkflowType.HUMAN_HANDOFF: "việc chuyển tổng đài viên",
    }[workflow]


def _mentions_workflow(transcript: str, workflow: WorkflowType) -> bool:
    normalized = transcript.casefold()
    terms = {
        WorkflowType.RIDE_BOOKING: ("đặt xe", "chuyến xe"),
        WorkflowType.TRIP_LOOKUP: ("tra cứu", "chuyến lúc nãy"),
        WorkflowType.FAQ: ("hỏi đáp", "câu hỏi"),
        WorkflowType.HUMAN_HANDOFF: ("tổng đài", "nhân viên"),
    }[workflow]
    return any(term in normalized for term in terms)


def _resume_prompt(frame: InterruptedWorkflow, state: AgentState) -> str:
    if frame.workflow is WorkflowType.RIDE_BOOKING:
        try:
            data = BookingData.model_validate(state.collected_data.get("booking", {}))
        except ValueError:
            return "Tiếp tục đặt xe. Bạn vui lòng cung cấp thông tin còn thiếu."
        if frame.step == BookingStep.CONFIRM.value and data.pickup and data.destination:
            return (
                f"Tiếp tục đặt xe. Bạn xác nhận đón tại {data.pickup.display_name} "
                f"và đến {data.destination.display_name}, đúng không?"
            )
    return _prompt_for_step(frame.workflow, frame.step)


def _active_prompt(state: AgentState) -> str:
    if state.current_workflow is None or state.current_step is None:
        return "Bạn muốn tiếp tục yêu cầu hiện tại như thế nào?"
    if state.current_workflow is WorkflowType.FAQ:
        return "Bạn muốn hỏi thông tin gì về dịch vụ?"
    try:
        frame = InterruptedWorkflow(
            workflow=state.current_workflow,
            step=state.current_step,
            confirmation=state.confirmation,
            retry_count=state.retry_count,
            reason=InterruptionReason.USER_PAUSE,
        )
    except ValueError:
        return "Bạn vui lòng tiếp tục yêu cầu hiện tại tại bước trước đó."
    return _resume_prompt(frame, state)


def _prompt_for_step(workflow: WorkflowType, step: str) -> str:
    prompts = {
        (WorkflowType.RIDE_BOOKING, BookingStep.COLLECT_PICKUP.value): (
            "Tiếp tục đặt xe. Bạn muốn đón ở đâu?"
        ),
        (WorkflowType.RIDE_BOOKING, BookingStep.COLLECT_DESTINATION.value): (
            "Tiếp tục đặt xe. Bạn muốn đi đến đâu?"
        ),
        (WorkflowType.RIDE_BOOKING, BookingStep.COLLECT_PHONE.value): (
            "Tiếp tục đặt xe. Bạn vui lòng cung cấp số điện thoại."
        ),
        (WorkflowType.RIDE_BOOKING, BookingStep.SELECT_PICKUP_CANDIDATE.value): (
            "Tiếp tục đặt xe. Bạn vui lòng chọn lại điểm đón trong các kết quả trước."
        ),
        (WorkflowType.RIDE_BOOKING, BookingStep.SELECT_DESTINATION_CANDIDATE.value): (
            "Tiếp tục đặt xe. Bạn vui lòng chọn lại điểm đến trong các kết quả trước."
        ),
        (WorkflowType.RIDE_BOOKING, BookingStep.SELECT_CORRECTION_FIELD.value): (
            "Tiếp tục đặt xe. Bạn muốn sửa điểm đón, điểm đến hay số điện thoại?"
        ),
        (WorkflowType.TRIP_LOOKUP, TripLookupStep.COLLECT_IDENTIFIER.value): (
            "Tiếp tục tra cứu. Bạn vui lòng cung cấp mã chuyến hoặc số điện thoại."
        ),
    }
    return prompts.get(
        (workflow, step),
        f"Tiếp tục {_workflow_label(workflow)} tại bước trước đó.",
    )


def _help_message(state: AgentState) -> str:
    if state.current_workflow is WorkflowType.RIDE_BOOKING:
        return (
            "Tôi có thể giúp thu thập điểm đón, điểm đến, số điện thoại, "
            "sửa thông tin hoặc hủy việc đặt xe."
        )
    if state.current_workflow is WorkflowType.TRIP_LOOKUP:
        return "Để tra cứu, bạn có thể cung cấp mã chuyến hoặc số điện thoại đặt xe."
    if state.current_workflow is WorkflowType.FAQ:
        return "Bạn có thể hỏi về dịch vụ, thanh toán hoặc chính sách hỗ trợ."
    if state.interrupted_workflow is not None:
        return (
            f"Bạn có thể nói tiếp tục để quay lại "
            f"{_workflow_label(state.interrupted_workflow.workflow)}."
        )
    return "Tôi có thể hỗ trợ đặt xe, tra cứu chuyến đi hoặc hỏi đáp về dịch vụ."


def _nested_interruption_action() -> AgentAction:
    return AgentAction(
        action_type=ActionType.ASK_USER,
        message=(
            "Đã có một yêu cầu đang tạm dừng. Bạn vui lòng tiếp tục hoặc hủy "
            "yêu cầu đó trước khi chuyển sang việc khác."
        ),
        reason="Nested workflow interruption is not allowed.",
    )


def _not_resumable_action() -> AgentAction:
    return AgentAction(
        action_type=ActionType.ASK_USER,
        message="Workflow hiện tại không thể tạm dừng an toàn ở bước này.",
        reason="The active workflow step is not resumable.",
    )


def _first_match(patterns: Iterable[re.Pattern[str]], transcript: str) -> str | None:
    for pattern in patterns:
        match = pattern.search(transcript)
        if match:
            return match.group()
    return None


def _workflow_from_text(value: str) -> WorkflowType | None:
    normalized = " ".join(value.casefold().split())
    return next(
        (workflow for phrase, workflow in _WORKFLOW_TARGETS.items() if phrase in normalized),
        None,
    )


def _recognized(
    act: DialogueAct,
    evidence: str,
    *,
    target_workflow: WorkflowType | None = None,
    correction_field: CorrectionField | None = None,
) -> DialogueActResult:
    return DialogueActResult(
        act=act,
        target_workflow=target_workflow,
        correction_field=correction_field,
        confidence=1.0,
        matched_evidence=[evidence],
    )
