"""
Claude Permissions Toggle
Category-based permissions with granular block list.
Supports minimal mode: single ON/OFF toggle.

When app opens: registers hook in Claude settings.json
When app closes: unregisters hook (Claude uses default behavior)
"""
import tkinter as tk
from tkinter import ttk
import atexit
import os
import sys
import json
import msvcrt

CONFIG_FILE = os.path.join(os.path.expanduser("~"), '.claude-permissions.json')
SETTINGS_FILE = os.path.join(os.path.expanduser("~"), ".claude", "settings.json")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HOOK_PY_SRC = os.path.join(SCRIPT_DIR, "claude-permissions-hook.py")
LOCK_FILE = os.path.join(os.path.expanduser("~"), '.claude-permissions.lock')
MANAGED_ALLOW_RULES_KEY = "managed_allow_rules"
MANAGED_ALLOW_RULES = {
    "write": "Write",
    "edit": "Edit",
    "notebook": "NotebookEdit",
}
APPROVAL_MODE_KEY = "approval_mode"
APPROVAL_MODE_SILENT = "silent"
APPROVAL_MODE_SHOW_ACCEPTS = "show_accepts"


def get_python_path():
    """Get the full path to the Python executable.
    Always use python.exe (not pythonw.exe) because hooks need stdout piping."""
    exe = sys.executable
    if exe.lower().endswith("pythonw.exe"):
        exe = exe[:-len("pythonw.exe")] + "python.exe"
    return exe


def to_hook_path(path):
    """Format a path for shell-safe hook commands on Windows."""
    return os.path.abspath(path).replace("\\", "/")


def build_hook_command():
    """Build a hook command that works under Windows Git Bash."""
    python_exe = to_hook_path(get_python_path())
    hook_script = to_hook_path(HOOK_PY_SRC)
    return f"\"{python_exe}\" \"{hook_script}\""


def atomic_write_json(path, payload):
    """Write JSON atomically to avoid partial reads by the hook process."""
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    temp_path = f"{path}.tmp"

    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.flush()
        os.fsync(f.fileno())

    os.replace(temp_path, path)


def build_preserved_config(config, minimal_mode, last_active_template, write_edit_on):
    """Persist UI preferences while dropping active allow/block state."""
    preserved = {
        "minimal_mode": minimal_mode,
        "last_active_template": last_active_template,
        "write_edit_on": write_edit_on,
        APPROVAL_MODE_KEY: config.get(APPROVAL_MODE_KEY, APPROVAL_MODE_SILENT),
    }

    if "saved_custom" in config:
        preserved["saved_custom"] = config["saved_custom"]
    if MANAGED_ALLOW_RULES_KEY in config:
        preserved[MANAGED_ALLOW_RULES_KEY] = config[MANAGED_ALLOW_RULES_KEY]

    return preserved


def sync_managed_permission_rules(config, toggle_enabled):
    """Sync transient Write/Edit allow rules for the current toggle state."""
    settings = {}
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                settings = json.load(f)
        except (json.JSONDecodeError, OSError):
            settings = {}

    permissions = settings.setdefault("permissions", {})
    allow_rules = permissions.get("allow")
    if not isinstance(allow_rules, list):
        allow_rules = []

    managed_rules = set(config.get(MANAGED_ALLOW_RULES_KEY, []))
    desired_rules = set()
    if toggle_enabled:
        allow_config = config.get("allow", {})
        for category, rule in MANAGED_ALLOW_RULES.items():
            if allow_config.get(category, False):
                desired_rules.add(rule)

    removed_rules = managed_rules - desired_rules
    if removed_rules:
        allow_rules = [rule for rule in allow_rules if rule not in removed_rules]
        managed_rules -= removed_rules

    allow_set = set(allow_rules)
    for rule in sorted(desired_rules):
        if rule not in allow_set:
            allow_rules.append(rule)
            allow_set.add(rule)
            managed_rules.add(rule)

    permissions["allow"] = allow_rules
    if managed_rules:
        config[MANAGED_ALLOW_RULES_KEY] = sorted(managed_rules)
    else:
        config.pop(MANAGED_ALLOW_RULES_KEY, None)

    atomic_write_json(SETTINGS_FILE, settings)


