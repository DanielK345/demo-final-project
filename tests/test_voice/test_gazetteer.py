import json

from src.voice.text.gazetteer import Gazetteer


def test_gazetteer_dedupes_and_strips_entries():
    gz = Gazetteer(["Landmark 81", " Landmark 81 ", "Vincom Đồng Khởi", ""])
    assert gz.entries == ["Landmark 81", "Vincom Đồng Khởi"]
    assert len(gz) == 2


def test_as_prompt_hint_joins_and_limits():
    gz = Gazetteer(["A", "B", "C"])
    assert gz.as_prompt_hint() == "A, B, C"
    assert gz.as_prompt_hint(limit=2) == "A, B"


def test_contains():
    gz = Gazetteer(["Landmark 81"])
    assert "Landmark 81" in gz
    assert "Landmark 82" not in gz


def test_load_missing_file_returns_empty_gazetteer(tmp_path):
    gz = Gazetteer.load(tmp_path / "does-not-exist.json")
    assert len(gz) == 0


def test_load_from_dict_shape(tmp_path):
    path = tmp_path / "place_names.json"
    path.write_text(json.dumps({"place_names": ["Landmark 81", "Vincom Đồng Khởi"]}), encoding="utf-8")
    gz = Gazetteer.load(path)
    assert gz.entries == ["Landmark 81", "Vincom Đồng Khởi"]


def test_load_from_plain_list_shape(tmp_path):
    path = tmp_path / "place_names.json"
    path.write_text(json.dumps(["Landmark 81"]), encoding="utf-8")
    gz = Gazetteer.load(path)
    assert gz.entries == ["Landmark 81"]


def test_default_seed_file_loads_and_is_nonempty():
    gz = Gazetteer.load()
    assert len(gz) > 0
    assert "Landmark 81" in gz
