# Keyring Secrets Manager Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Store all secrets in OS keyring (cross-platform via `keyring`), import once from env vars when keyring empty, and remove secrets from `config/settings.json`.

**Architecture:** Add `core/secrets_store.py` wrapping `keyring` with service naming by secret type. Update `core/settings_store.py` + all call sites to use keyring-backed secret getters. Keep `config/settings.json` for non-secrets only.

**Tech Stack:** Python 3, `keyring` library, existing settings store + Tkinter UI.

---

## File map (create/modify)

**Create**
- `core/secrets_store.py` — keyring wrapper + env import
- `tests/test_secrets_store.py` — unit tests with monkeypatched keyring

**Modify**
- `requirements.txt` — add `keyring`
- `core/settings_store.py` — remove file secret storage; delegate to secrets_store; migrate legacy
- `ui.py` — setup + settings modal save Gemini key to keyring
- (Optional) `readme.md` — mention keyring dependency + prompts

---

## Supported env vars (v1 list)

Implement mapping table in `core/secrets_store.py`:

```python
SECRET_ENV_VARS = [
    # Gemini
    "GEMINI_API_KEY",

    # OpenAI/OpenRouter/Groq
    "OPENAI_API_KEY",
    "OPENROUTER_API_KEY",
    "GROQ_API_KEY",

    # Telegram
    "TELEGRAM_BOT_TOKEN",

    # GitHub
    "GITHUB_PAT",
    "GITHUB_CLIENT_SECRET",

    # Captcha
    "CAPTCHA_SECRET",
]
```

(Keep extensible; this list is what we auto-import.)

---

### Task 1: Add `keyring` dependency + secrets store skeleton (tests first)

**Files:**
- Modify: `requirements.txt`
- Create: `core/secrets_store.py`
- Create: `tests/test_secrets_store.py`

- [ ] **Step 1: Add failing tests**

Create `tests/test_secrets_store.py`:

```python
import os


def test_service_name_by_secret_type(monkeypatch):
    from core import secrets_store

    assert secrets_store._service_name("gemini") == "mark-lxxxv:gemini"


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
    assert calls[0][0] == "mark-lxxxv:gemini"
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
```

- [ ] **Step 2: Run tests (expect fail: module missing)**

Run: `pytest -q`
Expected: FAIL with `ImportError: cannot import name 'secrets_store'` (or similar)

- [ ] **Step 3: Add `keyring` to requirements**

Edit `requirements.txt` add line:

```
keyring
```

- [ ] **Step 4: Implement minimal `core/secrets_store.py` to pass tests**

```python
from __future__ import annotations

import os

import keyring


def _secret_type_for_var(var_name: str) -> str:
    n = var_name.upper()
    if "GEMINI" in n:
        return "gemini"
    if "OPENAI" in n:
        return "openai"
    if "OPENROUTER" in n:
        return "openrouter"
    if "GROQ" in n:
        return "groq"
    if "TELEGRAM" in n:
        return "telegram"
    if n.startswith("GITHUB_"):
        return "github"
    if "CAPTCHA" in n:
        return "captcha"
    return "misc"


def _service_name(secret_type: str) -> str:
    return f"mark-lxxxv:{secret_type}"


def get_secret(var_name: str) -> str | None:
    service = _service_name(_secret_type_for_var(var_name))
    return keyring.get_password(service, var_name)


def set_secret(var_name: str, value: str) -> None:
    service = _service_name(_secret_type_for_var(var_name))
    keyring.set_password(service, var_name, value)


def import_from_env_once(var_names: list[str]) -> dict[str, str]:
    imported: dict[str, str] = {}
    for name in var_names:
        val = os.getenv(name)
        if not val:
            continue
        if get_secret(name):
            continue
        set_secret(name, val)
        imported[name] = "IMPORTED"
    return imported
```

- [ ] **Step 5: Run tests (expect pass)**

Run: `pytest -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add requirements.txt core/secrets_store.py tests/test_secrets_store.py
git commit -m "feat: add keyring-backed secrets store"
```

---

### Task 2: Wire secrets into `core/settings_store.py` (Gemini key)

**Files:**
- Modify: `core/settings_store.py`
- Modify: `tests/test_settings_store.py`

