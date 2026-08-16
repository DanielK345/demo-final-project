import json
from types import SimpleNamespace

import pytest

from src.backend.services.transcript_rewriter import (
    OpenAITranscriptRewriter,
    _confirmation_surface,
    _is_context_grounded_selection,
    _mask_sensitive_values,
    _minimal_context,
    _restore_sensitive_values,
    _RewriteOutput,
)


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


def test_large_phonetic_repair_is_allowed_only_when_grounded_in_current_candidates():
    raw = "muon thanh mua"
    candidate = "muon cong chinh vinuni"

    assert _is_context_grounded_selection(raw, candidate, _selection_context()) is True
    assert _is_context_grounded_selection(raw, candidate, None) is False


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
