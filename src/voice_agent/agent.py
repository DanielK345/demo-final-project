"""The single AloSM agent used by the LiveKit-native runtime."""

import json
import logging

from collections.abc import Awaitable, Callable

from livekit.agents import Agent, function_tool, llm

from src.backend.services.knowledge_service import KnowledgeService
from src.backend.services.pricing_service import PricingService
from src.voice.text.rewrite_contract import TranscriptRewriter, TranscriptRewriteResult
from src.voice_agent.persistence import EphemeralVoiceStateStore, VoiceStateStore
from src.voice_agent.session_data import AloSMSessionData, HandoffState
from src.voice_agent.state_sync import publish_booking_state
from src.voice_agent.tasks import BookingTask
from src.voice_agent.tools.handoffs import HandoffToolsService
from src.voice_agent.transcript_rewrite import rewrite_livekit_user_turn

logger = logging.getLogger(__name__)

TranscriptRewritePublisher = Callable[[str, TranscriptRewriteResult], Awaitable[object]]


class AloSMAgent(Agent):
    """Single call-level persona; scoped business flows run as AgentTasks."""

    def __init__(
        self,
        *,
        state_store: VoiceStateStore | None = None,
        session_data: AloSMSessionData | None = None,
        transcript_rewriter: TranscriptRewriter | None = None,
        transcript_rewrite_publisher: TranscriptRewritePublisher | None = None,
        knowledge_service: KnowledgeService | None = None,
        pricing_service: PricingService | None = None,
    ) -> None:
        self._state_store = state_store or EphemeralVoiceStateStore()
        self._session_data = session_data
        self._transcript_rewriter = transcript_rewriter
        self._transcript_rewrite_publisher = transcript_rewrite_publisher
        self._handoffs = HandoffToolsService()
        # These catalogs are local, validated and cached.  They are injected so
        # the LiveKit process can preload them once instead of reading files on
        # every call or every turn.
        self._knowledge_service = knowledge_service or KnowledgeService()
        self._pricing_service = pricing_service or PricingService()
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
                "Nếu khách nói muốn gặp người thật, tổng đài viên thật, nhân viên thật, operator hoặc yêu cầu chuyển máy, "
                "bắt buộc gọi request_handoff ngay; không được trả lời rằng bạn là người thật hoặc chưa có chức năng chuyển. "
                "Khi khách hỏi chính sách, hành lý, phí hoặc điều kiện dịch vụ, gọi search_knowledge; "
                "khi khách hỏi các loại xe, gọi get_vehicle_options. Chỉ đọc thông tin mà tool trả về, "
                "kèm nguồn hoặc phiên bản khi phù hợp; không tự bịa hoặc dùng RAG cho báo giá một lộ trình. "
                "Ngoài các capability trên, nói rõ nếu năng lực chưa được tích hợp." + recovered_context
            )
        )

    async def on_user_turn_completed(
        self,
        turn_ctx: llm.ChatContext,
        new_message: llm.ChatMessage,
    ) -> None:
        if HandoffToolsService.is_handoff_request(new_message.text_content or ""):
            await self._create_handoff(new_message.text_content or "")
        result = await rewrite_livekit_user_turn(
            rewriter=self._transcript_rewriter,
            userdata=self._session_data,
            turn_ctx=turn_ctx,
            new_message=new_message,
        )
        if result is not None and self._transcript_rewrite_publisher is not None:
            await self._transcript_rewrite_publisher(new_message.id, result)

    @function_tool()
    async def start_booking(self) -> str:
        """Start or resume the native AloSM ride-booking task for this call."""
        # LiveKit recommends carrying conversation history into a task while
        # excluding the parent instructions, so the focused task prompt remains
        # small and authoritative.
        task_context = self.chat_ctx.copy(exclude_instructions=True)
        outcome = await BookingTask(
            chat_ctx=task_context,
            state_store=self._state_store,
            session_data=self.session.userdata,
            transcript_rewriter=self._transcript_rewriter,
            transcript_rewrite_publisher=self._transcript_rewrite_publisher,
        )
        return outcome.message

    async def _create_handoff(self, reason: str) -> str:
        if self._session_data is None:
            return json.dumps(
                {"status": "failed", "message": "Chưa có phiên để chuyển tổng đài viên."},
                ensure_ascii=False,
            )
        current = self._session_data.handoff
        if current is not None and current.status in {"pending", "accepted", "connected"}:
            return json.dumps(
                {"status": current.status, "handoff_id": current.handoff_id},
                ensure_ascii=False,
            )
        room = getattr(getattr(self.session, "room_io", None), "room", None)
        room_name = getattr(room, "name", None)
        try:
            record = await self._handoffs.create(self._session_data, reason=reason, room_name=room_name)
            self._session_data.handoff_requested = True
            self._session_data.handoff = HandoffState(
                handoff_id=str(record["handoff_id"]),
                status="pending",
                reason_code=str(record.get("reason_code") or "USER_REQUEST"),
                room_name=str(record.get("room_name") or room_name or "") or None,
            )
            self._session_data.record_failure(
                "HANDOFF_REQUIRED",
                "Yêu cầu đã được chuyển tới tổng đài viên.",
                retryable=False,
                fallback_action="handoff",
            )
            await self._state_store.save(self._session_data)
            await publish_booking_state(self.session)
            return json.dumps(
                {
                    "status": "pending",
                    "handoff_id": record["handoff_id"],
                    "instruction": "Đã tạo yêu cầu. Hãy báo khách chờ tổng đài viên nhận cuộc gọi.",
                },
                ensure_ascii=False,
            )
        except Exception:
            logger.exception("failed to create top-level human handoff session=%s", self._session_data.app_session_id)
            self._session_data.record_failure(
                "HANDOFF_REQUIRED",
                "Chưa thể tạo yêu cầu chuyển tổng đài viên.",
                retryable=True,
                fallback_action="retry",
            )
            await publish_booking_state(self.session)
            return json.dumps(
                {"status": "failed", "message": "Chưa thể tạo yêu cầu chuyển tổng đài viên."},
                ensure_ascii=False,
            )

    @function_tool()
    async def request_handoff(self, reason: str) -> str:
        """Create a human operator handoff for any point in the conversation.

        This top-level tool is intentionally available before booking starts;
        BookingTask exposes the same LiveKit-native operation while a booking
        task is active.
        """
        return await self._create_handoff(reason)

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

    @function_tool()
    async def search_knowledge(self, query: str, top_k: int = 3) -> str:
        """Retrieve approved AloSM policy/FAQ context for a non-booking question.

        This is a local, read-only lookup over the versioned policy catalog. It
        must not be used to calculate a route quote or mutate booking state.
        """
        normalized_query = query.strip()
        if not normalized_query:
            return json.dumps(
                {"found": False, "results": [], "reason": "EMPTY_QUERY"},
                ensure_ascii=False,
            )
        bounded_top_k = max(1, min(int(top_k), 3))
        results = await self._knowledge_service.retrieve(normalized_query, top_k=bounded_top_k)
        catalog_version = self._knowledge_service.retriever.catalog.catalog_version
        return json.dumps(
            {
                "found": bool(results),
                "catalog_version": catalog_version,
                "results": [
                    {
                        "content": item["content"],
                        "source": item["source"],
                        "citation_id": item["citation_id"],
                        "score": item["score"],
                        "effective_at": (
                            item["effective_at"].isoformat()
                            if hasattr(item["effective_at"], "isoformat")
                            else item["effective_at"]
                        ),
                    }
                    for item in results
                ],
                "instruction": (
                    "Chỉ trả lời dựa trên results và nói rõ khi không có kết quả."
                    if results
                    else "Không có chính sách phù hợp trong catalog; không được suy đoán."
                ),
            },
            ensure_ascii=False,
        )

    @function_tool()
    async def get_vehicle_options(self) -> str:
        """List the vehicle classes and luggage capacity from the pricing catalog.

        This read-only catalog lookup intentionally does not calculate a fare;
        route-specific pricing remains inside BookingTask.estimate_fare.
        """
        catalog = self._pricing_service.catalog
        return json.dumps(
            {
                "catalog_version": catalog.version,
                "region": catalog.region,
                "pricing_status": catalog.status,
                "currency": catalog.currency,
                "options": [
                    {
                        "vehicle_type": vehicle_type,
                        "display_name": vehicle.display_name,
                        "capacity": vehicle.capacity,
                        "luggage_capacity": vehicle.luggage_capacity,
                    }
                    for vehicle_type, vehicle in catalog.vehicles.items()
                ],
                "instruction": (
                    "Đọc display_name, sức chứa và hành lý; không đọc mã vehicle_type. "
                    "Muốn biết giá cho một lộ trình thì phải bắt đầu quy trình đặt xe."
                ),
            },
            ensure_ascii=False,
        )