def _is_toggle_hook(entry):
    hooks = entry.get("hooks", [])
    for hook in hooks:
        command = hook.get("command", "")
        if any(marker in command for marker in [
            "auto-yes-hook.cmd",
            "claude-permissions-hook.cmd",
            "claude-permissions-hook.py",
        ]):
            return True
    return False


def register_hook():
    """Register the permissions hook in Claude's settings.json."""
    settings = {}
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                settings = json.load(f)
        except (json.JSONDecodeError, OSError):
            settings = {}

    hook_entry = {
        "matcher": "*",
        "hooks": [{
            "type": "command",
            "command": build_hook_command(),
        }],
    }

    hooks = settings.setdefault("hooks", {})
    for event_name in ("PreToolUse", "PermissionRequest"):
        event_hooks = hooks.setdefault(event_name, [])
        hooks[event_name] = [entry for entry in event_hooks if not _is_toggle_hook(entry)]
        hooks[event_name].append(hook_entry)

    atomic_write_json(SETTINGS_FILE, settings)


def unregister_hook():
    """Unregister the permissions hook from Claude's settings.json."""
    if not os.path.exists(SETTINGS_FILE):
        return True

    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            settings = json.load(f)
    except (json.JSONDecodeError, OSError):
        return False

    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return True

    removed_any = False

    for event_name in ("PreToolUse", "PermissionRequest"):
        event_hooks = hooks.get(event_name)
        if not isinstance(event_hooks, list):
            continue

        filtered = [entry for entry in event_hooks if not _is_toggle_hook(entry)]
        removed_any = removed_any or len(filtered) != len(event_hooks)

        if filtered:
            hooks[event_name] = filtered
        else:
            del hooks[event_name]

    if not removed_any:
        return True

    if not hooks:
        del settings["hooks"]

    try:
        atomic_write_json(SETTINGS_FILE, settings)
        return True
    except OSError:
        return False

# Allow categories
ALLOW_CATEGORIES = [
    ("read", "Read files"),
    ("write", "Write files"),
    ("edit", "Edit files"),
    ("search", "Search (Glob/Grep/ToolSearch/LSP/MCP)"),
    ("web", "Web access"),
    ("notebook", "Notebook edit"),
    ("task", "Task/plan/team tools"),
    ("bash_safe", "Shell (safe Bash/PowerShell commands)"),
    ("bash_delete", "Shell (file deletion: rm, del, rmdir, Remove-Item)"),
    ("bash_all", "Shell (all Bash/PowerShell commands)"),
    ("git", "Git commands (Bash/PowerShell)"),
]

# Block patterns
BLOCK_PATTERNS = [
    ("rm_rf", "rm -rf (recursive force delete)"),
    ("rm_rf_root", "rm -rf / or ~ (root/home delete)"),
    ("git_reset_hard", "git reset --hard"),
    ("git_checkout_discard", "git checkout -- (discard changes)"),
    ("git_clean", "git clean -f"),
    ("git_push_force", "git push --force"),
    ("git_branch_delete", "git branch -D (force delete)"),
    ("git_stash_drop", "git stash drop/clear"),
    ("find_delete", "find -delete"),
    ("xargs_rm", "xargs/parallel rm"),
    ("dd_if", "dd if= (disk write)"),
    ("mkfs", "mkfs (format disk)"),
    ("chmod_777", "chmod -R 777 /"),
]

# Templates (OFF, ALL*, ALL only - anything else is CUSTOM)
# Note: all_safe keeps bash_delete OFF so you always verify deletions
TEMPLATES = {
    "off": {
        "allow": {cat[0]: False for cat in ALLOW_CATEGORIES},
        "block": {pat[0]: True for pat in BLOCK_PATTERNS},
    },
    "all_safe": {
        "allow": {
            **{cat[0]: True for cat in ALLOW_CATEGORIES},
            "bash_delete": False,  # Always verify deletions in safe mode
        },
        "block": {pat[0]: True for pat in BLOCK_PATTERNS},
    },
    "all": {
        "allow": {cat[0]: True for cat in ALLOW_CATEGORIES},
        "block": {pat[0]: False for pat in BLOCK_PATTERNS},
    },
}


