import json

import pytest


def test_save_and_load_settings(tmp_path, monkeypatch):
    from core import settings_store

    monkeypatch.setattr(settings_store, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(settings_store, "SETTINGS_FILE", tmp_path / "settings.json")

    settings_store.save_settings({"browser": "brave", "camera_index": 2})
    s = settings_store.load_settings()

    assert s["browser"] == "brave"
    assert s["camera_index"] == 2


def test_set_get_key_delegates_to_keyring(monkeypatch, tmp_path):
    from core import settings_store

    monkeypatch.setattr(settings_store, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(settings_store, "SETTINGS_FILE", tmp_path / "settings.json")

    got = {"val": None}

    class S:
        def get_secret(self, name):
            return got["val"]

        def set_secret(self, name, value):
            got["val"] = value

    monkeypatch.setattr(settings_store, "secrets_store", S())

    settings_store.set_gemini_key("x" * 32)
    assert settings_store.get_gemini_key() == "x" * 32


def test_imports_legacy_file(tmp_path, monkeypatch):
    from core import settings_store

    monkeypatch.setattr(settings_store, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(settings_store, "SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(settings_store, "LEGACY_FILE", tmp_path / "api_keys.json")

    keyring_written = {"val": None}

    class S:
        def get_secret(self, name):
            return None

        def set_secret(self, name, value):
            keyring_written["val"] = value

    monkeypatch.setattr(settings_store, "secrets_store", S())

    (tmp_path / "api_keys.json").write_text(
        json.dumps(
            {
                "gemini_api_key": "g" * 32,
                "browser": "brave",
                "camera_index": 1,
            }
        ),
        encoding="utf-8",
    )

    settings_store.load_store()  # triggers legacy import + keyring write

    assert keyring_written["val"] == "g" * 32
    assert settings_store.load_settings()["browser"] == "brave"
    assert settings_store.load_settings()["camera_index"] == 1


def test_migrates_file_secret_to_keyring_and_removes_from_file(tmp_path, monkeypatch):
    from core import settings_store

    monkeypatch.setattr(settings_store, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(settings_store, "SETTINGS_FILE", tmp_path / "settings.json")

    (tmp_path / "settings.json").write_text(
        json.dumps(
            {
                "version": 1,
                "settings": {"browser": "brave"},
                "secrets": {"gemini_api_key": {"enc": "plain", "value": "g" * 32}},
            }
        ),
        encoding="utf-8",
    )

    keyring_written = {"val": None}

    class S:
        def get_secret(self, name):
            return None

        def set_secret(self, name, value):
            keyring_written["val"] = value

    monkeypatch.setattr(settings_store, "secrets_store", S())

    settings_store.load_store()

    assert keyring_written["val"] == "g" * 32

    stored = json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))
    assert "secrets" not in stored or "gemini_api_key" not in stored.get("secrets", {})
