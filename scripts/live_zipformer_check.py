"""Run the pinned ZipFormer model against a real Vietnamese WAV (no fake ASR)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.voice.asr.zipformer.config import get_zipformer_settings  # noqa: E402
from src.voice.asr.zipformer.service import get_zipformer_service  # noqa: E402


async def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    settings = get_zipformer_settings()
    service = get_zipformer_service()
    await service.start()
    try:
        if not service.ready:
            print(
                f"FAIL: state={service.runtime.state} reason={service.runtime.failure_reason}",
                file=sys.stderr,
            )
            return 1
        wavs = sorted((settings.asr_model_dir / "test_wavs").glob("*.wav"))
        if not wavs:
            print("FAIL: the pinned artifact has no real WAV fixture", file=sys.stderr)
            return 1
        result = await service.transcribe_upload(
            wavs[0].read_bytes(),
            filename=wavs[0].name,
            mime_type="audio/wav",
        )
        print(
            f"model={settings.asr_model_id} state={service.runtime.state} "
            f"audio_ms={result.audio_duration_ms} inference_ms={result.inference_ms} confidence={result.confidence} "
            f"rtf={result.realtime_factor} transcript={result.text!r}"
        )
        if not result.text:
            print("FAIL: real model returned an empty transcript", file=sys.stderr)
            return 1
        print("LIVE ZIPFORMER CHECK PASSED")
        return 0
    finally:
        await service.stop()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