class PermissionsToggle:
    def __init__(self):
        self.root = tk.Tk()
        self._cleaned_up = False
        self.lock_handle = None
        self.acquire_runtime_lock()

        # Register hook on startup
        register_hook()
        atexit.register(self.cleanup_state)

        # Dark theme colors
        self.c = {
            "bg": "#0d1117",
            "card": "#161b22",
            "border": "#30363d",
            "text": "#e6edf3",
            "muted": "#7d8590",
            "green": "#238636",
            "blue": "#1f6feb",
            "purple": "#8b5cf6",
            "red": "#da3633",
            "gray": "#484f58",
        }

        # Configure root
        self.root.configure(bg=self.c["bg"])
        self.root.attributes("-topmost", True)

        # Dark title bar (Windows 10/11)
        try:
            from ctypes import windll, byref, sizeof, c_int
            DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            hwnd = windll.user32.GetParent(self.root.winfo_id())
            windll.dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, byref(c_int(1)), sizeof(c_int))
        except:
            pass

        # Configure ttk styles
        self.style = ttk.Style()
        self.style.theme_use('clam')

        # Dark scrollbar
        self.style.configure("Dark.Vertical.TScrollbar",
            background=self.c["card"],
            troughcolor=self.c["bg"],
            bordercolor=self.c["bg"],
            arrowcolor=self.c["muted"],
            lightcolor=self.c["card"],
            darkcolor=self.c["card"],
        )
        self.style.map("Dark.Vertical.TScrollbar",
            background=[('active', self.c["gray"]), ('!active', self.c["card"])],
        )

        # Load config
        self.config = self.load_config()
        self.current_template = self.detect_template()

        # Load minimal mode preference and last active template
        self.minimal_mode = self.config.get("minimal_mode", False)
        self.last_active_template = self.config.get("last_active_template", "custom")

        # Track Write/Edit state separately (only meaningful when Custom is ON)
        self.write_edit_on = self.config.get("write_edit_on", True)
        self.config[APPROVAL_MODE_KEY] = self.get_approval_mode()

        # Auto-apply last active template on startup (config is cleared on close)
        self.apply_template_silent(self.last_active_template)
        self.apply_write_edit_state()
        self.is_on = True
        self.save_config()

        # Build appropriate UI
        if self.minimal_mode:
            self.build_minimal_ui()
        else:
            self.build_full_ui()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def load_config(self):
        # Default config
        default = {
            "allow": {cat[0]: False for cat in ALLOW_CATEGORIES},
            "block": {pat[0]: True for pat in BLOCK_PATTERNS},
            APPROVAL_MODE_KEY: APPROVAL_MODE_SILENT,
        }

        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    loaded = json.load(f)
                # Merge loaded config with defaults (preserves saved_custom, etc.)
                default.update(loaded)
                # Ensure allow/block dicts have all keys
                if "allow" not in default:
                    default["allow"] = {cat[0]: False for cat in ALLOW_CATEGORIES}
                if "block" not in default:
                    default["block"] = {pat[0]: True for pat in BLOCK_PATTERNS}
            except:
                pass

        return default

    def save_config(self):
        # Always save minimal_mode preference, last_active_template, and write_edit_on
        self.config["minimal_mode"] = self.minimal_mode
        self.config["last_active_template"] = self.last_active_template
        self.config["write_edit_on"] = self.write_edit_on
        self.config[APPROVAL_MODE_KEY] = self.get_approval_mode()

        sync_managed_permission_rules(self.config, self.is_on)
        atomic_write_json(CONFIG_FILE, self.config)

    def get_approval_mode(self):
        mode = self.config.get(APPROVAL_MODE_KEY, APPROVAL_MODE_SILENT)
        if mode in (APPROVAL_MODE_SILENT, APPROVAL_MODE_SHOW_ACCEPTS):
            return mode
        return APPROVAL_MODE_SILENT

    def toggle_approval_mode(self):
        next_mode = APPROVAL_MODE_SHOW_ACCEPTS
        if self.get_approval_mode() == APPROVAL_MODE_SHOW_ACCEPTS:
            next_mode = APPROVAL_MODE_SILENT
        self.set_approval_mode(next_mode)

    def set_approval_mode(self, mode):
        self.config[APPROVAL_MODE_KEY] = mode
        if hasattr(self, "approval_mode_var"):
            self.approval_mode_var.set(mode)
        self.save_config()
        if self.minimal_mode:
            self.update_minimal_display()
        else:
            self.update_display()

    def clear_active_config(self):
        """Clear active permissions but preserve preferences (like X close does)."""
        sync_managed_permission_rules(self.config, False)
        preserved = build_preserved_config(
            self.config,
            self.minimal_mode,
            self.last_active_template,
            self.write_edit_on,
        )
        atomic_write_json(CONFIG_FILE, preserved)

    def detect_template(self):
        for name, preset in TEMPLATES.items():
            if (all(self.config.get("allow", {}).get(k, False) == v for k, v in preset["allow"].items()) and
                all(self.config.get("block", {}).get(k, True) == v for k, v in preset["block"].items())):
                return name
        return "custom"

    def build_minimal_ui(self):
        """Build the minimal split-toggle UI: [Write/Edit] | [Custom]"""
        c = self.c

        self.root.title("Claude")
        self.root.minsize(240, 50)
        self.root.geometry("240x50")

        # Position bottom-right
        self.root.update_idletasks()
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        self.root.geometry(f"+{screen_w - 260}+{screen_h - 120}")

        # Main frame
        main = tk.Frame(self.root, bg=c["bg"])
        main.pack(fill="both", expand=True, padx=5, pady=5)

        # Single row: expand button + write/edit toggle + custom toggle
        row = tk.Frame(main, bg=c["bg"])
        row.pack(fill="x", expand=True)

        # Expand button (small, left side)
        expand_btn = tk.Button(row, text="...", font=("Segoe UI", 8),
                              bd=0, relief="flat", cursor="hand2",
                              bg=c["card"], fg=c["muted"],
                              padx=6, pady=2,
                              command=self.expand_ui)
        expand_btn.pack(side="left", padx=(0, 5))

        # Write/Edit toggle button (left of main area) - ✎ pencil symbol
        self.write_edit_btn = tk.Button(row, text="✎", font=("Segoe UI", 14),
                                        bd=0, relief="flat", cursor="hand2",
                                        padx=8, pady=4,
                                        command=self.toggle_write_edit)
        self.write_edit_btn.pack(side="left", padx=(0, 3))

        # Separator
        sep = tk.Frame(row, bg=c["border"], width=2)
        sep.pack(side="left", fill="y", padx=2, pady=4)

        # Custom toggle button (main area)
        self.power_btn = tk.Button(row, text="", font=("Segoe UI", 11, "bold"),
                                   bd=0, relief="flat", cursor="hand2",
                                   padx=15, pady=6,
                                   command=self.toggle_power)
        self.power_btn.pack(side="left", fill="x", expand=True)

        self.update_minimal_display()

    def update_minimal_display(self):
        """Update the minimal UI display with split buttons."""
        c = self.c
        approval_mode = self.get_approval_mode()

        if self.is_on:
            # Show current mode name on Custom button
            mode_names = {"all_safe": "ALL*", "all": "ALL", "custom": "CUSTOM"}
            mode_colors = {"all_safe": c["green"], "all": c["red"], "custom": c["purple"]}

            mode = self.last_active_template
            label = mode_names.get(mode, "ON")
            color = mode_colors.get(mode, c["green"])

            self.power_btn.config(text=label, bg=color, fg="white")

            # Write/Edit button - enabled and shows state
            if self.write_edit_on:
                self.write_edit_btn.config(text="✎", bg=c["blue"], fg="white",
                                          state="normal", cursor="hand2")
            else:
                self.write_edit_btn.config(text="✎", bg=c["gray"], fg=c["text"],
                                          state="normal", cursor="hand2")

            # Title shows both states
            we_status = "W/E" if self.write_edit_on else "R/O"
            approval_status = "SHOW" if approval_mode == APPROVAL_MODE_SHOW_ACCEPTS else "SILENT"
            self.root.title(f"Claude: {we_status}|{label}|{approval_status}")
        else:
            # Custom is OFF - everything disabled
            self.power_btn.config(text="OFF", bg=c["gray"], fg=c["text"])
            # Write/Edit greyed out and disabled when Custom is OFF
            self.write_edit_btn.config(text="✎", bg=c["card"], fg=c["muted"],
                                      state="disabled", cursor="arrow")
            self.root.title("Claude: OFF")

    def toggle_power(self):
        """Toggle between ON (last active mode) and OFF."""
        if self.is_on:
            # Turn OFF - unregister hook, Claude returns to native behavior
            unregister_hook()
            self.is_on = False
            # Clear active permissions but preserve preferences
            self.clear_active_config()
        else:
            # Turn ON - register hook and restore last active template
            register_hook()
            self.apply_template_silent(self.last_active_template)
            self.apply_write_edit_state()
            self.is_on = True
            self.save_config()

        self.update_minimal_display()

    def toggle_write_edit(self):
        """Toggle Write/Edit permissions on/off (only when Custom is ON)."""
        if not self.is_on:
            return  # Can't toggle when Custom is OFF

        self.write_edit_on = not self.write_edit_on
        self.apply_write_edit_state()
        self.save_config()
        self.update_minimal_display()

    def apply_write_edit_state(self):
        """Apply the current write_edit_on state to config."""
        if self.write_edit_on:
            # Enable write, edit, notebook
            self.config["allow"]["write"] = True
            self.config["allow"]["edit"] = True
            self.config["allow"]["notebook"] = True
        else:
            # Disable write, edit, notebook
            self.config["allow"]["write"] = False
            self.config["allow"]["edit"] = False
            self.config["allow"]["notebook"] = False

    def apply_template_silent(self, name):
        """Apply a template without UI updates (for minimal mode)."""
        if name == "custom":
            saved = self.config.get("saved_custom")
            if saved:
                for cat_id, value in saved.get("allow", {}).items():
                    self.config["allow"][cat_id] = value
                for pat_id, value in saved.get("block", {}).items():
                    self.config["block"][pat_id] = value
                self.current_template = "custom"
                return
            # No saved custom — fall back to all_safe
            name = "all_safe"
        preset = TEMPLATES[name]
        for cat_id, value in preset["allow"].items():
            self.config["allow"][cat_id] = value
        for pat_id, value in preset["block"].items():
            self.config["block"][pat_id] = value
        self.current_template = name

    def expand_ui(self):
        """Switch to full UI mode."""
        self.minimal_mode = False
        self.config["minimal_mode"] = False

        # Apply write_edit state to config before expanding
        # This ensures the full UI checkboxes match minimal mode state
        self.apply_write_edit_state()

        self.save_config()

        # Destroy current widgets and rebuild
        for widget in self.root.winfo_children():
            widget.destroy()

        self.build_full_ui()

    def build_full_ui(self):
        """Build the full expanded UI."""
        c = self.c

        self.root.title("Claude Permissions")
        self.root.minsize(340, 400)
        self.root.geometry("340x650")

        # Position bottom-right
        self.root.update_idletasks()
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        self.root.geometry(f"+{screen_w - 360}+{screen_h - 720}")

        # Main container with flex
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        # Outer frame
        outer = tk.Frame(self.root, bg=c["bg"])
        outer.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)
        outer.grid_rowconfigure(0, weight=1)
        outer.grid_columnconfigure(0, weight=1)

        # Canvas + Scrollbar
        canvas = tk.Canvas(outer, bg=c["bg"], highlightthickness=0, bd=0)
        scrollbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview, style="Dark.Vertical.TScrollbar")

        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Scrollable frame
        main = tk.Frame(canvas, bg=c["bg"])
        canvas_window = canvas.create_window((0, 0), window=main, anchor="nw")

        def configure_scroll(event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def configure_width(event):
            canvas.itemconfig(canvas_window, width=event.width)

        main.bind("<Configure>", configure_scroll)
        canvas.bind("<Configure>", configure_width)

        # Mouse wheel
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", on_mousewheel)

        # === HEADER ===
        header = tk.Frame(main, bg=c["bg"])
        header.pack(fill="x", padx=15, pady=(15, 5))

        # Title row with minimize button
        title_row = tk.Frame(header, bg=c["bg"])
        title_row.pack(fill="x")

        tk.Label(title_row, text="Claude Permissions", font=("Segoe UI", 16, "bold"),
                bg=c["bg"], fg=c["text"]).pack(side="left")

        # Minimize button (right side of title)
        minimize_btn = tk.Button(title_row, text="_", font=("Segoe UI", 10, "bold"),
                                bd=0, relief="flat", cursor="hand2",
                                bg=c["card"], fg=c["muted"],
                                padx=8, pady=2,
                                command=self.minimize_ui)
        minimize_btn.pack(side="right")

        self.status_label = tk.Label(header, text="", font=("Segoe UI", 10),
                                     bg=c["bg"], fg=c["muted"])
        self.status_label.pack(anchor="w", pady=(2, 0))

        # === TEMPLATE BUTTONS ===
        btn_frame = tk.Frame(main, bg=c["bg"])
        btn_frame.pack(fill="x", padx=15, pady=(10, 5))

        self.template_buttons = {}
        templates = [("off", "OFF"), ("all_safe", "ALL*"), ("all", "ALL"), ("custom", "CUSTOM")]

        for i, (name, label) in enumerate(templates):
            btn_frame.grid_columnconfigure(i, weight=1)
            btn = tk.Button(btn_frame, text=label, font=("Segoe UI", 10, "bold"),
                           bd=0, relief="flat", cursor="hand2", padx=12, pady=6,
                           command=lambda n=name: self.apply_template(n) if n != "custom" else self.load_custom())
            btn.grid(row=0, column=i, sticky="ew", padx=2)
            self.template_buttons[name] = btn

        # Legend + Save button row
        legend_row = tk.Frame(main, bg=c["bg"])
        legend_row.pack(fill="x", padx=15, pady=(5, 10))

        tk.Label(legend_row, text="ALL* = Allow all, block destructive", font=("Segoe UI", 8),
                bg=c["bg"], fg=c["muted"]).pack(side="left")

        self.save_btn = tk.Button(legend_row, text="Save", font=("Segoe UI", 8, "bold"),
                                  bd=0, relief="flat", cursor="hand2", padx=10, pady=2,
                                  bg=c["card"], fg=c["muted"],
                                  command=self.save_custom)
        self.save_btn.pack(side="right")

        mode_label = tk.Label(main, text="APPROVAL DISPLAY:", font=("Segoe UI", 10, "bold"),
                              bg=c["bg"], fg=c["text"], anchor="w")
        mode_label.pack(fill="x", padx=15, pady=(5, 5))

        mode_card = tk.Frame(main, bg=c["card"], bd=1,
                             highlightbackground=c["border"], highlightthickness=1)
        mode_card.pack(fill="x", padx=15, pady=(0, 10))

        self.approval_mode_var = tk.StringVar(value=self.get_approval_mode())

        silent_btn = tk.Radiobutton(
            mode_card,
            text="Silent mode: skip the permission dialog whenever Claude can be auto-approved",
            variable=self.approval_mode_var,
            value=APPROVAL_MODE_SILENT,
            font=("Segoe UI", 9),
            bg=c["card"],
            fg=c["text"],
            selectcolor=c["bg"],
            activebackground=c["card"],
            activeforeground=c["text"],
            highlightthickness=0,
            bd=0,
            anchor="w",
            padx=8,
            pady=2,
            command=lambda: self.set_approval_mode(APPROVAL_MODE_SILENT),
        )
        silent_btn.pack(fill="x")

        show_btn = tk.Radiobutton(
            mode_card,
            text="Show accepts: surface the permission dialog, then auto-accept allowed tools",
            variable=self.approval_mode_var,
            value=APPROVAL_MODE_SHOW_ACCEPTS,
            font=("Segoe UI", 9),
            bg=c["card"],
            fg=c["text"],
            selectcolor=c["bg"],
            activebackground=c["card"],
            activeforeground=c["text"],
            highlightthickness=0,
            bd=0,
            anchor="w",
            padx=8,
            pady=2,
            command=lambda: self.set_approval_mode(APPROVAL_MODE_SHOW_ACCEPTS),
        )
        show_btn.pack(fill="x")

        # === ALLOW SECTION ===
        self.build_section(main, "ALLOW (auto-approve):", ALLOW_CATEGORIES, "allow")

        # === BLOCK SECTION ===
        self.build_section(main, "BLOCK (always deny):", BLOCK_PATTERNS, "block", smaller=True)

        # === FOOTER INFO ===
        self.info_label = tk.Label(main, text="", font=("Segoe UI", 9),
                                  bg=c["bg"], fg=c["muted"], wraplength=300, justify="left")
        self.info_label.pack(fill="x", padx=15, pady=(10, 15))

        self.update_display()

    def minimize_ui(self):
        """Switch to minimal UI mode."""
        self.minimal_mode = True
        self.config["minimal_mode"] = True

        # Remember current mode if not OFF
        if self.current_template != "off":
            self.last_active_template = self.current_template
            self.is_on = True
        else:
            self.is_on = False

        # Sync write_edit_on from current allow config
        self.write_edit_on = (
            self.config.get("allow", {}).get("write", False) and
            self.config.get("allow", {}).get("edit", False)
        )

        self.save_config()

        # Destroy current widgets and rebuild
        for widget in self.root.winfo_children():
            widget.destroy()

        # Clear vars that full UI uses
        self.allow_vars = {}
        self.block_vars = {}

        self.build_minimal_ui()

    def build_section(self, parent, title, items, config_key, smaller=False):
        c = self.c

        # Section label
        tk.Label(parent, text=title, font=("Segoe UI", 10, "bold"),
                bg=c["bg"], fg=c["text"], anchor="w").pack(fill="x", padx=15, pady=(5, 5))

        # Card frame
        card = tk.Frame(parent, bg=c["card"], bd=1, highlightbackground=c["border"], highlightthickness=1)
        card.pack(fill="x", padx=15, pady=(0, 10))

        # Store vars
        vars_dict = getattr(self, f"{config_key}_vars", None)
        if vars_dict is None:
            vars_dict = {}
            setattr(self, f"{config_key}_vars", vars_dict)

        font_size = 9 if smaller else 10

        for item_id, label in items:
            default = True if config_key == "block" else False
            var = tk.BooleanVar(value=self.config.get(config_key, {}).get(item_id, default))

            cb = tk.Checkbutton(card, text=label, variable=var,
                               font=("Segoe UI", font_size),
                               bg=c["card"], fg=c["text"],
                               selectcolor=c["bg"],
                               activebackground=c["card"],
                               activeforeground=c["text"],
                               highlightthickness=0, bd=0,
                               anchor="w", padx=8, pady=2,
                               command=self.on_change)
            cb.pack(fill="x")
            vars_dict[item_id] = var

    def apply_template(self, name):
        preset = TEMPLATES[name]
        for cat_id, value in preset["allow"].items():
            self.allow_vars[cat_id].set(value)
            self.config["allow"][cat_id] = value
        for pat_id, value in preset["block"].items():
            self.block_vars[pat_id].set(value)
            self.config["block"][pat_id] = value
        self.current_template = name

        # Track last active template (if not OFF)
        if name != "off":
            self.last_active_template = name
            self.is_on = True
            # Re-register hook if turning back on
            register_hook()
            self.save_config()
        else:
            # OFF = unregister hook, Claude returns to native behavior
            self.is_on = False
            unregister_hook()
            self.clear_active_config()

        self.update_display()
        # Reset save button (templates auto-save)
        self.save_btn.config(bg=self.c["card"], fg=self.c["muted"], text="Save")

    def on_change(self):
        for cat_id, var in self.allow_vars.items():
            self.config["allow"][cat_id] = var.get()
        for pat_id, var in self.block_vars.items():
            self.config["block"][pat_id] = var.get()
        self.current_template = self.detect_template()

        # Track last active template (if not OFF)
        if self.current_template != "off":
            self.last_active_template = self.current_template
            self.is_on = True
        else:
            self.is_on = False

        # Hot save - takes effect immediately
        self.save_config()
        self.update_display()

    def save_custom(self):
        """Save current settings as the custom template."""
        # Read directly from UI vars to get current checkbox state
        self.config["saved_custom"] = {
            "allow": {cat_id: var.get() for cat_id, var in self.allow_vars.items()},
            "block": {pat_id: var.get() for pat_id, var in self.block_vars.items()}
        }
        self.save_config()
        # Flash green to confirm save
        self.save_btn.config(bg=self.c["green"], fg="white", text="Saved!")
        self.root.after(1500, lambda: self.save_btn.config(
            bg=self.c["card"], fg=self.c["muted"], text="Save"))

    def load_custom(self):
        """Load the saved custom template."""
        saved = self.config.get("saved_custom")
        if saved:
            for cat_id, value in saved.get("allow", {}).items():
                if cat_id in self.allow_vars:
                    self.allow_vars[cat_id].set(value)
                    self.config["allow"][cat_id] = value
            for pat_id, value in saved.get("block", {}).items():
                if pat_id in self.block_vars:
                    self.block_vars[pat_id].set(value)
                    self.config["block"][pat_id] = value
            self.current_template = "custom"
            self.last_active_template = "custom"
            self.is_on = True
            self.save_config()
            self.update_display()

    def update_display(self):
        c = self.c
        template = self.current_template
        approval_mode = self.get_approval_mode()

        if hasattr(self, "approval_mode_var"):
            self.approval_mode_var.set(approval_mode)

        # Button colors
        colors = {"off": c["gray"], "all_safe": c["green"], "all": c["red"], "custom": c["purple"]}
        for name, btn in self.template_buttons.items():
            if name == template:
                btn.config(bg=colors.get(name, c["purple"]), fg="white")
            else:
                btn.config(bg=c["card"], fg=c["muted"])

        # Status
        allowed = sum(1 for v in self.allow_vars.values() if v.get())
        blocked = sum(1 for v in self.block_vars.values() if v.get())

        if allowed == 0:
            status = "OFF - Claude asks for everything"
            self.status_label.config(fg=c["gray"])
        elif template == "all":
            status = "ALL - No protections (dangerous!)"
            self.status_label.config(fg=c["red"])
        elif template == "all_safe":
            status = f"ALL* - {blocked} destructive blocked"
            self.status_label.config(fg=c["green"])
        else:
            status = f"CUSTOM - {allowed} allowed, {blocked} blocked"
            self.status_label.config(fg=c["purple"])

        self.status_label.config(text=status)
        approval_status = "Show accepts" if approval_mode == APPROVAL_MODE_SHOW_ACCEPTS else "Silent"
        self.root.title(f"Claude: {template.upper()} | {approval_status}")

        # Info
        if template == "all":
            self.info_label.config(
                text=f"Warning: Destructive commands will run! Approval display: {approval_status}.",
                fg=c["red"],
            )
        elif blocked > 0:
            self.info_label.config(
                text=f"Protected: {blocked} patterns blocked. Approval display: {approval_status}.",
                fg=c["green"],
            )
        else:
            self.info_label.config(text=f"Approval display: {approval_status}.", fg=c["muted"])

    def acquire_runtime_lock(self):
        """Hold an exclusive lock while the toggle process is alive."""
        self.lock_handle = open(LOCK_FILE, "a+b")
        self.lock_handle.seek(0, os.SEEK_END)
        if self.lock_handle.tell() == 0:
            self.lock_handle.write(b"1")
            self.lock_handle.flush()
        self.lock_handle.seek(0)

        try:
            msvcrt.locking(self.lock_handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            try:
                self.lock_handle.close()
            except OSError:
                pass
            self.lock_handle = None
            self.root.destroy()
            raise SystemExit("Claude Permissions Toggle is already running")

    def release_runtime_lock(self):
        if self.lock_handle is None:
            return

        try:
            self.lock_handle.seek(0)
            msvcrt.locking(self.lock_handle.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass

        try:
            self.lock_handle.close()
        except OSError:
            pass

        self.lock_handle = None

        try:
            if os.path.exists(LOCK_FILE):
                os.remove(LOCK_FILE)
        except OSError:
            pass

    def cleanup_state(self):
        if self._cleaned_up:
            return

        self._cleaned_up = True

        unregister_hook()
        sync_managed_permission_rules(self.config, False)
        preserved = build_preserved_config(
            self.config,
            self.minimal_mode,
            self.last_active_template,
            self.write_edit_on,
        )

        if preserved:
            atomic_write_json(CONFIG_FILE, preserved)
        elif os.path.exists(CONFIG_FILE):
            try:
                os.remove(CONFIG_FILE)
            except OSError:
                pass

        self.release_runtime_lock()

    def on_close(self):
        self.cleanup_state()
        self.root.destroy()

    def run(self):
        try:
            self.root.mainloop()
        finally:
            self.cleanup_state()


if __name__ == "__main__":
    app = PermissionsToggle()
    app.run()
