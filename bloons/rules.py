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


# --- heroes (heroes.json; see scripts/fetch_wiki_data.py) ----------------------------------

def hero_xp_for_round(r):
    """XP a hero gains at the end of round r (before map-difficulty multipliers)."""
    if r <= 20:
        return 20 * r + 20
    if r <= 50:
        return 40 * r - 380
    return 90 * r - 2880


def hero_xp_to_reach(hero, level):
    """Total XP from level 1 to `level` (1..20)."""
    return sum(hero["level_xp"][:level - 1])


def hero_level_cost(hero, level, xp_into_level=0):
    """Cash to buy the next level for a hero at `level` with `xp_into_level` XP already earned
    toward it: $1 per remaining XP (wiki; difficulty scaling unchecked). None at level 20."""
    if level >= 20:
        return None
    return max(0, hero["level_xp"][level - 1] - xp_into_level)


def hero_abilities(hero, level):
    """Activated abilities unlocked at `level`, each with its current cooldown:
    [{'name', 'level', 'cooldown'}]. None if the wiki has no data for this hero."""
    st = hero.get("stats")
    if not st:
        return None
    out = []
    for a in st["abilities"]:
        if a["level"] <= level:
            cds = [cd for lv, cd in a["cooldown"].items() if int(lv) <= level]
            out.append({"name": a["name"], "level": a["level"], "cooldown": cds[-1] if cds else None})
    return out


def hero_range(hero, level):
    st = hero.get("stats")
    return st["range_by_level"][level - 1] if st else None

