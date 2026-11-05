# START HERE

**Current phase / step:** Phase 2 → step 2.5 (version stamp + in-game spot check). Phase 0, 1, and 2.1–2.4 done.
**Status:** BTD6+ accepts synthetic clicks and keys. Every plain hotkey works via PostToPid; modifier combos (Ctrl/Shift) don't. `bloons/platform_mac.py` (`Game`) captures in the background at 2× and reads the HUD with Vision; `bloons/hud.py` parses it (`Game.read_hud()` → `Hud`, smooth with `HudFilter`). `bloons/vision.py` matches templates (`match`, `button_state`) on `Frame.content_bgr()`; `bloons/state.py` gives screen kind + `RoundTracker` (round_active / round_ended / outcome). Never send modifier events; `refocus()` recovers keys. Repo: https://github.com/dominictedrow/bloons (submodule `Bloons bot/` in journey).
**Last handoff:** [handoffs/020-2026-11-04.md](handoffs/020-2026-11-04.md)

## Next action
Step 2.5 (live, ask Dom first: it drives the game): stamp game version 57.4 in the data files, then read ~10 shop/upgrade prices in game (OCR) and compare with `towers.json`; also check a few ranges/footprints and the hero level cost. Offline alternative: Phase 3.1 shared `ui.json` coords from the fixtures.

## Open questions
- FF switched itself on twice in the live run (handoff 017). Did Dom click it? If not, read `button_state` before toggling FF.
- Tower stats to measure in game: Banana Farm, Skywarden, most Monkey Village tiers (handoff 018)
- Hero level cost: $1/XP per the wiki; check whether difficulty scales it (handoff 019)
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
