"""Offline tests (no game needed). Run: pytest tests/test_offline.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bloons.coords import box_to_pixels, to_norm, to_screen
from bloons.hud import Hud, HudFilter, parse_hud, parse_lives, parse_money, parse_round
from bloons.rules import (cost, hero_abilities, hero_level_cost, hero_range, hero_xp_for_round, hero_xp_to_reach,
                          tower_abilities, tower_range, tower_shape, upgrade_allowed)


# (base $, Easy price seen in game) - step 2.5, Monkey Meadow Easy sandbox, game 57.4
EASY_PRICES_SEEN = [
    (200, 170), (375, 320), (260, 220), (400, 340), (225, 190), (300, 255), (350, 300), (325, 275),
    (800, 680), (1200, 1020),                                              # shop (+ hero)
    (140, 120), (200, 170), (320, 275), (1800, 1530), (15000, 12750), (100, 85), (190, 160), (90, 75),
    (280, 240), (600, 510), (2000, 1700), (175, 150), (300, 255),          # dart, boomerang
    (225, 190), (550, 470), (2700, 2295), (150, 130), (220, 190),          # tack
    (500, 425), (250, 215), (450, 385), (220, 190), (200, 170),            # engineer, bomb
]


def test_cost():
    for base, seen in EASY_PRICES_SEEN:
        assert cost(base, "easy") == seen, (base, seen)
    assert [cost(200, d) for d in ("easy", "medium", "hard", "impoppable")] == [170, 200, 215, 240]
    assert cost(320, "easy") == 275 and cost(220, "easy") == 190   # x20 bases round up (wiki: down)
    assert cost(250, "easy") == 215 and cost(450, "easy") == 385   # ties round up (wiki: to even)
    assert cost(315, "easy") - 50 == 220                            # Boomerang after MK "Cheap 'Rangs"


# Easy shop prices seen in game (3.1, all 26 towers + hero, Dom's Monkey Knowledge active)
EASY_SHOP_SEEN = {
    "dart_monkey": 170, "boomerang_monkey": 220, "bomb_shooter": 320, "tack_shooter": 220, "ice_monkey": 340,
    "glue_gunner": 190, "desperado": 255, "sniper_monkey": 300, "monkey_sub": 275, "monkey_buccaneer": 340,
    "monkey_ace": 680, "heli_pilot": 1275, "mortar_monkey": 510, "dartling_gunner": 720, "wizard_monkey": 210,
    "super_monkey": 2125, "ninja_monkey": 340, "alchemist": 470, "druid": 340, "mermonkey": 255,
    "skywarden": 175, "banana_farm": 945, "spike_factory": 700, "monkey_village": 1000,
    "engineer_monkey": 300, "beast_handler": 210,
}


def test_shop_prices():
    import json
    from bloons.rules import shop_price, upgrade_price
    root = Path(__file__).resolve().parents[1] / "bloons/data"
    towers = json.loads((root / "towers.json").read_text())["towers"]
    acc = json.loads((root / "account.json").read_text())
    assert set(EASY_SHOP_SEEN) == set(towers)
    for name, seen in EASY_SHOP_SEEN.items():
        assert shop_price(name, towers[name]["cost"], "easy", acc) == seen, (name, seen)
    assert cost(1200, "easy", "tower") == 1020                                    # hero
    assert cost(250, "easy", "tower") == 210 and cost(250, "easy") == 215         # tie: tower even, upgrade up
    # first-only discounts drop off for the 2nd Farm / Spike Factory
    assert shop_price("spike_factory", 1000, "easy", acc, first=False) == 850
    assert shop_price("banana_farm", 1250, "easy", acc, first=False) == 1040      # 1062.5 x 0.98 = 1041.25
    assert shop_price("dart_monkey", 200, "easy") == 170                           # no account
    # MK upgrade discounts (read off the tree, not yet checked in game)
    assert upgrade_price("ninja_monkey", 0, 3, 900, "medium", acc) == 800
    assert upgrade_price("ninja_monkey", 0, 2, 350, "medium", acc) == 350


def test_account_data():
    import json
    acc = json.loads((Path(__file__).resolve().parents[1] / "bloons/data/account.json").read_text())
    assert acc["_meta"]["game_version"]
    mk = acc["monkey_knowledge"]
    assert mk["cheap_rangs"]["active"] and mk["scholarships"]["training_discount"] == 0.1
    assert all("active" in v and v["evidence"] for v in mk.values())


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
    def points(v):   # every [x, y] point / [x0, y0, x1, y1] box anywhere in a section
        if isinstance(v, dict):
            return [p for k, x in v.items() if not k.startswith("_") for p in points(x)]
        if isinstance(v, list) and v and isinstance(v[0], (int, float)):
            return [v] if len(v) in (2, 4) else []
        return [p for x in v for p in points(x)] if isinstance(v, list) else []
    for sec in ("buttons", "upgrade_panel", "ability_bar", "pause", "menus"):
        pts = points(ui[sec])
        assert pts, sec
        for p in pts:
            assert all(0 <= c <= 1 for c in p), (sec, p)
            if len(p) == 4:
                assert p[0] < p[2] and p[1] < p[3], (sec, p)


UI_FIX = Path(__file__).resolve().parents[1] / "bloons/data/fixtures/ui"


def test_ui_shop():
    import json
    import cv2
    from bloons.ui import UI, shop_cell
    towers = json.loads((Path(__file__).resolve().parents[1] / "bloons/data/towers.json").read_text())["towers"]
    order = UI["shop"]["order"]
    assert len(order) == len(set(order)) and set(order) == set(towers) | {"hero"}
    # towers without a hotkey must be clickable in one of the two scroll layouts
    assert shop_cell("desperado")[0] == "top"
    assert {shop_cell(n)[0] for n in ("mermonkey", "skywarden")} == {"bottom"}
    for n, t in towers.items():
        if t["hotkey"] is None:
            shop_cell(n)
    lay, (x, y) = shop_cell("dart_monkey")
    assert lay == "top" and abs(x - 0.935) < 1e-9 and abs(y - 0.2077) < 1e-9
    # scrolled-bottom frame: magic rows (8-10) have purple cells, support rows (11-13) orange
    img = cv2.imread(str(UI_FIX / "shop_scrolled_bottom.jpg")).astype(int)
    h, w = img.shape[:2]
    cw, ch = UI["shop"]["cell_size"]
    for n in order[16:]:
        lay, (x, y) = shop_cell(n)
        c = img[int((y - ch / 2) * h):int((y + ch / 2) * h), int((x - cw / 2) * w):int((x + cw / 2) * w)]
        b, g, r = c[..., 0], c[..., 1], c[..., 2]
        purple = ((b > 200) & (r > 130) & (g < 180)).mean()
        orange = ((r > 220) & (b < 170) & (g > 120) & (g < 225)).mean()
        magic = order.index(n) < 22
        assert lay == "bottom" and (purple if magic else orange) > 0.25 and (orange if magic else purple) < 0.1, \
            (n, purple, orange)


def test_ui_panel():
    import cv2
    from bloons.state import read_screen
    from bloons.ui import UI, ability_slot, panel
    from bloons.vision import Templates
    t = Templates()
    dx = UI["upgrade_panel"]["dx"]
    R, L = panel("right"), panel("left")
    assert abs(R["sell"][0] - L["sell"][0] - dx) < 1e-6 and R["path_buttons"][1][1] == L["path_buttons"][1][1]
    frames = [(s, f["sell_side"], img) for s, f, img in _frames() if "sell_side" in f]
    frames += [(n, side, cv2.imread(str(UI_FIX / f"{n}.jpg"))) for n, side in
               (("panel_left_ability_boomerang_040", "left"), ("hero_panel_right_benjamin_l3", "right"))]
    for stem, side, img in frames:
        assert read_screen(img).panel == side, stem
        x, y = t.match(img, "sell_button").center
        sx, sy = panel(side)["sell"]
        assert abs(x - sx) < 0.005 and abs(y - sy) < 0.005, stem
    # ability bar: 2 slots in this frame, nothing at a 3rd slot (plain grass there)
    img = cv2.imread(str(UI_FIX / "ability_bar_two_slots.jpg"))
    h, w = img.shape[:2]
    def dark_frac(i):   # icons have dark outlines; grass has none
        x, y = ability_slot(i)
        patch = img[int((y - 0.03) * h):int((y + 0.02) * h), int((x - 0.02) * w):int((x + 0.02) * w)]
        return float((patch.max(axis=2) < 70).mean())
    assert dark_frac(0) > 0.04 and dark_frac(1) > 0.04 and dark_frac(2) < 0.01, [dark_frac(i) for i in range(3)]
    assert ability_slot(0, "left")[0] > ability_slot(0)[0] + 0.2


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
    assert parse_money("$9.999.609") == 9999609 and parse_money("$1.020") == 1020   # seen in game
    assert parse_money("$1.5") is None
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


def _heroes():
    import json
    return json.loads((Path(__file__).resolve().parents[1] / "bloons/data/heroes.json").read_text())["heroes"]


def test_hero_data():
    heroes = _heroes()
    assert len(heroes) >= 18
    for k, h in heroes.items():
        assert len(h["level_xp"]) == 19 and all(x > 0 for x in h["level_xp"]), k
        assert len(h["levels"]) == 20 and all(h["levels"]), k
        if h["stats"]:
            assert len(h["stats"]["range_by_level"]) == 20 and h["stats"]["footprint"], k
    assert {k for k, h in heroes.items() if h["stats"]} >= {"quincy", "adora", "gwendolin", "sauda", "striker_jones"}
    assert heroes["quincy"]["level_xp"][:4] == [180, 460, 1000, 1860]       # xp_scale 1
    assert heroes["benjamin"]["level_xp"][:2] == [270, 690]                  # xp_scale 1.5
    assert heroes["benjamin"]["levels"][2].startswith("Biohack")             # level 3


def test_hero_rules():
    h = _heroes()
    q = h["quincy"]
    assert [hero_xp_for_round(r) for r in (1, 20, 21, 50, 51)] == [40, 420, 460, 1620, 1710]
    assert hero_xp_to_reach(q, 1) == 0 and hero_xp_to_reach(q, 3) == 640   # = the module's xpLv3
    assert hero_level_cost(q, 1) == 180 and hero_level_cost(q, 1, 100) == 80 and hero_level_cost(q, 20) is None
    assert hero_level_cost(h["benjamin"], 1, training_discount=0.1) == 243   # seen in game (Scholarships)
    assert hero_abilities(q, 2) == []
    assert hero_abilities(q, 3) == [{"name": "Rapid Shot", "level": 3, "cooldown": 60}]
    late = {a["name"]: a["cooldown"] for a in hero_abilities(q, 20)}
    assert late == {"Rapid Shot": 45, "Storm of Arrows": 55}
    assert hero_range(q, 1) == 50 and hero_range(q, 20) == 54
    assert hero_abilities(h["benjamin"], 10) is None and hero_range(h["benjamin"], 1) is None


def test_rounds_data():
    """rounds.json: RBE / cash / duration were checked against the wiki's own rendered table
    for all 140 rounds when generated (2026-11-04); these pin a few of those values."""
    import json
    r = json.loads((Path(__file__).resolve().parents[1] / "bloons/data/rounds.json").read_text())["rounds"]
    assert [x["round"] for x in r] == list(range(1, 141))
    for x in r:
        assert x["groups"] and x["duration"] > 0 and x["rbe"] > 0, x["round"]
        assert sum(x["counts"].values()) == sum(g["count"] for g in x["groups"]), x["round"]
        # game data has a few slightly negative starts (round 86: -0.15 s)
        assert all(-1 < g["start"] <= g["end"] <= x["duration"] + 1e-6 for g in x["groups"]), x["round"]
        assert x["end_bonus"] == 100 + x["round"]
    assert (r[0]["rbe"], r[0]["pop_cash"], r[0]["counts"]) == (20, 20, {"red": 20})
    assert r[39]["counts"] == {"moab": 1} and r[39]["rbe"] == 616
    assert r[79]["counts"] == {"zomg": 1} and r[62]["rbe"] == 14413
    assert sum(x["rbe"] for x in r[:40]) == 12289                   # wiki's running total at 40
    first = {f: next(x["round"] for x in r if x["has"][f]) for f in ("regrow", "camo", "lead", "moab_class")}
    assert first == {"regrow": 17, "camo": 24, "lead": 28, "moab_class": 40}
    assert r[49]["income_multiplier"] == 1 and r[50]["income_multiplier"] == 0.5
    ddt = [g for x in r for g in x["groups"] if g["type"] == "ddt"]
    assert ddt and all(g["camo"] for g in ddt)                     # DDTs are always camo


if __name__ == "__main__":
    test_fixture_crops()
    test_coords()
    test_ui_data()
    test_cost()
    test_account_data()
    test_upgrade_allowed()
    test_tower_data()
    test_tower_stats_data()
    test_tower_range()
    test_tower_abilities_and_shape()
    test_hero_data()
    test_hero_rules()
    test_rounds_data()
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
