from src.voice.schemas import ASRResult
from src.voice.asr.confidence import ConfidenceGate


def _gate() -> ConfidenceGate:
    return ConfidenceGate(default_threshold=0.60, booking_confirmation_threshold=0.80)


def test_threshold_for_default_vs_booking_confirmation():
    gate = _gate()
    assert gate.threshold_for(is_booking_confirmation=False) == 0.60
    assert gate.threshold_for(is_booking_confirmation=True) == 0.80


def test_passes_uses_default_threshold_outside_confirmation():
    gate = _gate()
    result = ASRResult(text="đi landmark 81", confidence=0.70)
    assert gate.passes(result, is_booking_confirmation=False) is True


def test_fails_default_threshold_when_below():
    gate = _gate()
    result = ASRResult(text="đi landmark 81", confidence=0.50)
    assert gate.passes(result, is_booking_confirmation=False) is False


def test_br001_booking_confirmation_needs_higher_confidence():
    gate = _gate()
    result = ASRResult(text="đúng rồi xác nhận đặt xe", confidence=0.70)
    # đạt ngưỡng thường (0.60) nhưng CHƯA đạt ngưỡng xác nhận đặt xe (0.80, BR-001)
    assert gate.passes(result, is_booking_confirmation=False) is True
    assert gate.passes(result, is_booking_confirmation=True) is False


def test_empty_text_never_passes_even_with_high_confidence():
    gate = _gate()
    result = ASRResult(text="   ", confidence=0.99)
    assert gate.passes(result) is False
