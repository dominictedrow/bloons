# START HERE

**Current phase / step:** Phase 0 → step 0.3 (hotkey sweep, mostly done). Done: 0.1, 0.2 (gate passed), 0.5, 2.4. Partly done: 2.1/2.2 (wiki fetch).
**Status:** BTD6+ accepts synthetic clicks and keys. All tower, upgrade, sell, targeting and pause hotkeys are confirmed; Space, abilities and modifier combos aren't yet. Repo: https://github.com/dominictedrow/bloons (submodule `Bloons bot/` in journey).
**Last handoff:** [handoffs/007-2026-11-04.md](handoffs/007-2026-11-04.md)

## Next action
Dom starts a **Standard** game (not sandbox; rounds wouldn't start there). Claude tests Space (start and fast-forward), a tower ability (`1`) and Ctrl+Tab from its own shell, finishes the RESEARCH.md hotkey table, ticks 0.3, then moves to 0.4. Keys: PostToPid. Clicks: HID, with ~0.5 s between a tower key and the placement click.

## Open questions
- Why didn't rounds start in the sandbox? Does Space work in a Standard game? (0.3)
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
