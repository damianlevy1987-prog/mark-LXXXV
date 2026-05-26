import os


def test_service_name_by_secret_type(monkeypatch):
    from core import secrets_store

    monkeypatch.setattr(secrets_store, "get_active_profile_id", lambda: 2)
    assert secrets_store._service_name("gemini") == "mark-lxxxv:2:gemini"


def test_import_from_env_once_imports_when_missing(monkeypatch):
    from core import secrets_store

    calls = []

    class K:
        def get_password(self, service, username):
            return None

        def set_password(self, service, username, password):
            calls.append((service, username, password))

    monkeypatch.setattr(secrets_store, "keyring", K())
    monkeypatch.setenv("GEMINI_API_KEY", "g" * 32)

    imported = secrets_store.import_from_env_once(["GEMINI_API_KEY"])

    assert imported == {"GEMINI_API_KEY": "IMPORTED"}
    assert calls[0][0] == f"mark-lxxxv:{secrets_store.get_active_profile_id()}:gemini"
    assert calls[0][1] == "GEMINI_API_KEY"


def test_import_from_env_once_does_not_override_existing(monkeypatch):
    from core import secrets_store

    calls = []

    class K:
        def get_password(self, service, username):
            return "already"

        def set_password(self, service, username, password):
            calls.append((service, username, password))

    monkeypatch.setattr(secrets_store, "keyring", K())
    monkeypatch.setenv("GEMINI_API_KEY", "new" * 10)

    imported = secrets_store.import_from_env_once(["GEMINI_API_KEY"])

    assert imported == {}
    assert calls == []
