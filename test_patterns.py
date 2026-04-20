#!/usr/bin/env python3
"""
Test script for Claude Permissions Hook
Simulates hook input and verifies block/allow behavior WITHOUT executing anything.
"""
import json
import sys
import os

# Add the hook's logic directly (don't import to avoid any side effects)
import re

TOOL_CATEGORIES = {
    "Read": "read", "Write": "write", "Edit": "edit",
    "ReadMcpResourceTool": "read",
    "Glob": "search", "Grep": "search", "LSP": "search", "MCPSearch": "search", "ListMcpResourcesTool": "search",
    "WebFetch": "web", "WebSearch": "web",
    "NotebookEdit": "notebook",
    "Agent": "task", "Task": "task", "TodoWrite": "task",
    "AskUserQuestion": "task", "EnterPlanMode": "task", "EnterWorktree": "task",
    "ExitPlanMode": "task", "ExitWorktree": "task", "Skill": "task",
    "TaskCreate": "task", "TaskUpdate": "task", "TaskList": "task", "TaskGet": "task", "TaskOutput": "task",
    "TaskStop": "task", "CronCreate": "task", "CronDelete": "task", "CronList": "task",
    "SendMessage": "task", "TeamCreate": "task", "TeamDelete": "task",
    "Bash": "bash", "BashOutput": "bash", "KillShell": "bash", "Monitor": "bash", "PowerShell": "bash",
}

PROMPT_REQUIRED_TOOLS = {
    "Bash", "Edit", "ExitPlanMode", "KillShell", "Monitor", "NotebookEdit",
    "PowerShell", "Skill", "WebFetch", "WebSearch", "Write",
}

APPROVAL_MODE_SILENT = "silent"
APPROVAL_MODE_SHOW_ACCEPTS = "show_accepts"

SAFE_BASH = [
    "npm ", "npm.cmd ", "npx ", "pnpm ", "yarn ",
    "node ", "python ", "python3 ", "pip ", "pip3 ",
    "ls ", "dir ", "pwd", "cd ", "cat ", "type ", "head ", "tail ",
    "echo ", "printf ", "mkdir ", "touch ",
    "curl ", "wget ", "which ", "where ", "whoami", "hostname",
    "printenv", "set ",
    "get-childitem", "gci ", "get-content ", "gc ", "select-string ", "sls ",
    "get-location", "set-location ", "write-host ", "write-output ",
    "test-path ", "get-item ", "gi ", "new-item ", "ni ",
    "get-command ", "gcm ", "get-process ", "gps ",
]

# File deletion command prefixes (copied from hook)
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
    "remove-item ",
    "remove-item\t",
    "ri ",
    "ri\t",
]


def is_delete_command(cmd):
    """Check if ANY part of a chained command is a file deletion command."""
    parts = re.split(r'\s*(?:&&|\|\||[;|])\s*', cmd)
    for part in parts:
        part = part.strip().lower()
        if not part:
            continue
        part = strip_env_prefix(part)
        if any(part.startswith(prefix.lower()) for prefix in DELETE_COMMANDS):
            return True
        if part == "rm" or part == "del" or part == "rd" or part == "rmdir":
            return True
    return False


def strip_env_prefix(part):
    return re.sub(r"^\s*env(?:\s+[A-Za-z_][A-Za-z0-9_]*=[^\s]+)*\s+", "", part, flags=re.IGNORECASE)


def is_git_command(cmd):
    parts = re.split(r'\s*(?:&&|\|\||[;|])\s*', cmd)
    for part in parts:
        part = part.strip()
        if part.startswith("git ") or part.startswith("git.exe "):
            return True
        if " git " in part or part.endswith(" git"):
            return True
    return False


def is_safe_bash(cmd):
    parts = re.split(r'\s*(?:&&|\|\||[;|])\s*', cmd)
    for part in parts:
        part = part.strip().lower()
        if not part:
            continue
        is_part_safe = any(part.startswith(prefix.lower()) for prefix in SAFE_BASH)
        if not is_part_safe:
            return False
    return True

def is_powershell_force_delete(cmd):
    lower = cmd.lower()
    if not re.search(r'^\s*(remove-item|ri)\b', lower):
        return False
    has_recurse = bool(re.search(r'-(recurse|r)\b', lower))
    has_force = bool(re.search(r'-(force|fo|f)\b', lower))
    return has_recurse and has_force


