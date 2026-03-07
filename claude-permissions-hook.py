#!/usr/bin/env python3
"""
Claude Permissions Hook
Checks allow categories + block patterns from config.

Logic:
1. Check if command matches a BLOCK pattern -> DENY
2. Check if tool/command matches an ALLOW category -> ALLOW
3. Otherwise -> ASK (explicit permission request)

Safety behavior:
- If toggle app is not running, this hook cleans stale state and asks.
- This prevents orphaned "allow all" config after crashes/forced termination.
"""
import json
import os
import re
import sys
import msvcrt

CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".claude-permissions.json")
SETTINGS_FILE = os.path.join(os.path.expanduser("~"), ".claude", "settings.json")
LOCK_FILE = os.path.join(os.path.expanduser("~"), ".claude-permissions.lock")
HOOK_MARKERS = [
    "auto-yes-hook.cmd",
    "claude-permissions-hook.cmd",
    "claude-permissions-hook.py",
]
PRESERVED_CONFIG_KEYS = [
    "saved_custom",
    "minimal_mode",
    "last_active_template",
    "write_edit_on",
]

# Tool name -> category mapping
# Keep in sync with Claude Code's current tool names.
TOOL_CATEGORIES = {
    "Read": "read",
    "Write": "write",
    "Edit": "edit",
    "Glob": "search",
    "Grep": "search",
    "LSP": "search",
    "MCPSearch": "search",
    "ToolSearch": "search",
    "WebFetch": "web",
    "WebSearch": "web",
    "NotebookEdit": "notebook",
    # Agent/task tools (old + new)
    "Agent": "task",          # Launches a sub-agent
    "Task": "task",           # Legacy alias
    "TodoWrite": "task",      # Legacy (pre-2.0.59)
    "AskUserQuestion": "task",
    "ExitPlanMode": "task",
    "Skill": "task",
    "TaskCreate": "task",     # New (2.1.16+)
    "TaskUpdate": "task",     # New (2.0.59+)
    "TaskList": "task",       # New (2.1.16+)
    "TaskGet": "task",        # New (2.1.16+)
    "TaskStop": "task",       # Stop background tasks
    "TaskOutput": "task",     # Read background task output
    # Bash tools
    "Bash": "bash",
    "BashOutput": "bash",
    "KillShell": "bash",
}

# Safe bash command prefixes
SAFE_BASH = [
    "npm ", "npm.cmd ", "npx ", "pnpm ", "yarn ",
    "node ", "python ", "python3 ", "pip ", "pip3 ",
    "ls ", "dir ", "pwd", "cd ", "cat ", "type ", "head ", "tail ",
    "echo ", "printf ", "mkdir ", "touch ",
    "curl ", "wget ", "which ", "where ", "whoami", "hostname",
    "env", "printenv", "set ",
]

# File deletion command prefixes (single and batch)
# When bash_delete is OFF, these commands will ASK for permission
DELETE_COMMANDS = [
    "rm ",       # Unix/Linux/Mac file delete
    "rm	",      # rm with tab
    "del ",      # Windows file delete
    "del	",
    "rmdir ",    # Remove directory (Unix)
    "rd ",       # Remove directory (Windows)
    "rd	",
    "erase ",    # Windows alias for del
    "unlink ",   # Unix file delete
    "shred ",    # Secure delete
]

# Block pattern detection functions
BLOCK_PATTERNS = {
    "rm_rf": lambda cmd: bool(re.search(r"\brm\s+.*-[^\s]*r[^\s]*f|rm\s+.*-[^\s]*f[^\s]*r|\brm\s+-rf\b", cmd, re.IGNORECASE)),
    "rm_rf_root": lambda cmd: bool(re.search(r"\brm\s+.*-rf\s+[/~]|\brm\s+.*-rf\s+\$HOME|\brm\s+.*-rf\s+%USERPROFILE%", cmd, re.IGNORECASE)),
    "git_reset_hard": lambda cmd: "git reset --hard" in cmd or "git reset --merge" in cmd,
    "git_checkout_discard": lambda cmd: bool(re.search(r"git\s+checkout\s+--\s+", cmd)),
    "git_clean": lambda cmd: bool(re.search(r"git\s+clean\s+-[^\s]*f", cmd)),
    "git_push_force": lambda cmd: bool(re.search(r"git\s+push\s+.*--force|git\s+push\s+-f\b", cmd)),
    "git_branch_delete": lambda cmd: bool(re.search(r"git\s+branch\s+-D\b", cmd)),
    "git_stash_drop": lambda cmd: "git stash drop" in cmd or "git stash clear" in cmd,
    "find_delete": lambda cmd: bool(re.search(r"find\s+.*-delete", cmd)),
    "xargs_rm": lambda cmd: bool(re.search(r"xargs\s+.*rm|parallel\s+.*rm", cmd)),
    "dd_if": lambda cmd: cmd.strip().startswith("dd ") and "if=" in cmd,
    "mkfs": lambda cmd: cmd.strip().startswith("mkfs"),
    "chmod_777": lambda cmd: bool(re.search(r"chmod\s+.*-R\s+777\s+/", cmd)),
}


