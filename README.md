# Claude Permissions Toggle

A dark-themed GUI for controlling Claude Code tool permissions with granular allow/block settings.

![Windows](https://img.shields.io/badge/Windows-0078D6?style=flat&logo=windows&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.x-blue?style=flat&logo=python&logoColor=white)

## Features

- **Zero overhead when closed** - Hook auto-unregisters on close, Claude uses native behavior
- **Auto-registers on open** - No installer needed, just launch the app
- **Hot-loading** - Changes take effect immediately, no restart needed
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
│  ☑ Search (Glob/Grep)                   │
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

## How It Works

### App Lifecycle

| Event | What Happens |
|-------|--------------|
| **App opens** | Registers hook in `~/.claude/settings.json` |
| **Toggle OFF** | Unregisters hook, Claude reverts to native behavior |
| **Toggle ON** | Re-registers hook, permissions applied |
| **App closes** | Unregisters hook, Claude reverts to native behavior |

When the app is closed **or toggled OFF**, there's **zero overhead** - no hook runs, no Python spawns. Claude Code uses its built-in permission logic.

Your saved custom template and preferences (minimal mode, last template, ✎ state) persist across restarts.

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
| Search | `Glob`, `Grep` |
| Web access | `WebFetch`, `WebSearch` |
| Notebook edit | `NotebookEdit` |
| Task/Todo tools | `Task`, `TodoWrite` (legacy), `TaskCreate`, `TaskUpdate`, `TaskList`, `TaskGet` (v2.1.16+) |
| Bash (safe) | Safe commands: npm, node, python, pip, ls, cd, echo, curl, etc. |
| Bash (delete) | `rm`, `del`, `rmdir`, `rd`, `erase`, `unlink`, `shred` |
| Bash (all) | `Bash`, `BashOutput`, `KillShell` |
| Git | Any command containing `git` |

**Note:** Task tools were updated in Claude Code v2.0.59-2.1.16. This hook supports both legacy (`TodoWrite`) and new (`TaskCreate`, `TaskUpdate`, `TaskList`, `TaskGet`) versions.

### Hook Response Format

The hook always outputs explicit JSON responses to Claude Code:

| Response | Meaning |
|----------|---------|
| `"permissionDecision": "allow"` | Auto-approve the tool |
| `"permissionDecision": "deny"` | Auto-block the tool |
| `"permissionDecision": "ask"` | Prompt user for permission |

**Note:** Claude Code treats no output as "allow", so the hook must always respond.

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
| `claude-permissions-hook.py` | Hook logic with pattern matching |
| `install.py` | Installer / uninstaller |
| `test_patterns.py` | Pattern verification test suite |

## Config Location

`~/.claude-permissions.json` - Stores your saved custom template and preferences.

When the app closes, active permissions are cleared but your saved template persists.

## Uninstall

Since the hook auto-unregisters when the app closes, simply closing the app is enough for normal use.

To fully remove:
```bash
python install.py --uninstall       # Removes config files
python install.py --uninstall --full  # Also removes project folder
```

## Requirements

- Windows 10/11
- Python 3.x
- Claude Code CLI

## License

MIT
