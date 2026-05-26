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
