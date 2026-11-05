# START HERE

**Current phase / step:** Phase 1 → live check of 1.5, then Phase 2/3. Phase 0 and 1.1–1.5 done (1.5 offline). Also done: 2.4; partly done: 2.1/2.2 (wiki fetch).
**Status:** BTD6+ accepts synthetic clicks and keys. Every plain hotkey works via PostToPid; modifier combos (Ctrl/Shift) don't. `bloons/platform_mac.py` (`Game`) captures in the background at 2× and reads the HUD with Vision; `bloons/hud.py` parses it (`Game.read_hud()` → `Hud`, smooth with `HudFilter`). `bloons/vision.py` matches templates (`match`, `button_state`) on `Frame.content_bgr()`; `bloons/state.py` gives screen kind + `RoundTracker` (round_active / round_ended / outcome). Never send modifier events; `refocus()` recovers keys. Repo: https://github.com/dominictedrow/bloons (submodule `Bloons bot/` in journey).
**Last handoff:** [handoffs/016-2026-11-04.md](handoffs/016-2026-11-04.md)

## Next action
Live check of 1.5: open BTD6+ (windowed 1470×830), run `.venv/bin/python scripts/watch_state.py <scratch dir>` (sends no input) during one Easy Monkey Meadow game. Toggle FF, open the upgrade panel, pause once. Confirm the transitions and template scores; turn surprises into fixtures and tests.

## Open questions
- `drag()` is untested in the game (1.2+, when a feature needs it)
- Stage Manager is on: if window moves cause trouble, consider turning it off for bot runs

## Environment notes
- Game device: Mac15,12 (MacBook Air M3 13"), macOS 27.0.1
- Repo lives on DOMS_DRIVE (FAT32): macOS writes `._*` files there; they're gitignored, and pip's "invalid distribution" warnings about them are harmless
- Game version: 57.4 (Info.plist). Runs windowed or full screen; the window rect includes a 33 pt title bar; capture comes out at 1 px/pt
- Permissions: Screen Recording + Accessibility granted to VS Code (Claude's shell inherits them)
- Window size used for calibration: **windowed 1470×830 pt** (title bar included; fixed 2026-11-04)
- Dev machine: Windows 11 (editing + git only)
- Git: repo-local identity set (no global git identity on this Windows machine)
