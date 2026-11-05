"""Placeable masks (portable): the sweep grid, the held-tower tint classifier, and the mask
format stored in data/maps/<map>.json.

While a tower is held, the game draws it at the cursor with its range circle. On a spot
where it can't go, the sprite gets a red outline and the circle turns red; otherwise the
outline is white and the circle blue-grey. `held_tint()` compares the probe crop with the
same pixels before the tower was picked up and uses two signals:
- the outline, drawn above everything (trees included): new pure-red vs new white pixels.
  Blocked if red > 0.6 x white. Valid spots measured <= 0.21 (Super's red cape), blocked
  >= 1.3 (Heli's white H), across Dart, Bomb, Spike, Super, Heli, Ace, Sub.
- the circle in a ring around the cursor: blocked if its median red-vs-green shift is
  >= 40 (blocked 86-103, valid -3..3). Tree canopies are drawn over the circle and hide
  it (median ~0 there), so this signal alone misses blocked spots under trees.

Masks are a regular grid of cell centres in normalized content coords. `rows[j][i]` is
'1' if a tower of that footprint class can be placed with its centre at (x0 + i*dx,
y0 + j*dy), '0' if not.
"""
from dataclasses import dataclass

import numpy as np

# Around the cursor, normalized half-size (~162 x 159 px at 2x): holds the whole ring.
PROBE_HALF = (0.055, 0.1)
RING_PX = (80, 150)           # at 2x: past most sprites, inside the smallest circle (Heli ~155)
RED_SHIFT_MIN = 40            # median d(R - G) in the ring: blocked 86-103, ok -3..3
OUTLINE_RED_RATIO = 0.6       # new red / new white: ok <= 0.21, blocked >= 1.3
OUTLINE_MIN = 0.005           # new red + white fraction below this = no tower drawn


def is_pure_red(bgr):
    a = bgr.astype(np.int16)
    return (a[..., 2] > 200) & (a[..., 1] < 70) & (a[..., 0] < 70)


def probe_box(x, y):
    hx, hy = PROBE_HALF
    return [x - hx, y - hy, x + hx, y + hy]


def ring_mask(shape, centre, ring=RING_PX):
    h, w = shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    d = np.hypot(xx - centre[0], yy - centre[1])
    return (d >= ring[0]) & (d <= ring[1])


def is_white(bgr):
    return bgr.min(axis=2) > 235


def held_tint(held, base, centre=None):
    """Classify a probe crop (BGR, same region of the frame while holding / before holding)
    around the cursor at pixel `centre` (x, y) in the crop (default: its middle):
    'blocked', 'ok', or 'none' (no tower drawn there, e.g. over UI)."""
    if held.shape != base.shape or held.size == 0:
        return "none"
    if centre is None:
        centre = (held.shape[1] / 2, held.shape[0] / 2)
    red = float((is_pure_red(held) & ~is_pure_red(base)).mean())
    white = float((is_white(held) & ~is_white(base)).mean())
    if red + white < OUTLINE_MIN:
        return "none"
    if red > OUTLINE_RED_RATIO * white:
        return "blocked"
    m = ring_mask(held.shape, centre)
    if m.any():
        d = held.astype(np.int16)[m] - base.astype(np.int16)[m]
        if np.median(d[:, 2] - d[:, 1]) >= RED_SHIFT_MIN:
            return "blocked"
    return "ok"


@dataclass(frozen=True)
class Grid:
    x0: float
    y0: float
    dx: float
    dy: float
    nx: int
    ny: int

    @classmethod
    def over(cls, box, dx, dy):
        """Cell centres covering box [x0, y0, x1, y1], half a step in from each edge."""
        x0, y0, x1, y1 = box
        nx, ny = int((x1 - x0) / dx + 1e-9), int((y1 - y0) / dy + 1e-9)
        return cls(round(x0 + dx / 2, 5), round(y0 + dy / 2, 5), dx, dy, nx, ny)

    def centre(self, i, j):
        return self.x0 + i * self.dx, self.y0 + j * self.dy

    def cell(self, x, y):
        """Nearest cell (i, j) to a normalized point, or None outside the grid."""
        i, j = round((x - self.x0) / self.dx), round((y - self.y0) / self.dy)
        return (i, j) if 0 <= i < self.nx and 0 <= j < self.ny else None

    def to_json(self):
        return {"x0": self.x0, "y0": self.y0, "dx": self.dx, "dy": self.dy, "nx": self.nx, "ny": self.ny}


@dataclass
class Mask:
    grid: Grid
    ok: np.ndarray            # bool, shape (ny, nx)

    def placeable(self, x, y):
        c = self.grid.cell(x, y)
        return bool(c and self.ok[c[1], c[0]])

    def to_json(self):
        return {"grid": self.grid.to_json(), "rows": ["".join("1" if v else "0" for v in r) for r in self.ok]}

    @classmethod
    def from_json(cls, d):
        g = Grid(**d["grid"])
        ok = np.array([[c == "1" for c in r] for r in d["rows"]], dtype=bool)
        assert ok.shape == (g.ny, g.nx)
        return cls(g, ok)


# --- which mask a tower uses -----------------------------------------------------------------
# Rect footprints have their own swept classes. Banana Farm and Skywarden have no footprint in
# towers.json yet (no wiki dump): assumed, to be measured.
RECT_CLASSES = {(27, 27): "heli", (28, 18): "ace"}
ASSUMED = {"banana_farm": {"placement": {"land": True, "water": False}, "footprint": {"radius": 11}},
           "skywarden": {"placement": {"land": True, "water": False}, "footprint": {"radius": 8}}}


def mask_classes(name, shape):
    """Mask class names a tower can use, e.g. ['land_r6'] or ['land_r6', 'water_r6'] (Ice).
    `shape` is rules.tower_shape(tower, tiers), or None for towers without stats."""
    shape = shape or ASSUMED.get(name)
    if shape is None:
        raise KeyError(f"no footprint for {name}")
    fp = shape["footprint"]
    if "radius" in fp:
        key = f"r{fp['radius']}"
    else:
        key = RECT_CLASSES.get(tuple(fp["rect"]), "rect{}x{}".format(*fp["rect"]))
    return [f"{kind}_{key}" for kind in ("land", "water") if shape["placement"][kind]]


def placeable(masks, classes, x, y):
    """Is (x, y) a valid centre for any of `classes`, given a map's {class: Mask}? A land class
    the map lacks falls back to the next larger swept land radius (conservative); a missing
    water class counts as no water on the map."""
    for c in classes:
        m = masks.get(c) or (_larger_land(masks, c) if c.startswith("land_") else None)
        if m is not None and m.placeable(x, y):
            return True
    return False


def _larger_land(masks, cls):
    radii = sorted(int(k[6:]) for k in masks if k.startswith("land_r") and k[6:].isdigit())
    want = int(cls[6:]) if cls[6:].isdigit() else 99
    bigger = [r for r in radii if r >= want]
    return masks[f"land_r{bigger[0]}"] if bigger else None


def load_masks(map_json):
    """{class: Mask} from a data/maps/<map>.json dict."""
    return {c: Mask.from_json(d) for c, d in map_json["masks"].items()}