- [ ] **Step 1: Update tests to reflect keyring-backed storage**

In `tests/test_settings_store.py`, replace `set_gemini_key/get_gemini_key` tests to monkeypatch `core.secrets_store`:

```python

def test_set_get_key_delegates_to_keyring(monkeypatch, tmp_path):
    from core import settings_store

    # prevent filesystem interference
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
```

- [ ] **Step 2: Run tests (expect fail until implementation updated)**

Run: `pytest -q`
Expected: FAIL

- [ ] **Step 3: Update `core/settings_store.py` to delegate**

Edits:
- remove/stop using `encrypt_secret/decrypt_secret` for gemini
- add import:

```python
from core import secrets_store
```

- change:

```python
def get_gemini_key() -> str | None:
    return secrets_store.get_secret("GEMINI_API_KEY")


def set_gemini_key(key: str) -> None:
    secrets_store.set_secret("GEMINI_API_KEY", key.strip())
```

- keep legacy import: if `api_keys.json` has `gemini_api_key`, call `set_gemini_key()` (but only if keyring empty).

- [ ] **Step 4: Run tests (expect pass)**

Run: `pytest -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/settings_store.py tests/test_settings_store.py
git commit -m "refactor: store gemini key in keyring"
```

---

### Task 3: Import secrets from env on startup

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Add import+call early in startup**

Near top (after settings imports):

```python
from core.secrets_store import import_from_env_once

AUTO_IMPORT_VARS = [
    "GEMINI_API_KEY",
    "OPENAI_API_KEY",
    "OPENROUTER_API_KEY",
    "GROQ_API_KEY",
    "TELEGRAM_BOT_TOKEN",
    "GITHUB_PAT",
    "GITHUB_CLIENT_SECRET",
    "CAPTCHA_SECRET",
]

import_from_env_once(AUTO_IMPORT_VARS)
```

- [ ] **Step 2: Manual verify (no secrets printed)**

Run: `python main.py`
Expected: no secret value printed; app runs if keyring has Gemini key or env var provided first run.

- [ ] **Step 3: Commit**

```bash
git add main.py
git commit -m "feat: import secrets from env into keyring on startup"
```

---

### Task 4: Update UI to save Gemini key into keyring

**Files:**
- Modify: `ui.py`

- [ ] **Step 1: Replace `set_gemini_key` import if needed**

Ensure UI uses `settings_store.set_gemini_key()` (which now stores in keyring).

- [ ] **Step 2: Manual verify**

Run: `python main.py`
- Enter key in setup -> subsequent runs skip setup
- Ctrl+, modal -> set new key -> used next run

- [ ] **Step 3: Commit**

```bash
git add ui.py
git commit -m "feat: save gemini key to keyring via settings store"
```

---

### Task 5: Migrate legacy file-stored Gemini key into keyring (then remove from file)

**Files:**
- Modify: `core/settings_store.py`
- Modify: `tests/test_settings_store.py`

- [ ] **Step 1: Implement `settings_store._maybe_migrate_file_gemini_key(store: dict) -> dict`**

Add to `core/settings_store.py`:

```python
from core import secrets_store


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
```

Then call it inside `load_store()` after loading/parsing JSON (for version==1), before returning.

- [ ] **Step 2: Add unit test for migration**

Append to `tests/test_settings_store.py`:

```python

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

    # Trigger load which runs migration
    settings_store.load_store()

    assert keyring_written["val"] == "g" * 32

    stored = json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))
    assert "secrets" not in stored or "gemini_api_key" not in stored.get("secrets", {})
```

- [ ] **Step 3: Run tests**

Run: `pytest -q`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add core/settings_store.py tests/test_settings_store.py
git commit -m "chore: migrate file gemini key to keyring and remove from settings"
```

---

## Plan self-review
- Spec coverage: keyring-only storage (Tasks 1-2,5), env import once (Task 3), UI save (Task 4), no secrets in file (Task 5).
- Placeholder scan: none.
- Type consistency: env var `GEMINI_API_KEY` is canonical.

---

Plan complete and saved to `docs/superpowers/plans/2026-05-26-keyring-secrets.md`.

Two execution options:
1) Subagent-Driven (recommended)
2) Inline Execution

Which approach?