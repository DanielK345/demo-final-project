from src.backend.config import Settings
from src.voice.config import VoiceSettings


def test_openai_and_edge_tts_voice_environment_names_are_unambiguous() -> None:
    backend = Settings(_env_file=None, VOICE_OPENAI_TTS_VOICE="echo")
    voice = VoiceSettings(_env_file=None, VOICE_TTS_PRIMARY_VOICE="vi-VN-NamMinhNeural")

    assert backend.voice_tts_voice == "echo"
    assert voice.voice_tts_primary_voice == "vi-VN-NamMinhNeural"


def test_legacy_voice_tts_voice_only_belongs_to_edge_runtime() -> None:
    backend = Settings(_env_file=None, VOICE_TTS_VOICE="vi-VN-HoaiMyNeural")
    voice = VoiceSettings(_env_file=None, VOICE_TTS_VOICE="vi-VN-HoaiMyNeural")

    assert backend.voice_tts_voice == "nova"
    assert voice.voice_tts_primary_voice == "vi-VN-HoaiMyNeural"
