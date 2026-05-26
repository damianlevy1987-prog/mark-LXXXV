# Browser Picker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace plain-text BROWSER field in settings modal with dropdown of detected browsers + custom path fallback + refresh button.

**Architecture:** Single-file change to `ui.py` `open_settings_modal()`. Reuses existing `actions/browser.detect_installed_browsers()`, `get_browser_preference()`, `set_browser_preference()`.

**Tech Stack:** Python 3, tkinter.

---

## File map

**Modify**
- `ui.py` — `open_settings_modal()`: replace `tk.Entry` for BROWSER with compound selector

---

### Task 1: Build browser picker widget in settings modal

**Files:**
- Modify: `ui.py` (in `open_settings_modal`, replace the BROWSER entry block)

- [ ] **Step 1: Read current BROWSER block in `open_settings_modal`**

Current code in `ui.py` around line 630-640:

```python
tk.Label(dialog, text="BROWSER", fg=C_DIM, bg=C_BG, font=("Courier", 9)).pack(pady=(12, 2))
browser_var = tk.StringVar(value=str(s.get("browser", "")))
tk.Entry(
    dialog,
    textvariable=browser_var,
    width=40,
    fg=C_TEXT,
    bg="#000d12",
    insertbackground=C_TEXT,
    borderwidth=0,
    font=("Courier", 10),
).pack()
```

- [ ] **Step 2: Add imports at top of `open_settings_modal`**

Add inside the function, after existing imports:

```python
from actions.browser import detect_installed_browsers, get_browser_preference, set_browser_preference
```

- [ ] **Step 3: Replace BROWSER block with compound selector**

Replace the BROWSER label + Entry block with:

```python
tk.Label(dialog, text="BROWSER", fg=C_DIM, bg=C_BG, font=("Courier", 9)).pack(pady=(12, 2))

browser_row = tk.Frame(dialog, bg=C_BG)
browser_row.pack(pady=(0, 2))

browsers = detect_installed_browsers()
browser_names = [b["name"] for b in browsers if b["available"]]
browser_displays = {b["name"]: b["display"] for b in browsers if b["available"]}

# Build option list: Auto-detect + detected browsers + Custom path
browser_options = ["(Auto-detect)"] + browser_names + ["(Custom path...)"]

current_pref = str(s.get("browser", ""))
# Find best match for current preference
if current_pref in browser_names:
    browser_default = current_pref
elif current_pref:
    browser_default = "(Custom path...)"
else:
    browser_default = "(Auto-detect)"

browser_var = tk.StringVar(value=browser_default)

def _rebuild_browser_dropdown():
    """Re-scan installed browsers and rebuild the OptionMenu."""
    nb = detect_installed_browsers()
    nb_names = [b["name"] for b in nb if b["available"]]
    nb_display = {b["name"]: b["display"] for b in nb if b["available"]}
    menu = browser_menu["menu"]
    menu.delete(0, "end")
    for opt in ["(Auto-detect)"] + nb_names + ["(Custom path...)"]:
        label = nb_display.get(opt, opt)
        menu.add_command(label=label, command=lambda v=opt: browser_var.set(v))
    return nb_names

browser_menu = tk.OptionMenu(browser_row, browser_var, *browser_options)
browser_menu.configure(
    bg=C_BG,
    fg=C_PRI,
    activebackground=C_DIM,
    activeforeground=C_PRI,
    highlightthickness=0,
    borderwidth=0,
    font=("Courier", 10),
)
browser_menu["menu"].configure(bg=C_BG, fg=C_PRI, activebackground=C_DIM, activeforeground=C_PRI)
browser_menu.pack(side="left", padx=(0, 6))

tk.Button(
    browser_row,
    text="↻",
    command=_rebuild_browser_dropdown,
    bg=C_BG,
    fg=C_PRI,
    activebackground=C_DIM,
    font=("Courier", 10),
    borderwidth=0,
    padx=10,
    pady=4,
).pack(side="left")

# Custom path entry — shown only when "(Custom path...)" is selected
custom_path_frame = tk.Frame(dialog, bg=C_BG)
custom_path_entry = tk.Entry(
    custom_path_frame,
    width=40,
    fg=C_TEXT,
    bg="#000d12",
    insertbackground=C_TEXT,
    borderwidth=0,
    font=("Courier", 10),
)
custom_path_entry.pack()

if current_pref and current_pref not in browser_names:
    custom_path_entry.insert(0, current_pref)
    custom_path_frame.pack(pady=(4, 0))
else:
    custom_path_frame.pack_forget()

def _on_browser_change(*_):
    """Show/hide custom path entry based on dropdown selection."""
    sel = browser_var.get()
    if sel == "(Custom path...)":
        custom_path_frame.pack(pady=(4, 0))
    else:
        custom_path_frame.pack_forget()

browser_var.trace_add("write", _on_browser_change)
```

- [ ] **Step 4: Update `_save()` to use the new browser widget**

Find the `_save()` function inside `open_settings_modal`. Replace the browser save block:

Current:

```python
patch = {}
b = browser_var.get().strip()
if b:
    patch["browser"] = b
```

Replace with:

```python
patch = {}
b = browser_var.get().strip()
if b == "(Auto-detect)":
    patch["browser"] = ""
elif b == "(Custom path...)":
    path = custom_path_entry.get().strip()
    if path:
        patch["browser"] = path
elif b in browser_displays:
    patch["browser"] = b
```

- [ ] **Step 5: Compile + tests**

Run:
- `python -m py_compile ui.py`
- `python -m pytest -q`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add ui.py
git commit -m "feat: browser picker in settings modal"
```

---

## Plan self-review
1. **Spec coverage:** dropdown with detected browsers, (Auto-detect), (Custom path...), refresh button, custom path entry toggle — all covered.
2. **Placeholder scan:** no TBD/TODO.
3. **Type consistency:** `browser_var` used consistently in both widget setup and save logic; `browser_displays` dict used for name→display mapping.

---

Plan complete and saved to `docs/superpowers/plans/2026-05-26-browser-picker.md`.

Two execution options:
1) Subagent-Driven (recommended)
2) Inline Execution

Which approach?
