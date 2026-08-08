from __future__ import annotations

from typing import TypedDict


class AgentState(TypedDict, total=False):
    """State schema cho LangGraph agent.

    Mỗi node đọc và ghi vào state này.
    total=False cho phép tất cả fields là optional.
    """

    query: str
    context: str
    analysis: str
    response: str
    error: str
    metadata: dict
    session_id: str
    intent: str
    pickup: dict
    destination: dict
    vehicle_type: str
    confirmation_status: str
    asr_confidence: float
    failed_count: int
    last_user_text: str
    last_action: str
    tool_result: dict
    handoff_candidate: bool
    handoff_reason: str
    booking_id: str
    handoff_triggered: bool
