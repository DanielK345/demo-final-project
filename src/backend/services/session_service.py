from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from src.agents.agent import LLMAgent
from src.agents.schemas import ActionType, AgentInput, AgentAction
from src.agents.state import AgentState
from src.backend.services.agent_tool_executor import AgentToolExecutor
from src.backend.services.conversation_logger import ConversationLogger


class SessionService:
    sessions: dict[str, dict[str, object]] = {}
    _agent = LLMAgent()
    _tool_executor = AgentToolExecutor()
    _conversation_logger = ConversationLogger()
    _MAX_TOOL_TURNS = 8

    def create_session(self, user_id: str, channel: str, device_id: str | None = None) -> dict[str, object]:
        session_id = f"sess_{uuid4().hex[:12]}"
        now = datetime.now(UTC).isoformat()
        log_path = self._conversation_logger.start_session(
            session_id=session_id,
            user_id=user_id,
            channel=channel,
            device_id=device_id,
        )
        self.sessions[session_id] = {
            "session_id": session_id,
            "call_id": f"call_{uuid4().hex[:8]}",
            "user_id": user_id,
            "status": "ACTIVE",
            "channel": channel,
            "device_id": device_id,
            "created_at": now,
            "log_file": log_path.name,
            "intent": None,
            "pickup": None,
            "destination": None,
            "vehicle_type": "4_SEAT",
            "confirmation_status": "pending",
            "failed_count": 0,
            "booking_id": None,
            "handoff_triggered": False,
            "booking_lifecycle_status": None,
            "feedback": None,
            "current_workflow": None,
            "current_step": None,
            "agent_state": None,
            "turn_sequence": 0,
        }
        return {"session_id": session_id, "status": "ACTIVE", "channel": channel, "created_at": now}

    def get_session(self, session_id: str) -> dict[str, object]:
        session = self.sessions.get(session_id)
        if session is None:
            raise KeyError("Không tìm thấy phiên hội thoại")
        return session.copy()

    def update_session(self, session_id: str, payload: dict[str, object]) -> dict[str, object]:
        session = self.sessions.get(session_id)
        if session is None:
            raise KeyError("Không tìm thấy phiên hội thoại")
        session.update(payload)
        return session.copy()

    def resume_session(self, session_id: str) -> dict[str, str]:
        session = self.sessions.get(session_id)
        if session is None:
            raise KeyError("Không tìm thấy phiên hội thoại")
        session["status"] = "ACTIVE"
        return {"session_id": session_id, "status": "resumed"}

    def end_session(self, session_id: str, reason: str) -> dict[str, str]:
        session = self.sessions.get(session_id)
        if session is None:
            raise KeyError("Không tìm thấy phiên hội thoại")
        log_file = session.get("log_file")
        if isinstance(log_file, str):
            self._conversation_logger.end_session(log_file, reason=reason)
        session.update({"status": "ENDED", "end_reason": reason})
        return {"session_id": session_id, "status": "ENDED", "ended_at": datetime.now(UTC).isoformat()}

    async def process_message(
        self,
        session_id: str,
        message: str,
        confidence: float | None = None,
        *,
        source: str = "TEXT",
    ) -> dict[str, object]:
        session = self.sessions.get(session_id)
        if session is None:
            raise KeyError("Không tìm thấy phiên hội thoại")
        if session["status"] != "ACTIVE":
            raise ValueError("Phiên hội thoại đã kết thúc")

        agent_state = self._load_agent_state(session_id, session)
        action = await self._run_agent_turn(
            session=session,
            session_id=session_id,
            agent_state=agent_state,
            transcript=message.strip(),
            stt_confidence=confidence,
        )
        agent_state = agent_state.apply(action.state_updates)
        tool_turns = 0

        while action.action_type is ActionType.CALL_TOOL and tool_turns < self._MAX_TOOL_TURNS:
            assert action.tool_call is not None
            tool_result = await self._tool_executor.execute(action.tool_call, session_id=session_id)
            action = await self._run_agent_turn(
                session=session,
                session_id=session_id,
                agent_state=agent_state,
                transcript="",
                tool_result=tool_result,
            )
            agent_state = agent_state.apply(action.state_updates)
            tool_turns += 1

        session["agent_state"] = agent_state.model_dump(mode="json")
        self._sync_legacy_session_fields(session, agent_state, action)
        response = self._format_action_response(session, agent_state, action)
        self._log_conversation_turn(
            session,
            user_message=message.strip(),
            source=source,
            stt_confidence=confidence,
            response=response,
        )
        return response

    @staticmethod
    def _next_turn_id(session: dict[str, object]) -> str:
        sequence = int(session.get("turn_sequence") or 0) + 1
        session["turn_sequence"] = sequence
        return f"turn-{sequence:03d}"

    async def _run_agent_turn(
        self,
        *,
        session: dict[str, object],
        session_id: str,
        agent_state: AgentState,
        transcript: str,
        stt_confidence: float | None = None,
        tool_result=None,
    ) -> AgentAction:
        agent_input = AgentInput(
            session_id=session_id,
            turn_id=self._next_turn_id(session),
            transcript=transcript,
            stt_confidence=stt_confidence,
            tool_result=tool_result,
        )
        return await self._agent.handle(agent_input, agent_state)

    @staticmethod
    def _load_agent_state(session_id: str, session: dict[str, object]) -> AgentState:
        raw_state = session.get("agent_state")
        if isinstance(raw_state, dict):
            return AgentState.model_validate(raw_state)
        return AgentState(session_id=session_id)

    @staticmethod
    def _sync_legacy_session_fields(
        session: dict[str, object],
        agent_state: AgentState,
        action: AgentAction,
    ) -> None:
        booking = agent_state.collected_data.get("booking", {})
        if isinstance(booking, dict):
            pickup = booking.get("pickup")
            destination = booking.get("destination")
            if isinstance(pickup, dict):
                session["pickup"] = pickup
            if isinstance(destination, dict):
                session["destination"] = destination
            if booking.get("vehicle_type"):
                session["vehicle_type"] = booking["vehicle_type"]
            if booking.get("booking_id"):
                session["booking_id"] = booking["booking_id"]
            lifecycle = booking.get("lifecycle_status")
            if lifecycle:
                session["booking_lifecycle_status"] = lifecycle
            session["booking_progress"] = SessionService._booking_progress(booking)

        session["current_workflow"] = (
            agent_state.current_workflow.value if agent_state.current_workflow else None
        )
        session["current_step"] = agent_state.current_step
        session["handoff_triggered"] = action.action_type is ActionType.HANDOFF
        if action.action_type is ActionType.END_SESSION:
            session["status"] = "ENDED"

    @staticmethod
    def _booking_progress(booking: dict[str, object]) -> dict[str, object]:
        def field_value(
            place: object,
            query: object,
        ) -> dict[str, object] | None:
            if isinstance(place, dict):
                label = place.get("display_name") or place.get("name")
                if label:
                    return {
                        "label": str(label),
                        "resolved": True,
                        "place_id": place.get("place_id"),
                    }
            if query:
                return {"label": str(query), "resolved": False, "place_id": None}
            return None

        pickup = field_value(booking.get("pickup"), booking.get("pickup_query"))
        destination = field_value(
            booking.get("destination"),
            booking.get("destination_query"),
        )
        vehicle_type = booking.get("vehicle_type")
        missing_field = None
        if pickup is None:
            missing_field = "pickup"
        elif destination is None:
            missing_field = "destination"
        elif not vehicle_type:
            missing_field = "vehicle_type"

        return {
            "pickup": pickup,
            "destination": destination,
            "vehicle_type": vehicle_type,
            "missing_field": missing_field,
            "lifecycle_status": booking.get("lifecycle_status"),
        }

    def _format_action_response(
        self,
        session: dict[str, object],
        agent_state: AgentState,
        action: AgentAction,
    ) -> dict[str, object]:
        action_name = {
            ActionType.ASK_USER: "ASK_USER",
            ActionType.RESPOND: "RESPOND",
            ActionType.HANDOFF: "HANDOFF",
            ActionType.END_SESSION: "END_SESSION",
        }.get(action.action_type, "RESPOND")

        booking = None
        booking_data = agent_state.collected_data.get("booking")
        booking_progress = None
        if isinstance(booking_data, dict):
            booking_progress = self._booking_progress(booking_data)
            if booking_data.get("booking_id"):
                booking = {
                    "booking_id": booking_data["booking_id"],
                    "status": booking_data.get("booking_status", "CONFIRMED"),
                    "lifecycle_status": booking_data.get("lifecycle_status"),
                    "estimated_fare": int(booking_data.get("fare_amount") or 85000),
                }

        message = action.message or "Em đang hỗ trợ anh/chị."
        lifecycle_status = session.get("booking_lifecycle_status")
        if lifecycle_status is None and isinstance(booking_data, dict):
            lifecycle_status = booking_data.get("lifecycle_status")

        state = {
            key: session.get(key)
            for key in (
                "current_workflow",
                "current_step",
                "pickup",
                "destination",
                "vehicle_type",
                "confirmation_status",
                "booking_id",
            )
        }
        state["booking_progress"] = booking_progress
        state["booking_lifecycle_status"] = lifecycle_status
        return {
            "message_id": f"msg_{uuid4().hex[:10]}",
            "action": action_name,
            "message": message,
            "state": state,
            "booking": booking,
        }

    @classmethod
    def _log_conversation_turn(
        cls,
        session: dict[str, object],
        *,
        user_message: str,
        source: str,
        stt_confidence: float | None,
        response: dict[str, object],
    ) -> None:
        log_file = session.get("log_file")
        if not isinstance(log_file, str) or not user_message:
            return
        cls._conversation_logger.log_turn(
            log_file,
            user_message=user_message,
            source=source,
            stt_confidence=stt_confidence,
            agent_message=str(response.get("message", "")),
            message_id=str(response.get("message_id", "")),
            action=str(response.get("action", "")),
            state=response.get("state") if isinstance(response.get("state"), dict) else None,
            booking=response.get("booking") if isinstance(response.get("booking"), dict) else None,
        )

    def submit_feedback(
        self,
        session_id: str,
        rating: int,
        comment: str | None = None,
    ) -> dict[str, object]:
        session = self.sessions.get(session_id)
        if session is None:
            raise KeyError("Không tìm thấy phiên hội thoại")
        if session.get("booking_lifecycle_status") != "SUCCESS":
            raise ValueError("Chỉ có thể đánh giá sau khi đặt xe thành công")
        feedback = {
            "rating": rating,
            "comment": comment,
            "submitted_at": datetime.now(UTC).isoformat(),
        }
        session["feedback"] = feedback
        return {"session_id": session_id, "feedback": feedback}
