from friday.ui.desktop import preferences


def test_save_merges_and_load_survives_bad_files(tmp_path):
    path = tmp_path / "sub" / "interface.json"
    assert preferences.load(path) == {}
    preferences.save({"color": "#112233"}, path)
    preferences.save({"other": 1}, path)
    assert preferences.load(path) == {"color": "#112233", "other": 1}
    path.write_text("{abîmé", encoding="utf-8")
    assert preferences.load(path) == {}
