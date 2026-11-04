# START HERE

**Current phase / step:** Phase 0 — Project scaffold + feasibility on Mac → step 0.2 (Mac feasibility checks); 0.1, 0.5, 2.4 done, 2.1/2.2 partial (wiki fetch); 0.2–0.4 need the Mac
**Status:** Feasibility script written (`scripts/feasibility_mac.py`) but not run yet. Repo is on GitHub: https://github.com/dominictedrow/bloons (submodule `Bloons bot/` in journey).
**Last handoff:** [handoffs/005-2026-11-03.md](handoffs/005-2026-11-03.md)

## Next action
On the Mac: install **Bloons TD 6+** from the App Store (Arcade tab); it isn't installed yet. Deps are already in `.venv/` (Homebrew Python 3.14). Give Terminal Screen Recording and Accessibility permissions, open BTD6+ in a game, then run `.venv/bin/python scripts/feasibility_mac.py` in your own Terminal (it asks y/n questions, so it can't run through Claude's shell). It finds the window, saves `frame.png`, and tries a `Q` key and a click through both the HID tap and PostToPid, asking you y/n for each one.

Paste the printed results into `docs/RESEARCH.md` (PLAN.md step 0.2), and note the BTD6+ version from Settings so step 2.5 can stamp the data.

## Open questions
- Do synthetic CGEvent inputs reach BTD6+? (Phase 0 gate)
- Which desktop hotkeys work in BTD6+ on Mac?
- Which window size / resolution do we fix for calibration?

## Environment notes
- Game device: Mac15,12 (MacBook Air M3 13"), macOS 27.0.1
- Repo lives on DOMS_DRIVE (FAT32): macOS writes `._*` files there; they're gitignored, and pip's "invalid distribution" warnings about them are harmless
- Game version: _TBD_
- Window size used for calibration: _TBD_
- Dev machine: Windows 11 (editing + git only)
- Git: repo-local identity set (no global git identity on this Windows machine)
