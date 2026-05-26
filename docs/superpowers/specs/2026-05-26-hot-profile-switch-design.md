# Hot Profile Switch (apply on next reconnect) — Design

## Goal
Allow user to switch active profile from Settings modal while app running.
- Profile switch updates settings/secrets/memory scope immediately for future operations.
- Voice live session re-auth/profile context takes effect on reconnect.
- Provide clear UI banner + button to reconnect immediately.

## Decisions
- Switch UI located in Settings modal.
- UX: show banner “Will apply on next reconnect” and a “Reconnect now” button.
- Reconnect now: close current live session and reconnect automatically.

## Components
### UI (`ui.py`)
- Extend `open_settings_modal()`:
  - Add Profile selector (current id, list from `core.profile_store.list_profiles()`).
  - Button “New profile” -> `create_profile()` and select it.
  - On save:
    - If profile changed: call `set_active_profile_id(new_id)`
    - Show banner + enable “Reconnect now”

### Live session (`main.py` / `JarvisLive`)
- Add `JarvisLive.request_reconnect()` thread-safe flag.
- In `JarvisLive.run()` loop:
  - If reconnect requested: close current session / cancel tasks so outer loop reconnects.

## Data flow
1) User selects profile in settings modal.
2) App writes `config/profile_state.json`.
3) Settings store + secrets store now resolve to new profile id.
4) UI indicates reconnect pending.
5) User clicks “Reconnect now” -> session reconnects.

## Verification criteria
- Switch profile in settings modal updates active profile id.
- Clicking “Reconnect now” results in disconnect/reconnect without crashing.
- After reconnect, tool calls use new profile’s settings + secrets.
