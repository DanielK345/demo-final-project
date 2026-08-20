import json
from types import SimpleNamespace

import pytest

from src.backend.services.transcript_rewriter import (
    OpenAITranscriptRewriter,
    _confirmation_surface,
    _contextual_booking_language_rewrite,
    _contextual_candidate_alias_rewrite,
    _is_context_grounded_selection,
    _mask_sensitive_values,
    _minimal_context,
    _relevant_alias_mappings,
    _restore_sensitive_values,
    _RewriteOutput,
)
from src.voice.text.place_aliases import PlaceAliasCatalog


def _selection_context() -> dict[str, object]:
    return {
        "current_workflow": "RIDE_BOOKING",
        "current_step": "SELECT_PICKUP_CANDIDATE",
        "user_phone": "0901234567",
        "agent_state": {
            "current_workflow": "RIDE_BOOKING",
            "current_step": "SELECT_PICKUP_CANDIDATE",
            "collected_data": {
                "booking": {
                    "pickup_query": "VinUni",
                    "pickup_candidates": [
                        {
                            "display_name": "Cổng chính VinUni",
                            "address": "Đường San Hô, Gia Lâm, Hà Nội",
                            "asr_aliases": ["cổng thành cũng", "cổng chính Vi Ni"],
                        },
                        {
                            "display_name": "Cổng phụ VinUni",
                            "address": "Vinhomes Ocean Park, Gia Lâm, Hà Nội",
                        },
                        {
                            "display_name": "Cổng ký túc xá VinUni",
                            "address": "Ký túc xá VinUni, Gia Lâm, Hà Nội",
                        },
                    ],
                }
            },
            "conversation_history": [
                {
                    "role": "ASSISTANT",
                    "content": "Bạn xác nhận điểm đón cụ thể nào tại VinUni?",
                }
            ],
        },
    }


class _FakeResponses:
    def __init__(self, parsed: _RewriteOutput) -> None:
        self.parsed = parsed
        self.request: dict[str, object] | None = None

    async def parse(self, **kwargs: object) -> SimpleNamespace:
        self.request = kwargs
        return SimpleNamespace(output_parsed=self.parsed)


class _FakeClient:
    def __init__(self, parsed: _RewriteOutput) -> None:
        self.responses = _FakeResponses(parsed)


def test_sensitive_values_are_masked_and_restored_exactly():
    raw = "Gọi 0901234567, mã AB-123 lúc 19:30 hoặc email a1@example.com"

    masked, replacements = _mask_sensitive_values(raw)

    assert "0901234567" not in masked
    assert "AB-123" not in masked
    assert "19:30" not in masked
    assert "a1@example.com" not in masked
    assert set(replacements) == {"<NUM_1>", "<ID_1>", "<NUM_2>", "<EMAIL_1>"}
    assert _restore_sensitive_values(masked, replacements) == raw


def test_only_workflow_and_step_are_sent_as_context():
    compact = _minimal_context(
        {
            "current_workflow": "RIDE_BOOKING",
            "current_step": "COLLECT_PICKUP",
            "user_phone": "0901234567",
            "conversation_history": [{"role": "user", "content": "đón tôi ở nhà"}],
        }
    )

    assert compact == {
        "current_workflow": "RIDE_BOOKING",
        "current_step": "COLLECT_PICKUP",
    }


def test_selection_context_includes_candidates_but_excludes_personal_data():
    compact = _minimal_context(_selection_context())

    assert compact["location_selection"] == {
        "target": "pickup",
        "original_query": "VinUni",
        "candidates": [
            {
                "display_name": "Cổng chính VinUni",
                "address": "Đường San Hô, Gia Lâm, Hà Nội",
                "asr_aliases": ["cổng thành cũng", "cổng chính Vi Ni"],
            },
            {
                "display_name": "Cổng phụ VinUni",
                "address": "Vinhomes Ocean Park, Gia Lâm, Hà Nội",
            },
            {
                "display_name": "Cổng ký túc xá VinUni",
                "address": "Ký túc xá VinUni, Gia Lâm, Hà Nội",
            },
        ],
    }
    assert compact["last_assistant_message"] == "Bạn xác nhận điểm đón cụ thể nào tại VinUni?"
    assert "0901234567" not in json.dumps(compact, ensure_ascii=False)


