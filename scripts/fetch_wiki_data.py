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


def page_text(titles):
    """{title: raw wikitext / module source} (missing pages left out)."""
    out = {}
    for i in range(0, len(titles), 10):
        q = {"action": "query", "prop": "revisions", "rvprop": "content", "rvslots": "main",
             "titles": "|".join(titles[i:i + 10]), "format": "json"}
        req = urllib.request.Request(f"{API}?{urllib.parse.urlencode(q)}", headers={"User-Agent": "bloons-bot-data-fetch"})
        for page in json.load(urllib.request.urlopen(req, timeout=60))["query"]["pages"].values():
            if "missing" not in page:
                out[page["title"]] = page["revisions"][0]["slots"]["main"]["*"]
    return out


def module_json(titles):
    """{title: parsed JSON} for wiki pages holding JSON (missing pages left out)."""
    return {t: json.loads(v) for t, v in page_text(titles).items()}


# --- heroes ---------------------------------------------------------------------------------
def hero_level_xp(xp_module_src):
    """Base XP to go from level n to n+1 (n = 1..19), parsed from Module:BTD6 hero xp."""
    m = re.search(r"levelReqs\s*=\s*\{([^}]*)\}", xp_module_src)
    reqs = [int(x) for x in re.findall(r"\d+", m.group(1))] if m else []
    if len(reqs) != 19:
        raise RuntimeError(f"hero xp table: expected 19 levels, got {reqs}")
    return reqs


def hero_levels_text(wikitext):
    """['level 1 description', ..., 'level 20'] from a hero page's ==Levels== table."""
    m = re.search(r"\n==\s*Levels\s*==\s*\n(.*?)\n\|\}", wikitext, re.S)
    rows = re.findall(r"\n!\s*(\d+)\s*\n\|(.*?)(?=\n\|-|\Z)", m.group(1) + "\n|-", re.S) if m else []
    def clean(t):
        t = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", t)     # [[link|text]] -> text
        t = re.sub(r"\{\{[^{}]*\}\}", "", t)                            # {{sic}} etc.
        t = re.sub(r"\n\|(?:[a-z]+=\"[^\"]*\"\s*\|)?", " | ", t)      # 2nd column (Dan's forms)
        return re.sub(r"\s+", " ", t).strip()
    text = {int(n): clean(t) for n, t in rows}
    return [text.get(n) for n in range(1, 21)] if text else None


def _ability_name(raw):
    name = re.sub(r"\s*sub-tower$", "", raw)
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", name)   # TargetFocus -> Target Focus


def hero_stats(name, model):
    """Hero game-model dump (base at top level, then only what changes at _2.._20) -> stats."""
    shape = _shape(model)
    rng, range_by_level, abilities = model["range"], [], {}
    for lvl in range(1, 21):
        m = model if lvl == 1 else (model.get(f"_{lvl}") or {})
        if lvl > 1 and "range" in m:
            rng = m["range"]
        range_by_level.append(rng)
        abil = m.get("abilities") or {}
        for a in abil.get("_order", []):
            n, cd = _ability_name(a), abil[a].get("cooldown")
            if n not in abilities:
                abilities[n] = {"name": n, "level": lvl, "cooldown": {}}
            if cd is not None and cd > 0:
                abilities[n]["cooldown"][str(lvl)] = cd
    return {"source": f"Module:BTD6 stats/{name}/new", "version": model.get("_last_updated"), **shape,
            "range_by_level": range_by_level, "abilities": list(abilities.values())}


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


def round_half_up(x):
    return int(x + 0.5)   # the wiki module's RoundHalfUp (values are positive)


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
    xp_src = page_text(["Module:BTD6 hero xp"])["Module:BTD6 hero xp"]
    base_xp = hero_level_xp(xp_src)
    pages = page_text([f"{h['name']} (BTD6)" for h in heroes.values()])
    hdumps = module_json([f"Module:BTD6 stats/{h['name']}/new" for h in heroes.values()])
    for h in heroes.values():
        h["level_xp"] = [round_half_up(x * h["xp_scale"]) for x in base_xp]
        h["levels"] = hero_levels_text(pages.get(f"{h['name']} (BTD6)", ""))
        if h["levels"] is None or None in h["levels"]:
            raise RuntimeError(f"{h['name']}: couldn't read the Levels table")
        model = hdumps.get(f"Module:BTD6 stats/{h['name']}/new")
        h["stats"] = hero_stats(h["name"], model) if model else None
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
    hero_meta = {**{k: v for k, v in meta.items() if k != "stats"},
                 "source": "bloonswiki.com Cargo (btd6_heroes), Module:BTD6 hero xp, <Hero> (BTD6) Levels tables, "
                           "Module:BTD6 stats/<Hero>/new",
                 "level_xp": "XP to go from level n to n+1 (n = 1..19): the module's base table x xp_scale, "
                             "rounded half up. A level can be bought with cash at $1 per remaining XP "
                             "(wiki; difficulty scaling unchecked).",
                 "xp_per_round": "XP gained at the end of round r: 20r+20 (r<=20), 40r-380 (r<=50), 90r-2880 "
                                 "(Module:BTD6 hero xp), before map-difficulty multipliers.",
                 "stats": "only for heroes with a wiki dump: placement, footprint, targeting, range_by_level, "
                          "abilities (unlock level, cooldown by level). null = read the ability bar in game."}
    OUT.mkdir(parents=True, exist_ok=True)
    for fname, body in (("towers.json", {"_meta": meta, "towers": towers}), ("heroes.json", {"_meta": hero_meta, "heroes": heroes})):
        (OUT / fname).write_text(json.dumps(body, indent=1) + "\n", encoding="utf-8")
    print(f"{len(towers)} towers, {len(heroes)} heroes -> {OUT}")


if __name__ == "__main__":
    main()
