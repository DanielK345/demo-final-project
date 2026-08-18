import pytest
from livekit.agents import llm

from src.voice_agent.agent import AloSMAgent
from src.voice_agent.session_data import AloSMSessionData, PlaceCandidate
from src.voice_agent.tasks.booking import (
    BookingTask,
    is_explicit_confirmation,
    requires_location_clarification,
)
from src.voice_agent.tools import PlaceToolsService


def test_agent_exposes_one_booking_task_entrypoint() -> None:
    assert [tool.id for tool in AloSMAgent().tools] == ["start_booking"]


def test_recovered_booking_is_available_to_the_parent_agent_without_full_history() -> None:
    userdata = AloSMSessionData(
        app_session_id="session",
        call_id="call",
        user_id="user",
        participant_identity="participant",
        recovered=True,
    )
    pickup = PlaceCandidate(
        place_id="my-dinh",
        display_name="Bến xe Mỹ Đình",
        address="Bến xe Mỹ Đình",
        provider="test",
    )
    userdata.booking_draft.set_candidates("pickup", "Mỹ Đình", [pickup])
    userdata.booking_draft.select_place("pickup", pickup.place_id)

    instructions = AloSMAgent(session_data=userdata).instructions

    assert "điểm đón Bến xe Mỹ Đình" in instructions
    assert "không có lịch sử" in instructions
    assert "pickup_candidates" not in instructions


@pytest.mark.asyncio
async def test_booking_task_uses_native_function_tools() -> None:
    chat_ctx = llm.ChatContext.empty()
    chat_ctx.add_message(role="user", content="Đặt xe từ VinUni đến Hồ Gươm")
    task = BookingTask(chat_ctx=chat_ctx)
    tool_names = {tool.id for tool in task.tools}

    assert tool_names == {
        "cancel_booking_flow",
        "confirm_booking",
        "create_booking",
        "estimate_fare",
        "prepare_booking_confirmation",
        "request_handoff",
        "search_place",
        "select_place",
        "set_vehicle_type",
    }
    assert task.chat_ctx.messages()[-1].text_content == "Đặt xe từ VinUni đến Hồ Gươm"


def test_terminal_task_tools_follow_livekit_complete_without_narrating_inside_task() -> None:
    for tool in (
        BookingTask.create_booking,
        BookingTask.request_handoff,
        BookingTask.cancel_booking_flow,
    ):
        assert tool.__annotations__["return"] in {None, type(None), "None"}


def test_explicit_confirmation_rejects_negative_or_ambiguous_text() -> None:
    assert is_explicit_confirmation("Tôi xác nhận đặt chuyến này") is True
    assert is_explicit_confirmation("Đúng rồi, đặt xe đi") is True
    assert is_explicit_confirmation("Không đúng, sửa điểm đến") is False
    assert is_explicit_confirmation("Ừ") is False


def test_native_transcript_confidence_only_blocks_low_confidence_audio() -> None:
    audio = llm.ChatMessage(
        role="user",
        content=["VinUni"],
        transcript_confidence=0.4,
    )
    text = llm.ChatMessage(role="user", content=["VinUni"])

    assert requires_location_clarification(audio, 0.65) is True
    assert requires_location_clarification(text, 0.65) is False


def test_place_tool_reuses_hanoi_gazetteer_without_echo_fallback() -> None:
    service = PlaceToolsService()

    assert service.search("VinUni")
    assert service.search("Trường Đại học Bách Khoa Hà Nội")[0].display_name == "Đại học Bách khoa Hà Nội"
    assert service.search("Đại học Ếch Khoa Hà Nội")[0].display_name == "Đại học Bách khoa Hà Nội"
    assert service.search("phố Hồ Hà Nội") == []
    assert service.search("một địa điểm hoàn toàn không tồn tại") == []
