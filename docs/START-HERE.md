# START HERE

**Current phase / step:** Phase 4 → step 4.9 in progress (new_game / restart / go_home work; map search flaky). Phases 0–3 and steps 4.1–4.6 + 4.8 done; 4.7 skipped (no obstacles on beginner maps). `docs/PLACEMENT-PLAN.md` orders 1–2 done; order 3 is in Phase 4.
**Status:** BTD6+ accepts synthetic clicks and keys. Every plain hotkey works via PostToPid; modifier combos (Ctrl/Shift) don't. `bloons/platform_mac.py` (`Game`) captures in the background at 2× and reads the HUD with Vision; `bloons/hud.py` parses it (`Game.read_hud()` → `Hud`, smooth with `HudFilter`). `bloons/vision.py` matches templates (`match`, `button_state`) on `Frame.content_bgr()`; `bloons/state.py` gives screen kind + `RoundTracker` (round_active / round_ended / outcome). `bloons/ui.py` gives shop cells (2 scroll layouts), both upgrade-panel sides, the hero panel and ability slots from `data/ui.json`. Never send modifier events; `refocus()` recovers keys. `rules.shop_price` / `upgrade_price` apply Dom's Monkey Knowledge (`data/account.json`). `tools/calibrate.py mask` + `bloons/placement.py` build placeable masks; Monkey Meadow has 6 land classes in `data/maps/monkey_meadow.json` (`placement.placeable()`). Layered placement: `placement.can_place` (own towers → `PathKeepout` → `SpotMemory` in `<map>.spots.json`, seeded from the sweep) with `record_placement` for tint results. Guards: `bloons/guards.py` (`can_*`, `available_actions`) return `ActionResult` (`bloons/result.py`). Path tooling: `bloons/pathmap.py` + `calibrate.py path / path-edit / keepout / spots`. Paths recorded on all 4 maps (red-bloon lead track, blobs < 300 px dropped, sprite offset 4 units; half-width 0.25 fitted on Meadow, default 0.5 elsewhere). No removable obstacles on any of them. Map-select pages in `ui.json` `map_select`. In Sandbox, rounds start only from `sandbox_send_round`; Sandbox is locked on the other 3 maps (use Standard, Space). `bloons/harness.py` `BloonsHarness` (4.1): registry, guard/place contexts, `press` hotkey-or-click, `select_shop` (scrolls via `Game.scroll`); 4.2 `place_tower` / `place_hero` / `sell` (guard → can_place → one tint read → click → HUD money confirms; refusals remembered); 4.3 `upgrade` / `buy_hero_level` (panel closed before the HUD money check: a left panel covers it); 4.4 `start_round` (Standard: idle → Space → ▶▶; Sandbox: bloon panel → send → back to shop), `set_fast_forward`, `set_auto_start` (gear → pause → knob probe → Continue). `BloonsHarness(mode='sandbox')` for Sandbox. 4.5 abilities: bar slot = ability name (identical abilities share an icon), instances with cooldown estimates, `use_ability` / `place_ability_target` / `use_ability_of`, confirmed by the slot icon changing; hero bar abilities in `data/hero_abilities.json`. 4.6 `set_targeting` / `set_flight_path` (Tab + OCR'd label until it matches), `set_target_point` / `set_patrol_points` (label-spot button → map clicks → panel reopens). 4.8 `handle_prompts()` (ui.json `prompts`: collect / continue / cancel; victory & defeat left to the caller). 4.9 `go_home`, `restart`, `new_game(map, difficulty, mode, overwrite_save=False)` (finds the map by OCR'd thumbnail name; screens home / difficulty_select / overwrite_save templated). Repo: https://github.com/dominictedrow/bloons (submodule `Bloons bot/` in journey).
**Last handoff:** [handoffs/036-2026-11-05.md](handoffs/036-2026-11-05.md)

## Next action
Make `_pick_map` (map search on map select) reliable: 10+ live picks with page/click logging, find the occasional overshoot / `map_not_found`, fix (e.g. confirm each page flip changed the names), then tick 4.9 → 4.10.

## Open questions
- 4.1–4.6, 4.8 and 4.9 (partial) committed, nothing pushed; 4.7 skipped
- Junk saves from session 036 (Meadow / maybe Tree Stump / an ice map, Easy Standard): Dom to check
- Keys can be dead after a Stage Manager restore until one real click (handoff 032); ability hotkeys 2–= untested
- A probe flipped Drag & Drop → Drop & Lock in the pause menu; restored at once (handoff 028)
- Default half-width 0.5 on Tree Stump / Town Center / Logs isn't validated live
- The path tool's red detector assumes round 1 is red bloons and no red decoration moves: check the `--debug` heat map on each new map
- `path-edit` hasn't been used by hand yet
- Masks not yet checked visually: run `tools/calibrate.py show` on a full 2× screenshot
- macOS can pop a screen-capture privacy prompt for VS Code mid-run; it steals focus and blocks all input until answered
- MK upgrade discounts (Double Shot, Heart of Oak, Guided/Intense Magic, Maim MOAB, Cluster Bombs) are in `account.json` but their prices aren't checked in game yet
- FF switched itself on twice in the live run (handoff 017). Did Dom click it? If not, read `button_state` before toggling FF.
- Tower stats to measure in game: Banana Farm, Skywarden, most Monkey Village tiers (handoff 018)
- `drag()` is untested in the game
- Stage Manager is on: if window moves cause trouble, consider turning it off for bot runs

## Environment notes
- Game device: Mac15,12 (MacBook Air M3 13"), macOS 27.0.1
- Repo lives on DOMS_DRIVE (FAT32): macOS writes `._*` files there; they're gitignored, and pip's "invalid distribution" warnings about them are harmless
- Game version: 57.4 (Info.plist). Runs windowed or full screen; the window rect includes a 33 pt title bar; capture comes out at 1 px/pt
- Permissions: Screen Recording + Accessibility granted to VS Code (Claude's shell inherits them)
- Window size used for calibration: **windowed 1470×830 pt** (title bar included; fixed 2026-11-04)
- Dev machine: Windows 11 (editing + git only)
- Git: repo-local identity set (no global git identity on this Windows machine)
