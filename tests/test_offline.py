"""Offline tests (no game needed). Run: pytest tests/test_offline.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bloons.coords import box_to_pixels, to_norm, to_screen
from bloons.hud import Hud, HudFilter, parse_hud, parse_lives, parse_money, parse_round
from bloons.rules import cost, tower_abilities, tower_range, tower_shape, upgrade_allowed


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


def _hud_truth():
    """(name, field, raw OCR text, truth) for every hud_* fixture crop."""
    import json
    crops = json.loads((Path(__file__).resolve().parents[1] / "bloons/data/fixtures/crops.json").read_text())["crops"]
    return [(n, n.rsplit("_", 1)[1], c["ocr"], c["truth"]) for n, c in crops.items() if n.startswith("hud_")]


PARSERS = {"lives": parse_lives, "money": parse_money, "round": lambda t: list(parse_round(t) or ())}


def test_hud_parse_fixtures():
    """Recorded Vision output of each committed HUD crop parses to its truth value."""
    rows = _hud_truth()
    assert len(rows) >= 18
    for name, field, raw, truth in rows:
        assert PARSERS[field](raw) == truth, (name, raw)


def test_hud_parse_edge_cases():
    # junk from the 'ROUND' label (Latin and Cyrillic look-alikes) is ignored
    assert parse_round("KOMID 1/40") == (1, 40)
    assert parse_round("\u041a\u041e\u041c\u041f\u0412 30/40") == (30, 40)
    # upgrade panel open: HUD shifted, boxes clip it (upgrade_panel_left/right.png)
    assert parse_money("20") is None
    assert parse_round("TINYN") is None
    # nothing read (defeat screen lives box, menus)
    assert parse_lives("") is None and parse_money("") is None and parse_round("") is None
    assert parse_hud({}) == Hud()
    # thousands separators must be well-formed
    assert parse_money("$12,345,678") == 12345678
    assert parse_money("$1,35") is None and parse_money("$13,57") is None
    # digit confusables, only inside numeric-looking tokens
    assert parse_lives("2OO") == 200 and parse_lives("l89") == 189
    assert parse_money("$1,3S7") == 1357
    assert parse_lives("ROUND") is None
    # impossible values
    assert parse_round("41/40") is None and parse_round("0/40") is None
    assert parse_lives("12345") is None
    # two different candidates in one box is ambiguous
    assert parse_lives("200 189") is None and parse_lives("200 200") == 200
    full = parse_hud({"lives": "189", "money": "$1,630", "round": "39/40"})
    assert full == Hud(189, 1630, 39, 40) and full.complete
    assert not Hud(189, None, 39, 40).complete


def test_hud_filter():
    f = HudFilter(confirm=2)
    assert f.update(Hud(200, 650, 1, 40)) == Hud(200, 650, 1, 40)   # first reading taken as is
    assert f.update(Hud(200, 65, 1, 40)).money == 650                # one-off misread held back
    assert f.update(Hud(200, 650, 1, 40)).money == 650
    assert f.update(Hud(200, 480, 1, 40)).money == 650               # real change: needs a 2nd read
    assert f.update(Hud(200, 480, 1, 40)).money == 480
    assert f.update(Hud(None, None, None, None)) == Hud(200, 480, 1, 40)   # unreadable: keep values
    assert f.misses == {"lives": 1, "money": 1, "round": 1, "rounds_total": 1}
    f.update(Hud(200, 480, 2, 40))
    assert f.misses["round"] == 0 and f.current.round == 1
    f.update(Hud(200, 480, 3, 40))                                   # different candidate restarts the count
    assert f.current.round == 1
    assert f.update(Hud(200, 480, 3, 40)).round == 3
    f.reset()
    assert f.current == Hud() and f.update(Hud(200, 650, 1, 40)).round == 1
    assert HudFilter(confirm=1).update(Hud(1, 2, 3, 4)) == Hud(1, 2, 3, 4)


def test_hud_filter_money_income():
    """Live bug (step 1.5): money rising every read must not freeze the filter."""
    f = HudFilter()
    f.update(Hud(200, 356, 4, 40))
    seq = [241, 244, 247, 250, 253, 256]          # spent $115, then pop income each read
    out = [f.update(Hud(200, m, 4, 40)).money for m in seq]
    assert out == [356, 244, 247, 250, 253, 256]  # one read of lag, then tracks
    # a dropped digit is still held back, and accepted only if it repeats
    f = HudFilter()
    f.update(Hud(money=1357))
    assert f.update(Hud(money=357)).money == 1357
    assert f.update(Hud(money=1360)).money == 1357   # disagrees with 357: restart count
    assert f.update(Hud(money=1362)).money == 1362
    assert f.update(Hud(money=357)).money == 1362
    assert f.update(Hud(money=357)).money == 357     # repeated: genuinely spent
    # lives / round still need exact agreement
    f = HudFilter()
    f.update(Hud(lives=200))
    assert f.update(Hud(lives=199)).lives == 200 and f.update(Hud(lives=198)).lives == 200


def test_hud_ocr_live():
    """Mac only: run Vision on the committed crops and parse (skipped elsewhere)."""
    try:
        from bloons.platform_mac import load_png, ocr_image
    except ImportError:
        print("skip test_hud_ocr_live: not on macOS")
        return
    fix = Path(__file__).resolve().parents[1] / "bloons/data/fixtures"
    for name, field, _, truth in _hud_truth():
        raw = ocr_image(load_png(fix / f"{name}.png"))
        assert PARSERS[field](raw) == truth, (name, raw)


FIX = Path(__file__).resolve().parents[1] / "bloons/data/fixtures"


def _frames():
    import json
    import cv2
    man = json.loads((FIX / "frames.json").read_text())["frames"]
    return [(stem, f, cv2.imread(str(FIX / "frames" / f"{stem}.jpg"))) for stem, f in man.items()]


def test_vision_spec():
    from bloons.vision import SPEC, Templates
    t = Templates()
    for name, s in SPEC["templates"].items():
        x0, y0, x1, y1 = s["box"]
        assert 0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1, name
        assert 0.5 <= s["threshold"] < 1, name
        assert t.image(name).size > 0
    for p in SPEC["probes"].values():
        assert p["classes"] and p["max_dist"] > 0


def test_vision_templates():
    """Every frame: listed templates match, all others (except 'ignore') don't."""
    from bloons.vision import Templates
    t = Templates()
    frames = _frames()
    assert len(frames) >= 17
    for stem, f, img in frames:
        assert img is not None, stem
        for name, m in t.match_all(img).items():
            if name in f.get("ignore", []):
                continue
            assert m.found == (name in f["present"]), (stem, name, round(m.score, 3))


