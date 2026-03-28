#!/usr/bin/env python3
"""
Claude Permissions Toggle - Installer

Installs the permissions hook and toggle for Claude Code.

Usage:
    python install.py              # Install
    python install.py --uninstall  # Uninstall
"""

import os
import sys
import json
import shutil
import argparse

HOOK_MARKERS = [
    "auto-yes-hook.cmd",
    "claude-permissions-hook.cmd",
    "claude-permissions-hook.py",
]
MANAGED_ALLOW_RULES_KEY = "managed_allow_rules"


def get_python_path():
    """Get the full path to the Python executable.
    Always use python.exe (not pythonw.exe) because hooks need stdout piping."""
    exe = sys.executable
    # pythonw.exe can't reliably pipe stdout when spawned by Claude Code
    if exe.lower().endswith("pythonw.exe"):
        exe = exe[:-len("pythonw.exe")] + "python.exe"
    return exe


def to_hook_path(path):
    """Format a path for shell-safe hook commands on Windows."""
    return os.path.abspath(path).replace("\\", "/")


def get_paths():
    """Get all relevant paths."""
    home = os.path.expanduser("~")
    script_dir = os.path.dirname(os.path.abspath(__file__))

    return {
        "home": home,
        "script_dir": script_dir,
        "python_exe": get_python_path(),
        # Hook files
        "hook_py_src": os.path.join(script_dir, "claude-permissions-hook.py"),
        "hook_py_dst": os.path.join(home, "claude-permissions-hook.py"),
        # Other files
        "toggle_file": os.path.join(script_dir, "AutoYesToggle.pyw"),
        "settings_file": os.path.join(home, ".claude", "settings.json"),
        "config_file": os.path.join(home, ".claude-permissions.json"),
        # Old files (for cleanup)
        "old_hook_cmd": os.path.join(home, "auto-yes-hook.cmd"),
        "old_flag": os.path.join(home, ".claude-auto-yes"),
        "old_permissions_cmd": os.path.join(home, "claude-permissions-hook.cmd"),
    }


def remove_toggle_hooks(settings):
    """Remove hook entries owned by this project from all relevant hook events."""
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return

    for event_name in ("PreToolUse", "PermissionRequest"):
        event_hooks = hooks.get(event_name)
        if not isinstance(event_hooks, list):
            continue

        hooks[event_name] = [
            h for h in event_hooks
            if not any(
                marker in hook.get("command", "")
                for hook in h.get("hooks", [])
                for marker in HOOK_MARKERS
            )
        ]

        if not hooks[event_name]:
            del hooks[event_name]

    if not hooks:
        del settings["hooks"]


def load_managed_allow_rules(config_path):
    """Load transient permissions.allow rules managed by the toggle."""
    if not os.path.exists(config_path):
        return []

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []

    managed_rules = config.get(MANAGED_ALLOW_RULES_KEY, [])
    return managed_rules if isinstance(managed_rules, list) else []


def remove_managed_allow_rules(settings, managed_rules):
    """Remove transient permissions.allow rules managed by the toggle."""
    if not isinstance(managed_rules, list) or not managed_rules:
        return

    permissions = settings.get("permissions")
    if not isinstance(permissions, dict):
        return

    allow_rules = permissions.get("allow")
    if not isinstance(allow_rules, list):
        return

    remaining_rules = [rule for rule in allow_rules if rule not in set(managed_rules)]
    permissions["allow"] = remaining_rules


