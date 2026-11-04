"""Offline tests (no game needed). Run: pytest tests/test_offline.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bloons.coords import box_to_pixels, to_norm, to_screen
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


def test_coords():
    bounds, tb = (55.0, 33.0, 1470.0, 830.0), 33   # windowed calibration layout
    assert to_screen(0, 0, bounds, tb) == (55.0, 66.0)          # content starts below the title bar
    assert to_screen(1, 1, bounds, tb) == (1525.0, 863.0)
    x, y = to_screen(0.3, 0.7, bounds, tb)
    assert all(abs(a - b) < 1e-9 for a, b in zip(to_norm(x, y, bounds, tb), (0.3, 0.7)))
    # 2x Retina capture of the same window: title bar is 66 px
    assert box_to_pixels([0, 0, 1, 1], 2940, 1660, 66) == (0, 66, 2940, 1594)
    assert box_to_pixels([0.5, 0.5, 0.75, 1], 2940, 1660, 66) == (1470, 863, 735, 797)


def test_ui_data():
    import json
    ui = json.loads((Path(__file__).resolve().parents[1] / "bloons/data/ui.json").read_text())
    assert ui["_meta"]["game_version"]
    for x0, y0, x1, y1 in ui["hud"].values():
        assert 0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1
    for x, y in ui["buttons"].values():
        assert 0 <= x <= 1 and 0 <= y <= 1


def test_fixture_crops():
    import json
    fix = Path(__file__).resolve().parents[1] / "bloons/data/fixtures"
    crops = json.loads((fix / "crops.json").read_text())["crops"]
    assert len(crops) >= 30
    for name, c in crops.items():
        assert (fix / f"{name}.png").exists(), name
        x0, y0, x1, y1 = c["box"]
        assert 0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1
    assert all("truth" in c for n, c in crops.items() if n.startswith("hud_"))


if __name__ == "__main__":
    test_fixture_crops()
    test_coords()
    test_ui_data()
    test_cost()
    test_upgrade_allowed()
    test_tower_data()
    print("ok")
