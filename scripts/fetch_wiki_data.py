"""Rebuild bloons/data/towers.json and heroes.json from the Bloons Wiki.

    python scripts/fetch_wiki_data.py

Costs, upgrade names and hotkeys come from the Cargo tables. Per-tier tower stats (range,
footprint, land/water, targeting, abilities) come from the wiki's game-model dumps,
Module:BTD6 stats/<Tower>/new (JSON despite the module namespace), which cover the base
tower and the 15 single-path tiers. Towers without a dump get "stats": null or what the
Stats:<Tower> (BTD6) page has (see MISSING_STATS). Distances are in game units.

Re-run after a game update. game_version stays null until checked in game (PLAN step 2.5).
"""
import datetime
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://www.bloonswiki.com/api.php"
OUT = Path(__file__).resolve().parents[1] / "bloons" / "data"


def cargo(table, fields, where=None):
    q = {"action": "cargoquery", "tables": table, "fields": fields, "limit": 500, "format": "json"}
    if where:
        q["where"] = where
    req = urllib.request.Request(f"{API}?{urllib.parse.urlencode(q)}", headers={"User-Agent": "bloons-bot-data-fetch"})
    rows = json.load(urllib.request.urlopen(req, timeout=30))["cargoquery"]
    if len(rows) == 500:
        raise RuntimeError(f"{table}: hit the 500-row limit, add paging")
    return [r["title"] for r in rows]


def module_json(titles):
    """{title: parsed JSON} for wiki pages holding JSON (missing pages left out)."""
    out = {}
    for i in range(0, len(titles), 10):
        q = {"action": "query", "prop": "revisions", "rvprop": "content", "rvslots": "main",
             "titles": "|".join(titles[i:i + 10]), "format": "json"}
        req = urllib.request.Request(f"{API}?{urllib.parse.urlencode(q)}", headers={"User-Agent": "bloons-bot-data-fetch"})
        for page in json.load(urllib.request.urlopen(req, timeout=60))["query"]["pages"].values():
            if "missing" not in page:
                out[page["title"]] = json.loads(page["revisions"][0]["slots"]["main"]["*"])
    return out


def _targeting(m):
    """['first', 'last', ...] from the model's targetType* flags (game's own names, snake_case:
    targetTypeCloseTrack -> close_track, targetTypeTargetSelectedPoint -> target_selected_point)."""
    return [re.sub(r"(?<!^)(?=[A-Z])", "_", k[len("targetType"):]).lower()
            for k, v in m.items() if k.startswith("targetType") and v]


# Towers the wiki has no game-model dump for (checked 2026-11-04). Village values are from
# Stats:Monkey Village (BTD6), last updated in 46.2; everything else is measured in game later.
MISSING_STATS = {
    "Banana Farm": None,
    "Skywarden": None,
    "Monkey Village": {"source": "Stats:Monkey Village (BTD6)", "version": "46.2",
                       "placement": {"land": True, "water": False}, "footprint": {"radius": 11},
                       "range": 40, "targeting": [],
                       "range_by_tier": [[48, None, None, None, 55], [None] * 5, [None] * 5],
                       "abilities": None, "overrides": []},
}


def _shape(m):
    fp = {"radius": m["footprintRadius"]} if m.get("footprintRadius") is not None else (
        {"rect": [m["footprintX"], m["footprintY"]]} if m.get("footprintX") is not None else None)
    targeting = _targeting(m)
    return {"placement": {"land": bool(m.get("placeableOnLand")), "water": bool(m.get("placeableOnWater"))},
            "footprint": fp, "targeting": targeting}