def test_selected_booking_places_are_included_as_exact_rewrite_context():
    context = {
        "current_step": "COLLECT_DESTINATION",
        "agent_state": {
            "collected_data": {
                "booking": {
                    "pickup": {
                        "place_id": "vinuni-main-gate",
                        "display_name": "Cổng chính VinUni",
                    },
                    "destination": json.dumps(
                        {
                            "place_id": "ho-guom",
                            "display_name": "Hồ Gươm",
                        }
                    ),
                }
            }
        },
    }

    compact = _minimal_context(context)

    assert compact["known_booking_places"] == {
        "pickup": "Cổng chính VinUni",
        "destination": "Hồ Gươm",
    }
    assert "place_id" not in json.dumps(compact, ensure_ascii=False)


@pytest.mark.asyncio
async def test_selected_booking_place_is_prioritized_in_rewrite_terms():
    client = _FakeClient(
        _RewriteOutput(
            normalized_text="Đón tôi ở Cổng chính VinUni",
            meaning_preserved=True,
            requires_clarification=False,
            confidence=0.99,
            change_types=["spelling", "domain_term"],
        )
    )
    rewriter = OpenAITranscriptRewriter(
        api_key="",
        model="rewrite-test",
        timeout_seconds=1,
        glossary=["AloSM", "VinUni"],
        client=client,
    )
    context = {
        "current_step": "COLLECT_DESTINATION",
        "agent_state": {
            "collected_data": {
                "booking": {
                    "pickup": {"display_name": "Cổng chính VinUni"},
                }
            }
        },
    }

    result = await rewriter.rewrite(
        "Đón tôi ở cổng chính Bin Unite",
        session_context=context,
        session_id="sess-test",
    )

    payload = json.loads(str(client.responses.request["input"]))
    assert payload["canonical_terms"][:2] == ["Cổng chính VinUni", "AloSM"]
    assert result.normalized_text == "Đón tôi ở Cổng chính VinUni"


def test_large_phonetic_repair_is_allowed_only_when_grounded_in_current_candidates():
    raw = "muon thanh mua"
    candidate = "muon cong chinh vinuni"

    assert _is_context_grounded_selection(raw, candidate, _selection_context()) is True
    assert _is_context_grounded_selection(raw, candidate, None) is False


def test_contextual_candidate_alias_only_applies_in_active_selection_state():
    compact = _minimal_context(_selection_context())

    assert _contextual_candidate_alias_rewrite("CỔNG THÀNH CŨNG", compact) == "Cổng chính VinUni"
    assert _contextual_candidate_alias_rewrite("CỔNG THÀNH CŨNG", {}) is None
    assert _contextual_candidate_alias_rewrite("không chọn cổng thành cũng", compact) is None


def test_booking_language_rewrite_repairs_pickup_homophone_only_in_location_step():
    assert (
        _contextual_booking_language_rewrite(
            "Điểm đoán là VinUni",
            {"current_step": "COLLECT_PICKUP"},
        )
        == "Điểm đón là VinUni"
    )
    assert (
        _contextual_booking_language_rewrite(
            "Tôi đang đoán kết quả",
            {"current_step": "COLLECT_VEHICLE"},
        )
        == "Tôi đang đoán kết quả"
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("cũng chính VinUni", "cổng chính VinUni"),
        ("cũng phụ VinUni", "cổng phụ VinUni"),
        ("cũng trước trường", "cổng trước trường"),
        ("cũng sau trường", "cổng sau trường"),
        ("cũng số 2", "cổng số 2"),
        ("cũng 3", "cổng 3"),
        ("cũng A", "cổng A"),
    ],
)
def test_booking_language_rewrite_enforces_gate_homophones(raw: str, expected: str):
    assert _contextual_booking_language_rewrite(raw, {"current_step": "COLLECT_PICKUP"}) == expected


def test_booking_language_rewrite_uses_known_place_as_gate_name():
    assert (
        _contextual_booking_language_rewrite(
            "cũng VinUni",
            {
                "current_step": "COLLECT_PICKUP",
                "known_booking_places": {"pickup": "VinUni"},
            },
        )
        == "cổng VinUni"
    )


