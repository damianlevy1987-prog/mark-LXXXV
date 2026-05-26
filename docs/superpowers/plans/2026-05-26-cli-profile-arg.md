# CLI --profile Argument Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `--profile <id>` CLI arg to select active profile before UI starts. Improve error message when Tk UI cannot open.

**Architecture:** Parse args in `main.py` (argparse). If `--profile` provided, call `core.profile_store.set_active_profile_id(id)` before constructing `JarvisUI`. Wrap UI creation in try/except to print actionable message.

**Tech Stack:** Python stdlib `argparse`, existing `core/profile_store.py`.

---

### Task 1: Add argparse + select profile early

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Add argparse helper**

Add near bottom, above `main()`:

```python
import argparse


def _parse_args():
    p = argparse.ArgumentParser(add_help=True)
    p.add_argument("--profile", type=int, default=None, help="Active profile id (numeric)")
    return p.parse_args()
```

- [ ] **Step 2: Apply profile selection before UI init**

Inside `main()` before `ui = JarvisUI(...)`:

```python
from core.profile_store import set_active_profile_id
args = _parse_args()
if args.profile is not None:
    set_active_profile_id(args.profile)
```

- [ ] **Step 3: Run compile + tests**

Run:
- `python -m py_compile main.py`
- `python -m pytest -q`

Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add main.py
git commit -m "feat: add --profile CLI arg"
```

---

### Task 2: Better error message when UI cannot open

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Wrap UI creation**

Replace:

```python
ui = JarvisUI("face.png")
```

With:

```python
try:
    ui = JarvisUI("face.png")
except Exception as e:
    print("Failed to start UI (Tkinter).")
    print("If running headless, set a display or run on desktop environment.")
    raise
```

- [ ] **Step 2: Run compile + tests**

Run:
- `python -m py_compile main.py`
- `python -m pytest -q`

Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add main.py
git commit -m "chore: improve UI startup error message"
```
