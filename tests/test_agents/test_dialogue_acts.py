import pytest
from pydantic import ValidationError

from src.agents.repair import DialogueActDetector
from src.agents.repair_models import DialogueAct, DialogueActResult
from src.agents.schemas import WorkflowType
from src.agents.understanding.models import CorrectionField


@pytest.mark.parametrize(
    ("transcript", "expected_act"),
    [
        ("Nói lại giúp tôi", DialogueAct.REPEAT),
        ("Bạn vừa nói gì?", DialogueAct.REPEAT),
        ("Hủy đặt xe", DialogueAct.CANCEL),
        ("Hủy", DialogueAct.CANCEL),
        ("Tôi không cần xe nữa", DialogueAct.CANCEL),
        ("Làm lại từ đầu", DialogueAct.START_OVER),
        ("Bắt đầu lại từ đầu", DialogueAct.START_OVER),
        ("Tôi cần trợ giúp", DialogueAct.HELP),
        ("Khoan đã", DialogueAct.PAUSE),
        ("Tiếp tục", DialogueAct.RESUME),
        ("Tạm biệt", DialogueAct.GOODBYE),
    ],
)
def test_detector_recognizes_explicit_conversation_commands(transcript, expected_act):
    result = DialogueActDetector().detect(transcript)

    assert result.act is expected_act
    assert result.confidence == 1
    assert result.matched_evidence


@pytest.mark.parametrize(
    ("transcript", "field"),
    [
        ("Đổi điểm đón sang Nhà hát Lớn", CorrectionField.PICKUP),
        ("Sửa điểm đến thành Royal City", CorrectionField.DESTINATION),
        ("Thay số điện thoại", CorrectionField.PHONE_NUMBER),
        ("Số điện thoại đúng là 0987654321", CorrectionField.PHONE_NUMBER),
        ("Tôi muốn sửa lại thông tin", None),
    ],
)
def test_detector_identifies_correction_field(transcript, field):
    result = DialogueActDetector().detect(transcript)

    assert result.act is DialogueAct.CORRECT
    assert result.correction_field is field


@pytest.mark.parametrize(
    ("transcript", "workflow"),
    [
        ("Chuyển sang đặt xe", WorkflowType.RIDE_BOOKING),
        ("Đổi sang tra cứu chuyến", WorkflowType.TRIP_LOOKUP),
        ("Chuyển sang hỏi đáp", WorkflowType.FAQ),
    ],
)
def test_detector_identifies_explicit_intent_change_target(transcript, workflow):
    result = DialogueActDetector().detect(transcript)

    assert result.act is DialogueAct.CHANGE_INTENT
    assert result.target_workflow is workflow


def test_detector_identifies_resume_target_when_explicit():
    booking = DialogueActDetector().detect("Quay lại đặt xe")
    generic = DialogueActDetector().detect("Tiếp tục đi")

    assert booking.act is DialogueAct.RESUME
    assert booking.target_workflow is WorkflowType.RIDE_BOOKING
    assert generic.act is DialogueAct.RESUME
    assert generic.target_workflow is None


@pytest.mark.parametrize(
    "transcript",
    [
        "",
        "Không",
        "Không đúng điểm đón",
        "Đặt giúp tôi",
        "Đổi chỗ đó sang Times City",
        "Dịch vụ hỗ trợ thanh toán thế nào?",
        "Tôi đang gặp nguy hiểm",
        "Tôi muốn gặp tổng đài viên",
    ],
)
def test_detector_leaves_non_command_and_safety_utterances_for_existing_pipeline(transcript):
    result = DialogueActDetector().detect(transcript)

    assert result == DialogueActResult()


def test_start_over_takes_precedence_over_generic_resume_word():
    result = DialogueActDetector().detect("Quay lại và làm lại từ đầu")

    assert result.act is DialogueAct.START_OVER


def test_dialogue_act_result_rejects_inconsistent_payloads():
    with pytest.raises(ValidationError, match="CONTINUE"):
        DialogueActResult(
            act=DialogueAct.CONTINUE,
            matched_evidence=["tiếp tục"],
        )

    with pytest.raises(ValidationError, match="requires matched evidence"):
        DialogueActResult(act=DialogueAct.CANCEL)

    with pytest.raises(ValidationError, match="target workflow"):
        DialogueActResult(
            act=DialogueAct.CANCEL,
            target_workflow=WorkflowType.RIDE_BOOKING,
            matched_evidence=["hủy"],
        )

    with pytest.raises(ValidationError, match="correction field"):
        DialogueActResult(
            act=DialogueAct.REPEAT,
            correction_field=CorrectionField.PICKUP,
            matched_evidence=["nói lại"],
        )


def test_dialogue_act_result_normalizes_and_rejects_duplicate_evidence():
    result = DialogueActResult(
        act=DialogueAct.REPEAT,
        matched_evidence=["  Nói lại  "],
    )
    assert result.matched_evidence == ["Nói lại"]

    with pytest.raises(ValidationError, match="must be unique"):
        DialogueActResult(
            act=DialogueAct.REPEAT,
            matched_evidence=["nói lại", "nói lại"],
        )
