# Claude Allow-All Toggle - Installation Instructions

This file contains instructions for AI agents to install the Claude Code auto-approve toggle.

## What This Does

Installs a toggle that allows users to enable/disable automatic approval of ALL Claude Code tool calls.

## Installation Steps

### Step 1: Copy Hook Script

Copy `auto-yes-hook.cmd` to the user's home directory:

**Windows:**
```bash
copy auto-yes-hook.cmd %USERPROFILE%\
```

**Or programmatically:**
```python
import shutil
import os
shutil.copy('auto-yes-hook.cmd', os.path.expanduser('~'))
```

### Step 2: Configure Claude Code Settings

The hook must be registered in Claude Code's settings file at `%USERPROFILE%\.claude\settings.json`.

**If the file doesn't exist**, create it with:
```json
{
  "hooks": {
    "PreToolUse": [{
      "matcher": "*",
      "hooks": [{
        "type": "command",
        "command": "%USERPROFILE%\\auto-yes-hook.cmd"
      }]
    }]
  }
}
```

**If the file exists**, merge the `hooks` section. Example Python code:

```python
import json
import os

settings_path = os.path.join(os.path.expanduser('~'), '.claude', 'settings.json')

# Read existing settings
if os.path.exists(settings_path):
    with open(settings_path, 'r') as f:
        settings = json.load(f)
else:
    settings = {}

# Add hooks configuration
hook_entry = {
    "matcher": "*",
    "hooks": [{
        "type": "command",
        "command": os.path.join(os.path.expanduser('~'), 'auto-yes-hook.cmd')
    }]
}

if "hooks" not in settings:
    settings["hooks"] = {}
if "PreToolUse" not in settings["hooks"]:
    settings["hooks"]["PreToolUse"] = []

# Check if hook already exists
hook_exists = any(
    h.get("hooks", [{}])[0].get("command", "").endswith("auto-yes-hook.cmd")
    for h in settings["hooks"]["PreToolUse"]
)

if not hook_exists:
    settings["hooks"]["PreToolUse"].append(hook_entry)

# Write settings
os.makedirs(os.path.dirname(settings_path), exist_ok=True)
with open(settings_path, 'w') as f:
    json.dump(settings, f, indent=2)
```

### Step 3: Place Toggle on Desktop

Copy the toggle GUI to the user's desktop:

```bash
copy AutoYesToggle.pyw %USERPROFILE%\Desktop\
```

### Step 4: Verify Installation

1. The hook script should be at: `%USERPROFILE%\auto-yes-hook.cmd`
2. The settings file should contain the hooks configuration
3. The toggle should be at: `%USERPROFILE%\Desktop\AutoYesToggle.pyw`

### Step 5: Test

1. Double-click `AutoYesToggle.pyw` on the desktop
2. Click to turn ON (green)
3. In Claude Code, any tool call should now auto-approve
4. Click to turn OFF (red) to restore normal permission flow

## File Locations Summary

| File | Destination |
|------|-------------|
| `auto-yes-hook.cmd` | `%USERPROFILE%\auto-yes-hook.cmd` |
| `AutoYesToggle.pyw` | `%USERPROFILE%\Desktop\AutoYesToggle.pyw` |
| Settings entry | `%USERPROFILE%\.claude\settings.json` |
| Flag file (created by toggle) | `%USERPROFILE%\.claude-auto-yes` |

## Uninstallation

1. Delete `%USERPROFILE%\auto-yes-hook.cmd`
2. Delete `%USERPROFILE%\.claude-auto-yes` (if exists)
3. Remove the PreToolUse hook entry from `%USERPROFILE%\.claude\settings.json`
4. Delete `%USERPROFILE%\Desktop\AutoYesToggle.pyw`
