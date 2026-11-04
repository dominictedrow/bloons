# START HERE

**Current phase / step:** Phase 1 → step 1.1 (`platform_mac.py`). Phase 0 complete. Also done: 2.4; partly done: 2.1/2.2 (wiki fetch).
**Status:** BTD6+ accepts synthetic clicks and keys. Every plain hotkey works via PostToPid; modifier combos (Ctrl/Shift) don't. Capture ~47 FPS; Apple Vision reads the HUD in ~16 ms per field. Repo: https://github.com/dominictedrow/bloons (submodule `Bloons bot/` in journey).
**Last handoff:** [handoffs/009-2026-11-04.md](handoffs/009-2026-11-04.md)

## Next action
Step 1.1: write `bloons/platform_mac.py` (`find_window`, `grab`, `click`, `drag`, `key`, plus Vision OCR) from what `scripts/feasibility_mac.py` and `scripts/bench_capture_ocr.py` proved. Keys via PostToPid, clicks via HID, ~0.5 s between a tower key and the placement click, Ctrl/Shift key-up reset at start. Check the window is 1470×830 and warn if not.

## Open questions
- Do PostToPid clicks work when the game isn't the frontmost app? (lets Dom keep the mouse; 1.1)
- Does the game pause itself on focus loss? (1.1)

## Environment notes
- Game device: Mac15,12 (MacBook Air M3 13"), macOS 27.0.1
- Repo lives on DOMS_DRIVE (FAT32): macOS writes `._*` files there; they're gitignored, and pip's "invalid distribution" warnings about them are harmless
- Game version: 57.4 (Info.plist). Runs windowed or full screen; the window rect includes a 33 pt title bar; capture comes out at 1 px/pt
- Permissions: Screen Recording + Accessibility granted to VS Code (Claude's shell inherits them)
- Window size used for calibration: **windowed 1470×830 pt** (title bar included; fixed 2026-11-04)
- Dev machine: Windows 11 (editing + git only)
- Git: repo-local identity set (no global git identity on this Windows machine)
