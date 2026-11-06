"""The observation: GameState and what it's built from (PLAN Phase 5). Portable, no OS calls.

`BloonsHarness.observe()` fills a GameState from one frame (screen kind, play button, HUD)
plus what the harness knows (registry, hero, ability estimates) and the map data (path,
placeable masks). Fields that later steps fill are None until then:
  ability cooldown_frac from pixels (5.4; until then from the harness's
  estimate), measured ranges (5.5). upgrade_options come from the price table, with
  `checked` from the last panel read (5.3: harness.check_upgrades, and every upgrade()).
  to_vector / grid image are 5.6.
"""
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np

from .placement import Mask, footprint_radius, shape_of

# Footprint radius in game units for each swept mask class (rect classes: larger half-side).
RECT_RADIUS = {"heli": 13.5, "ace": 14.0}


@dataclass(frozen=True)
class TowerState:
    tid: Any
    kind: str
    xy: tuple                       # normalized content coords
    tiers: tuple
    range_units: Optional[float]    # rules.tower_range: None if unknown
    range_exact: bool               # False with two upgraded paths (5.5 measures it)
    range_norm: Optional[tuple]     # (rx, ry): the range circle's radii in normalized coords
    targeting: Optional[str]        # last mode set through the harness (None = game default)
    spent: int
    sell_value: int


@dataclass(frozen=True)
class HeroState:
    name: str
    xy: tuple
    level: int
    xp_into_level: int              # what the harness assumes (0 after a bought level); panel OCR later
    sell_value: int


@dataclass(frozen=True)
class UpgradeOption:
    cost: Optional[int]             # None when there's no next tier
    affordable: bool
    locked: Optional[str]           # None if allowed (money aside), else 'max_tier' / 'crosspath' / 'tier5_taken'
    checked: Optional[bool] = None  # the panel agreed (True) / disagreed (False) at these tiers; None = not read


@dataclass(frozen=True)
class AbilityState:
    slot: int
    name: str
    tid: Any
    ready: bool
    cooldown_frac: float            # 0 = ready, 1 = just used (estimated from the clock until 5.4)
    between_rounds: bool


@dataclass
class GameState:
    t: float                        # harness clock when observed
    screen: str                     # state.Screen kind ('game', 'pause', 'victory', ...)
    map_name: str
    difficulty: str
    mode: str
    # HUD (filtered; None until first read). hud_misses: consecutive unreadable reads per field.
    money: Optional[int]
    lives: Optional[int]
    round: Optional[int]            # the HUD round as read (ambiguous between rounds: use next_round)
    max_round: Optional[int]
    hud_misses: dict
    # round state (state.RoundTracker)
    round_active: bool
    round_ended: bool               # True on exactly one observe per finished round
    fast_forward: Optional[bool]
    outcome: Optional[str]          # None / 'win' / 'loss'
    # what's on the map
    towers: list                    # [TowerState]
    hero: Optional[HeroState]
    upgrade_options: dict           # tid -> [UpgradeOption] * 3
    abilities: list                 # [AbilityState] in bar order
    # map
    path: Optional[np.ndarray]      # (N, 2) centre polyline, normalized
    path_half_width_units: Optional[float]
    unit: tuple                     # normalized size of one game unit (ux, uy)
    placeable: dict                 # mask class -> placement.Mask, minus our towers and the path
    # rounds counted by the harness: finished this game, and the one running / next to start
    rounds_done: int
    next_round: int
    # rounds.json entry for `next_round` (Standard only): groups, counts, rbe, ... or None
    round_composition: Optional[dict]
    bloons: Optional[list] = None   # [detect.Bloon(x, y, kind, count, area, dist)]; None = no background yet
    extra: dict = field(default_factory=dict)


def class_radius(cls):
    """Footprint radius in units for a mask class name ('land_r6' -> 6, 'land_heli' -> 13.5)."""
    key = cls.split("_", 1)[1]
    return float(key[1:]) if key[0] == "r" and key[1:].isdigit() else RECT_RADIUS.get(key, 14.0)


def placeable_masks(masks, unit, placed, keepout, ctx=None):
    """{class: Mask}: the swept map masks minus cells whose footprint would touch the bloon path
    (keepout) or one of `placed` (placement.Placed, sized via `ctx`). The learned-spots memory
    isn't applied here (it's a per-point lookup; can_place uses it)."""
    out = {}
    for cls, m in masks.items():
        g = m.grid
        ii, jj = np.meshgrid(np.arange(g.nx), np.arange(g.ny))
        xs, ys = g.x0 + ii * g.dx, g.y0 + jj * g.dy
        r = class_radius(cls)
        ok = m.ok.copy()
        if keepout is not None:
            ok &= ~(keepout.distances(xs, ys).reshape(ok.shape) < r)
        for p in placed:
            shape = shape_of(p.kind, p.tiers, ctx) if ctx is not None else None
            rt = footprint_radius(shape) if shape else 6
            d = np.hypot((xs - p.xy[0]) / unit[0], (ys - p.xy[1]) / unit[1])
            ok &= ~(d < r + rt)
        out[cls] = Mask(g, ok)
    return out
