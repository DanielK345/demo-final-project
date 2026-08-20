"""The single AloSM agent used by the LiveKit-native runtime."""

import json

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
                "Mọi câu hỏi về trạng thái đặt xe, đặt thành công hay mã chuyến đều phải gọi "
                "get_booking_status trước khi trả lời. Chỉ được nói đã đặt thành công khi kết quả tool "
                "có booking_id; nếu booking_id là null thì phải nói chuyến chưa được tạo. "
                "Sau khi BookingTask chuyển tổng đài viên, không được tự coi yêu cầu đó là đã đặt. "
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

    @function_tool()
    async def get_booking_status(self) -> str:
        """Read the authoritative booking status and real booking ID for this call.

        This tool must be used before answering whether a ride was created or
        giving the customer a booking ID.
        """
        if self._session_data is None:
            return json.dumps(
                {
                    "created": False,
                    "booking_id": None,
                    "instruction": "Không có trạng thái phiên; không được nói chuyến đã được tạo.",
                },
                ensure_ascii=False,
            )

        draft = self._session_data.booking_draft
        booking = draft.booking
        return json.dumps(
            {
                "created": booking is not None,
                "booking_id": booking.booking_id if booking else None,
                "booking_status": booking.status if booking else None,
                "confirmation_status": draft.confirmation_status,
                "handoff_status": self._session_data.handoff.status if self._session_data.handoff else None,
                "summary": draft.conversation_summary(),
                "instruction": (
                    "Chỉ thông báo đặt thành công và đọc booking_id ở trên."
                    if booking is not None
                    else "Chuyến chưa được tạo; không được phát sinh hoặc suy đoán mã chuyến."
                ),
            },
            ensure_ascii=False,
        )
