from __future__ import annotations

import base64
import ctypes
import json
import os
import sys
from ctypes import wintypes
from pathlib import Path
from typing import Any

from core import secrets_store


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR = get_base_dir()
CONFIG_DIR = BASE_DIR / "config"

# Legacy single-profile locations
LEGACY_SETTINGS_FILE = CONFIG_DIR / "settings.json"
LEGACY_FILE = CONFIG_DIR / "api_keys.json"

from core.profile_store import ensure_profile_dirs, get_active_profile_id


def _profile_root_dir() -> Path:
    return ensure_profile_dirs(get_active_profile_id())


def _settings_file() -> Path:
    return _profile_root_dir() / "settings.json"

DEFAULT_STORE: dict[str, Any] = {
    "version": 1,
    "settings": {},
    "secrets": {},
}


def _atomic_write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(tmp, path)


class _DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def _dpapi_encrypt(plain: str) -> str:
    if os.name != "nt":
        raise RuntimeError("DPAPI only available on Windows")

    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32

    data = plain.encode("utf-8")
    in_blob = _DATA_BLOB(
        len(data),
        ctypes.cast(ctypes.create_string_buffer(data), ctypes.POINTER(ctypes.c_byte)),
    )
    out_blob = _DATA_BLOB()

    if not crypt32.CryptProtectData(
        ctypes.byref(in_blob),
        None,
        None,
        None,
        None,
        0,
        ctypes.byref(out_blob),
    ):
        raise ctypes.WinError()

    try:
        buf = ctypes.string_at(out_blob.pbData, out_blob.cbData)
        return base64.b64encode(buf).decode("ascii")
    finally:
        kernel32.LocalFree(out_blob.pbData)


def _dpapi_decrypt(b64: str) -> str:
    if os.name != "nt":
        raise RuntimeError("DPAPI only available on Windows")

    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32

    data = base64.b64decode(b64)
    in_blob = _DATA_BLOB(
        len(data),
        ctypes.cast(ctypes.create_string_buffer(data), ctypes.POINTER(ctypes.c_byte)),
    )
    out_blob = _DATA_BLOB()

    if not crypt32.CryptUnprotectData(
        ctypes.byref(in_blob),
        None,
        None,
        None,
        None,
        0,
        ctypes.byref(out_blob),
    ):
        raise ctypes.WinError()

    try:
        buf = ctypes.string_at(out_blob.pbData, out_blob.cbData)
        return buf.decode("utf-8")
    finally:
        kernel32.LocalFree(out_blob.pbData)


def encrypt_secret(plain: str) -> dict:
    if os.name == "nt":
        return {"enc": "dpapi", "value": _dpapi_encrypt(plain)}
    return {"enc": "plain", "value": plain}


def decrypt_secret(obj: dict) -> str | None:
    enc = obj.get("enc")
    val = obj.get("value")
    if not isinstance(val, str):
        return None
    if enc == "dpapi" and os.name == "nt":
        return _dpapi_decrypt(val)
    if enc == "plain":
        return val
    return None


def _migrate_legacy_settings_file_if_needed() -> None:
    """Move legacy config/settings.json into profile 0 on first run."""
    try:
        dst = ensure_profile_dirs(0) / "settings.json"
        if dst.exists():
            return
        if not LEGACY_SETTINGS_FILE.exists():
            return
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(LEGACY_SETTINGS_FILE.read_text(encoding="utf-8"), encoding="utf-8")
        try:
            LEGACY_SETTINGS_FILE.unlink()
        except Exception:
            pass
    except Exception:
        pass


def _import_legacy_if_present(store: dict) -> dict:
    # Only import when profile settings file does not exist yet
    if _settings_file().exists() or not LEGACY_FILE.exists():
        return store

    try:
        legacy = json.loads(LEGACY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return store

    if not isinstance(legacy, dict):
        return store

    gem = legacy.get("gemini_api_key")
    browser = legacy.get("browser")
    cam = legacy.get("camera_index")

    if isinstance(browser, str) and browser.strip():
        store["settings"]["browser"] = browser.strip()
    if isinstance(cam, int):
        store["settings"]["camera_index"] = cam

    if isinstance(gem, str) and gem.strip():
        # Only write if keyring doesn't already have it
        if not secrets_store.get_secret("GEMINI_API_KEY"):
            secrets_store.set_secret("GEMINI_API_KEY", gem.strip())

    save_store(store)
    return store


def _file_secret_to_plain(sec: object) -> str | None:
    # Old formats we may see in settings.json:
    # 1) {"enc":"plain","value":"..."}
    # 2) {"enc":"dpapi","value":"<b64>"}  (only decryptable on Windows)
    if not isinstance(sec, dict):
        return None
    enc = sec.get("enc")
    val = sec.get("value")
    if not isinstance(val, str):
        return None
    if enc == "plain":
        return val
    if enc == "dpapi" and os.name == "nt":
        return _dpapi_decrypt(val)
    return None


def _maybe_migrate_file_gemini_key(store: dict) -> dict:
    sec = store.get("secrets", {}).get("gemini_api_key")
    if not sec:
        return store

    plain = _file_secret_to_plain(sec)

    # Always remove it from file to enforce keyring-only going forward.
    try:
        store.get("secrets", {}).pop("gemini_api_key", None)
        if not store.get("secrets"):
            store.pop("secrets", None)
    except Exception:
        pass

    # Only write to keyring if keyring empty AND we can decrypt.
    if plain and not secrets_store.get_secret("GEMINI_API_KEY"):
        secrets_store.set_secret("GEMINI_API_KEY", plain)

    save_store(store)
    return store


def load_store() -> dict:
    _migrate_legacy_settings_file_if_needed()

    settings_file = _settings_file()
    if not settings_file.exists():
        store = {"version": 1, "settings": {}, "secrets": {}}
        return _import_legacy_if_present(store)

    try:
        raw = json.loads(settings_file.read_text(encoding="utf-8"))
    except Exception:
        return dict(DEFAULT_STORE)

    if not isinstance(raw, dict):
        return dict(DEFAULT_STORE)

    version = raw.get("version", 0)
    if version != 1:
        return dict(DEFAULT_STORE)

    settings = raw.get("settings") if isinstance(raw.get("settings"), dict) else {}
    secrets = raw.get("secrets") if isinstance(raw.get("secrets"), dict) else {}

    store = {"version": 1, "settings": settings, "secrets": secrets}
    return _maybe_migrate_file_gemini_key(store)


def save_store(store: dict) -> None:
    _atomic_write_json(_settings_file(), store)


def load_settings() -> dict:
    return load_store()["settings"]


def save_settings(patch: dict) -> dict:
    store = load_store()
    store_settings = store.get("settings", {})
    for k, v in patch.items():
        if v is None:
            store_settings.pop(k, None)
        else:
            store_settings[k] = v
    store["settings"] = store_settings
    save_store(store)
    return store_settings


def get_gemini_key() -> str | None:
    return secrets_store.get_secret("GEMINI_API_KEY")


def set_gemini_key(key: str) -> None:
    secrets_store.set_secret("GEMINI_API_KEY", key.strip())


def is_configured() -> bool:
    key = get_gemini_key()
    return bool(key and len(key) > 15)
