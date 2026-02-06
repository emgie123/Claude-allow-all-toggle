#!/usr/bin/env python3
"""
Claude Permissions Hook
Checks allow categories + block patterns from config.

Logic:
1. Check if command matches a BLOCK pattern -> DENY
2. Check if tool/command matches an ALLOW category -> ALLOW
3. Otherwise -> ASK (explicit permission request)

Note: Must always output JSON response. No output = allow (Claude Code behavior).
"""
import sys
import os
import json
import re

CONFIG_FILE = os.path.join(os.path.expanduser("~"), '.claude-permissions.json')

# Tool name -> category mapping
TOOL_CATEGORIES = {
    "Read": "read",
    "Write": "write",
    "Edit": "edit",
    "Glob": "search",
    "Grep": "search",
    "WebFetch": "web",
    "WebSearch": "web",
    "NotebookEdit": "notebook",
    # Task tools (old + new)
    "Task": "task",
    "TodoWrite": "task",      # Legacy (pre-2.0.59)
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
    "rm\t",      # rm with tab
    "del ",      # Windows file delete
    "del\t",
    "rmdir ",    # Remove directory (Unix)
    "rd ",       # Remove directory (Windows)
    "rd\t",
    "erase ",    # Windows alias for del
    "unlink ",   # Unix file delete
    "shred ",    # Secure delete
]

# Block pattern detection functions
BLOCK_PATTERNS = {
    "rm_rf": lambda cmd: bool(re.search(r'\brm\s+.*-[^\s]*r[^\s]*f|rm\s+.*-[^\s]*f[^\s]*r|\brm\s+-rf\b', cmd, re.IGNORECASE)),
    "rm_rf_root": lambda cmd: bool(re.search(r'\brm\s+.*-rf\s+[/~]|\brm\s+.*-rf\s+\$HOME|\brm\s+.*-rf\s+%USERPROFILE%', cmd, re.IGNORECASE)),
    "git_reset_hard": lambda cmd: "git reset --hard" in cmd or "git reset --merge" in cmd,
    "git_checkout_discard": lambda cmd: bool(re.search(r'git\s+checkout\s+--\s+', cmd)),
    "git_clean": lambda cmd: bool(re.search(r'git\s+clean\s+-[^\s]*f', cmd)),
    "git_push_force": lambda cmd: bool(re.search(r'git\s+push\s+.*--force|git\s+push\s+-f\b', cmd)),
    "git_branch_delete": lambda cmd: bool(re.search(r'git\s+branch\s+-D\b', cmd)),
    "git_stash_drop": lambda cmd: "git stash drop" in cmd or "git stash clear" in cmd,
    "find_delete": lambda cmd: bool(re.search(r'find\s+.*-delete', cmd)),
    "xargs_rm": lambda cmd: bool(re.search(r'xargs\s+.*rm|parallel\s+.*rm', cmd)),
    "dd_if": lambda cmd: cmd.strip().startswith("dd ") and "if=" in cmd,
    "mkfs": lambda cmd: cmd.strip().startswith("mkfs"),
    "chmod_777": lambda cmd: bool(re.search(r'chmod\s+.*-R\s+777\s+/', cmd)),
}


def load_config():
    """Load config from file, return None if not found."""
    if not os.path.exists(CONFIG_FILE):
        return None
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except:
        return None


def is_git_command(cmd):
    """Check if command contains a git command (handles chained commands)."""
    # Split on && || ; | and check each part
    parts = re.split(r'\s*(?:&&|\|\||[;|])\s*', cmd)
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
    parts = re.split(r'\s*(?:&&|\|\||[;|])\s*', cmd)
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
    parts = re.split(r'\s*(?:&&|\|\||[;|])\s*', cmd)
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
    1. BLOCK patterns → DENY
    2. Git command? → Check git category (never falls through)
    3. Safe bash? → Check bash_safe category
    4. Delete command? → Check bash_delete category (never falls through)
    5. bash_all enabled? → ALLOW
    6. Otherwise → ASK
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
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": reason
        }
    }))


def main():
    # Load config
    config = load_config()
    if config is None:
        # No config = OFF mode, ask for everything
        ask_permission("Permissions toggle: OFF mode")
        return

    # Read tool info from stdin
    try:
        input_data = json.loads(sys.stdin.read())
    except:
        ask_permission("Permissions toggle: Could not read input")
        return

    # Note: Claude Code uses snake_case (tool_name, tool_input)
    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})

    # Check permission
    result = check_permission(tool_name, tool_input, config)

    if result == "allow":
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "permissionDecisionReason": "Auto-approved by permissions toggle"
            }
        }))
    elif isinstance(result, tuple) and result[0] == "block":
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": f"Blocked by toggle: {result[1]} pattern"
            }
        }))
    else:
        # Explicitly ask for permission (no output doesn't work)
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason": "Requires user approval"
            }
        }))


if __name__ == "__main__":
    main()
