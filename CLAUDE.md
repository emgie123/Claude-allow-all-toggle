# Claude Permissions Toggle - AI Agent Instructions

Instructions for AI agents working with this project.

## What This Project Does

A GUI toggle for controlling Claude Code tool permissions with:
- **ALLOW categories** - Which tool types to auto-approve
- **BLOCK patterns** - Specific destructive commands to always deny
- **Fast W/E mode** - Write/Edit/NotebookEdit can run without the prompt flash
- **Approval display modes** - `silent` or `show_accepts` for prompt-worthy allowed tools
- **Hot toggles** - Category changes take effect immediately while hooks are already loaded
- **Custom templates** - Save and recall custom configurations
- **Minimal mode** - Collapse to single ON/OFF toggle

## Architecture

The GUI owns two pieces of state:

- `~/.claude-permissions.json` for saved templates and live toggle state
- `~/.claude/settings.json` for hook registration plus transient `permissions.allow` entries while W/E is ON

```
AutoYesToggle.pyw (GUI)
        │
        │ writes
        ▼
~/.claude-permissions.json (config)
        │
        │ reads
        ▼
claude-permissions-hook.py (hook)
        │
        │ registered in
        ▼
~/.claude/settings.json (Claude Code config)
```

## Key Files

| File | Purpose |
|------|---------|
| `AutoYesToggle.pyw` | Tkinter GUI with dark theme |
| `claude-permissions-hook.py` | Dual hook handler for `PreToolUse` and `PermissionRequest` |
| `install.py` | Installer / uninstaller |
| `test_patterns.py` | Pattern, delete, tool-mapping, and approval-mode tests |
| `test_state_preservation.py` | Regression test for preserved UI state written on close |

## Installation

```bash
python install.py
```

This will:
1. Register `PreToolUse` and `PermissionRequest` hooks in `~/.claude/settings.json` (points to repo source)
2. Clean up any old hook files

**Auto-updates:** Hook runs directly from repo folder - `git pull` updates take effect immediately.
If Claude Code is already open, restart it once or review the hook change in `/hooks`.

## Minimal Mode

Collapse the full UI into a compact split-toggle view:

**Full UI:**
```
┌─────────────────────────────────────────┐
│ Claude Permissions               [ _ ] │ ← Click to minimize
│ ALL* - 13 destructive blocked          │
├─────────────────────────────────────────┤
│ [OFF] [ALL*] [ALL] [CUSTOM]    [Save] │
│ ...checkboxes...                        │
└─────────────────────────────────────────┘
```

**Minimal UI (Split Button):**
```
┌────────────────────────────────┐
│ [...] [✎] │ [   ALL*      ] │
└────────────────────────────────┘
```

**Split Button Controls:**
| Button | Purpose |
|--------|---------|
| `✎` | Toggle Write/Edit/NotebookEdit permissions (blue=ON, gray=OFF) |
| `ALL*` etc. | Toggle all custom permissions ON/OFF |
| `...` | Expand back to full UI |

**States:**
| Custom | ✎ | Title Bar | Result |
|--------|---|-----------|--------|
| OFF | (disabled) | `Claude: OFF` | Full minimal - ask for everything |
| ON | OFF | `Claude: R/O\|ALL*\|SILENT` | Read-only - can read, search, bash, but NOT write/edit |
| ON | ON | `Claude: W/E\|ALL*\|SILENT` | Full custom - everything including write/edit |
| ON | ON | `Claude: W/E\|ALL*\|SHOW` | Full custom while the main window is set to visible approvals |

**Use case:** Stay in read-only mode while exploring code, then flip W/E on when ready to make changes.

- Click `_` in full UI to minimize
- Click `...` in minimal UI to expand
- Both states (Custom mode + W/E) persist across restarts

## Config File Format

