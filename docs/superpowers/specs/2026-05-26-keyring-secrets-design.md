# Keyring Secrets Manager — Design

## Goal
Move secrets out of `config/settings.json` and into OS keyring, cross-platform, using Python `keyring`. Keep non-secret settings in `config/settings.json`. Support importing secrets from environment variables once (keyring empty -> import), then **keyring becomes source-of-truth**.

## User decisions locked in
- OS secret store is source-of-truth (file stores non-secrets only)
- Cross-platform via `keyring` library
- Prompts/unlock dialogs acceptable
- Import from env vars on startup if keyring missing (one-time)
- Naming: service = `mark-lxxxv:<secret-type>`; username = exact env var name
- After import, env var ignored (keyring wins)

## Non-goals (v1)
- End-to-end encryption of secrets in files (no secrets in files)
- Multi-user profiles / per-profile secrets (future)
- Sync secrets between machines

## Approach options considered
1) **Keyring-only (chosen)** — simplest mental model; secrets never written to file.
2) Hybrid fallback to file-encrypted secrets — more robust when keyring backend missing, but added complexity and two sources.
3) Env-only — no persistence and too easy to leak.

## Data model
### Non-secrets
File: `config/settings.json`
- `version: 1`
- `settings: { browser, camera_index, ... }`
- `secrets` section removed (or ignored during migration)

### Secrets
OS keyring entries:
- **service**: `mark-lxxxv:<secret-type>`
- **username**: exact env var name (`GEMINI_API_KEY`, `TELEGRAM_BOT_TOKEN`, ...)
- **password/value**: secret value

Secret type mapping (initial)
- `gemini`: `GEMINI_API_KEY`
- `openai`: `OPENAI_API_KEY`
- `openrouter`: `OPENROUTER_API_KEY`
- `groq`: `GROQ_API_KEY`
- `telegram`: `TELEGRAM_BOT_TOKEN`
- `github`: `GITHUB_PAT`, `GITHUB_CLIENT_SECRET`
- `captcha`: `CAPTCHA_SECRET`

(Exact list can expand; design supports arbitrary env var names.)

## Modules / responsibilities
### `core/secrets_store.py` (new)
Public API:
- `get_secret(var_name: str) -> str | None`
- `set_secret(var_name: str, value: str) -> None`
- `import_from_env_once(var_names: list[str]) -> dict[str, str]`  
  Returns mapping of imported var_name -> redacted marker (never logs raw secret).

Internal:
- `_secret_type_for_var(var_name) -> str` (mapping table; unknown -> `misc`)
- `_service_name(secret_type) -> str` => `mark-lxxxv:{secret_type}`

Error handling:
- If keyring backend missing/unavailable/locked, raise a typed exception with actionable message.

### `core/settings_store.py` (modify)
- Remove `encrypt_secret/decrypt_secret` and file secret storage for `gemini_api_key`.
- Add migration: if legacy file contains `gemini_api_key`, write to keyring as `GEMINI_API_KEY` (only if keyring missing), then remove/ignore file secret.
- Provide `get_gemini_key()` by calling `secrets_store.get_secret("GEMINI_API_KEY")`.

### Call sites
Replace callers to use:
- `get_gemini_key()` remains stable, but now backed by keyring.

## Startup behavior
1) Load non-secret settings from `config/settings.json`.
2) Call `secrets_store.import_from_env_once([...])` early in startup (before Gemini client init).
3) Read required secrets from keyring.
4) If required secret missing, show clear UI message / console error.

## UI changes
- Settings modal: “Gemini API key” save writes to keyring (`set_secret("GEMINI_API_KEY", ...)`).
- First-run wizard: same as today, but save to keyring.

## Security notes
- Never print secret values.
- Prefer allowing users to supply secrets via env vars in CI/dev; import-once prevents repeated overwrites.
- Keyring prompts are acceptable; document this.

## Testing
- Unit tests: monkeypatch `keyring` module functions.
- Tests cover:
  - import-from-env when keyring empty
  - ignore env when key exists
  - service naming by secret type

## Verification criteria
- `config/settings.json` contains no secrets.
- Secrets persist across runs via keyring.
- Env var set once imports into keyring; subsequent runs use keyring even if env changes.