def test_vision_button_state():
    from bloons.vision import Templates
    t = Templates()
    for stem, f, img in _frames():
        assert t.button_state(img) == f["button"], stem


def test_vision_match_location():
    from bloons.vision import Templates
    t = Templates()
    for stem, f, img in _frames():
        if "sell_side" in f:   # one sell template finds the panel on either side
            x, _ = t.match(img, "sell_button").center
            assert ("left" if x < 0.5 else "right") == f["sell_side"], stem
    stem, f, img = next(r for r in _frames() if r[0] == "victory_monkey_meadow_easy")
    x, y = t.match(img, "victory_next").center   # ~ where to click Next (RESEARCH: 0.50, 0.84)
    assert abs(x - 0.50) < 0.01 and abs(y - 0.84) < 0.01


def test_frame_bgr_mac():
    """Mac only: Quartz -> numpy conversion gives OpenCV's BGR layout (skipped elsewhere)."""
    try:
        from bloons.platform_mac import cgimage_bgr, load_png
    except ImportError:
        print("skip test_frame_bgr_mac: not on macOS")
        return
    import cv2
    import numpy as np
    for name in ("btn_ff_on", "victory_banner"):
        a = cgimage_bgr(load_png(FIX / f"{name}.png"))
        b = cv2.imread(str(FIX / f"{name}.png"))
        assert a.shape == b.shape and np.abs(a.astype(int) - b).max() <= 1, name


def test_read_screen():
    from bloons.state import read_screen
    for stem, f, img in _frames():
        sc = read_screen(img)
        assert sc.kind == f["screen"], (stem, sc.kind)
        assert sc.button == f["button"], stem
        assert sc.panel == f.get("sell_side"), stem


