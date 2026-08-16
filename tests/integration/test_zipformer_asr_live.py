from __future__ import annotations

import io
import wave
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.backend.main import app
from src.voice.asr.zipformer.config import get_zipformer_settings


def _real_wav() -> Path:
    wavs = sorted((get_zipformer_settings().asr_model_dir / "test_wavs").glob("*.wav"))
    if not wavs:
        pytest.skip("Pinned real ZipFormer model/WAV artifact is not installed")
    return wavs[0]


def test_real_zipformer_model_through_rest_api() -> None:
    wav = _real_wav()
    with TestClient(app) as client:
        ready = client.get("/health/ready")
        assert ready.status_code == 200
        response = client.post(
            "/v1/audio/transcriptions",
            files={"file": (wav.name, wav.read_bytes(), "audio/wav")},
        )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["text"].strip()
    assert payload["model"] == "hynt/Zipformer-30M-RNNT-6000h"
    assert payload["audio_duration_ms"] > 0
    assert payload["inference_ms"] >= 0
    assert payload["realtime_factor"] >= 0
    assert payload["confidence"] is None or 0 <= payload["confidence"] <= 1


def test_asr_api_rejects_unsupported_upload_without_inference() -> None:
    _real_wav()
    with TestClient(app) as client:
        response = client.post(
            "/v1/audio/transcriptions",
            files={"file": ("payload.txt", b"not audio", "text/plain")},
        )
    assert response.status_code == 415
    assert response.json()["error"]["code"] == "UNSUPPORTED_AUDIO"


def test_asr_health_contracts_and_metrics() -> None:
    _real_wav()
    with TestClient(app) as client:
        live = client.get("/health/live")
        ready = client.get("/health/ready")
        metrics = client.get("/metrics")
    assert live.status_code == 200
    assert live.json() == {"status": "alive"}
    assert ready.status_code == 200
    assert ready.json()["model_state"] == "READY"
    assert metrics.status_code == 200
    assert "alosm_asr_model_ready 1" in metrics.text


def test_asr_api_rejects_corrupt_and_oversized_audio() -> None:
    _real_wav()
    with TestClient(app) as client:
        corrupt = client.post(
            "/v1/audio/transcriptions",
            files={"file": ("broken.wav", b"not-a-wave", "audio/wav")},
        )
        oversized = client.post(
            "/v1/audio/transcriptions",
            files={"file": ("large.wav", b"0" * (15 * 1024 * 1024 + 1), "audio/wav")},
        )
    assert corrupt.status_code == 422
    assert corrupt.json()["error"]["code"] == "INVALID_AUDIO"
    assert oversized.status_code == 413
    assert oversized.json()["error"]["code"] == "AUDIO_TOO_LARGE"


def test_asr_api_rejects_audio_over_duration_limit() -> None:
    _real_wav()
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b"\x00\x00" * 16000 * 61)
    with TestClient(app) as client:
        response = client.post(
            "/v1/audio/transcriptions",
            files={"file": ("too-long.wav", output.getvalue(), "audio/wav")},
        )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "AUDIO_TOO_LONG"


def test_real_zipformer_handles_concurrent_rest_requests() -> None:
    wav = _real_wav()
    audio = wav.read_bytes()
    with TestClient(app) as client:
        def submit(_: int):
            return client.post(
                "/v1/audio/transcriptions",
                files={"file": (wav.name, audio, "audio/wav")},
            )

        with ThreadPoolExecutor(max_workers=4) as executor:
            responses = list(executor.map(submit, range(4)))
    assert all(response.status_code == 200 for response in responses)
    assert all(response.json()["text"].strip() for response in responses)
    assert any(response.json()["queue_wait_ms"] > 0 for response in responses)
