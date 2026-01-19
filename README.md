# Claude Permissions Toggle

A dark-themed GUI for controlling Claude Code tool permissions with granular allow/block settings.

![Windows](https://img.shields.io/badge/Windows-0078D6?style=flat&logo=windows&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.x-blue?style=flat&logo=python&logoColor=white)

## Features

- **Hot-loading** - Changes take effect immediately, no restart needed
- **Two-layer system** - ALLOW categories + BLOCK specific patterns
- **13 destructive patterns** blocked by default (rm -rf, git reset --hard, etc.)
- **Save custom templates** - Save your preferred settings and recall them
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

## Installation

```bash
git clone https://github.com/Trigun1127/Claude-allow-all-toggle.git
cd Claude-allow-all-toggle
python install.py
```

Then double-click `AutoYesToggle.pyw` to launch.

**Note:** The installer will configure Claude Code to use your system's Python. If you have multiple Python installations, you may need to manually update the path in `~/.claude/settings.json`.

## How It Works

### Two-Layer Permission System

1. **ALLOW** = Categories of tools to auto-approve
2. **BLOCK** = Specific dangerous patterns to always deny (even if category is allowed)

**Example:** You can allow "Git commands" but still block "git push --force".

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

This runs 53 test cases against the regex patterns to ensure destructive commands are blocked.

## Files

| File | Purpose |
|------|---------|
| `AutoYesToggle.pyw` | Dark-themed GUI toggle |
| `claude-permissions-hook.py` | Hook logic with pattern matching |
| `install.py` | Automated installer |
| `test_patterns.py` | Pattern verification test suite |

## Config Location

`~/.claude-permissions.json` - Created when you enable any permissions.

No file = OFF mode (Claude asks for everything).

## Uninstall

```bash
python install.py --uninstall
```

## Requirements

- Windows 10/11
- Python 3.x
- Claude Code CLI

## License

MIT
