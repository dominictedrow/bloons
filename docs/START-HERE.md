# START HERE

**Current phase / step:** Phase 3 → step 3.3 (bloon path). Phases 0–2 and steps 3.1–3.2 done.
**Status:** BTD6+ accepts synthetic clicks and keys. Every plain hotkey works via PostToPid; modifier combos (Ctrl/Shift) don't. `bloons/platform_mac.py` (`Game`) captures in the background at 2× and reads the HUD with Vision; `bloons/hud.py` parses it (`Game.read_hud()` → `Hud`, smooth with `HudFilter`). `bloons/vision.py` matches templates (`match`, `button_state`) on `Frame.content_bgr()`; `bloons/state.py` gives screen kind + `RoundTracker` (round_active / round_ended / outcome). `bloons/ui.py` gives shop cells (2 scroll layouts), both upgrade-panel sides, the hero panel and ability slots from `data/ui.json`. Never send modifier events; `refocus()` recovers keys. `rules.shop_price` / `upgrade_price` apply Dom's Monkey Knowledge (`data/account.json`). `tools/calibrate.py mask` + `bloons/placement.py` build placeable masks; Monkey Meadow has 6 land classes in `data/maps/monkey_meadow.json` (`placement.placeable()`). Repo: https://github.com/dominictedrow/bloons (submodule `Bloons bot/` in journey).
**Last handoff:** [handoffs/025-2026-11-05.md](handoffs/025-2026-11-05.md)

## Next action
Step 3.3: `tools/calibrate.py path monkey_meadow`. Start round 1 in the Monkey Meadow sandbox, frame-difference the moving bloons against an empty-map frame, and fit a polyline (entry → exit) into `data/maps/monkey_meadow.json` under `path`. Then add a hand-correct click tool.

## Open questions
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