def test_gate_homophone_is_repaired_while_correcting_an_already_complete_booking():
    assert (
        _contextual_booking_language_rewrite(
            "Sửa điểm đón thành cũng chính VinUni",
            {"current_step": "PRESENT_QUOTE"},
        )
        == "Sửa điểm đón thành cổng chính VinUni"
    )


@pytest.mark.asyncio
async def test_gate_homophone_cannot_be_reintroduced_by_llm_output():
    client = _FakeClient(
        _RewriteOutput(
            normalized_text="Sửa điểm đón thành cũng chính VinUni",
            meaning_preserved=True,
            requires_clarification=False,
            confidence=0.99,
            change_types=["spelling", "domain_term"],
        )
    )
    rewriter = OpenAITranscriptRewriter(
        api_key="",
        model="rewrite-test",
        timeout_seconds=1,
        client=client,
    )

    result = await rewriter.rewrite(
        "Sửa điểm đón thành cũng chính VinUni",
        session_context={"current_step": "PRESENT_QUOTE"},
        session_id="sess-test",
    )

    assert result.normalized_text == "Sửa điểm đón thành cổng chính VinUni"


def test_relevant_alias_mappings_include_phonetically_close_vinuni_aliases():
    mappings = _relevant_alias_mappings("Điểm đón là Pinn Yuni", PlaceAliasCatalog.load())

    assert mappings[0]["canonical_name"] == "VinUni"
    assert "Bin Yuni" in mappings[0]["asr_aliases"]


@pytest.mark.asyncio
async def test_contextual_alias_overrides_wrong_llm_candidate_selection():
    client = _FakeClient(
        _RewriteOutput(
            normalized_text="Cổng phụ VinUni",
            meaning_preserved=True,
            requires_clarification=False,
            confidence=0.97,
            change_types=["spelling", "domain_term"],
        )
    )
    rewriter = OpenAITranscriptRewriter(
        api_key="",
        model="rewrite-test",
        timeout_seconds=1,
        client=client,
    )

    result = await rewriter.rewrite(
        "CỔNG THÀNH CŨNG",
        session_context=_selection_context(),
        session_id="sess-test",
    )

    assert result.applied is True
    assert result.normalized_text == "Cổng chính VinUni"
    assert result.reason == "contextual_candidate_alias"
    assert result.confidence == 1.0


@pytest.mark.asyncio
async def test_deterministic_alias_survives_a_rejected_llm_candidate():
    client = _FakeClient(
        _RewriteOutput(
            normalized_text="Một địa điểm khác",
            meaning_preserved=False,
            requires_clarification=False,
            confidence=0.2,
            change_types=["domain_term"],
        )
    )
    rewriter = OpenAITranscriptRewriter(
        api_key="",
        model="rewrite-test",
        timeout_seconds=1,
        client=client,
    )

    result = await rewriter.rewrite(
        "Điểm đoán là Vinyuni",
        session_context={"current_step": "COLLECT_PICKUP"},
        session_id="sess-test",
    )

    assert result.raw_text == "Điểm đoán là Vinyuni"
    assert result.normalized_text == "Điểm đón là VinUni"
    assert result.applied is True
    assert result.reason == "deterministic_alias"


@pytest.mark.asyncio
async def test_rewriter_uses_selection_context_to_restore_misheard_vinuni_gate():
    client = _FakeClient(
        _RewriteOutput(
            normalized_text="Muốn Cổng chính VinUni",
            meaning_preserved=True,
            requires_clarification=False,
            confidence=0.97,
            change_types=["spelling", "domain_term"],
        )
    )
    rewriter = OpenAITranscriptRewriter(
        api_key="",
        model="rewrite-test",
        timeout_seconds=1,
        client=client,
    )

    result = await rewriter.rewrite(
        "MUỐN THÀNH MUA",
        session_context=_selection_context(),
        session_id="sess-test",
    )

    assert result.applied is True
    assert result.normalized_text == "Muốn Cổng chính VinUni"
    assert result.reason == "applied"
    request_payload = json.loads(str(client.responses.request["input"]))
    assert request_payload["conversation_context"]["location_selection"]["candidates"][0][
        "display_name"
    ] == "Cổng chính VinUni"


def test_confirmation_guard_detects_diacritic_semantic_change():
    assert _confirmation_surface("dung roi") != _confirmation_surface("đúng rồi")
