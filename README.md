# Claude Allow-All Toggle

A simple GUI toggle that enables/disables auto-approval of ALL Claude Code tool calls using the native hooks system.

![Toggle Preview](https://img.shields.io/badge/Status-ON-green) ![Toggle Preview](https://img.shields.io/badge/Status-OFF-red)

## What It Does

When **ON**: Claude Code automatically approves ALL tool calls (Read, Write, Edit, Bash, etc.) without asking for permission.

When **OFF**: Normal permission flow - Claude Code asks before each tool use.

## How It Works

```
┌─────────────────┐     creates/removes     ┌──────────────────┐
│ AutoYesToggle   │ ──────────────────────► │ .claude-auto-yes │
│ (GUI Toggle)    │                         │ (Flag File)      │
└─────────────────┘                         └────────┬─────────┘
                                                     │
                                                     │ checks if exists
                                                     ▼
┌─────────────────┐     registers      ┌──────────────────────┐
│ settings.json   │ ─────────────────► │ auto-yes-hook.cmd    │
│ (Claude Config) │                    │ IF flag exists:      │
└─────────────────┘                    │   output "allow" JSON│
                                       └──────────────────────┘
```

## Installation

### Option 1: Automated (Recommended)

```bash
python install.py
```

### Option 2: Manual

1. **Copy the hook script** to your home directory:
   ```
   copy auto-yes-hook.cmd %USERPROFILE%\
   ```

2. **Add hook to Claude Code settings** - Edit `%USERPROFILE%\.claude\settings.json`:
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

   Or if you already have settings, just add the `hooks` section.

3. **Place the toggle** anywhere convenient (Desktop recommended):
   ```
   copy AutoYesToggle.pyw %USERPROFILE%\Desktop\
   ```

4. **Double-click** `AutoYesToggle.pyw` to launch the toggle.

## Usage

1. Double-click `AutoYesToggle.pyw` to open the toggle window
2. Click the button to toggle between **ON** (green) and **OFF** (red)
3. The toggle stays always-on-top in the bottom-right corner
4. State persists even after closing the toggle window

## Requirements

- Windows (uses `%USERPROFILE%` environment variable)
- Python 3.x with tkinter (included in standard Python)
- Claude Code CLI

## Files

| File | Purpose |
|------|---------|
| `AutoYesToggle.pyw` | GUI toggle - click to enable/disable |
| `auto-yes-hook.cmd` | Hook script - checks flag and approves tools |
| `install.py` | Automated installer |
| `CLAUDE.md` | Instructions for AI agents |

## How the Hook Works

The hook uses Claude Code's native [PreToolUse hook](https://docs.anthropic.com/en/docs/claude-code/hooks) system:

1. Claude Code calls `auto-yes-hook.cmd` before EVERY tool use
2. The script checks if `%USERPROFILE%\.claude-auto-yes` exists
3. If yes: outputs JSON with `"permissionDecision": "allow"` → tool runs without asking
4. If no: outputs nothing → normal permission flow

## Safety Notes

- **Use responsibly** - This bypasses ALL permission prompts
- Toggle OFF when you want to review changes before they happen
- The hook only affects YOUR machine - it's not a security risk to others

## Uninstall

```bash
python install.py --uninstall
```

Or manually:
1. Delete `%USERPROFILE%\auto-yes-hook.cmd`
2. Delete `%USERPROFILE%\.claude-auto-yes`
3. Remove the `hooks` section from `%USERPROFILE%\.claude\settings.json`

## License

MIT
