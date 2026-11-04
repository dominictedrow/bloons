# Research — Bloons TD 6+ (Apple Arcade) automation

Living document. Add findings with dates. Mark each item **CONFIRMED**, **UNVERIFIED** or **FALSE**.

## Platform
- BTD6+ shipped on Apple Arcade for iOS and macOS in Feb 2022. The App Store listing requires macOS 11+. **CONFIRMED** ([App Store](https://apps.apple.com/kw/app/bloons-td-6/id1584423325), [Bloons wiki: BTD6+](https://www.bloonswiki.com/Bloons_TD_6%2B))
- It's a signed, sandboxed Mac App Store app, so MelonLoader and BTD6 Mod Helper (Steam modding) can't be used. Ninja Kiwi also disallows mods outside Steam. The harness therefore uses **pixels and synthetic input only**.
- iPad/iPhone isn't a target. iOS blocks programmatic touches without a jailbreak, capture card or HID emulator.

## Tooling (macOS Python)
| Need | Library | Notes |
|---|---|---|
| Find window | `pyobjc-framework-Quartz` `CGWindowListCopyWindowInfo` | match the owner name containing "Bloons" |
| Capture | `mss` | needs the Screen Recording permission |
| Input | Quartz `CGEventCreateMouseEvent` / `CGEventCreateKeyboardEvent` + `CGEventPost` | needs the Accessibility permission. **UNVERIFIED** that BTD6+ accepts it |
| OCR | `ocrmac` (Apple Vision) | fast and local. Restrict to digits/`$` for the HUD |
| Vision | `opencv-python`, `numpy` | template matching, HSV bloon classes |
| RL | `gymnasium`, `stable-baselines3`, `sb3-contrib` (MaskablePPO) | |

Fallback if CGEvent input is ignored: a HID-level virtual keyboard/mouse (e.g. Karabiner-DriverKit), or an external microcontroller acting as a USB HID device.

## Prior art (Steam BTD6, same approach)
- [Schnurzel700/BTD6bot](https://github.com/Schnurzel700/BTD6bot): OCR + keyboard/mouse automation + scripted strategies. Last release targeted game version 54.
- [GraemeIBB/BloonPlayer](https://github.com/GraemeIBB/BloonPlayer): OpenCV-only autoplayer, best run round 104 on Meadows.
- [Runeste3/cvbot](https://github.com/Runeste3/cvbot): generic CV + OCR desktop automation.

## Hotkeys (desktop BTD6 defaults — all UNVERIFIED on BTD6+ Mac)
Source: [Bloons wiki: Hotkeys](https://www.bloonswiki.com/Hotkeys). Fill in the status column during Phase 0.

| Action | Key | BTD6+ Mac |
|---|---|---|
| Hero | U | ? |
| Dart / Boomerang / Bomb / Tack / Ice / Glue | Q / W / E / R / T / Y | ? |
| Sniper / Sub / Buccaneer / Ace / Heli / Mortar / Dartling | Z / X / C / V / B / N / M | ? |
| Wizard / Super / Ninja / Alchemist / Druid | A / S / D / F / G | ? |
| Farm / Spike Factory / Village / Engineer | H / J / K / L | ? |
| Newer towers (Mermonkey, Beast Handler, Desperado, …) | check the in-game hotkey settings | ? |
| Upgrade path 1 / 2 / 3 | `,` / `.` / `/` | ? |
| Sell | Backspace | ? |
| Change targeting | Tab (Ctrl+Tab = reverse) | ? |
| Abilities 1–10 | 1–0 | ? |
| Start round / fast-forward | Space | ? |

Rule: once a key is confirmed, the harness uses it, otherwise it clicks the UI coordinate from `data/maps/*.json` / `data/ui.json`.

## Game mechanics the harness relies on
- **Rounds are deterministic in Standard mode.** Bloon types, counts, spacing and properties (camo, regrow, fortified) are fixed per round. They go into `rounds.json` from the wiki, so the bloon type is known exactly and vision only has to supply positions.
- **Upgrades:** 3 paths × 5 tiers. Crosspath rule: at most 2 paths upgraded, and only one beyond tier 2 (e.g. 5-2-0). Only one tier-5 per path per tower type on the map (Paragons excepted).
- **Costs:** base cost × difficulty multiplier. Easy 0.85, Medium 1.0, Hard 1.08, Impoppable 1.2, rounded to the nearest $5. Cross-check against OCR of the upgrade panel. Ninja Kiwi rebalances often, so stamp the game version on the data.
- **Sell value:** 70% of money spent by default (more with some upgrades/villages). The harness tracks money spent per tower.
- **Placement:** while a tower is held, an invalid spot tints the range circle red. That's how the per-map placeable mask is calibrated. Land, water and both-type towers need separate masks.
- **Ranges:** base range per tower plus upgrade modifiers. A selected tower shows its circle, which can be measured to verify.
- **Heroes:** level up from XP each round. The upgrade panel lets you buy levels with money.
- **Abilities:** these show in an ability bar with cooldown overlays. Some need a target point.
- **Configurable towers:** Ace (flight pattern, centered path), Heli (lock/pursuit/patrol points), Mortar / Dartling / Sniper Elite targeting (target point), Spike Factory (placement target), plus the general targeting modes First/Last/Close/Strong.
- **Removable obstacles:** click the obstacle → a panel shows the removal cost → confirm. Varies per map.
- **Round flow:** the start button becomes fast-forward while a round is running, which is how round end is detected. Auto-start is a Settings toggle. Victory and defeat screens are template-matched.
- **Popups to handle:** level-up, insta-monkey / reward collection, "continue to freeplay?", confirm dialogs, event/collection notices.

## Findings log
- 2026-11-03: Initial research. No direct confirmation found of hotkey support in BTD6+ Mac. A Steam user reported hotkeys working on a MacBook Air, but that was the Steam build ([thread](https://steamcommunity.com/app/960090/discussions/0/5226999188079746942)).
