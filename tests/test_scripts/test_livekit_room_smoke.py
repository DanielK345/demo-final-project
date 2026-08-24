import pytest

from scripts.livekit_room_smoke import (
    _durable_booking_checks,
    _request_quote_confirmation,
    _select_location_with_clarification,
)


@pytest.mark.asyncio
async def test_location_selection_answers_livekit_task_clarification() -> None:
    state: dict[str, object] = {"destination": None}
    turns: list[str] = []

    async def send_turn(text: str) -> None:
        turns.append(text)
        if len(turns) == 2:
            state["destination"] = {"display_name": "Bưu điện Hà Nội"}

    await _select_location_with_clarification(
        target="destination",
        selection_text="Tôi chọn Bưu điện Hà Nội làm điểm đến.",
        clarification_text="Đúng, tôi xác nhận chọn Bưu điện Hà Nội làm điểm đến.",
        send_turn=send_turn,
        current_state=lambda: state,
    )

    assert turns == [
        "Tôi chọn Bưu điện Hà Nội làm điểm đến.",
        "Đúng, tôi xác nhận chọn Bưu điện Hà Nội làm điểm đến.",
    ]


@pytest.mark.asyncio
async def test_location_selection_does_not_add_an_unneeded_turn() -> None:
    state: dict[str, object] = {"pickup": None}
    turns: list[str] = []

    async def send_turn(text: str) -> None:
        turns.append(text)
        state["pickup"] = {"display_name": "Cổng chính VinUni"}

    await _select_location_with_clarification(
        target="pickup",
        selection_text="Tôi chọn Cổng chính VinUni.",
        clarification_text="Đúng, tôi xác nhận chọn Cổng chính VinUni.",
        send_turn=send_turn,
        current_state=lambda: state,
    )

    assert turns == ["Tôi chọn Cổng chính VinUni."]


@pytest.mark.asyncio
async def test_location_selection_fails_after_bounded_clarification() -> None:
    state: dict[str, object] = {"destination": None}

    async def send_turn(_text: str) -> None:
        return None

    with pytest.raises(TimeoutError, match="destination was not selected"):
        await _select_location_with_clarification(
            target="destination",
            selection_text="selection",
            clarification_text="clarification",
            send_turn=send_turn,
            current_state=lambda: state,
        )


@pytest.mark.asyncio
async def test_quote_followup_advances_a_multi_turn_agent_task() -> None:
    state: dict[str, object] = {"quote": None, "confirmation_status": "not_requested"}
    turns: list[str] = []

    async def send_turn(text: str) -> None:
        turns.append(text)
        state.update({"quote": {"fare_amount": 100_000}, "confirmation_status": "awaiting"})

    await _request_quote_confirmation(send_turn=send_turn, current_state=lambda: state)

    assert len(turns) == 1


def test_durable_booking_checks_require_matching_authoritative_rows() -> None:
    checks = _durable_booking_checks(
        session_id="sess_1",
        user_id="guest_1",
        quote_id="quote_1",
        booking_id="book_1",
        session_row={
            "status": "ENDED",
            "booking_id": "book_1",
            "booking_lifecycle_status": "SUCCESS",
            "confirmation_status": "confirmed",
            "voice_state_revision": 10,
        },
        quote_row={
            "quote_id": "quote_1",
            "session_id": "sess_1",
            "user_id": "guest_1",
            "status": "CONSUMED",
        },
        booking_row={
            "booking_id": "book_1",
            "quote_id": "quote_1",
            "session_id": "sess_1",
            "user_id": "guest_1",
        },
    )

    assert all(checks.values())


def test_durable_booking_checks_reject_cross_session_booking() -> None:
    checks = _durable_booking_checks(
        session_id="sess_1",
        user_id="guest_1",
        quote_id="quote_1",
        booking_id="book_1",
        session_row=None,
        quote_row=None,
        booking_row={
            "booking_id": "book_1",
            "quote_id": "quote_1",
            "session_id": "sess_other",
            "user_id": "guest_1",
        },
    )

    assert checks["durable_booking_matches"] is False
