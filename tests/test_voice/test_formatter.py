from src.voice.tts.formatter import format_for_speech, number_to_vietnamese_words, sanitize_for_speech


def test_zero_and_small_numbers():
    assert number_to_vietnamese_words(0) == "không"
    assert number_to_vietnamese_words(1) == "một"
    assert number_to_vietnamese_words(5) == "năm"


def test_teens():
    assert number_to_vietnamese_words(10) == "mười"
    assert number_to_vietnamese_words(11) == "mười một"
    assert number_to_vietnamese_words(15) == "mười lăm"


def test_tens_with_mot_tu_lam_substitutions():
    assert number_to_vietnamese_words(20) == "hai mươi"
    assert number_to_vietnamese_words(21) == "hai mươi mốt"
    assert number_to_vietnamese_words(24) == "hai mươi tư"
    assert number_to_vietnamese_words(25) == "hai mươi lăm"


def test_hundreds_with_linh():
    assert number_to_vietnamese_words(100) == "một trăm"
    assert number_to_vietnamese_words(105) == "một trăm linh năm"
    assert number_to_vietnamese_words(110) == "một trăm mười"
    assert number_to_vietnamese_words(121) == "một trăm hai mươi mốt"


def test_thousands_and_millions():
    assert number_to_vietnamese_words(1000) == "một nghìn"
    assert number_to_vietnamese_words(20_000) == "hai mươi nghìn"
    assert number_to_vietnamese_words(100_000) == "một trăm nghìn"
    assert number_to_vietnamese_words(105_000) == "một trăm linh năm nghìn"
    assert number_to_vietnamese_words(1_000_000) == "một triệu"
    assert number_to_vietnamese_words(1_500_000) == "một triệu năm trăm nghìn"


def test_negative_number():
    assert number_to_vietnamese_words(-5) == "âm năm"


def test_format_for_speech_currency():
    assert format_for_speech("cho tôi vé 20.000 đồng") == "cho tôi vé hai mươi nghìn đồng"


def test_format_for_speech_multiple_numbers():
    result = format_for_speech("giá chuyến này là 105.000 đồng, dự kiến 15 phút nữa tới")
    assert result == "giá chuyến này là một trăm linh năm nghìn đồng, dự kiến mười lăm phút nữa tới"


def test_format_for_speech_decimal_reads_digit_by_digit():
    assert format_for_speech("khoảng cách 3,5 km") == "khoảng cách ba phẩy năm km"


def test_format_for_speech_leaves_text_without_numbers_untouched():
    text = "không có số nào ở đây cả"
    assert format_for_speech(text) == text


def test_format_for_speech_empty_string():
    assert format_for_speech("") == ""


def test_format_for_speech_reads_currency_symbol_as_dong():
    # Regression: "₫" đọc theo nghĩa đen (không phải chữ) nếu không thay — phát hiện
    # thật từ câu trả lời "giá dự kiến 85.000 ₫" của SessionService.
    assert format_for_speech("giá dự kiến 85.000 ₫") == "giá dự kiến tám mươi lăm nghìn đồng"


def test_sanitize_for_speech_strips_straight_and_curly_quotes():
    assert sanitize_for_speech('nói "Đúng" để xác nhận') == "nói Đúng để xác nhận"
    assert sanitize_for_speech("nói “Đúng” để xác nhận") == "nói Đúng để xác nhận"


def test_sanitize_for_speech_replaces_slash_with_space():
    assert sanitize_for_speech("Anh/chị muốn đón ở đâu ạ?") == "Anh chị muốn đón ở đâu ạ?"


def test_sanitize_for_speech_collapses_whitespace_after_stripping():
    assert sanitize_for_speech('nói “Đúng”  để xác nhận, hoặc “Thôi” để hủy.') == "nói Đúng để xác nhận, hoặc Thôi để hủy."


def test_sanitize_for_speech_leaves_clean_text_untouched():
    text = "Xin chào, tôi có thể giúp gì cho anh chị?"
    assert sanitize_for_speech(text) == text


def test_sanitize_for_speech_empty_string():
    assert sanitize_for_speech("") == ""


def test_format_for_speech_alone_can_eat_digits_inside_place_names():
    """Regression đã tự phát hiện: `format_for_speech` một mình KHÔNG biết "81" ở
    đây là 1 phần tên riêng ("Landmark 81") — nó cứ đổi thành chữ. Đây chính là lý
    do `gateway.py::_speak()` BẮT BUỘC chạy pronunciation override TRƯỚC formatter
    (không phải sau) — xem `src/voice/gateway.py` và test dưới."""
    assert format_for_speech("từ Landmark 81 đến") == "từ Landmark tám mươi mốt đến"


def test_format_and_sanitize_together_match_real_session_service_reply():
    """Câu thật từ `SessionService._confirm()` — verify đúng thứ tự pipeline thật
    dùng trong `gateway.py::_speak()`: pronunciation TRƯỚC, formatter+sanitize SAU —
    nhờ vậy "Landmark 81" được khoá thành "Len Mác Tám Mươi Mốt" (hết chữ số) trước
    khi formatter kịp "ăn" mất số 81."""
    from src.voice.tts.pronunciation import apply_pronunciation_overrides

    raw = 'Xe 4 chỗ từ Landmark 81 đến Vincom Đồng Khởi, giá dự kiến 85.000 ₫. Anh/chị xác nhận “Đúng” nhé?'
    result = sanitize_for_speech(format_for_speech(apply_pronunciation_overrides(raw)))
    assert result == (
        "Xe bốn chỗ từ Len Mác Tám Mươi Mốt đến Vincom Đồng Khởi, "
        "giá dự kiến tám mươi lăm nghìn đồng. Anh chị xác nhận Đúng nhé?"
    )
