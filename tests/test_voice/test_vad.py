import numpy as np
import pytest

from src.voice.audio.vad import EndpointScorer, EnergyVAD, SileroVAD, build_vad_provider


def _frame(value: float, n: int) -> bytes:
    samples = (np.ones(n, dtype=np.float32) * value * 32767).astype("<i2")
    return samples.tobytes()


def test_energy_vad_distinguishes_silence_and_loud_audio():
    vad = EnergyVAD(threshold_rms=0.05)
    silence = np.zeros(320, dtype=np.float32)
    loud = np.ones(320, dtype=np.float32) * 0.5
    assert vad.is_speech(silence, 16000) == 0.0
    assert vad.is_speech(loud, 16000) == 1.0


def test_energy_vad_empty_frame_is_not_speech():
    vad = EnergyVAD()
    assert vad.is_speech(np.empty(0, dtype=np.float32), 16000) == 0.0


def test_build_vad_provider_defaults_to_energy():
    vad = build_vad_provider("energy")
    assert isinstance(vad, EnergyVAD)


def test_silero_vad_requires_model_path():
    with pytest.raises(ValueError):
        SileroVAD("")


def test_endpoint_scorer_emits_speech_start_then_speech_end():
    vad = EnergyVAD(threshold_rms=0.1)
    scorer = EndpointScorer(vad=vad, sample_rate=16000, frame_ms=32, silence_ms=100)
    loud_frame = _frame(0.5, scorer.frame_size)
    silent_frame = _frame(0.0, scorer.frame_size)

    start_events = scorer.push(loud_frame)
    assert any(e.event == "speech_start" for e in start_events)

    end_events = []
    for _ in range(8):  # 8 * 32ms = 256ms > 100ms silence threshold
        end_events.extend(scorer.push(silent_frame))

    speech_end = [e for e in end_events if e.event == "speech_end"]
    assert len(speech_end) == 1
    assert speech_end[0].utterance_pcm16
    assert speech_end[0].utterance_ms > 0


def test_endpoint_scorer_ignores_pure_silence():
    vad = EnergyVAD(threshold_rms=0.1)
    scorer = EndpointScorer(vad=vad, sample_rate=16000, frame_ms=32, silence_ms=100)
    silent_frame = _frame(0.0, scorer.frame_size)
    events = scorer.push(silent_frame * 5)
    assert events == []


def test_endpoint_scorer_forces_end_on_max_utterance():
    vad = EnergyVAD(threshold_rms=0.1)
    scorer = EndpointScorer(
        vad=vad, sample_rate=16000, frame_ms=32, silence_ms=10_000, max_utterance_ms=100
    )
    loud_frame = _frame(0.5, scorer.frame_size)
    events = []
    for _ in range(10):
        events.extend(scorer.push(loud_frame))
    assert any(e.event == "speech_end" for e in events)


def test_endpoint_scorer_flush_returns_pending_utterance():
    vad = EnergyVAD(threshold_rms=0.1)
    scorer = EndpointScorer(vad=vad, sample_rate=16000, frame_ms=32, silence_ms=100_000)
    loud_frame = _frame(0.5, scorer.frame_size)
    scorer.push(loud_frame)
    result = scorer.flush()
    assert result is not None
    assert result.event == "speech_end"


def test_endpoint_scorer_flush_without_speech_returns_none():
    vad = EnergyVAD(threshold_rms=0.1)
    scorer = EndpointScorer(vad=vad, sample_rate=16000)
    assert scorer.flush() is None