def test_read_screen_bright_button():
    """Live (step 1.5): the FF button glowing brighter than any probe class (hover?) is
    still a game frame, with button None, and the tracker keeps its state."""
    import numpy as np
    from bloons.state import RoundTracker, read_screen
    from bloons.vision import box_px, SPEC
    _, _, orig = next(r for r in _frames() if r[0] == "hud_r05")
    img = orig.copy()
    x0, y0, x1, y1 = box_px(SPEC["templates"]["btn_ff"]["box"], img)
    btn = img[y0:y1, x0:x1].astype(int)
    img[y0:y1, x0:x1] = np.clip(btn + (33, 5, 20), 0, 255).astype(np.uint8)   # (76,236,152) -> (109,241,172)
    sc = read_screen(img)
    assert sc.kind == "game" and sc.button is None
    t = RoundTracker(confirm=1)
    assert t.update(read_screen(orig)).round_active is True
    assert t.update(sc).round_active is True and t.current.fast_forward is True


def _feed(tracker, seq):
    """seq of (kind, button, round) -> list of RoundState."""
    from bloons.hud import Hud
    from bloons.state import Screen
    return [tracker.update(Screen(k, b), Hud(round=r, rounds_total=40 if r else None)) for k, b, r in seq]


def test_round_tracker_manual_start():
    from bloons.state import RoundTracker
    t = RoundTracker(auto_start=False, confirm=2)
    out = _feed(t, [("game", "idle", 1), ("game", "idle", 1),
                    ("game", "ff_on", 1), ("game", "ff_on", 1), ("game", "ff_on", 1),
                    ("game", "idle", 1),                     # one-off misread: ignored
                    ("game", "ff_on", 1),
                    ("pause", None, 1), ("game", "ff_on", 1),  # pause keeps the state
                    ("game", "idle", 2), ("game", "idle", 2), ("game", "idle", 2),
                    ("game", "ff_off", 2), ("game", "ff_off", 2)])
    assert [s.round_active for s in out] == [False, False, False, True, True, True, True, True, True,
                                             True, False, False, False, True]
    assert [i for i, s in enumerate(out) if s.round_ended] == [10]   # exactly once, round 1
    assert out[4].fast_forward is True and out[13].fast_forward is False
    assert out[7].screen == "pause" and out[7].round_active is True
    assert all(s.outcome is None for s in out)


def test_round_tracker_auto_start():
    from bloons.state import RoundTracker
    t = RoundTracker(auto_start=True)
    out = _feed(t, [("game", "idle", 1), ("game", "ff_on", 1), ("game", "ff_on", 1),
                    ("game", "ff_on", 1), ("game", "ff_on", 2), ("game", "ff_on", 2),
                    ("game", None, 2), ("game", "ff_on", 3)])
    assert [i for i, s in enumerate(out) if s.round_ended] == [4, 7]
    assert out[-1].round == 3 and out[-1].rounds_total == 40


def test_round_tracker_outcome():
    from bloons.state import RoundTracker
    t = RoundTracker()
    out = _feed(t, [("game", "ff_on", 40), ("game", "ff_on", 40),
                    ("victory", None, 40),                   # needs a second frame
                    ("victory", None, 40), ("unknown", None, None), ("map_select", None, None)])
    assert [s.outcome for s in out] == [None, None, None, "win", "win", "win"]
    assert out[3].round_active is False and not any(s.round_ended for s in out)
    t.reset()
    out = _feed(t, [("game", "ff_on", 13), ("defeat", None, 13), ("defeat", None, 13),
                    ("restart_confirm", None, None), ("defeat", None, 13)])
    assert [s.outcome for s in out] == [None, None, "loss", "loss", "loss"]
    t.reset()
    assert t.current is None and _feed(t, [("game", "idle", 1)])[0].outcome is None


def test_round_tracker_on_frames():
    """Real frames end to end: idle -> ff_off -> ff_on -> victory."""
    from bloons.hud import Hud
    from bloons.state import RoundTracker, read_screen
    frames = {stem: img for stem, _, img in _frames()}
    t = RoundTracker(confirm=1)
    seq = ["hud_r1_idle_play_button", "hud_r1_running_ff_off", "hud_r1_running_ff_on",
           "pause_menu", "hud_r39", "victory_monkey_meadow_easy"]
    out = [t.update(read_screen(frames[s]), Hud()) for s in seq]
    assert [s.round_active for s in out] == [False, True, True, True, True, False]
    assert [s.fast_forward for s in out] == [False, False, True, True, True, None]
    assert out[-1].outcome == "win"


