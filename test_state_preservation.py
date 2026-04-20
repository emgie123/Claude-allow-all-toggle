#!/usr/bin/env python3
"""State-preservation tests for the GUI config helpers."""
import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("AutoYesToggle.pyw")
spec = importlib.util.spec_from_file_location("auto_yes_toggle", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


def main():
    config = {
        "saved_custom": {"allow": {"read": True}, "block": {"rm_rf": True}},
        "approval_mode": "show_accepts",
        "managed_allow_rules": ["Write", "Edit"],
        "allow": {"read": True},
        "block": {"rm_rf": True},
    }

    preserved = module.build_preserved_config(
        config=config,
        minimal_mode=True,
        last_active_template="custom",
        write_edit_on=False,
    )

    assert preserved["minimal_mode"] is True
    assert preserved["last_active_template"] == "custom"
    assert preserved["write_edit_on"] is False
    assert preserved["approval_mode"] == "show_accepts"
    assert preserved["saved_custom"] == config["saved_custom"]
    assert preserved["managed_allow_rules"] == ["Write", "Edit"]
    assert "allow" not in preserved
    assert "block" not in preserved

    print("state preservation tests passed")


if __name__ == "__main__":
    main()
