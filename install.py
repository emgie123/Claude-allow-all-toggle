#!/usr/bin/env python3
"""
Claude Allow-All Toggle - Installer

Installs the auto-yes hook and toggle for Claude Code.

Usage:
    python install.py           # Install
    python install.py --uninstall  # Uninstall
"""

import os
import sys
import json
import shutil
import argparse

def get_paths():
    """Get all relevant paths."""
    home = os.path.expanduser("~")
    script_dir = os.path.dirname(os.path.abspath(__file__))

    return {
        "home": home,
        "script_dir": script_dir,
        "hook_src": os.path.join(script_dir, "auto-yes-hook.cmd"),
        "hook_dst": os.path.join(home, "auto-yes-hook.cmd"),
        "toggle_file": os.path.join(script_dir, "AutoYesToggle.pyw"),
        "settings_file": os.path.join(home, ".claude", "settings.json"),
        "flag_file": os.path.join(home, ".claude-auto-yes"),
    }

def install():
    """Install the hook and toggle."""
    paths = get_paths()

    print("Installing Claude Allow-All Toggle...")
    print()

    # Step 1: Copy hook script
    print(f"1. Copying hook script to {paths['hook_dst']}")
    if os.path.exists(paths["hook_src"]):
        shutil.copy(paths["hook_src"], paths["hook_dst"])
        print("   Done!")
    else:
        print(f"   ERROR: Source file not found: {paths['hook_src']}")
        return False

    # Step 2: Configure Claude Code settings
    print(f"2. Configuring Claude Code settings at {paths['settings_file']}")

    # Load existing settings or create new
    settings = {}
    if os.path.exists(paths["settings_file"]):
        try:
            with open(paths["settings_file"], 'r') as f:
                settings = json.load(f)
            print("   Loaded existing settings")
        except json.JSONDecodeError:
            print("   Warning: Could not parse existing settings, creating new")
            settings = {}

    # Add hooks configuration
    hook_entry = {
        "matcher": "*",
        "hooks": [{
            "type": "command",
            "command": paths["hook_dst"]
        }]
    }

    if "hooks" not in settings:
        settings["hooks"] = {}
    if "PreToolUse" not in settings["hooks"]:
        settings["hooks"]["PreToolUse"] = []

    # Check if hook already exists
    hook_exists = any(
        h.get("hooks", [{}])[0].get("command", "").endswith("auto-yes-hook.cmd")
        for h in settings["hooks"]["PreToolUse"]
    )

    if hook_exists:
        print("   Hook already configured, skipping")
    else:
        settings["hooks"]["PreToolUse"].append(hook_entry)
        print("   Added hook configuration")

    # Write settings
    os.makedirs(os.path.dirname(paths["settings_file"]), exist_ok=True)
    with open(paths["settings_file"], 'w') as f:
        json.dump(settings, f, indent=2)
    print("   Saved settings")

    print()
    print("=" * 50)
    print("Installation complete!")
    print()
    print("To use:")
    print(f"  1. Double-click: {paths['toggle_file']}")
    print("  2. Click the button to toggle ON/OFF")
    print("  3. When ON (green), all Claude Code tools auto-approve")
    print("=" * 50)

    return True

def uninstall():
    """Uninstall the hook and toggle."""
    paths = get_paths()

    print("Uninstalling Claude Allow-All Toggle...")
    print()

    # Remove hook script
    if os.path.exists(paths["hook_dst"]):
        os.remove(paths["hook_dst"])
        print(f"1. Removed {paths['hook_dst']}")
    else:
        print(f"1. Hook not found at {paths['hook_dst']}")

    # Remove flag file
    if os.path.exists(paths["flag_file"]):
        os.remove(paths["flag_file"])
        print(f"2. Removed flag file {paths['flag_file']}")
    else:
        print(f"2. Flag file not found (toggle was OFF)")

    # Remove hook from settings
    if os.path.exists(paths["settings_file"]):
        try:
            with open(paths["settings_file"], 'r') as f:
                settings = json.load(f)

            if "hooks" in settings and "PreToolUse" in settings["hooks"]:
                original_count = len(settings["hooks"]["PreToolUse"])
                settings["hooks"]["PreToolUse"] = [
                    h for h in settings["hooks"]["PreToolUse"]
                    if not h.get("hooks", [{}])[0].get("command", "").endswith("auto-yes-hook.cmd")
                ]

                # Clean up empty structures
                if not settings["hooks"]["PreToolUse"]:
                    del settings["hooks"]["PreToolUse"]
                if not settings["hooks"]:
                    del settings["hooks"]

                with open(paths["settings_file"], 'w') as f:
                    json.dump(settings, f, indent=2)

                if len(settings.get("hooks", {}).get("PreToolUse", [])) < original_count:
                    print(f"3. Removed hook from settings")
                else:
                    print(f"3. Hook not found in settings")
            else:
                print(f"3. No hooks found in settings")
        except Exception as e:
            print(f"3. Error updating settings: {e}")
    else:
        print(f"3. Settings file not found")

    print()
    print("Uninstallation complete!")

    return True

def main():
    parser = argparse.ArgumentParser(
        description="Install or uninstall Claude Allow-All Toggle"
    )
    parser.add_argument(
        "--uninstall",
        action="store_true",
        help="Uninstall instead of install"
    )

    args = parser.parse_args()

    if args.uninstall:
        success = uninstall()
    else:
        success = install()

    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
