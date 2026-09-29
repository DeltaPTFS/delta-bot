"""Regression checks for weekly audit persistence and Eastern boundaries."""

from datetime import datetime
from pathlib import Path
import sys
import tempfile
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bot"))

from audit_log import AuditLogStore  # noqa: E402
from main import latest_sunday_midnight  # noqa: E402


eastern = ZoneInfo("America/New_York")
assert latest_sunday_midnight(datetime(2026, 10, 1, 15, tzinfo=eastern)) == datetime(
    2026, 9, 27, 0, tzinfo=eastern
)
assert latest_sunday_midnight(datetime(2026, 11, 1, 0, tzinfo=eastern)) == datetime(
    2026, 11, 1, 0, tzinfo=eastern
)

with tempfile.TemporaryDirectory() as directory:
    store = AuditLogStore(Path(directory) / "audit.db")
    store.record("member_join", 100)
    store.record("member_join", 101)
    store.record("automod", 102)
    store.record("message_delete", 200)
    assert store.counts(100, 200) == {
        "member_join": 2,
        "automod": 1,
    }
    assert store.last_report() == 0
    store.mark_reported(200)
    assert AuditLogStore(store.path).last_report() == 200

print("Audit counters, checkpoints, and Eastern weekly boundaries are valid.")
