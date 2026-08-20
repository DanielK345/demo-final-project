"""Configuration contract for the LiveKit-native voice runtime."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class LiveKitVoiceSettings(BaseSettings):
    """Load LiveKit settings without activating the new runtime implicitly.

    ``VOICE_RUNTIME`` is the migration switch. The default remains ``legacy`` so
    adding this package cannot change the deployed audio path. Credentials and
    model selections become mandatory only when the LiveKit path is selected.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    voice_runtime: Literal["legacy", "livekit"] = "legacy"

    livekit_url: str = ""
    livekit_api_key: SecretStr = SecretStr("")
    livekit_api_secret: SecretStr = SecretStr("")
    livekit_agent_name: str = "alosm-voice"

    livekit_stt_model: str = ""
    livekit_stt_language: str = "vi"
    livekit_llm_model: str = ""
    livekit_tts_model: str = ""
    livekit_tts_voice: str = ""
    livekit_tts_language: str = "vi"

    # LiveKit owns turn handling in the new path. Semantic turn detection is not
    # a Vietnamese baseline until LiveKit documents/supports it and we benchmark it.
    livekit_turn_detection: Literal["vad"] = "vad"
    # Keep the Phase 2 baseline on LiveKit's VAD interruption path. Adaptive is
    # still framework-native, but it consumes a separate Cloud quota and must be
    # enabled only for an explicit benchmark/deployment decision.
    livekit_interruption_mode: Literal["vad", "adaptive"] = "vad"
    # Vietnamese is not supported by LiveKit's semantic turn detector yet, so
    # keep VAD and give natural mid-address pauses a slightly wider endpoint.
    livekit_endpointing_mode: Literal["fixed", "dynamic"] = "fixed"
    # Hold the user turn open across short Vietnamese pauses. The conversation
    # LLM must not see a turn until two seconds of silence have elapsed.
    livekit_endpointing_min_delay_seconds: float = Field(default=2.0, ge=0.25, le=3)
    livekit_endpointing_max_delay_seconds: float = Field(default=3.0, ge=0.5, le=5)
    livekit_interruption_min_duration_seconds: float = Field(default=0.5, ge=0, le=5)
    livekit_interruption_min_words: int = Field(default=1, ge=0, le=10)

    # Privacy-safe defaults. Enabling persistence requires an explicit policy and
    # consent decision; it is never inferred from selecting the LiveKit runtime.
    livekit_record_audio: bool = False
    livekit_record_transcript: bool = False
    livekit_record_traces: bool = False
    livekit_record_logs: bool = False

    # Local/session diagnostics. JSONL and transcript content are separate
    # opt-ins so production keeps the privacy-safe default.
    livekit_debug_event_log: bool = False
    livekit_debug_transcripts: bool = False
    livekit_debug_log_dir: Path = Path("logs/livekit")

    livekit_connection_timeout_seconds: float = Field(default=10.0, gt=0, le=60)
    livekit_token_ttl_seconds: int = Field(default=600, ge=60, le=3600)
    # Development mode otherwise keeps zero job processes warm. One idle process
    # removes Python import/process startup from the first call without creating a Room.
    livekit_num_idle_processes: int = Field(default=1, ge=0, le=16)
    livekit_critical_confidence_threshold: float = Field(default=0.65, ge=0, le=1)
    # Deepgram can rarely end a VAD segment after partial text without sending a
    # final transcript. Reprompt safely instead of committing partial text.
    livekit_stt_final_fallback_enabled: bool = True
    livekit_stt_final_fallback_seconds: float = Field(default=3.0, ge=0.5, le=10)

    @property
    def enabled(self) -> bool:
        return self.voice_runtime == "livekit"

    def configuration_errors(self) -> list[str]:
        """Validate LiveKit itself without depending on the rollout switch."""

        required = {
            "LIVEKIT_URL_REQUIRED": self.livekit_url,
            "LIVEKIT_API_KEY_REQUIRED": self.livekit_api_key.get_secret_value(),
            "LIVEKIT_API_SECRET_REQUIRED": self.livekit_api_secret.get_secret_value(),
            "LIVEKIT_AGENT_NAME_REQUIRED": self.livekit_agent_name,
            "LIVEKIT_STT_MODEL_REQUIRED": self.livekit_stt_model,
            "LIVEKIT_LLM_MODEL_REQUIRED": self.livekit_llm_model,
            "LIVEKIT_TTS_MODEL_REQUIRED": self.livekit_tts_model,
            "LIVEKIT_TTS_VOICE_REQUIRED": self.livekit_tts_voice,
        }
        errors = [code for code, value in required.items() if not value.strip()]
        inference_models = {
            "LIVEKIT_STT_MODEL_MUST_USE_PROVIDER_MODEL": self.livekit_stt_model,
            "LIVEKIT_LLM_MODEL_MUST_USE_PROVIDER_MODEL": self.livekit_llm_model,
            "LIVEKIT_TTS_MODEL_MUST_USE_PROVIDER_MODEL": self.livekit_tts_model,
        }
        errors.extend(
            code
            for code, model in inference_models.items()
            if model.strip() and "/" not in model and not (code.startswith("LIVEKIT_STT_") and model == "auto")
        )
        if self.livekit_url and not self.livekit_url.startswith(("ws://", "wss://")):
            errors.append("LIVEKIT_URL_MUST_USE_WS")
        if self.livekit_endpointing_max_delay_seconds < self.livekit_endpointing_min_delay_seconds:
            errors.append("LIVEKIT_ENDPOINTING_MAX_MUST_NOT_BE_LOWER_THAN_MIN")
        if self.livekit_debug_transcripts and not self.livekit_debug_event_log:
            errors.append("LIVEKIT_DEBUG_TRANSCRIPTS_REQUIRES_EVENT_LOG")
        return errors

    def readiness_errors(self) -> list[str]:
        """Return rollout readiness errors without exposing credential values."""

        return self.configuration_errors() if self.enabled else []

    def require_configured(self) -> None:
        """Fail before an explicitly requested token/worker operation."""

        errors = self.configuration_errors()
        if errors:
            raise ValueError("LiveKit voice configuration is not ready: " + ", ".join(errors))

    def require_ready(self) -> None:
        """Fail when the rollout switch selects an incomplete LiveKit runtime."""

        errors = self.readiness_errors()
        if errors:
            raise ValueError("LiveKit voice configuration is not ready: " + ", ".join(errors))


@lru_cache
def get_livekit_voice_settings() -> LiveKitVoiceSettings:
    return LiveKitVoiceSettings()
