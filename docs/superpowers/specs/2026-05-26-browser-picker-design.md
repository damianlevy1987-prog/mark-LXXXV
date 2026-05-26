# Browser Picker for Settings Modal — Design

## Goal
Replace the plain-text BROWSER field in the settings modal with a compound selector: dropdown of detected browsers + optional custom path input + refresh button.

## Components
### Dropdown (tk.OptionMenu)
- Populated from `actions.browser.detect_installed_browsers()` — shows `b["display"]` name.
- First entry: `"Auto-detect"` (saves `""` → lets `_resolve_browser()` decide).
- Last entry: `"Custom path..."` — selecting reveals the text field below.
- On modal open: pre-select matching entry from `get_browser_preference()`.

### Refresh button (🔄)
- Re-runs `detect_installed_browsers()`, rebuilds dropdown options.
- Useful if user installs a browser while settings modal is open.

### Custom path text field
- `tk.Entry` hidden by default; shown when `"Custom path..."` selected.
- Holds full executable path (e.g. `/usr/bin/brave-browser`).
- Saved as-is via `set_browser_preference(path)`.

## Data flow
| Action | Effect |
|--------|--------|
| Select detected browser | `set_browser_preference(name)` |
| Select "Auto-detect" | `set_browser_preference("")` |
| Select "Custom path..." | reveal Entry; on save `set_browser_preference(entry_value)` |

## Files changed
- **Modify** `ui.py` — replace `tk.Entry` for BROWSER with compound selector widget.

## Not changed
- `actions/browser.py` — no changes needed (reuses `detect_installed_browsers`, `get_browser_preference`, `set_browser_preference`).

## Verification
- Open settings modal (Ctrl+,)
- Browser field shows dropdown with detected browsers + "Auto-detect" + "Custom path..."
- Selecting a detected browser saves preference correctly
- Custom path entry field appears/disappears as expected
- Refresh button re-scans and updates dropdown
