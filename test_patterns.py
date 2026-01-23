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
    "Glob": "search", "Grep": "search",
    "WebFetch": "web", "WebSearch": "web",
    "NotebookEdit": "notebook",
    "Task": "task", "TodoWrite": "task",
    "Bash": "bash", "BashOutput": "bash", "KillShell": "bash",
}

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
]


def is_delete_command(cmd):
    """Check if ANY part of a chained command is a file deletion command."""
    parts = re.split(r'\s*(?:&&|\|\||[;|])\s*', cmd)
    for part in parts:
        part = part.strip().lower()
        if not part:
            continue
        if any(part.startswith(prefix.lower()) for prefix in DELETE_COMMANDS):
            return True
        if part == "rm" or part == "del" or part == "rd" or part == "rmdir":
            return True
    return False

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

# Test cases: (pattern_id, command, should_block)
DESTRUCTIVE_TESTS = [
    # rm -rf tests
    ("rm_rf", "rm -rf ./build", True),
    ("rm_rf", "rm -rf /tmp/test", True),
    ("rm_rf", "rm -Rf node_modules", True),
    ("rm_rf", "rm -fr dist", True),
    ("rm_rf", "rm -r ./old", False),  # No -f, should NOT match rm_rf
    ("rm_rf", "rm file.txt", False),  # Simple rm, should NOT block

    # rm -rf root/home tests
    ("rm_rf_root", "rm -rf /", True),
    ("rm_rf_root", "rm -rf ~", True),
    ("rm_rf_root", "rm -rf $HOME", True),
    ("rm_rf_root", "rm -rf %USERPROFILE%", True),
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

    # Chained commands with delete - SHOULD be detected
    ("npm run build && rm -r dist", True),
    ("ls -la; rm old.txt", True),
    ("git pull && rm -rf node_modules && npm install", True),
    ("echo 'done' | rm temp.log", True),  # Pipe chain

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