def atomic_write_json(path, payload):
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    temp_path = f"{path}.tmp"

    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.flush()
        os.fsync(f.fileno())

    os.replace(temp_path, path)


def load_json(path):
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def load_config():
    """Load config from file, return None if not found."""
    return load_json(CONFIG_FILE)


def is_toggle_hook(entry):
    hooks = entry.get("hooks", [])
    for hook in hooks:
        command = hook.get("command", "")
        if any(marker in command for marker in HOOK_MARKERS):
            return True
    return False


def unregister_hook_if_present():
    settings = load_json(SETTINGS_FILE)
    if not isinstance(settings, dict):
        return

    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return

    pretool_hooks = hooks.get("PreToolUse")
    if not isinstance(pretool_hooks, list):
        return

    filtered = [entry for entry in pretool_hooks if not is_toggle_hook(entry)]
    if len(filtered) == len(pretool_hooks):
        return

    if filtered:
        hooks["PreToolUse"] = filtered
    else:
        hooks.pop("PreToolUse", None)

    if not hooks:
        settings.pop("hooks", None)

    try:
        atomic_write_json(SETTINGS_FILE, settings)
    except OSError:
        # If we cannot unregister here, default ask behavior still keeps it safe.
        pass


def is_toggle_running():
    """Detect whether the toggle UI process currently holds the runtime lock."""
    if not os.path.exists(LOCK_FILE):
        return False

    try:
        with open(LOCK_FILE, "a+b") as lock_handle:
            lock_handle.seek(0, os.SEEK_END)
            if lock_handle.tell() == 0:
                lock_handle.write(b"1")
                lock_handle.flush()
            lock_handle.seek(0)

            try:
                msvcrt.locking(lock_handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                return True
            else:
                msvcrt.locking(lock_handle.fileno(), msvcrt.LK_UNLCK, 1)
                return False
    except OSError:
        return False


def has_active_permissions(config):
    if not isinstance(config, dict):
        return False
    return isinstance(config.get("allow"), dict) or isinstance(config.get("block"), dict)


def clear_active_permissions(config):
    preserved = {}
    if isinstance(config, dict):
        for key in PRESERVED_CONFIG_KEYS:
            if key in config:
                preserved[key] = config[key]

    if preserved:
        try:
            atomic_write_json(CONFIG_FILE, preserved)
        except OSError:
            pass
    elif os.path.exists(CONFIG_FILE):
        try:
            os.remove(CONFIG_FILE)
        except OSError:
            pass


def cleanup_stale_state(config):
    if has_active_permissions(config):
        clear_active_permissions(config)

    if os.path.exists(LOCK_FILE):
        try:
            os.remove(LOCK_FILE)
        except OSError:
            pass

    unregister_hook_if_present()


def is_git_command(cmd):
    """Check if command contains a git command (handles chained commands)."""
    # Split on && || ; | and check each part
    parts = re.split(r"\s*(?:&&|\|\||[;|])\s*", cmd)
    for part in parts:
        part = part.strip()
        if part.startswith("git ") or part.startswith("git.exe "):
            return True
        # Handle env vars like VAR=x git push
        if " git " in part or part.endswith(" git"):
            return True
    return False


def is_safe_bash(cmd):
    """Check if ALL parts of a chained command are safe."""
    # Split on && || ; | and check each part
    parts = re.split(r"\s*(?:&&|\|\||[;|])\s*", cmd)
    for part in parts:
        part = part.strip().lower()
        if not part:
            continue
        # Check if this part starts with a safe prefix
        is_part_safe = any(part.startswith(prefix.lower()) for prefix in SAFE_BASH)
        if not is_part_safe:
            return False  # One unsafe part = whole chain is unsafe
    return True  # All parts are safe


def is_delete_command(cmd):
    """Check if ANY part of a chained command is a file deletion command."""
    # Split on && || ; | and check each part
    parts = re.split(r"\s*(?:&&|\|\||[;|])\s*", cmd)
    for part in parts:
        part = part.strip().lower()
        if not part:
            continue
        # Check if this part starts with a delete command
        if any(part.startswith(prefix.lower()) for prefix in DELETE_COMMANDS):
            return True
        # Also catch "rm" at end of line (bare command)
        if part == "rm" or part == "del" or part == "rd" or part == "rmdir":
            return True
    return False


def check_blocks(cmd, config):
    """Check if command matches any enabled block pattern."""
    blocks = config.get("block", {})
    for pattern_id, detector in BLOCK_PATTERNS.items():
        if blocks.get(pattern_id, True) and detector(cmd):
            return pattern_id
    return None


def check_permission(tool_name, tool_input, config):
    """
    Check if tool should be allowed.
    Returns: "allow", ("block", reason), or None (ask)

    Flow for bash commands:
    1. BLOCK patterns -> DENY
    2. Git command? -> Check git category (never falls through)
    3. Safe bash? -> Check bash_safe category
    4. Delete command? -> Check bash_delete category (never falls through)
    5. bash_all enabled? -> ALLOW
    6. Otherwise -> ASK
    """
    allow = config.get("allow", {})
    category = TOOL_CATEGORIES.get(tool_name)

    if category is None:
        return None  # Unknown tool, let Claude ask

    # Non-bash tools: simple category check
    if category != "bash":
        if allow.get(category, False):
            return "allow"
        return None

    # Bash tools: first check block patterns
    cmd = tool_input.get("command", "")

    blocked = check_blocks(cmd, config)
    if blocked:
        return ("block", blocked)

    # Check git category - if git is OFF, require approval (don't fall through)
    if is_git_command(cmd):
        if allow.get("git", False):
            return "allow"
        return None  # Git OFF = always ask, even if bash_all is ON

    # Check bash_safe - if bash_safe is OFF, fall through to bash_all
    if is_safe_bash(cmd):
        if allow.get("bash_safe", False):
            return "allow"
        # Safe commands can still be allowed by bash_all

    # Check bash_delete - if OFF, require approval (don't fall through to bash_all)
    # This lets user verify deletion is correct even when bash_all is enabled
    if is_delete_command(cmd):
        if allow.get("bash_delete", False):
            return "allow"
        return None  # Delete OFF = always ask, even if bash_all is ON

    # Check bash_all (allows anything not blocked, except git/delete when those are OFF)
    if allow.get("bash_all", False):
        return "allow"

    return None


def ask_permission(reason="Requires user approval"):
    """Output JSON to ask for user permission."""
    print(json.dumps({
        "continue": True,
        "suppressOutput": False,
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": reason
        }
    }))


def main():
    config = load_config()

    if not is_toggle_running():
        cleanup_stale_state(config)
        ask_permission("Permissions toggle not running; reverted to default prompts")
        return

    if config is None:
        # No config = OFF mode, ask for everything
        ask_permission("Permissions toggle: OFF mode")
        return

    # Read tool info from stdin
    try:
        input_data = json.loads(sys.stdin.read())
    except Exception:
        ask_permission("Permissions toggle: Could not read input")
        return

    # Note: Claude Code uses snake_case (tool_name, tool_input)
    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})

    # Check permission
    result = check_permission(tool_name, tool_input, config)

    if result == "allow":
        print(json.dumps({
            "continue": True,
            "suppressOutput": False,
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "permissionDecisionReason": "Auto-approved by permissions toggle"
            }
        }))
    elif isinstance(result, tuple) and result[0] == "block":
        print(json.dumps({
            "continue": True,
            "suppressOutput": False,
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": f"Blocked by toggle: {result[1]} pattern"
            }
        }))
    else:
        # Explicitly ask for permission (no output doesn't work)
        print(json.dumps({
            "continue": True,
            "suppressOutput": False,
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason": "Requires user approval"
            }
        }))


if __name__ == "__main__":
    main()
