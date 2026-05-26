# Hot Profile Switch (apply on next reconnect) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let user change active profile from Settings modal and optionally reconnect live session immediately; otherwise changes apply on next reconnect.

**Architecture:** Add reconnect-request flag in `JarvisLive` and wire UI button to call it. Update Settings modal to select profile id + create new profile. Changing profile updates `profile_state.json` immediately; reconnect refreshes session context.

**Tech Stack:** Python 3, Tkinter, existing `core/profile_store.py`.

---

## File map

**Modify**
- `main.py` — add `JarvisLive.request_reconnect()` flag + handling
- `ui.py` — settings modal: profile selector + banner + reconnect button

---

### Task 1: Add reconnect request flag in JarvisLive (tests via smoke)

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Add flag + method**

In `class JarvisLive` `__init__`:

```python
self._reconnect_requested = threading.Event()
```

Add method:

```python
def request_reconnect(self):
    self._reconnect_requested.set()
```

- [ ] **Step 2: Make `run()` loop honor reconnect request**

Inside `JarvisLive.run()` main `while True:` loop, just after connecting and creating tasks, add a small task that watches event and triggers disconnect:

Simplest: in the `async with ( ... TaskGroup() as tg )` block add:

```python
async def _watch_reconnect():
    while True:
        await asyncio.sleep(0.1)
        if self._reconnect_requested.is_set():
            self._reconnect_requested.clear()
            raise RuntimeError("Reconnect requested")

tg.create_task(_watch_reconnect())
```

This intentionally raises to break out of TaskGroup and outer try/except will reconnect.

- [ ] **Step 3: Compile**

Run: `python -m py_compile main.py`
Expected: no output

- [ ] **Step 4: Commit**

```bash
git add main.py
git commit -m "feat: add reconnect request flag"
```

---

### Task 2: Add profile selector + reconnect banner/button in settings modal

**Files:**
- Modify: `ui.py`

- [ ] **Step 1: Pass jarvis reference into settings modal**

`open_settings_modal` already has access to `self`. We need access to `jarvis` instance. Add on `JarvisUI`:

```python
def set_jarvis(self, jarvis):
    self._jarvis = jarvis
```

Call from `main.py` after `jarvis = JarvisLive(ui)`:

```python
ui.set_jarvis(jarvis)
```

- [ ] **Step 2: Add profile dropdown**

In `open_settings_modal`, add at top:

```python
from core.profile_store import get_active_profile_id, list_profiles, create_profile, set_active_profile_id

active_pid = get_active_profile_id()
profiles = list_profiles()
if active_pid not in profiles:
    profiles.append(active_pid)
profiles = sorted(set(profiles))

pid_var = tk.StringVar(value=str(active_pid))
```

UI:
- label "PROFILE"
- `tk.OptionMenu` or `ttk.Combobox` (stick to tk): `OptionMenu(dialog, pid_var, *[str(p) for p in profiles])`
- button "NEW" -> create_profile(), update menu, set pid_var.

- [ ] **Step 3: Add banner + reconnect button**

Add label hidden by default:

```python
pending_lbl = tk.Label(dialog, text="Will apply on next reconnect.", fg=C_ACC2, bg=C_BG, font=("Courier", 9))
reconnect_btn = tk.Button(dialog, text="RECONNECT NOW", command=_reconnect_now, ...)
```

`_reconnect_now`:
- if `self._jarvis` exists: call `self._jarvis.request_reconnect()`

On save:
- if selected pid != active_pid:
  - `set_active_profile_id(int(pid_var.get()))`
  - show pending label + reconnect button

- [ ] **Step 4: Compile + tests**

Run:
- `python -m py_compile ui.py main.py`
- `python -m pytest -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ui.py main.py
git commit -m "feat: switch profile from settings modal"
```

---

## Plan self-review
- Spec coverage: in-modal switch + banner + reconnect now.
- Placeholder scan: none.
- Type consistency: profile id int.

---

Plan complete and saved to `docs/superpowers/plans/2026-05-26-hot-profile-switch.md`.

Two execution options:
1) Subagent-Driven (recommended)
2) Inline Execution

Which approach?
