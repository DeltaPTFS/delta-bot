"""Regression checks for durable economy balances and atomic transfers."""

from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bot"))

from economy import EconomyStore  # noqa: E402


with tempfile.TemporaryDirectory() as directory:
    path = Path(directory) / "economy.db"
    store = EconomyStore(path)
    reward, remaining = store.claim(1, "daily", 86_400, 250, 250)
    assert (reward, remaining) == (250, 0)
    assert store.claim(1, "daily", 86_400, 250, 250)[0] == 0
    assert store.balance(1) == 250
    assert store.transfer(1, 2, 100)
    assert (store.balance(1), store.balance(2)) == (150, 100)
    assert not store.transfer(2, 1, 101)
    assert not store.transfer(1, 1, 1)
    assert store.leaderboard() == [(1, 150), (2, 100)]

    reopened = EconomyStore(path)
    assert (reopened.balance(1), reopened.balance(2)) == (150, 100)

print("Economy persistence, cooldowns, transfers, and ranking are valid.")
