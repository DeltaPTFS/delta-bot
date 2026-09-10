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


if __name__ == "__main__":
    validate_python_sources()
    validate_support_formats()
    print("Bot Python syntax, definitions, and support formats are valid.")
