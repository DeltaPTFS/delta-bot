"""Fail CI on syntax damage commonly introduced during web conflict resolution."""

from __future__ import annotations

import ast
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BOT_DIR = ROOT / "bot"


def validate_python_sources() -> None:
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
