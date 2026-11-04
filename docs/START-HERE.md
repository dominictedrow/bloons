# START HERE

**Current phase / step:** Phase 0 → step 0.4 (capture FPS, OCR latency, window size). Done: 0.1, 0.2 (gate passed), 0.3 (hotkeys), 0.5, 2.4. Partly done: 2.1/2.2 (wiki fetch).
**Status:** BTD6+ accepts synthetic clicks and keys. Every plain hotkey works via PostToPid; modifier combos (Ctrl/Shift) don't, so use UI clicks for those. Repo: https://github.com/dominictedrow/bloons (submodule `Bloons bot/` in journey).
**Last handoff:** [handoffs/008-2026-11-04.md](handoffs/008-2026-11-04.md)

## Next action
Step 0.4: measure mss capture FPS on the game window and OCR latency on the HUD (money, lives, round). Ask Dom whether he wants windowed or full screen, then fix the calibration window size and record it below. Claude can run all of this from its own shell while a game is open.

## Open questions
- Do PostToPid clicks work when the game isn't the frontmost app? (lets Dom keep the mouse; 1.1)
- Which window size do we fix for calibration? (0.4)

## Environment notes
- Game device: Mac15,12 (MacBook Air M3 13"), macOS 27.0.1
- Repo lives on DOMS_DRIVE (FAT32): macOS writes `._*` files there; they're gitignored, and pip's "invalid distribution" warnings about them are harmless
- Game version: 57.4 (Info.plist). Runs windowed or full screen; the window rect includes a 33 pt title bar; capture comes out at 1 px/pt
- Permissions: Screen Recording + Accessibility granted to VS Code (Claude's shell inherits them)
- Window size used for calibration: _TBD_
- Dev machine: Windows 11 (editing + git only)
- Git: repo-local identity set (no global git identity on this Windows machine)
