from types import SimpleNamespace

import pytest
from livekit.agents import llm

from src.voice_agent.agent import AloSMAgent
from src.voice_agent.persistence import EphemeralVoiceStateStore
from src.voice_agent.session_data import AloSMSessionData, PlaceCandidate, QuoteSnapshot
from src.voice_agent.tasks import booking as booking_module
from src.voice_agent.tasks.booking import (
    BookingTask,
    can_auto_select_place,
    is_explicit_confirmation,
    requires_location_clarification,
)
from src.voice_agent.tools import PlaceToolsService


class _QuoteService:
    async def estimate(self, **_: object) -> QuoteSnapshot:
        return QuoteSnapshot(
            quote_id="quote-regression",
            pickup_place_id="pickup",
            destination_place_id="destination",
            vehicle_type="CAR_4",
            fare_amount=95_180,
            currency="VND",
            distance_km=20.0,
            eta_minutes=16,
            expires_at="2099-01-01T00:00:00+00:00",
            estimated=True,
        )


def test_agent_exposes_native_booking_entrypoint_and_authoritative_status_tool() -> None:
    assert {tool.id for tool in AloSMAgent().tools} == {
        "start_booking",
        "request_handoff",
        "get_booking_status",
        "search_knowledge",
        "get_vehicle_options",
    }


@pytest.mark.asyncio
async def test_agent_rag_tool_returns_versioned_policy_citation() -> None:
    result = await AloSMAgent().search_knowledge("Tôi muốn yêu cầu hoàn tiền")

    assert '"found": true' in result
    assert '"catalog_version": "2026-08-16"' in result
    assert '"citation_id": "policy-refund"' in result


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("question", "citation"),
    [
        ("Sau khi xác nhận giá, giá có được tự ý thay đổi không?", "policy-price-change"),
        ("Chính sách hủy chuyến và phí hủy là gì?", "policy-cancellation"),
    ],
)
async def test_livekit_faq_tool_keeps_natural_policy_questions_grounded(
    question: str,
    citation: str,
) -> None:
    result = await AloSMAgent().search_knowledge(question)

    assert f'"citation_id": "{citation}"' in result


@pytest.mark.asyncio
async def test_agent_vehicle_options_tool_reads_pricing_catalog_without_quote() -> None:
    result = await AloSMAgent().get_vehicle_options()

    assert '"pricing_status": "DEMO"' in result
    assert '"display_name": "AloSM Car 4 chỗ"' in result
    assert '"luggage_capacity":' in result
    assert '"fare_amount"' not in result


@pytest.mark.asyncio
async def test_parent_booking_status_never_invents_a_booking_id() -> None:
    userdata = AloSMSessionData(
        app_session_id="session",
        call_id="call",
        user_id="user",
        participant_identity="participant",
    )

    status = await AloSMAgent(session_data=userdata).get_booking_status()

    assert '"created": false' in status
    assert '"booking_id": null' in status
    assert "Chuyến chưa được tạo" in status


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

    assert "điểm đón đã khóa Bến xe Mỹ Đình" in instructions
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
        "request_handoff",
        "search_place",
        "select_place",
        "set_vehicle_type",
        "unlock_booking_field",
    }
    assert task.chat_ctx.messages()[-1].text_content == "Đặt xe từ VinUni đến Hồ Gươm"


@pytest.mark.asyncio
async def test_estimate_fare_atomically_starts_confirmation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    userdata = AloSMSessionData(
        app_session_id="session",
        call_id="call",
        user_id="user",
        participant_identity="participant",
    )
    pickup = PlaceCandidate(
        place_id="pickup",
        display_name="Cổng chính VinUni",
        address="Đường San Hô, Gia Lâm, Hà Nội",
        provider="test",
    )
    destination = PlaceCandidate(
        place_id="destination",
        display_name="Bưu điện Hà Nội",
        address="Đinh Tiên Hoàng, Hoàn Kiếm, Hà Nội",
        provider="test",
    )
    draft = userdata.booking_draft
    draft.set_candidates("pickup", "VinUni", [pickup])
    draft.select_place("pickup", pickup.place_id)
    draft.set_candidates("destination", "Bưu điện Hà Nội", [destination])
    draft.select_place("destination", destination.place_id)
    draft.set_vehicle_type("CAR_4")
    task = BookingTask(quotes=_QuoteService(), state_store=EphemeralVoiceStateStore())

    async def _publish(_: object) -> None:
        return None

    monkeypatch.setattr(booking_module, "publish_booking_state", _publish)
    context = SimpleNamespace(userdata=userdata, session=object())

    result = await BookingTask.estimate_fare._func(task, context)

    assert draft.confirmation_status == "awaiting"
    assert draft.confirmation_fingerprint == draft.quote.fingerprint
    assert "Hãy hỏi xác nhận rõ ràng" in result


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


def test_booking_field_unlock_requires_explicit_targeted_change() -> None:
    assert is_explicit_booking_field_change("Sửa điểm đến thành Hồ Tây", "destination") is True
    assert is_explicit_booking_field_change("Đón tôi ở cổng chính VinUni", "pickup") is True
    assert is_explicit_booking_field_change("Tôi muốn xe bảy chỗ", "vehicle_type") is True
    assert is_explicit_booking_field_change("Sửa điểm đến thành Hồ Tây", "pickup") is False
    assert is_explicit_booking_field_change("Thông tin đó đúng rồi", "destination") is False


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


def test_only_unique_exact_or_alias_place_can_skip_clarification() -> None:
    service = PlaceToolsService()

    assert can_auto_select_place(service.search("Đại học Bách khoa Hà Nội")) is True
    assert can_auto_select_place(service.search("Cổng chính VinUni")) is True
    assert can_auto_select_place(service.search("Bưu điện Hà Nội")) is True
    assert can_auto_select_place(service.search("Đại học Ếch Khoa Hà Nội")) is False
    assert can_auto_select_place(service.search("VinUni")) is False
    assert can_auto_select_place(service.search("Hồ Gươm")) is False
