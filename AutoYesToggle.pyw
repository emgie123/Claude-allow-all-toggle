"""
Claude Permissions Toggle
Category-based permissions with granular block list.
"""
import tkinter as tk
from tkinter import ttk
import os
import json

CONFIG_FILE = os.path.join(os.path.expanduser("~"), '.claude-permissions.json')

# Allow categories
ALLOW_CATEGORIES = [
    ("read", "Read files"),
    ("write", "Write files"),
    ("edit", "Edit files"),
    ("search", "Search (Glob/Grep)"),
    ("web", "Web access"),
    ("notebook", "Notebook edit"),
    ("task", "Task/Todo tools"),
    ("bash_safe", "Bash (safe: npm, node, pip, ls)"),
    ("bash_all", "Bash (all commands)"),
    ("git", "Git commands"),
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
TEMPLATES = {
    "off": {
        "allow": {cat[0]: False for cat in ALLOW_CATEGORIES},
        "block": {pat[0]: True for pat in BLOCK_PATTERNS},
    },
    "all_safe": {
        "allow": {cat[0]: True for cat in ALLOW_CATEGORIES},
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
        self.root.title("Claude Permissions")
        self.root.minsize(340, 400)
        self.root.geometry("340x650")
        self.root.attributes("-topmost", True)

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

        # Build UI
        self.build_ui()
        self.update_display()

        # Position bottom-right
        self.root.update_idletasks()
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        self.root.geometry(f"+{screen_w - 360}+{screen_h - 720}")

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {
            "allow": {cat[0]: False for cat in ALLOW_CATEGORIES},
            "block": {pat[0]: True for pat in BLOCK_PATTERNS},
        }

    def save_config(self):
        if not any(self.config["allow"].values()):
            if os.path.exists(CONFIG_FILE):
                os.remove(CONFIG_FILE)
        else:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(self.config, f, indent=2)

    def detect_template(self):
        for name, preset in TEMPLATES.items():
            if (all(self.config.get("allow", {}).get(k, False) == v for k, v in preset["allow"].items()) and
                all(self.config.get("block", {}).get(k, True) == v for k, v in preset["block"].items())):
                return name
        return "custom"

    def build_ui(self):
        c = self.c

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

        tk.Label(header, text="Claude Permissions", font=("Segoe UI", 16, "bold"),
                bg=c["bg"], fg=c["text"]).pack(anchor="w")

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

        # === ALLOW SECTION ===
        self.build_section(main, "ALLOW (auto-approve):", ALLOW_CATEGORIES, "allow")

        # === BLOCK SECTION ===
        self.build_section(main, "BLOCK (always deny):", BLOCK_PATTERNS, "block", smaller=True)

        # === FOOTER INFO ===
        self.info_label = tk.Label(main, text="", font=("Segoe UI", 9),
                                  bg=c["bg"], fg=c["muted"], wraplength=300, justify="left")
        self.info_label.pack(fill="x", padx=15, pady=(10, 15))

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
        self.save_config()
        self.update_display()
        # Reset save button (templates auto-save)
        self.save_btn.config(bg=self.c["card"], fg=self.c["muted"], text="Save")

    def on_change(self):
        for cat_id, var in self.allow_vars.items():
            self.config["allow"][cat_id] = var.get()
        for pat_id, var in self.block_vars.items():
            self.config["block"][pat_id] = var.get()
        self.current_template = self.detect_template()
        # Hot save - takes effect immediately
        self.save_config()
        self.update_display()

    def save_custom(self):
        """Save current settings as the custom template."""
        self.config["saved_custom"] = {
            "allow": dict(self.config["allow"]),
            "block": dict(self.config["block"])
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
            self.save_config()
            self.update_display()

    def update_display(self):
        c = self.c
        template = self.current_template

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
        self.root.title(f"Claude: {template.upper()}")

        # Info
        if template == "all":
            self.info_label.config(text="Warning: Destructive commands will run!", fg=c["red"])
        elif blocked > 0:
            self.info_label.config(text=f"Protected: {blocked} patterns blocked", fg=c["green"])
        else:
            self.info_label.config(text="")

    def on_close(self):
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = PermissionsToggle()
    app.run()