def install():
    """Install the hook and toggle."""
    paths = get_paths()

    print("=" * 55)
    print("Claude Permissions Toggle - Installer")
    print("=" * 55)
    print()

    # Step 1: Verify hook exists (no longer copying - use source directly)
    print(f"1. Verifying hook file: {paths['hook_py_src']}")
    if os.path.exists(paths["hook_py_src"]):
        print("   Found!")
    else:
        print(f"   ERROR: Source file not found: {paths['hook_py_src']}")
        return False

    # Remove old copied hook if it exists
    if os.path.exists(paths["hook_py_dst"]):
        os.remove(paths["hook_py_dst"])
        print(f"   Removed old copy at: {paths['hook_py_dst']}")

    # Step 2: Configure Claude Code settings
    print(f"\n2. Configuring Claude Code settings")

    # Load existing settings or create new
    settings = {}
    if os.path.exists(paths["settings_file"]):
        try:
            with open(paths["settings_file"], 'r') as f:
                settings = json.load(f)
            print("   Loaded existing settings.json")
        except json.JSONDecodeError:
            print("   Warning: Could not parse existing settings, creating new")
            settings = {}

    # Build hook command with full Python path - point to SOURCE file so updates work immediately
    hook_command = f"\"{to_hook_path(paths['python_exe'])}\" \"{to_hook_path(paths['hook_py_src'])}\""

    hook_entry = {
        "matcher": "*",
        "hooks": [{
            "type": "command",
            "command": hook_command
        }]
    }

    if "hooks" not in settings:
        settings["hooks"] = {}

    for event_name in ("PreToolUse", "PermissionRequest"):
        if event_name not in settings["hooks"]:
            settings["hooks"][event_name] = []

        # Remove old hooks if present
        settings["hooks"][event_name] = [
            h for h in settings["hooks"][event_name]
            if not any(
                marker in hook.get("command", "")
                for hook in h.get("hooks", [])
                for marker in HOOK_MARKERS
            )
        ]
        settings["hooks"][event_name].append(hook_entry)

    # Write settings
    os.makedirs(os.path.dirname(paths["settings_file"]), exist_ok=True)
    with open(paths["settings_file"], 'w') as f:
        json.dump(settings, f, indent=2)
    print("   Added hook to settings.json")
    print(f"   Using Python: {paths['python_exe']}")

    # Step 3: Clean up old files
    old_files_removed = []
    for name, path in [
        ("old cmd hook", paths["old_hook_cmd"]),
        ("old flag file", paths["old_flag"]),
        ("old permissions cmd", paths["old_permissions_cmd"]),
    ]:
        if os.path.exists(path):
            os.remove(path)
            old_files_removed.append(name)

    if old_files_removed:
        print(f"\n3. Cleaned up old files: {', '.join(old_files_removed)}")

    print()
    print("=" * 55)
    print("Installation complete!")
    print("=" * 55)
    print()
    print("To use:")
    print(f"  1. Run: python {paths['toggle_file']}")
    print("     Or double-click AutoYesToggle.pyw")
    print()
    print("  2. Click a template button:")
    print("     - OFF:    Claude asks for everything")
    print("     - ALL*:   Allow all, block destructive (recommended)")
    print("     - ALL:    Allow everything (dangerous!)")
    print("     - CUSTOM: Load your saved custom settings")
    print()
    print("  3. Or check individual boxes and click Save")
    print()
    print("If Claude Code is already open, restart it or review the change in /hooks once.")
    print()
    print("NOTE: Hook runs directly from repo folder.")
    print("      Git pull updates take effect immediately!")
    print("=" * 55)

    return True


def uninstall(full=False):
    """Uninstall the hook and toggle."""
    paths = get_paths()
    managed_rules = load_managed_allow_rules(paths["config_file"])

    print("Uninstalling Claude Permissions Toggle...")
    print()

    # Remove installed files
    for name, path in [
        ("Python hook", paths["hook_py_dst"]),
        ("Config file", paths["config_file"]),
        ("Debug log", os.path.join(paths["home"], ".claude-hook-debug.log")),
        ("Old cmd hook", paths["old_hook_cmd"]),
        ("Old flag file", paths["old_flag"]),
        ("Old permissions cmd", paths["old_permissions_cmd"]),
    ]:
        if os.path.exists(path):
            os.remove(path)
            print(f"Removed: {path}")

    # Remove hook from settings
    if os.path.exists(paths["settings_file"]):
        try:
            with open(paths["settings_file"], 'r') as f:
                settings = json.load(f)

            remove_toggle_hooks(settings)
            remove_managed_allow_rules(settings, managed_rules)

            with open(paths["settings_file"], 'w') as f:
                json.dump(settings, f, indent=2)

            print("Removed hook from Claude settings")
        except Exception as e:
            print(f"Error updating settings: {e}")

    print()
    print("Uninstallation complete!")

    # Full uninstall: also remove the repo folder
    if full:
        print()
        print("Removing project folder...")
        import shutil
        try:
            shutil.rmtree(paths["script_dir"])
            print(f"Removed: {paths['script_dir']}")
        except Exception as e:
            print(f"Could not remove project folder: {e}")
            print("You may need to delete it manually.")

    return True


def main():
    parser = argparse.ArgumentParser(
        description="Install or uninstall Claude Permissions Toggle"
    )
    parser.add_argument(
        "--uninstall",
        action="store_true",
        help="Uninstall installed files and remove hook from settings"
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Full uninstall: also delete the project folder (use with --uninstall)"
    )

    args = parser.parse_args()

    if args.uninstall:
        success = uninstall(full=args.full)
    else:
        success = install()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
