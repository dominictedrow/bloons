"""Pure game rules: difficulty pricing and the upgrade crosspath rule (RESEARCH.md)."""
import math

DIFFICULTY_MULT = {"easy": 0.85, "medium": 1.0, "hard": 1.08, "impoppable": 1.2}


def cost(base, difficulty):
    """Base price scaled by difficulty, rounded to the nearest $5."""
    # ponytail: ties (x.5 of $5) round up; confirm against the in-game panel in step 2.5
    return int(math.floor(base * DIFFICULTY_MULT[difficulty] / 5 + 0.5)) * 5


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
