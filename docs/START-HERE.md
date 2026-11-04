# START HERE

**Current phase / step:** Phase 1 → step 1.2 (capture fixtures). Phase 0 and 1.1 done. Also done: 2.4; partly done: 2.1/2.2 (wiki fetch).
**Status:** BTD6+ accepts synthetic clicks and keys. Every plain hotkey works via PostToPid; modifier combos (Ctrl/Shift) don't. `bloons/platform_mac.py` (`Game`) captures in the background at 2× and reads the HUD with Vision. Never send modifier events; `refocus()` recovers keys. Repo: https://github.com/dominictedrow/bloons (submodule `Bloons bot/` in journey).
**Last handoff:** [handoffs/010-2026-11-04.md](handoffs/010-2026-11-04.md)

## Next action
Step 1.2: collect fixtures into `bloons/data/fixtures/` with `Game().grab().save_png(...)`: the HUD at varied values, the pause menu, the upgrade panel on the left and right, play/fast-forward button states, victory, and popups (defeat and restart-confirm are already saved). Run `scripts/smoke_platform.py --input` first to check the platform layer still works.

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