`~/.claude-permissions.json`:
```json
{
  "minimal_mode": false,
  "last_active_template": "all_safe",
  "write_edit_on": true,
  "approval_mode": "silent",
  "managed_allow_rules": ["Edit", "NotebookEdit", "Write"],
  "allow": {
    "read": true,
    "write": true,
    "edit": true,
    "search": true,
    "web": false,
    "notebook": false,
    "task": true,
    "bash_safe": false,
    "bash_delete": false,
    "bash_all": false,
    "git": false
  },
  "block": {
    "rm_rf": true,
    "rm_rf_root": true,
    "git_reset_hard": true,
    ...
  },
  "saved_custom": { ... }
}
```

`managed_allow_rules` tracks which `permissions.allow` entries were added by the toggle so they can be removed cleanly when W/E is turned off or the app exits.

`approval_mode` controls whether allowed prompt-worthy tools should stay hidden (`silent`) or show Claude's approval UI before being auto-accepted (`show_accepts`).

## Hook Input Format

Claude Code sends JSON via stdin with snake_case keys:
```json
{
  "hook_event_name": "PreToolUse|PermissionRequest",
  "tool_name": "Read",
  "tool_input": {"file_path": "..."},
  "session_id": "...",
  ...
}
```

**Important:** Use `tool_name` and `tool_input` (not camelCase). The same hook script now receives both `PreToolUse` and `PermissionRequest` events.

## Hook Output Format

`PreToolUse` should always return an explicit JSON decision:

```json
{
  "continue": true,
  "suppressOutput": false,
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow|deny|ask",
    "permissionDecisionReason": "Reason string"
  }
}
```

| Decision | Effect |
|----------|--------|
| `"allow"` | Auto-approve, no user prompt |
| `"deny"` | Auto-block, tool won't run |
| `"ask"` | Prompt user for permission |

`PermissionRequest` uses a different payload:

```json
{
  "hookSpecificOutput": {
    "hookEventName": "PermissionRequest",
    "decision": {
      "behavior": "allow|deny"
    }
  }
}
```

If no `PermissionRequest` decision is emitted, Claude shows its normal prompt.

## Write/Edit Fast Path

When W/E is ON, the GUI temporarily adds `Write`, `Edit`, and `NotebookEdit` to `permissions.allow` in `~/.claude/settings.json`. That avoids the prompt flash on recent Claude Code builds. Those managed rules must be removed again when W/E is OFF or the app closes.

## Approval Display Modes

The hook supports two approval behaviors:

- `silent`: `PreToolUse` returns `allow`, so approved tools run without showing the permission UI
- `show_accepts`: `PreToolUse` returns `ask`, then `PermissionRequest` returns `allow`, so Claude shows the approval surface and auto-accepts it

## Recent Fixes

Recent code changes in this repo include:

- Windows `PowerShell` tool support in the hook's shell classification
- newer Claude tool-name coverage for MCP resource readers and task/team/worktree actions
- `approval_mode` persistence across normal app close/restart
- stronger detection for env-wrapped delete commands
- stronger PowerShell root/home delete blocking for quoted and slash-style paths
- removal of the approval toggle from minimal mode

## Git Override Behavior

When `git=OFF`, git commands always return `"ask"` even if `bash_all=ON`.
This ensures granular control - you can allow all bash but still require approval for git.

## File Deletion Override (bash_delete)

When `bash_delete=OFF`, file deletion commands always return `"ask"` even if `bash_all=ON`.
This lets you verify exactly what will be deleted before approving.

**Detected commands:** `rm`, `del`, `rmdir`, `rd`, `erase`, `unlink`, `shred`, `Remove-Item`, `ri`

**Chained commands:** If ANY part of a chained command is a delete, it triggers the check:
```bash
npm build && rm -r dist   # Detected as delete
ls -la; rm old.txt        # Detected as delete
```

## Testing Patterns

Run without executing any commands:
```bash
python test_patterns.py
python test_state_preservation.py
```

## Uninstall

```bash
python install.py --uninstall        # Keep project folder
python install.py --uninstall --full # Remove everything
```
