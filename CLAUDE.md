# Claude Permissions Toggle - AI Agent Instructions

Instructions for AI agents working with this project.

## What This Project Does

A GUI toggle for controlling Claude Code tool permissions with:
- **ALLOW categories** - Which tool types to auto-approve
- **BLOCK patterns** - Specific destructive commands to always deny
- **Hot-loading** - Changes take effect immediately
- **Custom templates** - Save and recall custom configurations
- **Minimal mode** - Collapse to single ON/OFF toggle

## Architecture

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
| `claude-permissions-hook.py` | PreToolUse hook with pattern matching |
| `claude-permissions-toggle.py` | Installer / uninstaller |
| `test_patterns.py` | 53 test cases for pattern verification |

## Installation

```bash
python claude-permissions-toggle.py
```

This will:
1. Register hook in `~/.claude/settings.json` (points to repo source)
2. Clean up any old hook files

**Auto-updates:** Hook runs directly from repo folder - `git pull` updates take effect immediately.

## Minimal Mode

Collapse the full UI into a single ON/OFF toggle button:

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

**Minimal UI:**
```
┌──────────────────────┐
│ [...] [   ALL*    ] │ ← Single toggle, [...] expands
└──────────────────────┘
```

- Click `_` in full UI to minimize
- Click `...` in minimal UI to expand
- Toggle remembers last active mode (ALL*, ALL, or CUSTOM)
- Preference persists across restarts

## Config File Format

`~/.claude-permissions.json`:
```json
{
  "minimal_mode": false,
  "last_active_template": "all_safe",
  "allow": {
    "read": true,
    "write": true,
    "edit": true,
    "search": true,
    "web": false,
    "notebook": false,
    "task": true,
    "bash_safe": false,
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

## Hook Input Format

Claude Code sends JSON via stdin with snake_case keys:
```json
{
  "tool_name": "Read",
  "tool_input": {"file_path": "..."},
  "session_id": "...",
  ...
}
```

**Important:** Use `tool_name` and `tool_input` (not camelCase).

## Hook Output Format

The hook **must always** output a JSON response. No output = allow (Claude Code behavior).

```json
{
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

## Git Override Behavior

When `git=OFF`, git commands always return `"ask"` even if `bash_all=ON`.
This ensures granular control - you can allow all bash but still require approval for git.

## Testing Patterns

Run without executing any commands:
```bash
python test_patterns.py
```

## Uninstall

```bash
python claude-permissions-toggle.py --uninstall        # Keep project folder
python claude-permissions-toggle.py --uninstall --full # Remove everything
```
