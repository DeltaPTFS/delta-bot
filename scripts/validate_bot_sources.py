"""Fail CI on syntax damage commonly introduced during web conflict resolution."""

from __future__ import annotations

import ast
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BOT_DIR = ROOT / "bot"
REMOVED_IMPLEMENTATIONS = {
    "delta_bot.py",
    "commands.py",
    "embeds.py",
    "tickets.py",
    "utils.py",
    "views.py",
}


def validate_python_sources() -> None:
    stale = sorted(path.name for path in BOT_DIR.iterdir() if path.name in REMOVED_IMPLEMENTATIONS)
    if stale:
        raise ValueError(
            "stale bot implementation files must not be restored: " + ", ".join(stale)
        )

    for path in sorted(BOT_DIR.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        top_level_names = [
            node.name
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        ]
        duplicates = [
            name for name, count in Counter(top_level_names).items() if count > 1
        ]
        if duplicates:
            names = ", ".join(sorted(duplicates))
            raise ValueError(f"{path}: duplicate top-level definitions: {names}")

    main_source = (BOT_DIR / "main.py").read_text(encoding="utf-8")
    if 'if __name__ == "__main__":\n    main()' not in main_source:
        raise ValueError("bot/main.py must invoke main() directly")
    if "delta_bot" in main_source:
        raise ValueError("bot/main.py must not redirect into delta_bot.py")

    config_tree = ast.parse(
        (BOT_DIR / "config.py").read_text(encoding="utf-8"),
        filename=str(BOT_DIR / "config.py"),
    )
    version_assignments = [
        node
        for node in config_tree.body
        if isinstance(node, (ast.Assign, ast.AnnAssign))
        and any(
            isinstance(target, ast.Name) and target.id == "BOT_VERSION"
            for target in ([node.target] if isinstance(node, ast.AnnAssign) else node.targets)
        )
    ]
    if len(version_assignments) != 1 or "BOT_VERSION =" in main_source:
        raise ValueError("BOT_VERSION must be defined exactly once in bot/config.py")


def validate_support_formats() -> None:
    path = BOT_DIR / "support_formats.json"
    formats = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(formats, dict) or not formats:
        raise ValueError(f"{path}: expected a non-empty object")
    if "unavailable" in formats:
        raise ValueError(f"{path}: the removed unavailable response was restored")
    for key, value in formats.items():
        if not isinstance(value, dict):
            raise ValueError(f"{path}: {key!r} must be an object")
        if not all(isinstance(value.get(field), str) and value[field] for field in ("label", "message")):
            raise ValueError(f"{path}: {key!r} requires non-empty label and message strings")
        if len(value["message"]) > 4096:
            raise ValueError(f"{path}: {key!r} exceeds Discord's embed description limit")

    for key in ("leadership", "hr"):
        message = formats[key]["message"]
        required_sections = (
            "**CV - Resume**",
            "**Statement Of Intent**",
            "**Which Department are you applying for, why?**",
            "**a bare minimum** of **3 sentences**",
        )
        if not all(section in message for section in required_sections):
            raise ValueError(f"{path}: {key!r} is missing application requirements")


def validate_messages() -> None:
    path = BOT_DIR / "messages.json"
    messages = json.loads(path.read_text(encoding="utf-8"))
    required = {"ticket_claimed"}
    if not isinstance(messages, dict) or set(messages) != required:
        raise ValueError(f"{path}: expected exactly these keys: {sorted(required)}")
    if not all(isinstance(value, str) and value for value in messages.values()):
        raise ValueError(f"{path}: every message must be a non-empty string")


if __name__ == "__main__":
    validate_python_sources()
    validate_support_formats()
    validate_messages()
    print("Bot Python syntax, definitions, support formats, and messages are valid.")
