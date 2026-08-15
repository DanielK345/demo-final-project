from src.voice.text.normalizer import normalize_transcript


def test_collapses_extra_whitespace():
    assert normalize_transcript("tôi    muốn   đặt xe") == "tôi muốn đặt xe"


def test_strips_leading_filler_word():
    assert normalize_transcript("ừm tôi muốn đặt xe") == "tôi muốn đặt xe"


def test_strips_filler_word_in_middle():
    assert normalize_transcript("tôi ờ muốn đặt xe") == "tôi muốn đặt xe"


def test_normalizes_tens_with_magnitude_to_currency():
    assert normalize_transcript("cho tôi vé hai mươi nghìn đồng") == "cho tôi vé 20.000 đồng"


def test_normalizes_single_digit_with_magnitude():
    assert normalize_transcript("giá một trăm đồng") == "giá 100 đồng"


def test_normalizes_multiword_tens_without_magnitude():
    assert normalize_transcript("mười lăm phút nữa tới") == "15 phút nữa tới"


def test_does_not_touch_ambiguous_bare_single_digit_word():
    # "năm" đứng riêng (không kèm đơn vị) dễ nhầm "năm nay" (year) -> không đổi.
    assert normalize_transcript("năm nay tôi hai mươi lăm tuổi") == "năm nay tôi 25 tuổi"


def test_does_not_touch_bare_word_with_other_meaning():
    assert normalize_transcript("ba tôi bảo vậy") == "ba tôi bảo vậy"


def test_empty_and_whitespace_only_input_is_returned_unchanged():
    assert normalize_transcript("") == ""
    assert normalize_transcript("   ") == "   "


def test_idempotent_on_already_normalized_text():
    text = "cho tôi vé 20.000 đồng"
    assert normalize_transcript(text) == text
