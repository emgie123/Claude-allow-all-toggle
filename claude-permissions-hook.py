#!/usr/bin/env python3
"""
Claude Permissions Hook
Checks allow categories + block patterns from config.

Logic:
1. Check if command matches a BLOCK pattern -> BLOCK
2. Check if tool/command matches an ALLOW category -> ALLOW
3. Otherwise -> let Claude ask (no output)
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
    "Task": "task",
    "TodoWrite": "task",
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
    """Check if command is a git command."""
    return cmd.strip().startswith("git ") or cmd.strip().startswith("git.exe ")


def is_safe_bash(cmd):
    """Check if command starts with a safe prefix."""
    cmd_lower = cmd.lower().strip()
    return any(cmd_lower.startswith(prefix.lower()) for prefix in SAFE_BASH)


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
    Returns: "allow", ("block", reason), or None
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

    # Check git category
    if is_git_command(cmd):
        if allow.get("git", False):
            return "allow"
        # Fall through to bash_all

    # Check bash_safe
    if is_safe_bash(cmd):
        if allow.get("bash_safe", False):
            return "allow"
        # Fall through to bash_all

    # Check bash_all (allows anything not blocked)
    if allow.get("bash_all", False):
        return "allow"

    return None


def main():
    # Load config
    config = load_config()
    if config is None:
        sys.exit(0)  # No config = OFF mode, let Claude ask

    # Read tool info from stdin
    try:
        input_data = json.loads(sys.stdin.read())
    except:
        sys.exit(0)

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
                "permissionDecision": "block",
                "permissionDecisionReason": f"Blocked by toggle: {result[1]} pattern"
            }
        }))
    # else: no output = let Claude ask normally


if __name__ == "__main__":
    main()
