"""Rebuild bloons/data/towers.json and heroes.json from the Bloons Wiki Cargo tables.

    python scripts/fetch_wiki_data.py

Re-run after a game update. game_version stays null until checked in game (PLAN step 2.5).
"""
import datetime
import json
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
    }
    OUT.mkdir(parents=True, exist_ok=True)
    for fname, body in (("towers.json", {"_meta": meta, "towers": towers}), ("heroes.json", {"_meta": meta, "heroes": heroes})):
        (OUT / fname).write_text(json.dumps(body, indent=1) + "\n", encoding="utf-8")
    print(f"{len(towers)} towers, {len(heroes)} heroes -> {OUT}")


if __name__ == "__main__":
    main()