def _towers():
    import json
    return json.loads((Path(__file__).resolve().parents[1] / "bloons/data/towers.json").read_text())["towers"]


def test_tower_stats_data():
    towers = _towers()
    missing = {k for k, t in towers.items() if t["stats"] is None}
    assert missing == {"banana_farm", "skywarden"}   # no wiki dump: measure in game
    for k, t in towers.items():
        st = t["stats"]
        if st is None:
            continue
        assert st["placement"]["land"] or st["placement"]["water"], k
        fp = st["footprint"]
        assert ("radius" in fp and fp["radius"] > 0) or ("rect" in fp and min(fp["rect"]) > 0), k
        assert st["range"] > 0 and len(st["range_by_tier"]) == 3 and all(len(p) == 5 for p in st["range_by_tier"]), k
        for a in st["abilities"] or []:
            assert 0 <= a["path"] <= 2 and 1 <= a["tier"] <= 5 and a["cooldown"] > 0 and a["name"], (k, a)
    # spot checks against the game
    d = towers["dart_monkey"]["stats"]
    assert (d["range"], d["footprint"], d["placement"]) == (32, {"radius": 6}, {"land": True, "water": False})
    assert towers["monkey_sub"]["stats"]["placement"] == {"land": False, "water": True}
    assert towers["monkey_buccaneer"]["stats"]["placement"] == {"land": False, "water": True}
    assert "rect" in towers["heli_pilot"]["stats"]["footprint"] and "rect" in towers["monkey_ace"]["stats"]["footprint"]
    assert "patrol_points" in towers["heli_pilot"]["stats"]["targeting"]
    assert towers["monkey_village"]["stats"]["footprint"] == {"radius": 11}


def test_tower_range():
    t = _towers()
    dart = t["dart_monkey"]
    assert tower_range(dart, (0, 0, 0)) == (32, True)
    assert tower_range(dart, (0, 0, 2)) == (48, True)      # Enhanced Eyesight
    assert tower_range(dart, (3, 0, 0)) == (36.8, True)    # Spike-o-pult x1.15
    assert tower_range(dart, (3, 0, 2)) == (52.8, False)   # crosspath: estimate
    assert tower_range(t["banana_farm"], (0, 0, 0)) == (None, False)
    assert tower_range(t["monkey_village"], (1, 0, 0)) == (48, True)
    assert tower_range(t["monkey_village"], (0, 1, 0)) == (None, False)   # not on the wiki


def test_tower_abilities_and_shape():
    t = _towers()
    dart, sup = t["dart_monkey"], t["super_monkey"]
    assert [a["name"] for a in tower_abilities(dart, (0, 4, 0))] == ["Super Monkey Fan Club"]
    assert [a["name"] for a in tower_abilities(dart, (2, 5, 0))] == ["Plasma Monkey Fan Club"]
    assert tower_abilities(dart, (2, 0, 3)) == []
    assert tower_abilities(t["banana_farm"], (0, 0, 0)) is None
    heli = [a["name"] for a in tower_abilities(t["heli_pilot"], (0, 5, 0))]
    assert "Support Drop" in heli and len(heli) == 3
    assert tower_shape(sup, (0, 0, 0))["footprint"] == {"radius": 11}
    sun = tower_shape(sup, (4, 0, 2))                        # Sun Temple: bigger, can go on water
    assert sun["footprint"] == {"rect": [37, 40]} and sun["placement"]["water"]
    assert "strong" in tower_shape(t["ice_monkey"], (0, 0, 3))["targeting"]
    assert tower_shape(t["ice_monkey"], (0, 0, 0))["targeting"] == ["close"]


if __name__ == "__main__":
    test_fixture_crops()
    test_coords()
    test_ui_data()
    test_cost()
    test_upgrade_allowed()
    test_tower_data()
    test_tower_stats_data()
    test_tower_range()
    test_tower_abilities_and_shape()
    test_hud_parse_fixtures()
    test_hud_parse_edge_cases()
    test_hud_filter()
    test_hud_filter_money_income()
    test_hud_ocr_live()
    test_vision_spec()
    test_vision_templates()
    test_vision_button_state()
    test_vision_match_location()
    test_frame_bgr_mac()
    test_read_screen()
    test_read_screen_bright_button()
    test_round_tracker_manual_start()
    test_round_tracker_auto_start()
    test_round_tracker_outcome()
    test_round_tracker_on_frames()
    print("ok")