def tower_stats(name, model, upgrade_names):
    """Game-model dump -> the compact per-tower stats block stored in towers.json."""
    base = model["_000"]
    shape0 = _shape(base)
    stats = {"source": f"Module:BTD6 stats/{name}/new", "version": model.get("_last_updated"),
             **shape0, "range": base["range"], "range_by_tier": [], "abilities": [], "overrides": []}
    for path in range(3):
        ranges = []
        for tier in range(1, 6):
            key = "_" + "".join(str(tier) if p == path else "0" for p in range(3))
            m = model[key]
            ranges.append(m["range"])
            diff = {k: v for k, v in _shape(m).items() if v != shape0[k]}
            if diff:
                stats["overrides"].append({"path": path, "tier": tier, **diff})
            abil = m.get("abilities") or {}
            for a in abil.get("_order", []):
                cd = abil[a].get("cooldown", 0)
                if cd <= 0:          # passive (e.g. Druid's), not on the ability bar
                    continue
                stats["abilities"].append({
                    "path": path, "tier": tier,
                    "name": upgrade_names[path][tier - 1] if a == "Ability" else a,
                    "cooldown": cd, "between_rounds": bool(abil[a].get("canActivateBetweenRounds"))})
        stats["range_by_tier"].append(ranges)
    return stats


def slug(name):
    return name.lower().replace(" ", "_").replace("'", "")


def main():
    upgrades = cargo("btd6_upgrades", "tower,path,tier,name,cost", "unused = 0 AND path > 0")
    towers = {}
    for t in cargo("btd6_towers", "name,category,cost,hotkey"):
        if not t["cost"]:  # unreleased / placeholder rows
            continue
        paths = [[None] * 5 for _ in range(3)]
        for u in upgrades:
            if u["tower"] == t["name"]:
                paths[int(u["path"]) - 1][int(u["tier"]) - 1] = {"name": u["name"], "cost": int(u["cost"])}
        if any(None in p for p in paths):
            raise RuntimeError(f"{t['name']}: missing upgrades {paths}")
        towers[slug(t["name"])] = {
            "name": t["name"],
            "category": t["category"],
            "cost": int(t["cost"]),
            "hotkey": t["hotkey"] or None,  # wiki's desktop default; RESEARCH.md says if it works on BTD6+
            "upgrades": paths,  # [path][tier-1], medium-difficulty prices
        }
    dumps = module_json([f"Module:BTD6 stats/{t['name']}/new" for t in towers.values()])
    for t in towers.values():
        model = dumps.get(f"Module:BTD6 stats/{t['name']}/new")
        if model:
            t["stats"] = tower_stats(t["name"], model, [[u["name"] for u in p] for p in t["upgrades"]])
        elif t["name"] in MISSING_STATS:
            t["stats"] = MISSING_STATS[t["name"]]
        else:
            raise RuntimeError(f"{t['name']}: no stats dump and no MISSING_STATS entry")
    heroes = {
        slug(h["name"]): {"name": h["name"], "cost": int(h["cost"]), "xp_scale": float(h["xp scale"] or 1)}
        for h in cargo("btd6_heroes", "name,cost,xp_scale")
        if h["cost"]
    }
    meta = {
        "source": "bloonswiki.com Cargo (btd6_towers, btd6_upgrades, btd6_heroes)",
        "fetched": datetime.date.today().isoformat(),
        "game_version": None,
        "prices": "medium difficulty, before Monkey Knowledge; use bloons.rules.cost() for other difficulties",
        "stats": "per tower: placement, footprint (radius or rect, game units), range (game units), targeting, "
                 "range_by_tier[path][tier-1], abilities (cooldown s), overrides (tiers that change "
                 "placement/footprint/targeting). Single-path tiers only; bloons.rules.tower_range() "
                 "estimates crosspaths. stats.version is the game version of the wiki dump; null stats = measure in game.",
    }
    OUT.mkdir(parents=True, exist_ok=True)
    for fname, body in (("towers.json", {"_meta": meta, "towers": towers}), ("heroes.json", {"_meta": {k: v for k, v in meta.items() if k != "stats"}, "heroes": heroes})):
        (OUT / fname).write_text(json.dumps(body, indent=1) + "\n", encoding="utf-8")
    print(f"{len(towers)} towers, {len(heroes)} heroes -> {OUT}")


if __name__ == "__main__":
    main()
