from __future__ import annotations

import numpy as np
import pytest

from src.voice.asr.zipformer.audio import pcm16_to_float32, validate_upload
from src.voice.asr.zipformer.config import ZipformerSettings
from src.voice.asr.zipformer.errors import ASRErrorCode, ZipformerASRError


def test_validate_upload_rejects_empty_audio() -> None:
    with pytest.raises(ZipformerASRError) as caught:
        validate_upload(b"", filename="recording.wav", mime_type="audio/wav", settings=ZipformerSettings())
    assert caught.value.code is ASRErrorCode.EMPTY_AUDIO


def test_validate_upload_requires_matching_supported_extension_and_mime() -> None:
    with pytest.raises(ZipformerASRError) as caught:
        validate_upload(
            b"not-audio",
            filename="recording.exe",
            mime_type="application/octet-stream",
            settings=ZipformerSettings(),
        )
    assert caught.value.code is ASRErrorCode.UNSUPPORTED_AUDIO


def test_validate_upload_enforces_size_before_decode() -> None:
    settings = ZipformerSettings(max_audio_size_mb=1)
    with pytest.raises(ZipformerASRError) as caught:
        validate_upload(
            b"0" * (1024 * 1024 + 1),
            filename="recording.webm",
            mime_type="audio/webm;codecs=opus",
            settings=settings,
        )
    assert caught.value.code is ASRErrorCode.AUDIO_TOO_LARGE


def test_pcm16_conversion_is_normalized_float32() -> None:
    samples = pcm16_to_float32(np.array([-32768, 0, 32767], dtype="<i2").tobytes())
    assert samples.dtype == np.float32
    assert samples.tolist() == pytest.approx([-1.0, 0.0, 32767 / 32768])


@pytest.mark.asyncio
async def test_disabled_service_reports_model_unavailable() -> None:
    from src.voice.asr.zipformer.service import ZipformerASRService

    service = ZipformerASRService(ZipformerSettings(asr_enabled=False))
    await service.start()
    with pytest.raises(ZipformerASRError) as caught:
        await service.transcribe_pcm16(b"\x00\x00" * 16000, sample_rate=16000)
    assert caught.value.code is ASRErrorCode.MODEL_UNAVAILABLE
