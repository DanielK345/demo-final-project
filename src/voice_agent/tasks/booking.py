"""LiveKit ``AgentTask`` implementing AloSM's native booking happy path."""

from __future__ import annotations

import json
import re
import unicodedata
from typing import Literal

from livekit.agents import AgentTask, RunContext, ToolError, function_tool, llm
from pydantic import BaseModel, ConfigDict

from src.voice_agent.persistence import (
    EphemeralVoiceStateStore,
    VoiceStateConflictError,
    VoiceStateStore,
)
from src.voice_agent.session_data import (
    AloSMSessionData,
    BookingResult,
    BookingTarget,
    HandoffState,
    VehicleType,
    vehicle_spoken_label,
)
from src.voice_agent.state_sync import publish_booking_state
from src.voice_agent.tools import (
    BookingToolsService,
    HandoffToolsService,
    PlaceToolsService,
    QuoteToolsService,
)


class BookingOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["success", "cancelled", "handoff"]
    message: str
    booking: BookingResult | None = None


def _normalize_confirmation(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold().replace("đ", "d"))
    plain = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", plain).split())


def is_explicit_confirmation(value: str) -> bool:
    normalized = _normalize_confirmation(value)
    negative_tokens = {"khong", "chua", "huy", "thoi"}
    if not normalized or negative_tokens.intersection(normalized.split()) or "dung dat" in normalized:
        return False
    affirmative_phrases = (
        "toi xac nhan",
        "xac nhan dat",
        "dong y dat",
        "dat chuyen nay",
        "dat xe di",
        "dung roi dat",
        "ok dat",
    )
    return any(phrase in normalized for phrase in affirmative_phrases)


def requires_location_clarification(
    message: llm.ChatMessage | None,
    threshold: float,
) -> bool:
    """Text input has no confidence and remains an intentional fallback path."""

    return (
        message is not None and message.transcript_confidence is not None and message.transcript_confidence < threshold
    )


