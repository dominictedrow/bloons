"""Offline tests (no game needed). Run: pytest tests/test_offline.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bloons.rules import cost, upgrade_allowed


def test_cost():
    # Dart Monkey base $200
    assert [cost(200, d) for d in ("easy", "medium", "hard", "impoppable")] == [170, 200, 215, 240]
    assert cost(220, "easy") == 185  # 187 -> 185
    assert cost(140, "easy") == 120  # 119 -> 120
    assert cost(50, "easy") == 40    # 42.5 tie -> even multiple
    assert cost(150, "easy") == 130  # 127.5 tie -> even multiple


def test_tower_data():
    import json
    towers = json.loads((Path(__file__).resolve().parents[1] / "bloons/data/towers.json").read_text())["towers"]
    assert towers["dart_monkey"]["cost"] == 200
    for t in towers.values():
        assert len(t["upgrades"]) == 3 and all(len(p) == 5 and all(u["cost"] > 0 for u in p) for p in t["upgrades"])


def test_upgrade_allowed():
    assert upgrade_allowed((0, 0, 0), 0)
    assert upgrade_allowed((4, 2, 0), 0)       # -> 5-2-0
    assert not upgrade_allowed((5, 0, 0), 0)   # past tier 5
    assert not upgrade_allowed((2, 2, 0), 2)   # third path
    assert not upgrade_allowed((3, 2, 0), 1)   # second path past 2
    assert upgrade_allowed((2, 2, 0), 0)       # -> 3-2-0


if __name__ == "__main__":
    test_cost()
    test_upgrade_allowed()
    test_tower_data()
    print("ok")
