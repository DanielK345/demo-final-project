from src.voice.tts.pronunciation import apply_pronunciation_overrides


def test_replaces_known_brand_name():
    assert apply_pronunciation_overrides("Chào mừng đến với AloSM") == "Chào mừng đến với Alo Ét Em"


def test_replaces_case_insensitively():
    assert apply_pronunciation_overrides("đặt xe qua alosm nhé") == "đặt xe qua Alo Ét Em nhé"


def test_replaces_landmark_81():
    assert apply_pronunciation_overrides("đón bạn ở Landmark 81") == "đón bạn ở Len Mác Tám Mươi Mốt"


def test_leaves_unrelated_text_untouched():
    text = "tôi muốn đặt xe đi làm"
    assert apply_pronunciation_overrides(text) == text


def test_custom_overrides_merge_with_defaults():
    result = apply_pronunciation_overrides(
        "AloSM và Vincom Đồng Khởi",
        overrides={"Vincom Đồng Khởi": "Vin Côm Đồng Khởi"},
    )
    assert result == "Alo Ét Em và Vin Côm Đồng Khởi"


def test_empty_text():
    assert apply_pronunciation_overrides("") == ""


def test_longest_match_wins_when_overlapping():
    # "Landmark 81" phải thắng thay vì có sub-match ngắn hơn tình cờ trùng.
    result = apply_pronunciation_overrides("gặp nhau ở Landmark 81 nhé")
    assert result == "gặp nhau ở Len Mác Tám Mươi Mốt nhé"
