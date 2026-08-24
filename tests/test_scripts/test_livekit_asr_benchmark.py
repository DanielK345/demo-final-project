import hashlib
import json
from pathlib import Path

import pytest

from scripts.benchmark_livekit_asr import _load_manifest, error_rate, normalize_text


def test_vietnamese_normalization_preserves_diacritics() -> None:
    assert normalize_text("  BƯU ĐIỆN Hà Nội! ") == "bưu điện hà nội"


def test_error_rate_uses_reference_length() -> None:
    assert error_rate(["xin", "chào"], ["xin", "chao"]) == 0.5
    assert error_rate([], []) == 0.0


def test_manifest_requires_consent_and_ground_truth(tmp_path: Path) -> None:
    audio_path = tmp_path / "case.wav"
    audio_path.write_bytes(b"test-audio-placeholder")
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(
        json.dumps(
            {
                "case_id": "north-quiet-001",
                "dataset_version": "vi-v1",
                "audio_path": audio_path.name,
                "audio_sha256": hashlib.sha256(audio_path.read_bytes()).hexdigest(),
                "consent": True,
                "expected_transcript": "Tôi muốn đến Bưu điện Hà Nội",
                "expected_entities": ["Bưu điện Hà Nội"],
                "accent": "north",
                "noise": "quiet",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    cases = _load_manifest(manifest)

    assert cases[0].audio_path == audio_path.resolve()
    assert cases[0].expected_entities == ("Bưu điện Hà Nội",)


def test_manifest_rejects_audio_without_consent(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(
        json.dumps(
            {
                "case_id": "case-1",
                "dataset_version": "vi-v1",
                "audio_path": "case.wav",
                "audio_sha256": "a" * 64,
                "consent": False,
                "expected_transcript": "xin chào",
                "expected_entities": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="consent"):
        _load_manifest(manifest)