def targets_root_or_home(cmd):
    return any(re.search(pattern, cmd, re.IGNORECASE) for pattern in [
        r'(^|\s)[\'"]?[/~][\'"]?(?=\s|$)',
        r'(^|\s)[\'"]?\$HOME\b[\'"]?(?=\s|$)',
        r'(^|\s)[\'"]?%USERPROFILE%[\'"]?(?=\s|$)',
        r'(^|\s)[\'"]?\$env:USERPROFILE\b[\'"]?(?=\s|$)',
        r'(^|\s)[\'"]?[a-zA-Z]:(?:\\|/)[\'"]?(?=\s|$)',
    ])


def check_blocks(cmd, config):
    blocks = config.get("block", {})
    for pattern_id, detector in BLOCK_PATTERNS.items():
        if blocks.get(pattern_id, True) and detector(cmd):
            return pattern_id
    return None


def check_permission(tool_name, tool_input, config):
    allow = config.get("allow", {})
    category = TOOL_CATEGORIES.get(tool_name)

    if category is None:
        return None

    if category != "bash":
        if allow.get(category, False):
            return "allow"
        return None

    cmd = tool_input.get("command", "")

    blocked = check_blocks(cmd, config)
    if blocked:
        return ("block", blocked)

    if is_git_command(cmd):
        if allow.get("git", False):
            return "allow"
        return None

    if is_safe_bash(cmd):
        if allow.get("bash_safe", False):
            return "allow"

    if is_delete_command(cmd):
        if allow.get("bash_delete", False):
            return "allow"
        return None

    if allow.get("bash_all", False):
        return "allow"

    return None


