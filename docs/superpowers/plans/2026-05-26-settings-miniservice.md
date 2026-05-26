# Settings mini-service Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace legacy `config/api_keys.json` direct access with local settings mini-service using `config/settings.json`, keep settings in file, keep Gemini key encrypted (Windows DPAPI), ship first-run + edit-later UI.

**Architecture:** Add `core/settings_store.py` as single source for settings + secret handling. Migrate legacy `api_keys.json` -> `settings.json` on first run. Update callers (`main.py`, `actions/*`, `agent/*`, `ui.py`) to use store API.

**Tech Stack:** Python 3, stdlib (`json`, `pathlib`, `base64`, `tempfile`, `os`), Windows DPAPI via `ctypes` (no new deps), Tkinter UI.

---

## File map (create/modify)

**Create**
- `core/settings_store.py` — load/save store, migrations, DPAPI secret encryption/decryption
- `tests/test_settings_store.py` — unit tests for normalization/migration + non-Windows fallback behavior

**Modify**
- `ui.py` — first-run key save path; add minimal settings modal to edit key + settings
- `main.py` — replace `_get_api_key` usage; browser selection + config reads/writes -> store
- `actions/vision.py` — camera index read/write via store
- `actions/screen_processor.py` — camera index read/write via store
- `actions/browser.py`, `actions/computer.py`, `actions/os_control.py`, `actions/terminal.py` — replace `_get_api_key` implementations
- `agent/planner.py`, `agent/executor.py`, `agent/error_handler.py` — replace `_get_api_key` implementations
- `memory/config_manager.py` — either delete (if unused) or refactor to call store (decide after grep)
- `.gitignore` — ensure `config/settings.json` ignored (avoid accidental commit)

---

### Task 1: Add settings store skeleton + tests scaffold

**Files:**
- Create: `core/settings_store.py`
- Create: `tests/test_settings_store.py`

- [ ] **Step 1: Create `tests/test_settings_store.py` scaffold**

```python
import json
from pathlib import Path

import pytest

# tests will monkeypatch core.settings_store paths to a temp dir
```

- [ ] **Step 2: Add initial `core/settings_store.py` public API (no DPAPI yet)**

```python
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR = get_base_dir()
CONFIG_DIR = BASE_DIR / "config"
SETTINGS_FILE = CONFIG_DIR / "settings.json"
LEGACY_FILE = CONFIG_DIR / "api_keys.json"

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


def load_store() -> dict:
    if not SETTINGS_FILE.exists():
        return dict(DEFAULT_STORE)
    try:
        raw = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return dict(DEFAULT_STORE)

    if not isinstance(raw, dict):
        return dict(DEFAULT_STORE)

    version = raw.get("version", 0)
    if version != 1:
        # treat unknown as empty v1 for now; migration added later
        return dict(DEFAULT_STORE)

    settings = raw.get("settings") if isinstance(raw.get("settings"), dict) else {}
    secrets = raw.get("secrets") if isinstance(raw.get("secrets"), dict) else {}

    return {"version": 1, "settings": settings, "secrets": secrets}


def save_store(store: dict) -> None:
    _atomic_write_json(SETTINGS_FILE, store)


def load_settings() -> dict:
    return load_store()["settings"]


def save_settings(patch: dict) -> dict:
    store = load_store()
    store_settings = store.get("settings", {})
    store_settings.update(patch)
    store["settings"] = store_settings
    save_store(store)
    return store_settings


def get_gemini_key() -> str | None:
    store = load_store()
    sec = store.get("secrets", {}).get("gemini_api_key")
    if isinstance(sec, str):
        # temporary plaintext support until DPAPI wired
        return sec
    return None


def set_gemini_key(key: str) -> None:
    store = load_store()
    store.setdefault("secrets", {})["gemini_api_key"] = key.strip()
    save_store(store)


def is_configured() -> bool:
    key = get_gemini_key()
    return bool(key and len(key) > 15)
```

