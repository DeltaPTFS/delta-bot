"""Compatibility launcher for hosts that have not yet switched to ``bot/main.py``.

There is no bot implementation here. New deployments must run ``python bot/main.py``;
this wrapper only forwards old launch commands to the single production entry point.
"""

from main import main


LEGACY_COMPATIBILITY_SHIM = True


if __name__ == "__main__":
    main()
