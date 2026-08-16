from src.voice.text.place_aliases import PlaceAliasCatalog


def test_hanoi_alias_catalog_has_broad_coverage():
    catalog = PlaceAliasCatalog.load()

    assert len(catalog.entries) >= 50
    assert all(len(entry.asr_aliases) >= 10 for entry in catalog.entries)
    assert all(len(set(entry.asr_aliases)) >= 10 for entry in catalog.entries)


def test_known_vietnamese_asr_place_confusions_are_corrected():
    catalog = PlaceAliasCatalog.load()

    corrected = catalog.correct("Đón tôi ở Bình Yuni rồi đi Hồ Cương và qua sân bay Nội Bai")

    assert corrected == "Đón tôi ở VinUni rồi đi Hồ Gươm và qua Sân bay Nội Bài"


def test_zipformer_uppercase_and_truncated_aliases_are_corrected():
    catalog = PlaceAliasCatalog.load()

    corrected = catalog.correct("CHO TÔI MỘT XE BỐN CHỖ ĐI TỪ BIN YOMI TỚI HỒ GƯƠ")

    assert corrected == "CHO TÔI MỘT XE BỐN CHỖ ĐI TỪ VinUni TỚI Hồ Gươm"


def test_alias_correction_does_not_replace_partial_words():
    catalog = PlaceAliasCatalog.load()

    assert catalog.correct("Bình Yunicorn không phải là tên địa danh") == "Bình Yunicorn không phải là tên địa danh"
