import json


def test_default_profile_created_and_selected(tmp_path, monkeypatch):
    from core import profile_store

    monkeypatch.setattr(profile_store, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(profile_store, "PROFILES_DIR", tmp_path / "profiles")
    monkeypatch.setattr(profile_store, "STATE_FILE", tmp_path / "profile_state.json")

    pid = profile_store.get_active_profile_id()
    assert pid == 0
    assert (tmp_path / "profiles" / "0").exists()


def test_create_profile_returns_next_int(tmp_path, monkeypatch):
    from core import profile_store

    monkeypatch.setattr(profile_store, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(profile_store, "PROFILES_DIR", tmp_path / "profiles")
    monkeypatch.setattr(profile_store, "STATE_FILE", tmp_path / "profile_state.json")

    profile_store.ensure_profile_dirs(0)
    (tmp_path / "profiles" / "2").mkdir(parents=True)

    new_id = profile_store.create_profile()
    assert new_id == 3
    assert (tmp_path / "profiles" / "3").exists()


def test_set_active_profile_persists(tmp_path, monkeypatch):
    from core import profile_store

    monkeypatch.setattr(profile_store, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(profile_store, "PROFILES_DIR", tmp_path / "profiles")
    monkeypatch.setattr(profile_store, "STATE_FILE", tmp_path / "profile_state.json")

    profile_store.set_active_profile_id(2)

    data = json.loads((tmp_path / "profile_state.json").read_text(encoding="utf-8"))
    assert data["active_profile_id"] == 2
    assert profile_store.get_active_profile_id() == 2
