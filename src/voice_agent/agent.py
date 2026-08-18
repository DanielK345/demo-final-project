"""The single AloSM agent used by the LiveKit-native runtime."""

from livekit.agents import Agent, function_tool

from src.voice_agent.persistence import EphemeralVoiceStateStore, VoiceStateStore
from src.voice_agent.session_data import AloSMSessionData
from src.voice_agent.tasks import BookingTask


class AloSMAgent(Agent):
    """Single call-level persona; scoped business flows run as AgentTasks."""

    def __init__(
        self,
        *,
        state_store: VoiceStateStore | None = None,
        session_data: AloSMSessionData | None = None,
    ) -> None:
        self._state_store = state_store or EphemeralVoiceStateStore()
        self._session_data = session_data
        recovered_context = ""
        if session_data is not None and session_data.recovered:
            recovered_context = (
                " Trạng thái nghiệp vụ đã khôi phục từ hệ thống: "
                f"{session_data.booking_draft.conversation_summary()}. "
                "Dùng trạng thái này khi khách hỏi lại hoặc muốn tiếp tục; không nói rằng không có lịch sử."
            )
        super().__init__(
            instructions=(
                "Bạn là tổng đài viên giọng nói AloSM nói tiếng Việt. "
                "Trả lời tự nhiên, lịch sự và ngắn gọn, thường không quá hai câu. "
                "Luôn dùng từ ngữ phù hợp để đọc thành tiếng: gọi khách là bạn hoặc quý khách; "
                "không dùng dấu gạch chéo, chữ viết tắt hay mã enum trong câu trả lời. "
                "Khi khách muốn đặt xe, phải gọi start_booking và để BookingTask thu thập, "
                "xác nhận, báo giá và tạo booking demo. Không tự bịa địa chỉ, giá, ETA hoặc mã chuyến. "
                "Ngoài đặt xe, chỉ trả lời ngắn gọn và nói rõ nếu năng lực chưa được tích hợp."
                + recovered_context
            )
        )

    @function_tool()
    async def start_booking(self) -> str:
        """Start or resume the native AloSM ride-booking task for this call."""
        # LiveKit recommends carrying conversation history into a task while
        # excluding the parent instructions, so the focused task prompt remains
        # small and authoritative.
        task_context = self.chat_ctx.copy(exclude_instructions=True)
        outcome = await BookingTask(chat_ctx=task_context, state_store=self._state_store)
        return outcome.message
