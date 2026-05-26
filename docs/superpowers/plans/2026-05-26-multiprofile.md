# Multi-profile (full separation) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add numeric-ID multi-profile support with startup profile picker, isolating settings + secrets + memory per profile.

**Architecture:** Introduce `core/profile_store.py` to manage active profile id + directories. Update settings store to use `config/profiles/<id>/settings.json` and migrate legacy single-profile settings into profile 0. Update secrets store keyring service namespace to include profile id. Update memory manager to store per-profile memory under `config/profiles/<id>/memory/`.

**Tech Stack:** Python 3, stdlib JSON/Pathlib, Tkinter, keyring.

---

## File map

**Create**
- `core/profile_store.py`
- `tests/test_profile_store.py`

**Modify**
- `core/settings_store.py`
- `core/secrets_store.py`
- `main.py`
- `ui.py`
- `memory/memory_manager.py`

---

## Conventions
- Default profile id = `0`
- Profile root = `config/profiles/<id>/`
- Settings file = `config/profiles/<id>/settings.json`
- Memory dir = `config/profiles/<id>/memory/`
- Active profile state file = `config/profile_state.json` with `{ "active_profile_id": <int> }`

---

### Task 1: Add profile store (tests first)

**Files:**
- Create: `core/profile_store.py`
- Create: `tests/test_profile_store.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_profile_store.py`:

```python
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
```

- [ ] **Step 2: Run tests (expect fail: module missing)**

Run: `python -m pytest -q`
Expected: FAIL

- [ ] **Step 3: Implement `core/profile_store.py` minimal**

```python
from __future__ import annotations

import json
import sys
from pathlib import Path


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR = get_base_dir()
CONFIG_DIR = BASE_DIR / "config"
PROFILES_DIR = CONFIG_DIR / "profiles"
STATE_FILE = CONFIG_DIR / "profile_state.json"


def ensure_profile_dirs(profile_id: int) -> Path:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    root = PROFILES_DIR / str(profile_id)
    (root / "memory").mkdir(parents=True, exist_ok=True)
    return root


def list_profiles() -> list[int]:
    if not PROFILES_DIR.exists():
        return []
    out: list[int] = []
    for p in PROFILES_DIR.iterdir():
        if p.is_dir() and p.name.isdigit():
            out.append(int(p.name))
    return sorted(out)


def _read_state() -> dict:
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_state(data: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def get_active_profile_id() -> int:
    ensure_profile_dirs(0)
    st = _read_state()
    pid = st.get("active_profile_id")
    if isinstance(pid, int) and pid >= 0:
        ensure_profile_dirs(pid)
        return pid
    _write_state({"active_profile_id": 0})
    return 0


def set_active_profile_id(profile_id: int) -> None:
    if profile_id < 0:
        raise ValueError("profile_id must be >= 0")
    ensure_profile_dirs(profile_id)
    _write_state({"active_profile_id": int(profile_id)})


def create_profile() -> int:
    ids = list_profiles()
    next_id = (max(ids) + 1) if ids else 0
    while (PROFILES_DIR / str(next_id)).exists():
        next_id += 1
    ensure_profile_dirs(next_id)
    return next_id
```

- [ ] **Step 4: Run tests (expect pass)**

Run: `python -m pytest -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/profile_store.py tests/test_profile_store.py
git commit -m "feat: add profile store"
```

---

### Task 2: Make settings store per-profile + migrate legacy settings

**Files:**
- Modify: `core/settings_store.py`

- [ ] **Step 1: Add helper to compute per-profile paths**

Add near top:

```python
from core.profile_store import get_active_profile_id, ensure_profile_dirs


def _profile_config_dir() -> Path:
    pid = get_active_profile_id()
    return ensure_profile_dirs(pid)
```

Then change `CONFIG_DIR` usage in this module:
- `SETTINGS_FILE` becomes dynamic: `(_profile_config_dir() / "settings.json")`
- legacy single-profile file `config/settings.json` treated as migration input into profile 0.

- [ ] **Step 2: Implement migration**

On load:
- If `config/settings.json` exists and `config/profiles/0/settings.json` does not, move/copy content into profile 0, then delete legacy file.

- [ ] **Step 3: Add unit test for migration**

Create new test in `tests/test_settings_store.py` that writes legacy file under temp config dir, then asserts profile 0 file created.

- [ ] **Step 4: Run tests**

Run: `python -m pytest -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/settings_store.py tests/test_settings_store.py
git commit -m "refactor: per-profile settings store"
```

---

### Task 3: Update secrets store keyring namespace to include profile id

**Files:**
- Modify: `core/secrets_store.py`
- Modify: `tests/test_secrets_store.py`

- [ ] **Step 1: Update service naming to include active profile id**

Change `_service_name`:

```python
from core.profile_store import get_active_profile_id

def _service_name(secret_type: str) -> str:
    pid = get_active_profile_id()
    return f"mark-lxxxv:{pid}:{secret_type}"
```

- [ ] **Step 2: Update tests**

Monkeypatch `get_active_profile_id` to return fixed value (e.g. 2) and assert service name matches.

- [ ] **Step 3: Run tests**

Run: `python -m pytest -q`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add core/secrets_store.py tests/test_secrets_store.py
git commit -m "feat: scope keyring secrets by profile id"
```

---

### Task 4: Move memory to per-profile directory

**Files:**
- Modify: `memory/memory_manager.py`

- [ ] **Step 1: Change memory paths to use `config/profiles/<id>/memory/`**

Add:

```python
from core.profile_store import ensure_profile_dirs, get_active_profile_id

PROFILE_ROOT = ensure_profile_dirs(get_active_profile_id())
MEM_DIR = PROFILE_ROOT / "memory"
```

Then update existing memory file paths to be under `MEM_DIR`.

- [ ] **Step 2: Migration**

If legacy `memory/long_term.json` exists and profile 0 memory does not, move/copy into profile 0.

- [ ] **Step 3: Add regression test (optional)**

If memory manager has tests, add; otherwise add a small unit test verifying computed paths.

- [ ] **Step 4: Run tests**

Run: `python -m pytest -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add memory/memory_manager.py
git commit -m "refactor: store memory per profile"
```

---

### Task 5: Add startup profile picker (UI)

**Files:**
- Modify: `ui.py`
- Modify: `main.py`

- [ ] **Step 1: Add `JarvisUI.choose_profile()` modal**

Implement Toplevel with listbox of profile ids + buttons:
- Create new profile (calls `create_profile()`)
- Select profile (calls `set_active_profile_id(selected)`)

- [ ] **Step 2: Call picker early in startup**

In `main.py` before starting session connection, call UI picker once.

- [ ] **Step 3: Manual verify**

Run: `python main.py`
Expected:
- modal appears
- selecting profile changes settings/memory/secrets scope

- [ ] **Step 4: Commit**

```bash
git add ui.py main.py
git commit -m "feat: startup profile picker"
```

---

## Plan self-review
- Spec coverage: per-profile dirs, default profile 0, startup picker, memory isolation, keyring isolation.
- Placeholder scan: none.
- Type consistency: profile id int.

---

Plan complete and saved to `docs/superpowers/plans/2026-05-26-multiprofile.md`.

Two execution options:
1) Subagent-Driven (recommended)
2) Inline Execution

Which approach?
