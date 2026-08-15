from src.voice.asr.biasing import correct_place_names
from src.voice.text.gazetteer import Gazetteer


def _gazetteer() -> Gazetteer:
    return Gazetteer(["Vincom Đồng Khởi", "Landmark 81", "Chợ Bến Thành"])


def test_corrects_missing_diacritics_same_word_count():
    text = "cho tôi đến vincom dong khoi"
    assert correct_place_names(text, _gazetteer()) == "cho tôi đến Vincom Đồng Khởi"


def test_corrects_missing_diacritics_two_word_entry():
    text = "cho toi den cho ben thanh"
    assert correct_place_names(text, _gazetteer()) == "cho toi den Chợ Bến Thành"


def test_does_not_touch_already_correct_text():
    text = "đã tới Vincom Đồng Khởi rồi"
    assert correct_place_names(text, _gazetteer()) == text


def test_does_not_corrupt_unrelated_sentence():
    text = "tôi muốn đặt xe đi làm sớm hôm nay vì có việc gấp"
    assert correct_place_names(text, _gazetteer()) == text


def test_never_eats_a_neighboring_unrelated_word():
    """Regression: cửa sổ dài hơn không được 'nuốt' từ hàng xóm không liên quan
    chỉ vì phần còn lại của span khớp mờ với 1 địa danh ngắn hơn."""
    text = "đã tới Vincom Đồng Khởi rồi"
    result = correct_place_names(text, _gazetteer())
    assert "tới" in result
    assert result.count("Vincom Đồng Khởi") == 1


def test_empty_gazetteer_is_noop():
    text = "cho tôi đến vincom dong khoi"
    assert correct_place_names(text, Gazetteer(entries=[])) == text


def test_empty_text_is_noop():
    assert correct_place_names("", _gazetteer()) == ""


def test_landmark_81_digit_suffix_matches():
    text = "đón tôi ở landmark 81"
    assert correct_place_names(text, _gazetteer()) == text