- [ ] **Step 3: Add unit tests for basic load/save_settings**

```python
from core import settings_store


def test_save_and_load_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(settings_store, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(settings_store, "SETTINGS_FILE", tmp_path / "settings.json")

    settings_store.save_settings({"browser": "brave", "camera_index": 2})
    s = settings_store.load_settings()
    assert s["browser"] == "brave"
    assert s["camera_index"] == 2
```

- [ ] **Step 4: Run tests**

Run: `pytest -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/settings_store.py tests/test_settings_store.py
git commit -m "feat: add settings store skeleton"
```

---

### Task 2: Implement Windows DPAPI secret encryption + non-Windows fallback

**Files:**
- Modify: `core/settings_store.py`
- Modify: `tests/test_settings_store.py`

- [ ] **Step 1: Implement DPAPI helpers (Windows only) in `core/settings_store.py`**

Add:

```python
import base64
import ctypes
from ctypes import wintypes


class _DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def _dpapi_encrypt(plain: str) -> str:
    if os.name != "nt":
        raise RuntimeError("DPAPI only available on Windows")

    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32

    data = plain.encode("utf-8")
    in_blob = _DATA_BLOB(len(data), ctypes.cast(ctypes.create_string_buffer(data), ctypes.POINTER(ctypes.c_byte)))
    out_blob = _DATA_BLOB()

    if not crypt32.CryptProtectData(ctypes.byref(in_blob), None, None, None, None, 0, ctypes.byref(out_blob)):
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
    in_blob = _DATA_BLOB(len(data), ctypes.cast(ctypes.create_string_buffer(data), ctypes.POINTER(ctypes.c_byte)))
    out_blob = _DATA_BLOB()

    if not crypt32.CryptUnprotectData(ctypes.byref(in_blob), None, None, None, None, 0, ctypes.byref(out_blob)):
        raise ctypes.WinError()

    try:
        buf = ctypes.string_at(out_blob.pbData, out_blob.cbData)
        return buf.decode("utf-8")
    finally:
        kernel32.LocalFree(out_blob.pbData)
```

- [ ] **Step 2: Replace plaintext secret storage with `{enc, value}` object**

Update:

```python
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


def get_gemini_key() -> str | None:
    sec = load_store().get("secrets", {}).get("gemini_api_key")
    if isinstance(sec, dict):
        return decrypt_secret(sec)
    return None


def set_gemini_key(key: str) -> None:
    store = load_store()
    store.setdefault("secrets", {})["gemini_api_key"] = encrypt_secret(key.strip())
    save_store(store)
```

- [ ] **Step 3: Add tests for structure + non-Windows fallback**

```python
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
```

- [ ] **Step 4: Run tests**

Run: `pytest -q`
Expected: PASS (Windows DPAPI path not required for tests)

- [ ] **Step 5: Commit**

```bash
git add core/settings_store.py tests/test_settings_store.py
git commit -m "feat: encrypt gemini key in settings store"
```

---

### Task 3: Legacy migration from `config/api_keys.json` -> `config/settings.json`

**Files:**
- Modify: `core/settings_store.py`
- Modify: `tests/test_settings_store.py`

- [ ] **Step 1: Add migration function**

```python
def _import_legacy_if_present(store: dict) -> dict:
    if SETTINGS_FILE.exists():
        return store
    if not LEGACY_FILE.exists():
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

    if isinstance(browser, str):
        store["settings"]["browser"] = browser
    if isinstance(cam, int):
        store["settings"]["camera_index"] = cam
    if isinstance(gem, str) and gem.strip():
        store["secrets"]["gemini_api_key"] = encrypt_secret(gem.strip())

    save_store(store)
    return store
```

Call it inside `load_store()` before returning, when no settings file exists.

- [ ] **Step 2: Add test for legacy import**

