"""LiveKit ``AgentTask`` implementing AloSM's native booking happy path."""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from collections.abc import Awaitable, Callable
from typing import Literal

from livekit.agents import AgentTask, RunContext, ToolError, function_tool, llm
from pydantic import BaseModel, ConfigDict

from src.voice.text.rewrite_contract import TranscriptRewriter, TranscriptRewriteResult
from src.voice_agent.persistence import (
    EphemeralVoiceStateStore,
    VoiceStateConflictError,
    VoiceStateStore,
)
from src.voice_agent.session_data import (
    AloSMSessionData,
    BookingField,
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
from src.voice_agent.transcript_rewrite import rewrite_livekit_user_turn

logger = logging.getLogger(__name__)


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


_CHANGE_CUES = ("doi", "sua", "thay", "chinh", "cap nhat", "khong phai", "nham")
_FIELD_TERMS: dict[BookingField, tuple[str, ...]] = {
    "pickup": ("diem don", "diem di", "noi don", "cho don", "don o", "don tai", "di tu", "xuat phat tu"),
    "destination": ("diem den", "noi den", "cho den", "dich den", "di den", "di toi"),
    "vehicle_type": ("loai xe", "xe may", "xe oto", "xe o to", "xe bon cho", "xe bay cho", "xe cao cap"),
}


def is_explicit_booking_field_change(value: str, field: BookingField) -> bool:
    """Require transcript evidence before an already selected slot can be unlocked."""

    normalized = _normalize_confirmation(value)
    if not normalized:
        return False
    field_mentioned = any(term in normalized for term in _FIELD_TERMS[field])
    change_requested = any(cue in normalized for cue in _CHANGE_CUES)
    if field_mentioned and change_requested:
        return True
    # These complete constructions directly replace an existing value even when
    # Vietnamese speakers omit an explicit "đổi/sửa" verb.
    if field == "pickup":
        return any(term in normalized for term in ("diem don la", "don toi o", "don minh o", "di tu"))
    if field == "destination":
        return any(term in normalized for term in ("diem den la", "toi muon den", "di den", "di toi"))
    return field_mentioned and any(term in normalized for term in ("toi muon", "cho toi", "chuyen sang"))


def requires_location_clarification(
    message: llm.ChatMessage | None,
    threshold: float,
) -> bool:
    """Text input has no confidence and remains an intentional fallback path."""

    return (
        message is not None and message.transcript_confidence is not None and message.transcript_confidence < threshold
    )


def can_auto_select_place(candidates: list[object]) -> bool:
    """Auto-select only one deterministic exact/alias gazetteer result.

    Fuzzy results and landmarks with multiple pickup points remain explicit
    clarification turns because a location is a booking-critical entity.
    """

    return len(candidates) == 1 and getattr(candidates[0], "provider", None) in {
        "local_gazetteer",
        "local_landmark_mock_exact",
    }


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
        session_data: AloSMSessionData | None = None,
        transcript_rewriter: TranscriptRewriter | None = None,
        transcript_rewrite_publisher: Callable[[str, TranscriptRewriteResult], Awaitable[object]] | None = None,
    ) -> None:
        self._places = places or PlaceToolsService()
        self._quotes = quotes or QuoteToolsService()
        self._bookings = bookings or BookingToolsService()
        self._handoffs = handoffs or HandoffToolsService()
        self._state_store = state_store or EphemeralVoiceStateStore()
        self._session_data = session_data
        self._transcript_rewriter = transcript_rewriter
        self._transcript_rewrite_publisher = transcript_rewrite_publisher
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
                "Nếu search_place báo đã tự chọn một kết quả khớp duy nhất thì không hỏi xác nhận "
                "địa điểm đó lần nữa. Với kết quả mơ hồ, phải hỏi khách chọn candidate. "
                "Thu thập đủ điểm đón, điểm đến và loại xe rồi gọi estimate_fare. "
                "estimate_fare đồng thời khóa báo giá ở trạng thái chờ xác nhận; đọc lại đầy đủ "
                "thông tin mà tool trả về và không tự bỏ qua bước này. "
                "Chỉ gọi confirm_booking khi lượt nói mới nhất của khách xác nhận đặt chuyến rõ ràng. "
                "Chỉ gọi create_booking sau khi confirm_booking thành công. "
                "Điểm đón, điểm đến và loại xe đã xác nhận là các trường đã khóa. Không được gọi "
                "search_place, select_place hoặc set_vehicle_type để thay trường đã khóa chỉ vì mất "
                "context. Chỉ khi lượt mới nhất của khách yêu cầu đổi đúng trường đó, gọi "
                "unlock_booking_field trước rồi mới gọi tool cập nhật tương ứng; các trường còn lại "
                "phải được giữ nguyên. Hệ thống sẽ tự xoá giá và xác nhận cũ. Không được tự bịa giá, "
                "ETA hoặc mã chuyến. "
                "Nếu tool báo ASR_LOW_CONFIDENCE thì yêu cầu khách nói lại hoặc nhập tay. "
                "Nếu khách yêu cầu gặp người thật, tổng đài viên thật, nhân viên thật, operator hoặc yêu cầu chuyển máy, "
                "bắt buộc gọi request_handoff ngay; không được nói bạn là người thật hay chưa có chức năng chuyển. "
                "Nếu không thể tiếp tục cũng gọi request_handoff."
            ),
        )

    async def on_user_turn_completed(
        self,
        turn_ctx: llm.ChatContext,
        new_message: llm.ChatMessage,
    ) -> None:
        result = await rewrite_livekit_user_turn(
            rewriter=self._transcript_rewriter,
            userdata=self._session_data,
            turn_ctx=turn_ctx,
            new_message=new_message,
        )
        if result is not None and self._transcript_rewrite_publisher is not None:
            await self._transcript_rewrite_publisher(new_message.id, result)

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

    async def _create_handoff(self, userdata: AloSMSessionData, reason: str) -> BookingOutcome:
        room = getattr(getattr(self.session, "room_io", None), "room", None)
        room_name = getattr(room, "name", None)
        record = await self._handoffs.create(userdata, reason=reason, room_name=room_name)
        userdata.handoff_requested = True
        userdata.handoff = HandoffState(
            handoff_id=str(record["handoff_id"]),
            status="pending",
            reason_code=str(record.get("reason_code") or "LIVEKIT_VOICE_HANDOFF"),
            room_name=str(record.get("room_name") or room_name or "") or None,
        )
        userdata.record_failure(
            "HANDOFF_REQUIRED",
            "Yêu cầu đã được chuyển tới tổng đài viên.",
            retryable=False,
            fallback_action="handoff",
        )
        await self._state_store.save(userdata)
        await publish_booking_state(self.session)
        return BookingOutcome(
            status="handoff",
            message="Đã chuyển yêu cầu cùng trạng thái đặt xe hiện tại tới tổng đài viên.",
        )

    async def on_user_turn_completed(self, turn_ctx: llm.ChatContext, new_message: llm.ChatMessage) -> None:
        # Human-handoff intent is booking-critical. Detect it before the task
        # LLM responds so an ambiguous location turn cannot swallow the request.
        if HandoffToolsService.is_handoff_request(new_message.text_content or ""):
            try:
                outcome = await self._create_handoff(self.session.userdata, new_message.text_content or "")
            except Exception:
                logger.exception("failed to create deterministic human handoff session=%s", self.session.userdata.app_session_id)
                self.session.userdata.record_failure(
                    "HANDOFF_REQUIRED",
                    "Chưa thể tạo yêu cầu chuyển tổng đài viên.",
                    retryable=True,
                    fallback_action="retry",
                )
                await publish_booking_state(self.session)
                return
            if not self.done():
                self.complete(outcome)

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
    async def unlock_booking_field(
        self,
        context: RunContext[AloSMSessionData],
        field: BookingField,
    ) -> str:
        """Unlock exactly one selected field when the latest user turn explicitly changes it.

        Args:
            field: The selected pickup, destination, or vehicle_type field to change.
        """
        latest = self._latest_user_message()
        latest_user_text = latest.text_content if latest is not None else ""
        if not is_explicit_booking_field_change(latest_user_text, field):
            raise ToolError(f"LATEST_USER_MESSAGE_DOES_NOT_CHANGE_LOCKED_FIELD:{field}")
        try:
            self._draft(context).unlock_field(field)
        except ValueError as exc:
            raise ToolError(str(exc)) from exc
        context.userdata.clear_failure()
        await self._commit(context)
        labels = {"pickup": "điểm đón", "destination": "điểm đến", "vehicle_type": "loại xe"}
        return f"Đã cho phép cập nhật {labels[field]}; giữ nguyên các thông tin đã khóa khác."

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
        try:
            draft.set_candidates(target, query, candidates)
        except ValueError as exc:
            raise ToolError(str(exc)) from exc
        if not candidates:
            context.userdata.record_failure(
                "PLACE_NOT_FOUND",
                "Không tìm thấy địa điểm phù hợp.",
                fallback_action="repeat_or_text",
            )
            await self._commit(context)
            return "Không tìm thấy địa điểm trong dữ liệu demo. Hãy hỏi khách tên địa điểm khác hoặc rõ hơn."
        if can_auto_select_place(candidates):
            selected = draft.select_place(target, candidates[0].place_id)
            context.userdata.clear_failure()
            await self._commit(context)
            return json.dumps(
                {
                    "target": target,
                    "auto_selected": True,
                    "place_id": selected.place_id,
                    "display_name": selected.display_name,
                    "instruction": "Đã tự chọn exact match duy nhất; tiếp tục trường còn thiếu, không hỏi lại.",
                },
                ensure_ascii=False,
            )
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
        try:
            self._draft(context).set_vehicle_type(vehicle_type)
        except ValueError as exc:
            raise ToolError(str(exc)) from exc
        context.userdata.clear_failure()
        await self._commit(context)
        return f"Đã chọn {vehicle_spoken_label(vehicle_type)}."

    @function_tool()
    async def estimate_fare(self, context: RunContext[AloSMSessionData]) -> str:
        """Create a quote and atomically move it to awaiting confirmation."""
        draft = self._draft(context)
        try:
            quote = await self._quotes.estimate(
                user_id=context.userdata.user_id,
                app_session_id=context.userdata.app_session_id,
                draft=draft,
            )
            draft.set_quote(quote)
            # Awaiting-confirmation is a business invariant, not an optional
            # second LLM tool choice. Keeping quote creation and confirmation
            # preparation atomic prevents a valid spoken confirmation from
            # failing when the model narrates the quote without calling another
            # tool first.
            draft.request_confirmation()
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
            booking = await self._bookings.create(
                user_id=context.userdata.user_id,
                app_session_id=context.userdata.app_session_id,
                draft=draft,
            )
            draft.set_booking(booking)
            context.userdata.lifecycle_status = "completed"
        except ValueError as exc:
            raise ToolError(str(exc)) from exc
        except Exception as exc:
            logger.exception("failed to create booking handoff session=%s", context.userdata.app_session_id)
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
            outcome = await self._create_handoff(context.userdata, reason)
        except Exception as exc:
            context.userdata.record_failure(
                "HANDOFF_REQUIRED",
                "Chưa thể tạo yêu cầu chuyển tổng đài viên.",
                retryable=True,
                fallback_action="retry",
            )
            await self._commit(context)
            raise ToolError("HANDOFF_CREATE_FAILED") from exc
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
