# Settings mini-service (local-only, single profile) — Design

## Goal
Ship core feature: local auth/profiles/settings sync for JARVIS, scoped to **single user / single profile**, stored in **local file** source-of-truth, with **secrets not stored plaintext**.

User-selected must-ship:
- (A) Save/load settings (gemini key, browser pref, camera index) with schema + defaults
- (C) Settings UI flow (first-run wizard + edit later)
- (B) Secrets handling (no plaintext Gemini key)

Non-goals (v1)
- Multi-user login accounts
- Multiple named profiles
- Cloud sync

## Approaches considered
1) Plain JSON only (`config/api_keys.json`) — simplest, but stores Gemini key plaintext.
2) **JSON + encrypted secret blob in file (chosen)** — keeps file source-of-truth while avoiding plaintext.
3) JSON + OS secret store (Credential Manager/keyring) — best security, but file no longer source-of-truth for secret.

## Chosen approach
**Approach 2**: move to `config/settings.json` containing non-secret settings + encrypted secret values.

- Windows: encrypt/decrypt via DPAPI (CurrentUser scope), store base64 in JSON.
- Non-Windows: allow plaintext fallback (or env var) with explicit warning; keep API stable.

## Data model
File: `config/settings.json`

```jsonc
{
  "version": 1,
  "settings": {
    "browser": "brave",
    "camera_index": 0
  },
  "secrets": {
    "gemini_api_key": {
      "enc": "dpapi",
      "value": "<base64>"
    }
  }
}
```

Defaults
- `version`: 1
- `settings.browser`: absent => trigger browser picker (existing flow)
- `settings.camera_index`: absent => auto-detect current behavior
- `secrets.gemini_api_key`: absent => show first-run API key setup UI

Migration policy
- `version` required once file exists.
- If missing/invalid: treat as v0 legacy and attempt to import from `config/api_keys.json` if present.

## Mini-service API
Module: `core/settings_store.py`

Functions
- `load_store() -> dict` (read + normalize + defaults)
- `save_store(store: dict) -> None` (atomic write)
- `load_settings() -> dict` (returns `settings` dict)
- `save_settings(patch: dict) -> dict` (merge patch into settings, persist)
- `get_gemini_key() -> str | None`
- `set_gemini_key(key: str) -> None`
- `is_configured() -> bool` (key present, length sanity)

Secret helpers (internal)
- `encrypt_secret(plain: str) -> dict` -> `{enc, value}`
- `decrypt_secret(obj: dict) -> str | None`

Atomic write
- write to temp file in same dir, then replace.

## UI flow
### First-run
- Existing `ui.py` setup frame remains.
- On save: call `settings_store.set_gemini_key()` instead of `json.dump({"gemini_api_key": ...})`.

### Edit later (minimal v1)
- Add Settings modal (Tkinter `Toplevel`) reachable from UI (button or hotkey):
  - Show current browser, camera index
  - Button: “Change browser” (reuse existing browser picker in `main.py` or move into shared UI helper)
  - Button: “Re-enter API key” (opens same masked entry, calls `set_gemini_key`)

## Integration changes
Replace direct reads of `config/api_keys.json`:
- `main.py` `_get_api_key` -> `settings_store.get_gemini_key()`
- `actions/*` + `agent/*` API key reads -> shared getter
- `actions/vision.py` / `actions/screen_processor.py` camera index reads/writes -> use `settings_store.load_settings()` + `save_settings({"camera_index": best})`

Legacy import
- If `config/api_keys.json` exists:
  - import `gemini_api_key`, `browser`, `camera_index` into new store
  - then optionally leave legacy file or rename to `.bak` (decide in impl plan)

## Security notes
- DPAPI binds secrets to current Windows user; copied file won’t decrypt elsewhere.
- Non-Windows fallback must clearly warn that secrets stored plaintext unless user opts env var.

## Testing
- Unit tests for:
  - roundtrip encrypt/decrypt (Windows mocked or conditional)
  - store normalization + defaults
  - legacy import path
- Manual QA:
  - first-run prompts
  - restart retains key + browser pref + camera index

## Verification criteria
- App boots with existing config, no plaintext key stored.
- First-run wizard saves key; subsequent runs skip wizard.
- Browser selection saved + reused.
- Camera index persists.