```python
def test_imports_legacy_file(tmp_path, monkeypatch):
    from core import settings_store
    monkeypatch.setattr(settings_store, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(settings_store, "SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(settings_store, "LEGACY_FILE", tmp_path / "api_keys.json")

    (tmp_path / "api_keys.json").write_text(json.dumps({
        "gemini_api_key": "g" * 32,
        "browser": "brave",
        "camera_index": 1,
    }), encoding="utf-8")

    assert settings_store.get_gemini_key() == "g" * 32
    assert settings_store.load_settings()["browser"] == "brave"
    assert settings_store.load_settings()["camera_index"] == 1
```

- [ ] **Step 3: Run tests**

Run: `pytest -q`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add core/settings_store.py tests/test_settings_store.py
git commit -m "feat: migrate legacy api_keys.json to settings.json"
```

---

### Task 4: Wire `ui.py` first-run setup to store + add minimal settings modal

**Files:**
- Modify: `ui.py`
- Modify: `core/settings_store.py` (if UI helpers needed)

- [ ] **Step 1: Replace `_save_api_keys` to call store**

Change `ui.py`:

```python
from core.settings_store import set_gemini_key

...

def _save_api_keys(self):
    gemini = self.gemini_entry.get().strip()
    if not gemini:
        return
    set_gemini_key(gemini)
    self.setup_frame.destroy()
    self._api_key_ready = True
    self.status_text = "ONLINE"
    self.write_log("SYS: Systems initialised. JARVIS online.")
```

Also update `_api_keys_exist` to use store:

```python
from core.settings_store import is_configured

def _api_keys_exist(self):
    return is_configured()
```

- [ ] **Step 2: Add settings modal UI (minimal)**

Add method in `JarvisUI`:

```python
from core.settings_store import load_settings, save_settings, set_gemini_key


def open_settings_modal(self):
    dialog = tk.Toplevel(self.root)
    dialog.title("Settings")
    dialog.configure(bg=C_BG)
    dialog.resizable(False, False)
    dialog.grab_set()

    s = load_settings()

    tk.Label(dialog, text="BROWSER", fg=C_DIM, bg=C_BG, font=("Courier", 9)).pack(pady=(12, 2))
    browser_var = tk.StringVar(value=str(s.get("browser", "")))
    tk.Entry(dialog, textvariable=browser_var, width=40, fg=C_TEXT, bg="#000d12",
             insertbackground=C_TEXT, borderwidth=0, font=("Courier", 10)).pack()

    tk.Label(dialog, text="CAMERA INDEX", fg=C_DIM, bg=C_BG, font=("Courier", 9)).pack(pady=(12, 2))
    cam_var = tk.StringVar(value=str(s.get("camera_index", "")))
    tk.Entry(dialog, textvariable=cam_var, width=10, fg=C_TEXT, bg="#000d12",
             insertbackground=C_TEXT, borderwidth=0, font=("Courier", 10)).pack()

    tk.Label(dialog, text="GEMINI API KEY", fg=C_DIM, bg=C_BG, font=("Courier", 9)).pack(pady=(12, 2))
    key_var = tk.StringVar(value="")
    tk.Entry(dialog, textvariable=key_var, width=40, fg=C_TEXT, bg="#000d12",
             insertbackground=C_TEXT, borderwidth=0, font=("Courier", 10), show="*").pack()

    def _save():
        patch = {}
        b = browser_var.get().strip()
        if b:
            patch["browser"] = b
        ci = cam_var.get().strip()
        if ci.isdigit():
            patch["camera_index"] = int(ci)
        if patch:
            save_settings(patch)
        k = key_var.get().strip()
        if k:
            set_gemini_key(k)
        dialog.destroy()

    tk.Button(dialog, text="SAVE", command=_save, bg=C_BG, fg=C_PRI,
              activebackground="#003344", font=("Courier", 10), borderwidth=0, pady=8).pack(pady=16)
