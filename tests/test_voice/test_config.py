from src.voice.config import VoiceSettings


def test_edge_tts_voice_is_separate_from_openai_voice(monkeypatch):
    monkeypatch.setenv("VOICE_TTS_VOICE", "nova")
    monkeypatch.setenv("VOICE_EDGE_TTS_VOICE", "vi-VN-HoaiMyNeural")

    settings = VoiceSettings(_env_file=None)

    assert settings.voice_tts_voice == "vi-VN-HoaiMyNeural"


def test_edge_tts_voice_uses_its_default_when_only_openai_voice_is_set(monkeypatch):
    monkeypatch.setenv("VOICE_TTS_VOICE", "nova")
    monkeypatch.delenv("VOICE_EDGE_TTS_VOICE", raising=False)

    settings = VoiceSettings(_env_file=None)

    assert settings.voice_tts_voice == "vi-VN-HoaiMyNeural"
