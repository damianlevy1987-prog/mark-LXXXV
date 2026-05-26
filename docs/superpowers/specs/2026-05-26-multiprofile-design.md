# Multi-profile (full separation) — Design

## Goal
Support multiple local profiles with **full separation**:
- settings
- secrets (keyring)
- memory (long_term + sessions)

Profiles selected at **startup** via picker.

## Locked-in decisions
- Profiles = full separation (settings + secrets + memory)
- Profile select at startup
- Storage: folder per profile under `config/profiles/<id>/`
- Profile IDs: numeric
- Default profile always exists: id `0`
- Memory stored under profile folder
- Secrets keyring service: `mark-lxxxv:<profile-id>:<secret-type>`
- Hot swap allowed only for next reconnect cycle (no immediate disconnect)

## Approach options
1) **Minimal profile isolation (chosen)** — isolate settings + memory + secrets; keep everything else shared.
2) Strong isolation — also isolate browser profile dir, logs, task queue state.
3) Config-only profiles — share secrets; rejected.

## Data layout
- `config/profiles/0/settings.json` (default)
- `config/profiles/0/memory/long_term.json`
- `config/profiles/0/memory/session_*.json`
- `config/profile_state.json` (active profile id, last-used)

## Components
### `core/profile_store.py` (new)
- `get_active_profile_id() -> int`
- `set_active_profile_id(id: int) -> None`
- `list_profiles() -> list[int]`
- `create_profile() -> int` (next available int)
- `ensure_profile_dirs(id: int) -> Path`

### `core/settings_store.py`
- Base dir becomes `config/profiles/<active>/`.
- Legacy migration: if old `config/settings.json` exists, migrate into profile `0`.

### `core/secrets_store.py`
- Service name includes profile id: `mark-lxxxv:{profile_id}:{secret_type}`.
- Env import once imports into **active profile** only.

### Memory
- Update `memory/memory_manager.py` to read/write from active profile memory dir.

## UI
Startup modal profile picker before connecting:
- list existing profile IDs
- button: create new profile
- select + continue
- persist selection to `config/profile_state.json`

## Verification criteria
- Switching profiles uses different settings + memory + keyring secrets.
- Profile 0 created automatically.
- Existing users migrated to profile 0 without losing settings.
