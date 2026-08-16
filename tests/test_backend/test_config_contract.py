from src.backend.config import Settings
from src.voice.config import VoiceSettings


def test_openai_and_edge_tts_voice_environment_names_are_unambiguous() -> None:
    backend = Settings(_env_file=None, VOICE_OPENAI_TTS_VOICE="echo")
    voice = VoiceSettings(_env_file=None, VOICE_TTS_PRIMARY_VOICE="vi-VN-NamMinhNeural")

    assert backend.voice_tts_voice == "echo"
    assert backend.voice_tts_provider == "openai"
    assert voice.voice_tts_primary_voice == "vi-VN-NamMinhNeural"


def test_legacy_voice_tts_voice_only_belongs_to_edge_runtime() -> None:
    backend = Settings(_env_file=None, VOICE_TTS_VOICE="vi-VN-HoaiMyNeural")
    voice = VoiceSettings(_env_file=None, VOICE_TTS_VOICE="vi-VN-HoaiMyNeural")

    assert backend.voice_tts_voice == "nova"
    assert voice.voice_tts_primary_voice == "vi-VN-HoaiMyNeural"

def test_production_readiness_cannot_bypass_missing_durable_service_persistence():
    from src.backend.config import Settings

    settings = Settings(
        app_env="production",
        database_url="postgresql://runtime.example/db",
        database_url_migrations="postgresql://migration.example/db",
        cors_origins="https://app.example.com",
    )
    errors = settings.production_readiness_errors()
    assert "DURABLE_SERVICE_PERSISTENCE_REQUIRED" in errors
    assert all("postgresql://" not in error for error in errors)
