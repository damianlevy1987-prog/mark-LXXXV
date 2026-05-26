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


def test_set_key_stores_object(tmp_path, monkeypatch):
    from core import settings_store

    monkeypatch.setattr(settings_store, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(settings_store, "SETTINGS_FILE", tmp_path / "settings.json")

    settings_store.set_gemini_key("x" * 32)
    store = settings_store.load_store()

    sec = store["secrets"]["gemini_api_key"]
    assert isinstance(sec, dict)
    assert "enc" in sec and "value" in sec


def test_plain_fallback_roundtrip_non_windows(tmp_path, monkeypatch):
    from core import settings_store

    monkeypatch.setattr(settings_store, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(settings_store, "SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(settings_store.os, "name", "posix")

    settings_store.set_gemini_key("k" * 32)
    assert settings_store.get_gemini_key() == "k" * 32


def test_imports_legacy_file(tmp_path, monkeypatch):
    from core import settings_store

    monkeypatch.setattr(settings_store, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(settings_store, "SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(settings_store, "LEGACY_FILE", tmp_path / "api_keys.json")

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

    assert settings_store.get_gemini_key() == "g" * 32
    assert settings_store.load_settings()["browser"] == "brave"
    assert settings_store.load_settings()["camera_index"] == 1
