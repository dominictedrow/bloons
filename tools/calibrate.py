"""Map calibration tools. PLAN Phase 3.

  python tools/calibrate.py mask <map> <class> <key> [--step 0.01] [--box x0 y0 x1 y1]   (Mac, game running)
  python tools/calibrate.py show <map> <class> <screenshot.png> <out.png>                  (anywhere)

`mask`: hold the tower bound to <key> (e.g. q = Dart for land_r6) and move the cursor over a
grid on the map, classifying the held tower's tint at every cell (bloons/placement.py). The
result goes into data/maps/<map>.json under masks[<class>]. Use an empty map (a fresh
sandbox) with nothing selected and the tower shop showing. Nothing is clicked except the
shop's cancel button at the end. The real cursor moves (HID), so don't use the mouse
meanwhile.

`show`: draw a stored mask over a full-window 2x screenshot (green = placeable, red = not).
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bloons.coords import box_to_pixels                       # noqa: E402
from bloons.placement import Grid, Mask, held_tint, probe_box  # noqa: E402
from bloons.ui import UI                                       # noqa: E402

MAP_BOX = [0.03, 0.0, 0.84, 1.0]     # between the wooden left border (the cursor there drops a held tower) and the shop
SETTLE_S = 0.05                      # tint follows the cursor within ~20 ms


def clip(box):
    return [min(max(v, 0.0), 1.0) for v in box]


def crop_px(full_bgr, frame, box):
    x, y, w, h = box_to_pixels(clip(box), frame.width, frame.height, frame.title_bar_px)
    return full_bgr[y:y + h, x:x + w]


def classify(g, x, y, base, base_frame):
    import Quartz as Q
    from bloons.platform_mac import cgimage_bgr
    f = g.grab()
    if f is None:
        raise RuntimeError("capture failed (screen locked or game window off screen?)")
    box = probe_box(x, y)
    px = box_to_pixels(clip(box), f.width, f.height, f.title_bar_px)
    held = cgimage_bgr(Q.CGImageCreateWithImageInRect(f.image, Q.CGRectMake(*px)))
    cx = x * f.width - px[0]
    cy = f.title_bar_px + y * (f.height - f.title_bar_px) - px[1]
    return held_tint(held, crop_px(base, base_frame, box), (cx, cy))


def sweep(g, grid, key, log_every=200):
    from bloons.platform_mac import cgimage_bgr
    g.move(0.92, 0.5)
    time.sleep(0.3)
    base_frame = g.grab()
    base = cgimage_bgr(base_frame.image)
    g.key(key)
    time.sleep(0.6)
    labels = np.full((grid.ny, grid.nx), "", dtype=object)
    none_run, retries, t0 = 0, 0, time.monotonic()
    for j in range(grid.ny):
        cols = range(grid.nx) if j % 2 == 0 else range(grid.nx - 1, -1, -1)   # serpentine
        for i in cols:
            x, y = grid.centre(i, j)
            if not g.move(x, y):
                raise RuntimeError("game not frontmost")
            time.sleep(SETTLE_S)
            lab = classify(g, x, y, base, base_frame)
            if lab == "none":                 # hold lost (or over UI): pick the tower up again
                g.key(key)
                time.sleep(0.6)
                lab = classify(g, x, y, base, base_frame)
                retries += 1
            labels[j, i] = lab
            none_run = none_run + 1 if lab == "none" else 0
            if none_run > 60:
                raise RuntimeError(f"no held tower for 60 cells (at {x:.3f}, {y:.3f}); did the key register?")
        if (j + 1) % max(1, log_every // grid.nx) == 0:
            done = (j + 1) * grid.nx
            print(f"  {done}/{grid.nx * grid.ny} cells, {time.monotonic() - t0:.0f} s", flush=True)
    g.click(*UI["buttons"]["cancel_placement"])
    print(f"  re-picked the tower {retries} times")
    return labels


def show(a):
    import cv2
    data = json.loads((ROOT / "bloons/data/maps" / f"{a.map}.json").read_text())
    m = Mask.from_json(data["masks"][a.cls])
    img = cv2.imread(a.screenshot)
    tb = round(UI["window"]["title_bar_pt"] * img.shape[1] / UI["window"]["expected_pt"][0])
    h, w = img.shape[0] - tb, img.shape[1]
    over = img.copy()
    g = m.grid
    for j in range(g.ny):
        for i in range(g.nx):
            x, y = g.centre(i, j)
            p0 = (round((x - g.dx / 2) * w), tb + round((y - g.dy / 2) * h))
            p1 = (round((x + g.dx / 2) * w), tb + round((y + g.dy / 2) * h))
            cv2.rectangle(over, p0, p1, (0, 200, 0) if m.ok[j, i] else (0, 0, 230), -1)
    cv2.imwrite(a.out, cv2.addWeighted(over, 0.45, img, 0.55, 0))
    print(f"wrote {a.out}")


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("mask")
    m.add_argument("map")
    m.add_argument("cls", help="footprint class name, e.g. land_r6")
    m.add_argument("key", help="tower hotkey, e.g. q")
    m.add_argument("--step", type=float, default=0.01, help="x step; y step keeps cells square")
    m.add_argument("--box", type=float, nargs=4, default=MAP_BOX)
    m.add_argument("--out", default=None, help="default data/maps/<map>.json")
    sh = sub.add_parser("show")
    sh.add_argument("map")
    sh.add_argument("cls")
    sh.add_argument("screenshot")
    sh.add_argument("out")
    a = ap.parse_args(argv)
    if a.cmd == "show":
        return show(a)

    from bloons.platform_mac import Game
    g = Game()
    w, h = g.bounds[2], g.bounds[3] - g.title_bar_pt
    grid = Grid.over(a.box, a.step, round(a.step * w / h, 5))
    print(f"{a.map} {a.cls}: {grid.nx} x {grid.ny} cells", flush=True)
    t0 = time.monotonic()
    labels = sweep(g, grid, a.key)
    counts = {k: int((labels == k).sum()) for k in ("ok", "blocked", "none")}
    print(f"done in {time.monotonic() - t0:.0f} s: {counts}")

    out = Path(a.out) if a.out else ROOT / "bloons/data/maps" / f"{a.map}.json"
    data = json.loads(out.read_text()) if out.exists() else {"_meta": {}, "masks": {}}
    data["_meta"].update({"map": a.map, "game_version": UI["_meta"]["game_version"],
                          "window_pt": UI["window"]["expected_pt"],
                          "masks": "placeable cell centres per footprint class (bloons/placement.py)"})
    entry = Mask(grid, labels == "ok").to_json()
    entry.update({"tower_key": a.key, "swept": time.strftime("%Y-%m-%d"), "counts": counts})
    data["masks"][a.cls] = entry
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=1) + "\n")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
