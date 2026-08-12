import numpy as np

from src.voice.audio.codec import (
    PCM16Resampler,
    float32_to_pcm16_bytes,
    pcm16_bytes_to_float32,
    resample_pcm16,
    utterance_rms,
)


def _sine_pcm16(freq: float, duration_s: float, rate: int, amplitude: float = 0.5) -> bytes:
    t = np.arange(int(rate * duration_s)) / rate
    samples = (np.sin(2 * np.pi * freq * t) * amplitude * 32767).astype("<i2")
    return samples.tobytes()


def test_resample_pcm16_same_rate_is_passthrough():
    chunk = _sine_pcm16(440, 0.1, 16000)
    assert resample_pcm16(chunk, 16000, 16000) == chunk


def test_resample_pcm16_empty_input():
    assert resample_pcm16(b"", 48000, 16000) == b""


def test_resample_pcm16_48k_to_16k_has_expected_length_ratio():
    chunk = _sine_pcm16(440, 1.0, 48000)
    out = resample_pcm16(chunk, 48000, 16000)
    n_in = len(chunk) // 2
    n_out = len(out) // 2
    assert abs((n_out / n_in) - (1 / 3)) < 0.01


def test_pcm16_float32_roundtrip_stays_in_range():
    chunk = _sine_pcm16(440, 0.01, 16000)
    floats = pcm16_bytes_to_float32(chunk)
    assert floats.max() <= 1.0
    assert floats.min() >= -1.0
    back = float32_to_pcm16_bytes(floats)
    assert len(back) == len(chunk)


def test_streaming_resampler_same_rate_passthrough():
    resampler = PCM16Resampler(target_rate=16000)
    chunk = _sine_pcm16(440, 0.1, 16000)
    assert resampler.process(chunk, 16000) == chunk


def test_streaming_resampler_matches_offline_length_within_tolerance():
    resampler = PCM16Resampler(target_rate=16000)
    chunk = _sine_pcm16(440, 1.0, 48000)

    piece_bytes = int(48000 * 0.1) * 2  # 100ms pieces, 2 bytes/sample
    out = bytearray()
    for i in range(0, len(chunk), piece_bytes):
        out += resampler.process(chunk[i : i + piece_bytes], 48000)

    n_out = len(out) // 2
    assert abs(n_out - 16000) < 50


def test_streaming_resampler_reset_on_empty_chunk():
    resampler = PCM16Resampler(target_rate=16000)
    assert resampler.process(b"", 48000) == b""


def test_utterance_rms_of_pure_silence_is_zero():
    silence = np.zeros(16000, dtype="<i2").tobytes()
    assert utterance_rms(silence) == 0.0


def test_utterance_rms_of_empty_bytes_is_zero():
    assert utterance_rms(b"") == 0.0


def test_utterance_rms_of_loud_signal_is_high():
    chunk = _sine_pcm16(440, 0.5, 16000)
    assert utterance_rms(chunk) > 0.1


def test_utterance_rms_scales_with_amplitude():
    loud = _sine_pcm16(440, 0.5, 16000, amplitude=0.9)
    quiet = _sine_pcm16(440, 0.5, 16000, amplitude=0.05)
    assert utterance_rms(loud) > utterance_rms(quiet)