class BookingTask(AgentTask[BookingOutcome]):
    """Collect and validate one booking while preserving the single AloSM persona."""

    def __init__(
        self,
        *,
        chat_ctx: llm.ChatContext | None = None,
        places: PlaceToolsService | None = None,
        quotes: QuoteToolsService | None = None,
        bookings: BookingToolsService | None = None,
        handoffs: HandoffToolsService | None = None,
        state_store: VoiceStateStore | None = None,
    ) -> None:
        self._places = places or PlaceToolsService()
        self._quotes = quotes or QuoteToolsService()
        self._bookings = bookings or BookingToolsService()
        self._handoffs = handoffs or HandoffToolsService()
        self._state_store = state_store or EphemeralVoiceStateStore()
        super().__init__(
            chat_ctx=chat_ctx,
            instructions=(
                "Bạn vẫn là tổng đài viên AloSM, đang thực hiện đúng một yêu cầu đặt xe. "
                "Nói tiếng Việt tự nhiên, ngắn gọn và mỗi lượt chỉ hỏi một thông tin. "
                "Đây là nội dung đọc thành tiếng: gọi khách là bạn hoặc quý khách; không dùng dấu "
                "gạch chéo, chữ viết tắt, mã enum hoặc ký hiệu tiền tệ trong câu trả lời. "
                "Đọc MOTORBIKE là xe máy, CAR_4 là xe ô tô bốn chỗ, CAR_7 là xe ô tô bảy chỗ, "
                "LUXURY là xe cao cấp và VND là đồng. "
                "Phải dùng search_place cho lời người dùng nói về địa điểm; không tự tạo place_id. "
                "Chỉ dùng select_place với candidate_id có trong kết quả tìm kiếm hiện hành. "
                "Thu thập đủ điểm đón, điểm đến và loại xe rồi gọi estimate_fare. "
                "Sau khi có giá, gọi prepare_booking_confirmation và đọc lại đầy đủ thông tin. "
                "Chỉ gọi confirm_booking khi lượt nói mới nhất của khách xác nhận đặt chuyến rõ ràng. "
                "Chỉ gọi create_booking sau khi confirm_booking thành công. "
                "Nếu khách sửa điểm đón, điểm đến hoặc loại xe, gọi tool tương ứng; hệ thống sẽ "
                "tự xoá giá và xác nhận cũ. Không được tự bịa giá, ETA hoặc mã chuyến."
                "Nếu tool báo ASR_LOW_CONFIDENCE thì yêu cầu khách nói lại hoặc nhập tay. "
                "Nếu khách yêu cầu gặp người thật hoặc không thể tiếp tục, gọi request_handoff."
            ),
        )

    async def on_enter(self) -> None:
        current_state = self.session.userdata.booking_draft.conversation_summary()
        self.session.generate_reply(
            instructions=(
                f"Trạng thái booking hiện tại: {current_state}. "
                "Dựa trên yêu cầu đặt xe gần nhất của khách và trạng thái này, hãy gọi tool cần thiết ngay. "
                "Nếu yêu cầu chưa có đủ thông tin thì hỏi đúng một thông tin còn thiếu."
            )
        )

    @staticmethod
    def _draft(context: RunContext[AloSMSessionData]):
        return context.userdata.booking_draft

    def _latest_user_message(self) -> llm.ChatMessage | None:
        for item in reversed(self.chat_ctx.items):
            if getattr(item, "role", None) == "user":
                return item if isinstance(item, llm.ChatMessage) else None
        return None

    async def _commit(self, context: RunContext[AloSMSessionData]) -> None:
        try:
            await self._state_store.save(context.userdata)
        except VoiceStateConflictError as exc:
            context.userdata.record_failure(
                "STATE_CONFLICT",
                "Phiên này vừa được cập nhật ở kết nối khác.",
                retryable=False,
                fallback_action="handoff",
            )
            await publish_booking_state(context.session)
            raise ToolError("STATE_CONFLICT") from exc
        await publish_booking_state(context.session)

    @function_tool()
    async def search_place(
        self,
        context: RunContext[AloSMSessionData],
        target: BookingTarget,
        query: str,
    ) -> str:
        """Search real demo gazetteer candidates for a pickup or destination utterance.

        Args:
            target: Whether this location is the pickup or destination.
            query: The location words actually provided by the customer.
        """
        latest = self._latest_user_message()
        confidence = latest.transcript_confidence if latest is not None else None
        context.userdata.last_asr_confidence = confidence
        if requires_location_clarification(latest, context.userdata.critical_confidence_threshold):
            context.userdata.record_failure(
                "ASR_LOW_CONFIDENCE",
                "Tổng đài chưa nghe rõ địa điểm quan trọng.",
                fallback_action="repeat_or_text",
            )
            await self._commit(context)
            return "ASR_LOW_CONFIDENCE: Hãy yêu cầu khách nói lại địa điểm hoặc nhập tay."

        candidates = self._places.search(query)
        draft = self._draft(context)
        draft.set_candidates(target, query, candidates)
        if not candidates:
            context.userdata.record_failure(
                "PLACE_NOT_FOUND",
                "Không tìm thấy địa điểm phù hợp.",
                fallback_action="repeat_or_text",
            )
            await self._commit(context)
            return "Không tìm thấy địa điểm trong dữ liệu demo. Hãy hỏi khách tên địa điểm khác hoặc rõ hơn."
        context.userdata.clear_failure()
        await self._commit(context)
        return json.dumps(
            {
                "target": target,
                "candidates": [candidate.model_dump() for candidate in candidates],
                "instruction": "Hỏi khách chọn/xác nhận một candidate trước khi gọi select_place.",
            },
            ensure_ascii=False,
        )

    @function_tool()
    async def select_place(
        self,
        context: RunContext[AloSMSessionData],
        target: BookingTarget,
        place_id: str,
    ) -> str:
        """Resolve a location using an ID from the current search result only.

        Args:
            target: Whether the selected location is the pickup or destination.
            place_id: Exact candidate place_id returned by search_place.
        """
        try:
            selected = self._draft(context).select_place(target, place_id)
        except ValueError as exc:
            raise ToolError(str(exc)) from exc
        context.userdata.clear_failure()
        await self._commit(context)
        target_label = "điểm đón" if target == "pickup" else "điểm đến"
        return f"Đã xác nhận {target_label}: {selected.display_name}, {selected.address}."

    @function_tool()
    async def set_vehicle_type(
        self,
        context: RunContext[AloSMSessionData],
        vehicle_type: VehicleType,
    ) -> str:
        """Set the exact supported vehicle class requested by the customer.

        Args:
            vehicle_type: MOTORBIKE, CAR_4, CAR_7, or LUXURY.
        """
        self._draft(context).set_vehicle_type(vehicle_type)
        context.userdata.clear_failure()
        await self._commit(context)
        return f"Đã chọn {vehicle_spoken_label(vehicle_type)}."

    @function_tool()
    async def estimate_fare(self, context: RunContext[AloSMSessionData]) -> str:
        """Create a deterministic demo quote after all required fields are resolved."""
        draft = self._draft(context)
        try:
            quote = self._quotes.estimate(draft)
            draft.set_quote(quote)
        except ValueError as exc:
            context.userdata.record_failure(
                "QUOTE_UNAVAILABLE",
                "Chưa thể tạo báo giá từ thông tin hiện tại.",
                fallback_action="retry",
            )
            await self._commit(context)
            raise ToolError(str(exc)) from exc
        context.userdata.clear_failure()
        await self._commit(context)
        return json.dumps(quote.model_dump(), ensure_ascii=False)

    @function_tool()
    async def prepare_booking_confirmation(self, context: RunContext[AloSMSessionData]) -> str:
        """Freeze the current quote and return the exact summary that must be read to the customer."""
        draft = self._draft(context)
        try:
            draft.request_confirmation()
            quote = draft.quote_or_raise()
        except ValueError as exc:
            raise ToolError(str(exc)) from exc
        context.userdata.clear_failure()
        await self._commit(context)
        return (
            f"Hãy hỏi xác nhận rõ ràng: đón tại {draft.pickup.display_name}, "
            f"đến {draft.destination.display_name}, đi bằng {vehicle_spoken_label(draft.vehicle_type)}, "
            f"giá dự kiến {quote.fare_amount} đồng, "
            f"thời gian xe tới dự kiến {quote.eta_minutes} phút."
        )

    @function_tool()
    async def confirm_booking(self, context: RunContext[AloSMSessionData]) -> str:
        """Record confirmation only when the customer's latest message explicitly approves booking."""
        latest = self._latest_user_message()
        latest_user_text = latest.text_content if latest is not None else ""
        if not is_explicit_confirmation(latest_user_text):
            raise ToolError("LATEST_USER_MESSAGE_IS_NOT_EXPLICIT_BOOKING_CONFIRMATION")
        try:
            self._draft(context).confirm()
        except ValueError as exc:
            raise ToolError(str(exc)) from exc
        context.userdata.clear_failure()
        await self._commit(context)
        return "Khách đã xác nhận rõ ràng; có thể gọi create_booking."

    @function_tool(on_duplicate="confirm")
    async def create_booking(self, context: RunContext[AloSMSessionData]) -> None:
        """Create the idempotent demo booking after valid explicit confirmation."""
        # A confirmed write must finish deterministically even if the caller speaks
        # while this very short demo operation is being committed.
        context.disallow_interruptions()
        draft = self._draft(context)
        try:
            booking = self._bookings.create(
                app_session_id=context.userdata.app_session_id,
                draft=draft,
            )
            draft.set_booking(booking)
            context.userdata.lifecycle_status = "completed"
        except ValueError as exc:
            raise ToolError(str(exc)) from exc
        except Exception as exc:
            context.userdata.record_failure(
                "BOOKING_RESULT_UNKNOWN",
                "Chưa xác định được kết quả tạo chuyến; không tự động tạo lại.",
                retryable=False,
                fallback_action="handoff",
            )
            await self._commit(context)
            raise ToolError("BOOKING_RESULT_UNKNOWN") from exc
        context.userdata.clear_failure()
        await self._commit(context)
        outcome = BookingOutcome(
            status="success",
            booking=booking,
            message=f"Đặt chuyến thành công. Xe dự kiến tới sau {booking.eta_minutes} phút.",
        )
        if not self.done():
            self.complete(outcome)
        return None

    @function_tool()
    async def request_handoff(
        self,
        context: RunContext[AloSMSessionData],
        reason: str,
    ) -> None:
        """Send a privacy-safe booking summary to a human operator.

        Args:
            reason: Short reason for requesting a human operator.
        """
        context.disallow_interruptions()
        try:
            record = await self._handoffs.create(context.userdata, reason=reason)
        except Exception as exc:
            context.userdata.record_failure(
                "HANDOFF_REQUIRED",
                "Chưa thể tạo yêu cầu chuyển tổng đài viên.",
                retryable=True,
                fallback_action="retry",
            )
            await self._commit(context)
            raise ToolError("HANDOFF_CREATE_FAILED") from exc
        context.userdata.handoff_requested = True
        context.userdata.handoff = HandoffState(
            handoff_id=str(record["handoff_id"]),
            status="pending",
            reason_code=str(record.get("reason_code") or "LIVEKIT_VOICE_HANDOFF"),
        )
        context.userdata.record_failure(
            "HANDOFF_REQUIRED",
            "Yêu cầu đã được chuyển tới tổng đài viên.",
            retryable=False,
            fallback_action="handoff",
        )
        await self._commit(context)
        outcome = BookingOutcome(
            status="handoff",
            message="Đã chuyển yêu cầu cùng trạng thái đặt xe hiện tại tới tổng đài viên.",
        )
        if not self.done():
            self.complete(outcome)
        return None

    @function_tool()
    async def cancel_booking_flow(
        self,
        context: RunContext[AloSMSessionData],
        reason: str,
    ) -> None:
        """End this booking task when the customer explicitly cancels the flow.

        Args:
            reason: Short reason stated by the customer.
        """
        context.userdata.lifecycle_status = "cancelled"
        await self._commit(context)
        outcome = BookingOutcome(status="cancelled", message=f"Đã dừng đặt xe: {reason}.")
        if not self.done():
            self.complete(outcome)
        return None