BLOCK_PATTERNS = {
    "rm_rf": lambda cmd: bool(re.search(
        r'\brm\s+.*-[^\s]*r[^\s]*f|rm\s+.*-[^\s]*f[^\s]*r|\brm\s+-rf\b|'
        r'\b(?:remove-item|ri)\b.*-(?:recurse|r)\b.*-(?:force|fo|f)\b|'
        r'\b(?:remove-item|ri)\b.*-(?:force|fo|f)\b.*-(?:recurse|r)\b',
        cmd,
        re.IGNORECASE,
    )),
    "rm_rf_root": lambda cmd: bool(re.search(
        r'\brm\s+.*-rf\s+[/~]|\brm\s+.*-rf\s+\$HOME|\brm\s+.*-rf\s+%USERPROFILE%',
        cmd,
        re.IGNORECASE,
    )) or (is_powershell_force_delete(cmd) and targets_root_or_home(cmd)),
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

TOOL_MAPPING_TESTS = [
    ("PowerShell", "bash"),
    ("Monitor", "bash"),
    ("EnterPlanMode", "task"),
    ("EnterWorktree", "task"),
    ("ExitWorktree", "task"),
    ("ReadMcpResourceTool", "read"),
    ("ListMcpResourcesTool", "search"),
    ("TaskStop", "task"),
    ("SendMessage", "task"),
    ("TeamCreate", "task"),
]

APPROVAL_MODE_TESTS = [
    ("Write", "allow", APPROVAL_MODE_SILENT, False),
    ("Write", "allow", APPROVAL_MODE_SHOW_ACCEPTS, True),
    ("PowerShell", "allow", APPROVAL_MODE_SHOW_ACCEPTS, True),
    ("Read", "allow", APPROVAL_MODE_SHOW_ACCEPTS, False),
    ("Bash", None, APPROVAL_MODE_SHOW_ACCEPTS, False),
]

PERMISSION_PRECEDENCE_TESTS = [
    (
        "git_off_still_asks_even_with_bash_all",
        "Bash",
        {"command": "git status"},
        {"allow": {"git": False, "bash_all": True, "bash_safe": False, "bash_delete": False}, "block": {}},
        None,
    ),
    (
        "delete_off_still_asks_even_with_bash_all",
        "Bash",
        {"command": "rm temp.txt"},
        {"allow": {"git": False, "bash_all": True, "bash_safe": False, "bash_delete": False}, "block": {}},
        None,
    ),
    (
        "env_wrapped_delete_still_asks",
        "Bash",
        {"command": "env FOO=bar rm temp.txt"},
        {"allow": {"git": False, "bash_all": True, "bash_safe": False, "bash_delete": False}, "block": {}},
        None,
    ),
]

# Test cases: (pattern_id, command, should_block)
DESTRUCTIVE_TESTS = [
    # rm -rf tests
    ("rm_rf", "rm -rf ./build", True),
    ("rm_rf", "rm -rf /tmp/test", True),
    ("rm_rf", "rm -Rf node_modules", True),
    ("rm_rf", "rm -fr dist", True),
    ("rm_rf", "Remove-Item build -Recurse -Force", True),
    ("rm_rf", "ri build -Force -Recurse", True),
    ("rm_rf", "rm -r ./old", False),  # No -f, should NOT match rm_rf
    ("rm_rf", "rm file.txt", False),  # Simple rm, should NOT block

    # rm -rf root/home tests
    ("rm_rf_root", "rm -rf /", True),
    ("rm_rf_root", "rm -rf ~", True),
    ("rm_rf_root", "rm -rf $HOME", True),
    ("rm_rf_root", "rm -rf %USERPROFILE%", True),
    ("rm_rf_root", "Remove-Item C:\\ -Recurse -Force", True),
    ("rm_rf_root", "Remove-Item 'C:\\' -Recurse -Force", True),
    ("rm_rf_root", 'Remove-Item "C:\\" -Recurse -Force', True),
    ("rm_rf_root", "Remove-Item C:/ -Recurse -Force", True),
    ("rm_rf_root", "Remove-Item $env:USERPROFILE -Force -Recurse", True),
    ("rm_rf_root", "rm -rf ./local", False),  # Not root, should NOT match

    # git reset --hard
    ("git_reset_hard", "git reset --hard", True),
    ("git_reset_hard", "git reset --hard HEAD~1", True),
    ("git_reset_hard", "git reset --merge", True),
    ("git_reset_hard", "git reset --soft HEAD~1", False),  # Soft reset is safe
    ("git_reset_hard", "git reset HEAD file.txt", False),  # Unstage is safe

    # git checkout -- (discard changes)
    ("git_checkout_discard", "git checkout -- .", True),
    ("git_checkout_discard", "git checkout -- file.txt", True),
    ("git_checkout_discard", "git checkout -b new-branch", False),  # Create branch is safe
    ("git_checkout_discard", "git checkout main", False),  # Switch branch is safe

    # git clean -f
    ("git_clean", "git clean -f", True),
    ("git_clean", "git clean -fd", True),
    ("git_clean", "git clean -fxd", True),
    ("git_clean", "git clean -n", False),  # Dry run is safe

    # git push --force
    ("git_push_force", "git push --force", True),
    ("git_push_force", "git push -f origin main", True),
    ("git_push_force", "git push --force-with-lease", True),  # Still matches --force
    ("git_push_force", "git push origin main", False),  # Normal push is safe

    # git branch -D
    ("git_branch_delete", "git branch -D feature", True),
    ("git_branch_delete", "git branch -d feature", False),  # Lowercase -d is safe (only deletes merged)
    ("git_branch_delete", "git branch feature", False),  # Create branch is safe

    # git stash drop/clear
    ("git_stash_drop", "git stash drop", True),
    ("git_stash_drop", "git stash drop stash@{0}", True),
    ("git_stash_drop", "git stash clear", True),
    ("git_stash_drop", "git stash", False),  # Stash is safe
    ("git_stash_drop", "git stash pop", False),  # Pop is safe

    # find -delete
    ("find_delete", "find . -name '*.tmp' -delete", True),
    ("find_delete", "find /tmp -type f -delete", True),
    ("find_delete", "find . -name '*.log'", False),  # No -delete is safe

    # xargs/parallel rm
    ("xargs_rm", "find . | xargs rm", True),
    ("xargs_rm", "find . | xargs rm -rf", True),
    ("xargs_rm", "cat files.txt | parallel rm", True),
    ("xargs_rm", "find . | xargs grep pattern", False),  # xargs with grep is safe

    # dd if=
    ("dd_if", "dd if=/dev/zero of=/dev/sda", True),
    ("dd_if", "dd if=image.iso of=/dev/sdb", True),
    ("dd_if", "echo test", False),  # Not dd

    # mkfs
    ("mkfs", "mkfs.ext4 /dev/sda1", True),
    ("mkfs", "mkfs -t ext4 /dev/sdb1", True),
    ("mkfs", "ls /dev", False),  # Not mkfs

    # chmod -R 777 /
    ("chmod_777", "chmod -R 777 /", True),
    ("chmod_777", "chmod -R 777 /var/www", True),
    ("chmod_777", "chmod 755 file.sh", False),  # Not recursive 777 on root
    ("chmod_777", "chmod -R 755 ./dist", False),  # Not 777
]

# Safe commands that should ALWAYS be allowed (when bash_all is enabled)
SAFE_TESTS = [
    ("Bash", "npm install", "Should allow npm"),
    ("Bash", "node script.js", "Should allow node"),
    ("Bash", "python test.py", "Should allow python"),
    ("Bash", "ls -la", "Should allow ls"),
    ("Bash", "git status", "Should allow git status"),
    ("Bash", "git add .", "Should allow git add"),
    ("Bash", "git commit -m 'test'", "Should allow git commit"),
    ("Bash", "git push origin main", "Should allow normal push"),
    ("Read", "file.txt", "Should allow Read tool"),
    ("Write", "file.txt", "Should allow Write tool"),
    ("Edit", "file.txt", "Should allow Edit tool"),
    ("Glob", "**/*.js", "Should allow Glob tool"),
    ("Grep", "pattern", "Should allow Grep tool"),
]

# Delete command detection tests: (command, should_detect_as_delete)
DELETE_TESTS = [
    # Simple delete commands - SHOULD be detected
    ("rm file.txt", True),
    ("rm -f file.txt", True),
    ("rm -r directory", True),
    ("rm -rf build", True),  # Also detected (plus blocked by rm_rf pattern)
    ("rm *.log", True),
    ("del file.txt", True),
    ("del /q file.txt", True),
    ("rmdir empty_dir", True),
    ("rd /s /q folder", True),
    ("erase temp.txt", True),
    ("unlink symlink", True),
    ("shred secret.txt", True),
    ("Remove-Item temp.txt", True),
    ("Remove-Item build -Recurse -Force", True),
    ("ri build -Force -Recurse", True),

    # Chained commands with delete - SHOULD be detected
    ("npm run build && rm -r dist", True),
    ("ls -la; rm old.txt", True),
    ("git pull && rm -rf node_modules && npm install", True),
    ("echo 'done' | rm temp.log", True),  # Pipe chain
    ("env rm temp.txt", True),
    ("env FOO=bar rm temp.txt", True),

    # Commands that are NOT delete - should NOT be detected
    ("npm install", False),
    ("node script.js", False),
    ("python test.py", False),
    ("ls -la", False),
    ("mkdir new_folder", False),
    ("cat file.txt", False),
    ("grep -r pattern .", False),
    ("git status", False),
    ("git rm --cached file.txt", False),  # git rm is git, not rm
    ("echo 'rm file.txt'", False),  # rm in quotes, not command
    ("npm run remove-old", False),  # "remove" is not "rm "
    ("firmware update", False),  # Contains "rm" but not as command

    # Edge cases
    ("  rm file.txt", True),  # Leading whitespace
    ("RM FILE.TXT", True),  # Uppercase (case insensitive)
    ("Del /F file.txt", True),  # Windows uppercase
]


def test_block_pattern(pattern_id, command, should_block):
    """Test if a pattern correctly blocks/allows a command."""
    detector = BLOCK_PATTERNS.get(pattern_id)
    if not detector:
        return False, f"Unknown pattern: {pattern_id}"

    is_blocked = detector(command)

    if is_blocked == should_block:
        return True, None
    else:
        return False, f"Expected {'BLOCK' if should_block else 'ALLOW'}, got {'BLOCK' if is_blocked else 'ALLOW'}"


def test_delete_detection(command, should_detect):
    """Test if a command is correctly detected as a delete command."""
    is_delete = is_delete_command(command)

    if is_delete == should_detect:
        return True, None
    else:
        return False, f"Expected {'DELETE' if should_detect else 'NOT DELETE'}, got {'DELETE' if is_delete else 'NOT DELETE'}"


def should_show_permission_prompt(tool_name, result, approval_mode):
    return (
        result == "allow" and
        approval_mode == APPROVAL_MODE_SHOW_ACCEPTS and
        tool_name in PROMPT_REQUIRED_TOOLS
    )


def run_tests():
    print("=" * 60)
    print("CLAUDE PERMISSIONS HOOK - PATTERN TEST SUITE")
    print("=" * 60)
    print("\nTesting WITHOUT executing any commands - simulation only\n")

    passed = 0
    failed = 0

    # Test destructive patterns
    print("-" * 60)
    print("DESTRUCTIVE PATTERN TESTS (BLOCK patterns)")
    print("-" * 60)

    current_pattern = None
    for pattern_id, command, should_block in DESTRUCTIVE_TESTS:
        if pattern_id != current_pattern:
            current_pattern = pattern_id
            print(f"\n[{pattern_id}]")

        success, error = test_block_pattern(pattern_id, command, should_block)

        expected = "BLOCK" if should_block else "ALLOW"
        status = "PASS" if success else "FAIL"

        if success:
            passed += 1
            print(f"  [{status}] {expected}: {command[:50]}")
        else:
            failed += 1
            print(f"  [{status}] {expected}: {command[:50]}")
            print(f"         ERROR: {error}")

    # Test delete detection
    print("\n" + "-" * 60)
    print("DELETE COMMAND DETECTION TESTS (bash_delete category)")
    print("-" * 60)
    print("\nThese commands trigger ASK when bash_delete is OFF:\n")

    for command, should_detect in DELETE_TESTS:
        success, error = test_delete_detection(command, should_detect)

        expected = "DELETE" if should_detect else "NOT DELETE"
        status = "PASS" if success else "FAIL"

        if success:
            passed += 1
            print(f"  [{status}] {expected}: {command[:50]}")
        else:
            failed += 1
            print(f"  [{status}] {expected}: {command[:50]}")
            print(f"         ERROR: {error}")

    print("\n" + "-" * 60)
    print("TOOL MAPPING TESTS")
    print("-" * 60)

    for tool_name, expected_category in TOOL_MAPPING_TESTS:
        actual_category = TOOL_CATEGORIES.get(tool_name)
        success = actual_category == expected_category
        status = "PASS" if success else "FAIL"

        if success:
            passed += 1
            print(f"  [{status}] {tool_name} -> {expected_category}")
        else:
            failed += 1
            print(f"  [{status}] {tool_name} -> expected {expected_category}, got {actual_category}")

    print("\n" + "-" * 60)
    print("APPROVAL DISPLAY TESTS")
    print("-" * 60)

    for tool_name, result, approval_mode, expected_prompt in APPROVAL_MODE_TESTS:
        actual_prompt = should_show_permission_prompt(tool_name, result, approval_mode)
        success = actual_prompt == expected_prompt
        status = "PASS" if success else "FAIL"
        expected = "SHOW" if expected_prompt else "SILENT"

        if success:
            passed += 1
            print(f"  [{status}] {tool_name} / {approval_mode} -> {expected}")
        else:
            failed += 1
            actual = "SHOW" if actual_prompt else "SILENT"
            print(f"  [{status}] {tool_name} / {approval_mode} -> expected {expected}, got {actual}")

    print("\n" + "-" * 60)
    print("PERMISSION PRECEDENCE TESTS")
    print("-" * 60)

    for name, tool_name, tool_input, config, expected in PERMISSION_PRECEDENCE_TESTS:
        result = check_permission(tool_name, tool_input, config)
        success = result == expected
        status = "PASS" if success else "FAIL"

        if success:
            passed += 1
            print(f"  [{status}] {name}")
        else:
            failed += 1
            print(f"  [{status}] {name}")
            print(f"         ERROR: expected {expected!r}, got {result!r}")

    # Summary
    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)

    if failed == 0:
        print("\n[OK] All patterns working correctly!")
        print("\nYour destructive command protection is ready.")
        print("Delete commands will ASK when bash_delete is OFF.")
    else:
        print(f"\n[ERROR] {failed} tests failed - review the patterns above")

    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
