#!/usr/bin/env python3
"""Claude Token Dash — cross-platform installer.

Usage:
    python install.py          # Install
    python install.py --uninstall  # Uninstall
"""

import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

CLAUDE_DIR = Path.home() / ".claude"
HOOKS_DIR = CLAUDE_DIR / "hooks"
COMMANDS_DIR = CLAUDE_DIR / "commands"
SETTINGS_FILE = CLAUDE_DIR / "settings.json"
SCRIPT_DIR = Path(__file__).parent


def find_python_command():
    """Detect the available Python command on this system."""
    candidates = ["python3", "python", "py"]
    for cmd in candidates:
        try:
            result = subprocess.run(
                [cmd, "--version"], capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and "Python 3" in result.stdout:
                return cmd
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    # Fallback: use the current interpreter
    return sys.executable


def install():
    python_cmd = find_python_command()
    print("=== Claude Token Dash Installer ===")
    print(f"Platform: {platform.system()}")
    print(f"Python:   {python_cmd}")
    print()

    # Create directories
    HOOKS_DIR.mkdir(parents=True, exist_ok=True)
    COMMANDS_DIR.mkdir(parents=True, exist_ok=True)

    # Copy hook scripts
    print("[1/5] Installing hook scripts...")
    src_dir = SCRIPT_DIR / "src"
    for f in ["track_tokens.py", "dashboard.py", "import_history.py", "pricing.json"]:
        shutil.copy2(src_dir / f, HOOKS_DIR / f)
    print(f"  -> {HOOKS_DIR}")

    # Copy and patch slash commands (replace python3 with detected command)
    print("[2/5] Installing slash commands...")
    for f in ["token-dash.md", "token-cost.md"]:
        src = SCRIPT_DIR / "commands" / f
        content = src.read_text(encoding="utf-8")
        content = content.replace("python3 ", f"{python_cmd} ")
        (COMMANDS_DIR / f).write_text(content, encoding="utf-8")
    print(f"  -> {COMMANDS_DIR}")

    # Configure settings.json
    print("[3/5] Configuring Stop hook...")
    if not SETTINGS_FILE.exists():
        SETTINGS_FILE.write_text("{}", encoding="utf-8")

    settings = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    hook_script = str(HOOKS_DIR / "track_tokens.py")
    hook_cmd = f"{python_cmd} {hook_script}"

    hooks = settings.setdefault("hooks", {})
    stop_hooks = hooks.setdefault("Stop", [])

    already_exists = any(
        h.get("command", "").endswith("track_tokens.py")
        for group in stop_hooks
        for h in group.get("hooks", [])
    )

    if already_exists:
        # Update existing hook command (in case python command changed)
        for group in stop_hooks:
            for h in group.get("hooks", []):
                if h.get("command", "").endswith("track_tokens.py"):
                    h["command"] = hook_cmd
        print("  Hook updated in settings.json")
    else:
        stop_hooks.append({
            "matcher": "",
            "hooks": [{
                "type": "command",
                "command": hook_cmd,
                "timeout": 5,
            }],
        })
        print("  Hook added to settings.json")

    SETTINGS_FILE.write_text(json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8")

    # Import history
    print("[4/5] Importing historical data...")
    subprocess.run([python_cmd, str(HOOKS_DIR / "import_history.py")])

    # Done
    print()
    print("[5/5] Verifying installation...")
    checks = [
        (HOOKS_DIR / "track_tokens.py", "track_tokens.py"),
        (HOOKS_DIR / "dashboard.py", "dashboard.py"),
        (HOOKS_DIR / "pricing.json", "pricing.json"),
        (COMMANDS_DIR / "token-dash.md", "token-dash.md"),
        (COMMANDS_DIR / "token-cost.md", "token-cost.md"),
    ]
    all_ok = True
    for path, name in checks:
        if path.exists():
            print(f"  [OK] {name}")
        else:
            print(f"  [FAIL] {name}")
            all_ok = False

    print()
    if all_ok:
        print("=== Installation complete! ===")
    else:
        print("=== Installation completed with warnings ===")

    print()
    print("Usage:")
    print("  Token tracking is now automatic (runs on every Claude Code turn)")
    print("  In Claude Code, type /token-dash to open the dashboard")
    print("  In Claude Code, type /token-cost for a quick terminal summary")
    print(f"  Or run: {python_cmd} {HOOKS_DIR / 'dashboard.py'}")


def uninstall():
    print("=== Claude Token Dash Uninstaller ===")
    print()

    # Remove hook scripts
    print("[1/3] Removing hook scripts...")
    for f in ["track_tokens.py", "dashboard.py", "import_history.py", "pricing.json"]:
        p = HOOKS_DIR / f
        if p.exists():
            p.unlink()
            print(f"  Removed {f}")

    # Remove slash commands
    print("[2/3] Removing slash commands...")
    for f in ["token-dash.md", "token-cost.md"]:
        p = COMMANDS_DIR / f
        if p.exists():
            p.unlink()
            print(f"  Removed {f}")

    # Remove hook from settings.json
    print("[3/3] Removing hook from settings.json...")
    if SETTINGS_FILE.exists():
        settings = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        hooks = settings.get("hooks", {})
        stop_hooks = hooks.get("Stop", [])
        hooks["Stop"] = [
            group for group in stop_hooks
            if not any(
                h.get("command", "").endswith("track_tokens.py")
                for h in group.get("hooks", [])
            )
        ]
        if not hooks["Stop"]:
            del hooks["Stop"]
        if not hooks:
            del settings["hooks"]
        SETTINGS_FILE.write_text(json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8")
        print("  Hook removed from settings.json")

    print()
    print("=== Uninstall complete ===")
    print()
    print("Optional: remove data files manually:")
    print(f"  Database:  {CLAUDE_DIR / 'token_usage.db'}")
    print(f"  Dashboard: {CLAUDE_DIR / 'token_dashboard.html'}")


if __name__ == "__main__":
    if "--uninstall" in sys.argv:
        uninstall()
    else:
        install()
