from src.voice.config import VoiceSettings


def test_edge_voice_is_separate_from_openai_voice(monkeypatch):
    monkeypatch.setenv("VOICE_TTS_VOICE", "nova")
    monkeypatch.setenv("VOICE_EDGE_TTS_VOICE", "vi-VN-HoaiMyNeural")

    settings = VoiceSettings(_env_file=None)

    assert settings.voice_tts_voice == "vi-VN-HoaiMyNeural"


def test_openai_voice_does_not_override_edge_default(monkeypatch):
    monkeypatch.setenv("VOICE_TTS_VOICE", "nova")
    monkeypatch.delenv("VOICE_EDGE_TTS_VOICE", raising=False)

    settings = VoiceSettings(_env_file=None)

    assert settings.voice_tts_voice == "vi-VN-HoaiMyNeural"


def test_invalid_edge_voice_falls_back_to_vietnamese_neural_voice(monkeypatch):
    monkeypatch.setenv("VOICE_EDGE_TTS_VOICE", "nova")

    settings = VoiceSettings(_env_file=None)

    assert settings.voice_tts_voice == "vi-VN-HoaiMyNeural"
