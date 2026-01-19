"""
Auto-Yes Toggle for Claude Code
A simple GUI toggle that enables/disables auto-approval of Claude Code tool calls.

Double-click to launch. Click the window to toggle ON/OFF.
Works with the auto-yes-hook.cmd Claude Code hook.
"""
import tkinter as tk
import os

# User-agnostic path - works on any Windows machine
FLAG_FILE = os.path.join(os.path.expanduser("~"), '.claude-auto-yes')

class AutoYesToggle:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Auto-Yes")
        self.root.geometry("200x80")
        self.root.resizable(False, False)
        self.root.attributes("-topmost", True)

        # Position in bottom-right corner
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = screen_width - 220
        y = screen_height - 150
        self.root.geometry(f"200x80+{x}+{y}")

        # Main button (fills the window)
        self.btn = tk.Button(
            self.root,
            text="OFF",
            font=("Segoe UI", 24, "bold"),
            command=self.toggle,
            cursor="hand2"
        )
        self.btn.pack(fill=tk.BOTH, expand=True)

        # Check current state
        self.update_display()

        # Clean up flag file when window closes
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def is_on(self):
        return os.path.exists(FLAG_FILE)

    def toggle(self):
        if self.is_on():
            # Turn OFF
            try:
                os.remove(FLAG_FILE)
            except:
                pass
        else:
            # Turn ON
            with open(FLAG_FILE, 'w') as f:
                f.write('on')
        self.update_display()

    def update_display(self):
        if self.is_on():
            self.btn.config(text="ON", bg="#22C55E", fg="white", activebackground="#16A34A")
            self.root.title("Auto-Yes: ON")
        else:
            self.btn.config(text="OFF", bg="#DC2626", fg="white", activebackground="#B91C1C")
            self.root.title("Auto-Yes: OFF")

    def on_close(self):
        # State persists after closing - toggle stays ON or OFF
        self.root.destroy()

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = AutoYesToggle()
    app.run()
