# Claude Permissions Toggle

A dark-themed GUI for controlling Claude Code tool permissions with granular allow/block settings.

![Windows](https://img.shields.io/badge/Windows-0078D6?style=flat&logo=windows&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.x-blue?style=flat&logo=python&logoColor=white)

## Features

- **Zero overhead when closed** - Hook auto-unregisters on close, Claude uses native behavior
- **Auto-registers on open** - No installer needed, just launch the app
- **Fast W/E mode** - Write/Edit/NotebookEdit can run without the permission dialog flash
- **Hot toggles** - Category changes take effect immediately while the hook is already loaded
- **Two-layer system** - ALLOW categories + BLOCK specific patterns
- **13 destructive patterns** blocked by default (rm -rf, git reset --hard, etc.)
- **Save custom templates** - Settings persist across app restarts
- **Minimal mode** - Collapse to single ON/OFF toggle
- **Dark theme** with scrollable UI

## Screenshot

```
┌──────────────────────────────────────────┐
│  Claude Permissions                      │
│  CUSTOM - 5 allowed, 13 blocked          │
├──────────────────────────────────────────┤
│  [OFF] [ALL*] [ALL] [CUSTOM]    [Save]  │
├──────────────────────────────────────────┤
│  ALLOW (auto-approve):                   │
│  ☑ Read files                           │
│  ☑ Write files                          │
│  ☑ Edit files                           │
│  ☑ Search (Glob/Grep/ToolSearch)         │
│  ☐ Web access                           │
│  ☐ Notebook edit                        │
│  ☑ Task/Todo tools                      │
│  ☐ Bash (safe: npm, node, pip, ls)      │
│  ☐ Bash (file deletion: rm, del, rmdir) │
│  ☐ Bash (all commands)                  │
│  ☐ Git commands                         │
├──────────────────────────────────────────┤
│  BLOCK (always deny):                    │
│  ☑ rm -rf (recursive force delete)      │
│  ☑ rm -rf / or ~ (root/home delete)     │
│  ☑ git reset --hard                     │
│  ☑ git checkout -- (discard changes)    │
│  ☑ git clean -f                         │
│  ☑ git push --force                     │
│  ☑ git branch -D (force delete)         │
│  ☑ git stash drop/clear                 │
│  ☑ find -delete                         │
│  ☑ xargs/parallel rm                    │
│  ☑ dd if= (disk write)                  │
│  ☑ mkfs (format disk)                   │
│  ☑ chmod -R 777 /                       │
└──────────────────────────────────────────┘
```

### Minimal Mode

Click the `_` button to collapse into a compact split-toggle view:

```
┌────────────────────────────────┐
│ [...] [✎] │ [   ALL*      ] │
└────────────────────────────────┘
```

**Split Button Controls:**
| Button | What it does |
|--------|--------------|
| `✎` | Toggle Write/Edit permissions (blue=ON, gray=OFF) |
| `ALL*` / `CUSTOM` / etc. | Toggle all custom permissions ON/OFF |
| `...` | Expand back to full UI |

**States:**
| Custom | ✎ | Title Bar | Result |
|--------|---|-----------|--------|
| OFF | (disabled) | `Claude: OFF` | Hook unregistered - Claude uses native behavior |
| ON | OFF | `Claude: R/O\|ALL*` | Read-only - can read, search, bash, but NOT write/edit |
| ON | ON | `Claude: W/E\|ALL*` | Full custom - everything including write/edit |

**Use case:** Stay in read-only mode while exploring, then flip ✎ on when ready to make changes.

- Remembers both states across restarts
- ✎ controls: Write, Edit, NotebookEdit

## Installation

```bash
git clone https://github.com/Trigun1127/Claude-allow-all-toggle.git
cd Claude-allow-all-toggle
```

Then double-click `AutoYesToggle.pyw` to launch. That's it!

**Notes:**
- **No installer needed** - The app registers the hook automatically when opened
- **Auto-updates:** After `git pull`, changes take effect immediately
- If you have multiple Python installations, the app uses whichever `python` runs it
- If Claude Code was already open before the hook was registered, restart Claude Code once or review the change in `/hooks`

### Pin to Taskbar (Optional)

Use `create_shortcut.ps1` to create a desktop shortcut, then pin it to the taskbar for one-click access:

```powershell
powershell -ExecutionPolicy Bypass -File create_shortcut.ps1
```

1. Right-click the new **Claude Permissions** shortcut on your desktop
2. Select **Pin to taskbar**
3. Delete the desktop shortcut (the taskbar pin persists independently)

Now you can launch the toggle directly from the taskbar without a desktop shortcut.

## How It Works

### App Lifecycle

| Event | What Happens |
|-------|--------------|
| **App opens** | Registers `PreToolUse` + `PermissionRequest` hooks in `~/.claude/settings.json` |
| **W/E ON** | Temporarily adds `Write`, `Edit`, `NotebookEdit` to `permissions.allow` for a no-flash edit flow |
| **Toggle OFF** | Unregisters hooks, removes managed W/E allow rules, Claude reverts to native behavior |
| **App closes** | Unregisters hooks, removes managed W/E allow rules, Claude reverts to native behavior |

When the app is closed **or toggled OFF**, there's **zero overhead** - no hook runs, no Python spawns. Claude Code uses its built-in permission logic.

Your saved custom template and preferences (minimal mode, last template, ✎ state) persist across restarts.

### Why Write/Edit Is Different

Recent Claude Code builds can surface native file-permission UI through `PermissionRequest`, even when `PreToolUse` is already installed. To keep Write/Edit/NotebookEdit fast when W/E is ON, the toggle temporarily manages both:

- Hook decisions for `PreToolUse` and `PermissionRequest`
- Matching `permissions.allow` entries for `Write`, `Edit`, and `NotebookEdit`

Those allow rules are only managed while the toggle is active. Turning W/E OFF or closing the app removes the rules it added, so Claude goes back to its normal prompts.

### Two-Layer Permission System

1. **ALLOW** = Categories of tools to auto-approve
2. **BLOCK** = Specific dangerous patterns to always deny (even if category is allowed)

**Example:** You can allow "Git commands" but still block "git push --force".

### Tool Categories

Each checkbox controls one or more Claude Code tools:

| Category | Claude Tools |
|----------|--------------|
| Read files | `Read` |
| Write files | `Write` |
| Edit files | `Edit` |
| Search | `Glob`, `Grep`, `LSP`, `MCPSearch`, `ToolSearch` |
| Web access | `WebFetch`, `WebSearch` |
| Notebook edit | `NotebookEdit` |
| Task/Todo tools | `Agent`, `Task`, `TodoWrite` (legacy), `AskUserQuestion`, `ExitPlanMode`, `Skill`, `TaskCreate`, `TaskUpdate`, `TaskList`, `TaskGet`, `TaskOutput` |
| Bash (safe) | Safe commands: npm, node, python, pip, ls, cd, echo, curl, etc. |
| Bash (delete) | `rm`, `del`, `rmdir`, `rd`, `erase`, `unlink`, `shred` |
| Bash (all) | `Bash`, `BashOutput`, `KillShell` |
| Git | Any command containing `git` |

**Note:** Claude Code tool names evolve over time. This hook supports legacy names (`TodoWrite`, `Task`) and current names (`Agent`, `AskUserQuestion`, `ExitPlanMode`, `Skill`, `TaskCreate`, `TaskUpdate`, `TaskList`, `TaskGet`, `TaskOutput`).

### Hook Response Format

The toggle handles two Claude Code hook events:

**`PreToolUse` response**

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

**`PermissionRequest` response**

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

If the hook emits no `PermissionRequest` decision, Claude shows its normal permission dialog.

### Git Commands Override

When `git=OFF`, git commands will **always** ask for permission, even if `bash_all=ON`. This ensures granular control over git operations.

### File Deletion Override (bash_delete)

When `bash_delete=OFF`, file deletion commands will **always** ask for permission, even if `bash_all=ON`. This lets you verify what's being deleted before it happens.

**Detected deletion commands:**
- `rm`, `del`, `rmdir`, `rd`, `erase`, `unlink`, `shred`

**Why this matters:** Even if you trust Claude with general bash commands, accidental deletions can be catastrophic. With `bash_delete=OFF`, you get a prompt showing exactly what files will be deleted before approving.

**Template defaults:**
| Template | bash_delete |
|----------|-------------|
| OFF | OFF |
| ALL* | **OFF** (always verify deletions) |
| ALL | ON |

### Chained Command Handling

Claude often chains commands together (e.g., `cd /path && git push`). The hook properly handles these:

**Git detection:** Checks ALL parts of a chained command for git operations:
```bash
# All detected as git commands:
git push                      # Direct git command
cd /path && git push          # Git in second part
echo "done" && git status     # Git in chain
VAR=x git push                # Git with env vars
```

**Safe bash detection:** Requires ALL parts to be safe:
```bash
# Safe (all parts in safe list):
echo "test" && npm install

# NOT safe (tasklist not in safe list):
echo "test" && tasklist       # Falls through to bash_all check
```

**Delete detection:** Checks if ANY part is a deletion command:
```bash
# All detected as delete commands (when bash_delete=OFF):
rm file.txt                   # Simple delete
npm run build && rm -r dist   # Delete in chain
ls -la; rm old.txt            # Delete after semicolon
```

This prevents bypassing permissions by prefixing commands with safe operations.

### Templates

| Button | What it does |
|--------|--------------|
| **OFF** | Nothing auto-approved, Claude asks for everything |
| **ALL*** | Everything allowed, but destructive patterns blocked (recommended) |
| **ALL** | Everything allowed including destructive (dangerous!) |
| **CUSTOM** | Loads your saved custom settings |

### Save Button

Click **Save** to store your current settings as a custom template. Later, click **CUSTOM** to restore them.

## Block Patterns

Inspired by [claude-code-safety-net](https://github.com/kenryu42/claude-code-safety-net):

| Pattern | What it catches |
|---------|-----------------|
| `rm -rf` | `rm -rf`, `rm -Rf`, `rm -fr` (case insensitive) |
| `rm -rf / or ~` | Deleting root, home, $HOME, %USERPROFILE% |
| `git reset --hard` | `--hard`, `--merge` |
| `git checkout --` | Discarding file changes |
| `git clean -f` | Force cleaning untracked files |
| `git push --force` | `-f`, `--force`, `--force-with-lease` |
| `git branch -D` | Force deleting branches |
| `git stash drop/clear` | Losing stashed work |
| `find -delete` | Mass file deletion |
| `xargs/parallel rm` | Piped deletion commands |
| `dd if=` | Raw disk writes |
| `mkfs` | Formatting disks |
| `chmod -R 777 /` | Dangerous recursive permissions |

## Testing

Verify all patterns work correctly (without executing anything dangerous):

```bash
python test_patterns.py
```

This runs 84 test cases against the block patterns and delete detection to ensure destructive commands are blocked and file deletions are properly detected.

## Files

| File | Purpose |
|------|---------|
| `AutoYesToggle.pyw` | Dark-themed GUI toggle |
| `claude-permissions-hook.py` | Dual hook logic with pattern matching |
| `install.py` | Installer / uninstaller |
| `test_patterns.py` | Pattern verification test suite |

## Config Location

Two files matter:

- `~/.claude-permissions.json` - Saved template, minimal mode, last template, write/edit state, and transient rule ownership
- `~/.claude/settings.json` - Registered hooks and temporary `permissions.allow` entries while W/E is ON

When the app closes, active permissions are cleared, managed allow rules are removed, and your saved template persists.

## Uninstall

Since the hook auto-unregisters when the app closes, simply closing the app is enough for normal use.

To fully remove:
```bash
python install.py --uninstall       # Removes config files
python install.py --uninstall --full  # Also removes project folder
```

## Troubleshooting

### Hooks failing after Claude Code update ("hook error" on every tool)

**Symptom:** Every tool call shows a hook error or prompts for permission even though the toggle is ON. Claude Code logs may show `command not found` or `Hook output does not start with {`.

**Cause:** Claude Code runs hook commands via Git Bash on Windows. If your hook was registered with raw Windows backslash paths (e.g. `C:\Users\...\python.exe`), Bash mangles them and the hook process fails before producing any JSON output. Claude Code then falls back to its default permission behavior (prompting for everything).

**Fix:**

1. **Update the repo:** `git pull` to get the latest version
2. **Re-register the hook:** Either:
   - Close and reopen `AutoYesToggle.pyw`, OR
   - Run `python install.py`
3. **Restart Claude Code** (hooks are snapshot at session startup)

**Verify:** Check `~/.claude/settings.json` — the hook command should use **quoted forward-slash paths**:
```json
"command": "\"C:/Users/.../python.exe\" \"C:/Users/.../claude-permissions-hook.py\""
```

Not backslash paths like `C:\\Users\\...\\python.exe`.

**What changed:**
- Hook commands now use quoted forward-slash paths compatible with both cmd.exe and Git Bash
- `pythonw.exe` is replaced with `python.exe` (the GUI subsystem executable can't reliably pipe stdout when spawned by Claude Code)
- Hook JSON responses include explicit `continue` and `suppressOutput` fields for latest Claude Code compatibility

### Write/Edit still asks for permission or flashes briefly

**Symptom:** Write/Edit works, but Claude briefly shows the native prompt or still asks every time.

**Fix:**

1. Close and reopen `AutoYesToggle.pyw` so the latest hook code is the running process
2. Start a new Claude Code session, or review/reload the hook in `/hooks`
3. Check `~/.claude/settings.json` and confirm both hook events are present:
   - `hooks.PreToolUse`
   - `hooks.PermissionRequest`
4. While W/E is ON, confirm `permissions.allow` includes:
   - `Write`
   - `Edit`
   - `NotebookEdit`

**Expected behavior:**
- W/E ON: write/edit tools should run without the prompt flash
- W/E OFF: Claude should return to its normal permission prompt

### Hook shows "error" label but permissions work fine

This is a [known Claude Code bug](https://github.com/anthropics/claude-code/issues/17088) (cosmetic only). If your permissions are actually being applied correctly, the "error" label can be ignored.

## Requirements

- Windows 10/11
- Python 3.x
- Claude Code CLI

## License

MIT