```

Expose entry point (button/hotkey):
- simplest: bind Ctrl+Comma in `__init__`:

```python
self.root.bind_all("<Control-comma>", lambda e: self.open_settings_modal())
```

- [ ] **Step 3: Manual verify UI**

Run: `python main.py`
Expected:
- First-run still prompts for key
- Ctrl+, opens modal
- Save persists browser/camera_index + key

- [ ] **Step 4: Commit**

```bash
git add ui.py
git commit -m "feat: wire UI setup + settings modal to settings store"
```

---

### Task 5: Replace API key reads across codebase

**Files:**
- Modify: `main.py`
- Modify: `actions/browser.py`
- Modify: `actions/computer.py`
- Modify: `actions/os_control.py`
- Modify: `actions/terminal.py`
- Modify: `actions/vision.py`
- Modify: `agent/planner.py`
- Modify: `agent/executor.py`
- Modify: `agent/error_handler.py`

- [ ] **Step 1: Add shared import and remove per-file `_get_api_key`**

Pattern change in each file:

Before:
```python
def _get_api_key() -> str:
    with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["gemini_api_key"]
```

After:
```python
from core.settings_store import get_gemini_key


def _get_api_key() -> str:
    key = get_gemini_key()
    if not key:
        raise ValueError("Gemini API key not configured")
    return key
```

- [ ] **Step 2: Update `main.py` first-run waiting logic**

`JarvisUI.wait_for_api_key()` currently watches file existence. Update to use `is_configured()`.

- [ ] **Step 3: Run import/lint sanity**

Run: `python -c "import main"`
Expected: no ImportError

- [ ] **Step 4: Commit**

```bash
git add main.py actions agent
git commit -m "refactor: centralize gemini key access via settings store"
```

---

### Task 6: Persist browser preference + camera index via store

**Files:**
- Modify: `main.py`
- Modify: `actions/vision.py`
- Modify: `actions/screen_processor.py`

- [ ] **Step 1: Browser picker reads/writes store**

Where `main.py` saves browser to `api_keys.json`, replace with:

```python
from core.settings_store import load_settings, save_settings

...
if not load_settings().get("browser"):
    # show picker
    save_settings({"browser": chosen})
```

- [ ] **Step 2: Camera index uses store**

Replace reads of `camera_index` in config JSON with `load_settings().get("camera_index")`.
Replace writes with `save_settings({"camera_index": best})`.

- [ ] **Step 3: Manual verify**

Run: `python main.py`
Expected:
- Browser picker appears only when no browser set
- Camera index selection persists between runs

- [ ] **Step 4: Commit**

```bash
git add main.py actions/vision.py actions/screen_processor.py
git commit -m "feat: persist browser + camera index in settings store"
```

---

### Task 7: Remove/retire legacy config helpers + ignore settings file

**Files:**
- Modify: `.gitignore`
- Modify: `memory/config_manager.py` (or delete if unused)

- [ ] **Step 1: Ensure `config/settings.json` ignored**

Add:
```
config/settings.json
config/api_keys.json
```

- [ ] **Step 2: Decide `memory/config_manager.py` fate**

If `rg "memory.config_manager" -n` finds no imports: delete file.
If used: refactor functions to call `core.settings_store` and keep compatibility.

- [ ] **Step 3: Commit**

```bash
git add .gitignore memory/config_manager.py || true
git commit -m "chore: ignore local settings; retire legacy config helper"
```

---

## Plan self-review
- Spec coverage: settings load/save (Tasks 1,6), secrets encryption (Task 2), UI flow first-run + edit later (Task 4), legacy migration (Task 3).
- Placeholder scan: none (all steps have code/commands).
- Type consistency: `settings.json` store keys: `settings.browser`, `settings.camera_index`, `secrets.gemini_api_key`.

---

## Execution choice
Plan complete, saved to `docs/superpowers/plans/2026-05-26-settings-miniservice.md`.

2 options:
1) Subagent-Driven (recommended) — I dispatch fresh subagent per task, review between tasks
2) Inline Execution — execute tasks in this session with checkpoints

Which?