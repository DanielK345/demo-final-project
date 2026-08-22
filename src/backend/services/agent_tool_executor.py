from __future__ import annotations

import logging
from uuid import uuid4

from src.agents.schemas import ToolCall, ToolName, ToolResult, ToolStatus
from src.agents.state import AgentState
from src.backend.config import get_settings
from src.backend.services.booking_service import BookingService
from src.backend.services.knowledge_service import KnowledgeService
from src.backend.services.place_search_service import PlaceSearchService
from src.backend.services.pricing_service import PricingService
from src.backend.services.quote_service import QuoteService
from src.backend.services.trip_service import TripService

logger = logging.getLogger(__name__)


class AgentToolExecutor:
    """Thực thi các tool mà Core Agent (nhánh feature/agentic-ai) gọi tới — xem
    src/agents/docs/BACKEND_INTEGRATION.md §6 (bảng tool_name -> backend integration).
    Mỗi nhánh dưới đây gọi 1 service thật (PlaceSearchService/PricingService/
    BookingService/TripService/KnowledgeService), không còn trả dữ liệu hardcode như
    bản MVP trước (giá cước cố định 85.000đ mọi chuyến, FAQ luôn 2 câu giống nhau,
    trạng thái chuyến luôn "Đang đến điểm đón")."""

    def __init__(
        self,
        place_search: PlaceSearchService | None = None,
        pricing: PricingService | None = None,
        booking_service: BookingService | None = None,
        trip_service: TripService | None = None,
        knowledge_service: KnowledgeService | None = None,
    ) -> None:
        self._place_search = place_search or PlaceSearchService()
        self._pricing = pricing or PricingService()
        self._quotes = QuoteService(pricing=self._pricing)
        self._durable = get_settings().app_env != "test"
        self._booking_service = booking_service or BookingService()
        self._trip_service = trip_service or TripService()
        self._knowledge_service = knowledge_service or KnowledgeService()

    async def execute(
        self,
        tool_call: ToolCall,
        *,
        session_id: str,
        user_id: str | None,
        agent_state: AgentState,
    ) -> ToolResult:
        try:
            data = await self._dispatch(tool_call, session_id=session_id, user_id=user_id, agent_state=agent_state)
            return ToolResult(
                tool_name=tool_call.tool_name,
                call_id=tool_call.call_id,
                status=ToolStatus.SUCCESS,
                data=data,
            )
        except Exception as exc:
            logger.warning("Tool %s failed for session %s: %s", tool_call.tool_name, session_id, exc)
            return ToolResult(
                tool_name=tool_call.tool_name,
                call_id=tool_call.call_id,
                status=ToolStatus.ERROR,
                data={},
                error=str(exc)[:500],
                error_code="EXECUTOR_ERROR",
                retryable=True,
            )

    async def _dispatch(
        self,
        tool_call: ToolCall,
        *,
        session_id: str,
        user_id: str | None,
        agent_state: AgentState,
    ) -> dict[str, object]:
        params = tool_call.params

        if tool_call.tool_name is ToolName.SEARCH_PLACE:
            query = str(params["query"])
            return {"candidates": self._place_search.search(query)}

        if tool_call.tool_name is ToolName.GET_VEHICLE_OPTIONS:
            if user_id is None:
                raise ValueError("AUTHENTICATED_USER_REQUIRED_FOR_QUOTE")
            return {
                "options": await self._quotes.vehicle_options(
                    user_id=user_id,
                    session_id=session_id,
                    pickup_place_id=str(params["pickup_place_id"]),
                    destination_place_id=str(params["destination_place_id"]),
                    passenger_count=int(params["passenger_count"]),
                    luggage_count=params.get("luggage_count"),
                )
            }

        if tool_call.tool_name is ToolName.ESTIMATE_FARE:
            if user_id is None:
                raise ValueError("AUTHENTICATED_USER_REQUIRED_FOR_QUOTE")
            return await self._quotes.issue_quote(
                user_id=user_id,
                session_id=session_id,
                pickup_place_id=str(params["pickup_place_id"]),
                destination_place_id=str(params["destination_place_id"]),
                vehicle_type=str(params["vehicle_type"]),
            )

        if tool_call.tool_name is ToolName.CREATE_BOOKING:
            return await self._create_booking(params, session_id=session_id, user_id=user_id, agent_state=agent_state)

        if tool_call.tool_name is ToolName.CANCEL_BOOKING:
            booking_id = str(params["booking_id"])
            cancelled = (
                self._booking_service.cancel_booking(booking_id, str(params["idempotency_key"]))
                if not self._durable
                else await self._booking_service.cancel_booking_durable(
                    booking_id, str(params["idempotency_key"]), user_id
                )
            )
            if cancelled is None:
                raise ValueError(f"Không tìm thấy booking để huỷ: {booking_id}")
            return {"booking_id": booking_id, "status": str(cancelled["status"])}

        if tool_call.tool_name is ToolName.LOOKUP_TRIP:
            return await self._lookup_trip(params, user_id=user_id)

        if tool_call.tool_name is ToolName.RETRIEVE_KNOWLEDGE:
            query = str(params["query"])
            documents = await self._knowledge_service.retrieve(query)
            return {"documents": documents}

        if tool_call.tool_name is ToolName.CREATE_HANDOFF:
            reason = str(params.get("reason", ""))
            logger.info("Handoff requested for session %s: %s", session_id, reason)
            return {"handoff_id": f"handoff_{uuid4().hex[:8]}", "status": "pending"}

        raise ValueError(f"Unsupported tool: {tool_call.tool_name}")

    async def _create_booking(
        self,
        params: dict[str, object],
        *,
        session_id: str,
        user_id: str | None,
        agent_state: AgentState,
    ) -> dict[str, object]:
        if user_id is None:
            raise ValueError("AUTHENTICATED_USER_REQUIRED_FOR_BOOKING")
        if not self._durable:
            vehicle_type = str(params["vehicle_type"])
            fare = self._pricing.estimate_fare(
                pickup_place_id=str(params["pickup_place_id"]),
                destination_place_id=str(params["destination_place_id"]),
                vehicle_type=vehicle_type,
            )
            if str(params["fare_estimate_id"]) != str(fare["estimate_id"]):
                raise ValueError("Fare estimate does not match the confirmed route and vehicle")
            result = self._booking_service.create_booking(
                {
                    "idempotency_key": params["idempotency_key"],
                    "estimated_fare": fare["fare_amount"],
                    "user_id": user_id,
                    "pickup": None,
                    "destination": None,
                    "vehicle_type": vehicle_type,
                }
            )
            return {
                "booking_id": str(result["booking_id"]),
                "status": "CONFIRMED",
                "eta_minutes": fare.get("eta_minutes"),
                "fare_amount": result.get("estimated_fare"),
                "currency": "VND",
            }
        booking_state = agent_state.collected_data.get("booking", {})
        pickup = booking_state.get("pickup") if isinstance(booking_state, dict) else None
        destination = booking_state.get("destination") if isinstance(booking_state, dict) else None
        booking = await self._booking_service.create_booking_from_quote(
            {
                "quote_id": params["fare_estimate_id"],
                "fare_estimate_id": params["fare_estimate_id"],
                "idempotency_key": params["idempotency_key"],
                "session_id": session_id,
                "user_id": user_id,
                "pickup_place_id": params["pickup_place_id"],
                "destination_place_id": params["destination_place_id"],
                "vehicle_type": params["vehicle_type"],
                "pickup": pickup,
                "destination": destination,
            }
        )
        return {
            "booking_id": str(booking["booking_id"]),
            "status": str(booking["status"]),
            "eta_minutes": booking.get("eta_minutes"),
            "fare_amount": booking.get("quoted_fare_amount"),
            "currency": booking.get("currency", "VND"),
            "quote_id": booking.get("quote_id"),
        }

    async def _lookup_trip(self, params: dict[str, object], *, user_id: str | None) -> dict[str, object]:
        booking_id = params.get("booking_id")
        if booking_id:
            booking = (
                self._booking_service.get_booking(str(booking_id))
                if not self._durable
                else await self._booking_service.get_booking_durable(str(booking_id))
            )
            if booking is None or (user_id is not None and booking.get("user_id") != user_id):
                return {"found": False}
            live = (
                self._trip_service.get_status_for_booking(str(booking_id))
                if not self._durable
                else await self._trip_service.get_status_for_booking_durable(str(booking_id))
            )
            return {
                "found": True,
                "booking_id": str(booking_id),
                "status": str(live["status"]),
                "eta_minutes": live.get("eta_minutes"),
            }

        phone_number = params.get("phone_number")
        if phone_number:
            if self._durable and user_id is not None:
                all_bookings = await self._booking_service.list_bookings_for_user_durable(user_id)
                matches = [item for item in all_bookings if item.get("status") not in {"CANCELLED", "COMPLETED"}][:5]
            else:
                matches = self._booking_service.find_active_bookings_for_phone(str(phone_number))
            if not matches:
                return {"found": False}
            trips = []
            for booking in matches:
                live = (
                    self._trip_service.get_status_for_booking(str(booking["booking_id"]))
                    if not self._durable
                    else await self._trip_service.get_status_for_booking_durable(str(booking["booking_id"]))
                )
                pickup = booking.get("pickup")
                destination = booking.get("destination")
                trips.append(
                    {
                        "booking_id": str(booking["booking_id"]),
                        "status": str(live["status"]),
                        "eta_minutes": live.get("eta_minutes"),
                        "pickup_label": pickup.get("display_name") if isinstance(pickup, dict) else None,
                        "destination_label": destination.get("display_name") if isinstance(destination, dict) else None,
                    }
                )
            return {"found": True, "trips": trips}

        return {"found": False}
