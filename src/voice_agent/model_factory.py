"""Factories for LiveKit-native model instances shared by worker and evals."""

from __future__ import annotations

import os

from livekit.agents import inference, stt

from src.voice_agent.config import LiveKitVoiceSettings


def build_stt(settings: LiveKitVoiceSettings) -> stt.STT:
    """Build the configured STT using an official LiveKit integration."""

    if settings.livekit_stt_provider == "google":
        try:
            from livekit.plugins import google
        except ImportError as exc:  # pragma: no cover - depends on optional plugin
            raise RuntimeError("LIVEKIT_STT_PROVIDER=google requires the livekit-plugins-google package.") from exc
        # BaseSettings reads .env without exporting values process-wide. Google
        # ADC uses this official variable to resolve the Speech v2 recognizer.
        os.environ["GOOGLE_CLOUD_PROJECT"] = settings.google_cloud_project
        return google.STT(
            model=settings.livekit_stt_model,
            languages=settings.livekit_stt_language,
            location=settings.google_stt_location,
            spoken_punctuation=False,
        )

    return inference.STT(
        model=settings.livekit_stt_model,
        language=settings.livekit_stt_language,
        api_key=settings.livekit_api_key.get_secret_value(),
        api_secret=settings.livekit_api_secret.get_secret_value(),
    )
