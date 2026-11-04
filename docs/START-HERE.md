# START HERE

**Current phase / step:** Phase 0 — Project scaffold + feasibility on Mac → step 0.2 (Mac feasibility checks); 0.1 and 0.5 done, 0.2–0.4 need the Mac
**Status:** Feasibility script written (`scripts/feasibility_mac.py`) but not run yet. Repo is on GitHub: https://github.com/dominictedrow/bloons (submodule `Bloons bot/` in journey).
**Last handoff:** [handoffs/003-2026-11-03.md](handoffs/003-2026-11-03.md)

## Next action
On the Mac: install Python 3.11+, run `pip install -r requirements.txt`, give Terminal Screen Recording and Accessibility permissions, open BTD6+ in a game, then run `python3 scripts/feasibility_mac.py`. It finds the window, saves `frame.png`, and tries a `Q` key and a click through both the HID tap and PostToPid, asking you y/n for each one.

Paste the printed results into `docs/RESEARCH.md` (PLAN.md step 0.2).

## Open questions
- Do synthetic CGEvent inputs reach BTD6+? (Phase 0 gate)
- Which desktop hotkeys work in BTD6+ on Mac?
- Which window size / resolution do we fix for calibration?

## Environment notes
- Game device: Mac (model / macOS version: _TBD_)
- Game version: _TBD_
- Window size used for calibration: _TBD_
- Dev machine: Windows 11 (editing + git only)
- Git: repo-local identity set (no global git identity on this Windows machine)
