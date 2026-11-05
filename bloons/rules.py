"""Pure game rules: difficulty pricing and the upgrade crosspath rule (RESEARCH.md)."""

DIFFICULTY_MULT = {"easy": 0.85, "medium": 1.0, "hard": 1.08, "impoppable": 1.2}


def cost(base, difficulty):
    """Base price scaled by difficulty, rounded to the nearest $5, ties to the even multiple.

    Matches the Bloons Wiki's Module:BTD6_costs (identical for every $5 base up to $100k).
    """
    return round(base * DIFFICULTY_MULT[difficulty] / 5) * 5


def upgrade_allowed(tiers, path):
    """Can a tower at `tiers` (e.g. (2, 0, 3)) buy the next tier on `path` (0-2)?

    At most 2 paths upgraded, and only one of them past tier 2.
    Per-map "one tier-5 per path per tower type" is the harness's job, not this function's.
    """
    new = list(tiers)
    new[path] += 1
    if new[path] > 5:
        return False
    return sum(t > 0 for t in new) <= 2 and sum(t > 2 for t in new) <= 1


# --- tower stats (towers.json "stats" block; see scripts/fetch_wiki_data.py) ---------------
# Data covers the base tower and single-path tiers. Crosspaths aren't in it: the game builds
# them by applying each upgrade's changes, some additive (Long Range Darts +8) and some
# multiplicative (Spike-o-pult x1.15), in an order the data doesn't give.

def tower_range(tower, tiers):
    """(range in game units, exact) for a tower dict from towers.json at `tiers` (e.g. (2, 0, 3)).
    With one upgraded path the value is the game's; with two it's base + the sum of each
    path's change, flagged exact=False (PLAN 5.5 measures the circle). (None, False) if unknown."""
    st = tower.get("stats")
    if not st or st.get("range") is None:
        return None, False
    base, total, upgraded = st["range"], st["range"], 0
    for path, tier in enumerate(tiers):
        if tier:
            r = st["range_by_tier"][path][tier - 1]
            if r is None:
                return None, False
            total += r - base
            upgraded += 1
    return round(total, 2), upgraded <= 1


def tower_abilities(tower, tiers):
    """Activated abilities a tower at `tiers` has: [{'name', 'cooldown', 'between_rounds', ...}].
    Each upgraded path contributes the abilities listed for its current tier. None if unknown."""
    st = tower.get("stats")
    if not st or st.get("abilities") is None:
        return None
    return [a for a in st["abilities"] if a["tier"] == tiers[a["path"]]]


def tower_shape(tower, tiers):
    """{'placement', 'footprint', 'targeting'} at `tiers`: the base values with any override
    for an upgraded path's current tier applied (e.g. Sun Temple's 37x40 rect footprint)."""
    st = tower.get("stats")
    if not st:
        return None
    shape = {k: st[k] for k in ("placement", "footprint", "targeting")}
    for o in st["overrides"]:
        if tiers[o["path"]] == o["tier"]:
            shape.update({k: v for k, v in o.items() if k in shape})
    return shape

