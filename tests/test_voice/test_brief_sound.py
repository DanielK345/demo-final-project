from src.voice.asr.brief_sound import detect_brief_ambiguous_sound


def test_blocks_explicit_brief_vocalisations() -> None:
    for transcript in ("ừm", "HMM...", "khụ khụ", "hắt xì!"):
        decision = detect_brief_ambiguous_sound(transcript, speech_duration_ms=300, confidence=0.95)
        assert decision.blocked, transcript
        assert decision.reason == "brief_ambiguous_sound"


def test_allows_meaningful_short_vietnamese_turns() -> None:
    for transcript in ("alo", "dạ", "ừ", "đúng", "không", "đi", "xe"):
        decision = detect_brief_ambiguous_sound(transcript, speech_duration_ms=250, confidence=0.20)
        assert not decision.blocked, transcript


def test_blocks_low_confidence_tiny_token_only_when_audio_is_brief() -> None:
    assert detect_brief_ambiguous_sound("x", speech_duration_ms=200, confidence=0.10).blocked
    assert not detect_brief_ambiguous_sound("x", speech_duration_ms=1200, confidence=0.10).blocked
    assert not detect_brief_ambiguous_sound("x", speech_duration_ms=200, confidence=0.90).blocked


def test_upload_without_duration_uses_only_high_precision_vocalisation_list() -> None:
    assert detect_brief_ambiguous_sound("ừm").blocked
    assert not detect_brief_ambiguous_sound("tôi muốn đặt xe").blocked

