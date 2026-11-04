# PLAN — Bloons TD 6+ RL Bot

Progress is tracked by the checkboxes here. `START-HERE.md` points at the active step. Rationale and sources are in `RESEARCH.md`.

## Goal
An RL agent that plays **Bloons TD 6+ (Apple Arcade) on macOS** through a pixel-based harness. Its actions and observations are plain Python methods that a person can drive by hand and wire into an RL loop without trouble. The first targets are 4 beginner maps on Easy, Standard mode.

## Architecture
```
Bloons bot/
  CLAUDE.md                 # session protocol + project rules
  docs/START-HERE.md  PLAN.md  RESEARCH.md  handoffs/
  bloons/
    platform_mac.py         # find window, capture, click/drag/key (Quartz). Only OS-specific file.
    vision.py               # OCR, template match, bloon detector, popup detector
    data/towers.json heroes.json rounds.json ui.json
    data/maps/<map>.json    # UI coords, placeable masks, path polyline, obstacles
    data/templates/*.png    # buttons, popups, victory/defeat, upgrade-state crops
    data/fixtures/*.png     # saved screenshots for offline tests
    harness.py              # BloonsHarness: actions + observe() -> GameState
    env.py                  # Gymnasium env + action mask
  tools/calibrate.py        # subcommands: ui | mask <map> | path <map> | templates
  tools/play.py             # REPL to drive the harness by hand
  train.py                  # MaskablePPO
  tests/test_offline.py     # vision/data tests on fixtures (no game needed)
```

## Harness API (`bloons/harness.py`)
Every action returns `ActionResult(ok: bool, reason: str)` and doesn't raise on game-side failures. Coordinates are normalized `0–1` over the game window. Towers get a stable integer `tid` at placement. The harness keeps a **tower registry** (kind, xy, tiers, targeting, money spent).

### Actions
| Requirement | Method |
|---|---|
| Buy, select and place a monkey | `place_tower(kind, x, y) -> tid` (checks the mask and money first) |
| Buy an upgrade | `upgrade(tid, path)` with `path ∈ {0,1,2}` |
| Place a hero / upgrade a hero | `place_hero(x, y)`; `buy_hero_level(tid)` |
| Sell | `sell(tid)` |
| Use abilities | `use_ability(slot)`; `use_ability_of(tid)`; `place_ability_target(slot, x, y)` |
| Configure abilities and targeting | `set_targeting(tid, mode)`; `set_target_point(tid, x, y)`; `set_flight_path(tid, pattern)`; `set_patrol_points(tid, points)` |
| Remove terrain | `remove_obstacle(obstacle_id)` |
| Start next round | `start_round()` |
| Speed up / down | `set_fast_forward(on)` |
| Auto-start on / off | `set_auto_start(on)` |
| Handle prompts | `handle_prompts() -> list[str]` (runs automatically before every action) |
| Episode control | `new_game(map, difficulty, mode, hero)`; `restart()`; `go_home()` |

### Observation: `observe() -> GameState` (+ `.to_vector()`)
| Requirement | Field | Source |
|---|---|---|
| Money / health / round | `money`, `lives`, `round`, `max_round` | HUD OCR + sanity filter |
| Round ended | `round_active`, `round_ended` (edge) | start/FF button state |
| Won / lost | `outcome ∈ {None,"win","loss"}` | victory/defeat templates |
| Where monkeys can go | `placeable_mask[footprint]` | map calibration minus placed towers |
| Path | `path` polyline, `path_grid` | map calibration |
| Bloons + types | `bloons: [(x, y, type_guess)]`, `round_composition` | vision detector + `rounds.json` |
| Towers + ranges | `towers: [TowerState(tid, kind, xy, tiers, range_px, targeting, sell_value)]` | registry + `towers.json` (+ circle measurement) |
| Available upgrades + costs | `upgrade_options[tid][path] = (cost, affordable, locked)` | table × difficulty, crosspath rule, panel OCR |
| Monkey / tower abilities | `abilities: [(slot, tid, ready, cooldown_frac)]` | ability bar icons + cooldown overlay |
| Hero | `hero: (tid, level, xp_frac)` | panel OCR |

## RL layer (`bloons/env.py`)
**Owned by Dom, who builds the RL model himself.** Claude doesn't write the env, rewards, model or training code; the notes below are a starting sketch for Dom, not a spec. Claude's job ends at a harness that's clean to wrap (actions + `observe()`).
- **Step:** one macro action at round start, plus every N seconds during a round. After each action the env runs `handle_prompts()` and returns `observe()`.
- **Actions:** a flat `Discrete` table: `NOOP | START_ROUND | PLACE(kind, cell) | UPGRADE(slot, path) | SELL(slot) | ABILITY(slot) | TARGETING(slot, mode)`. Cells come from a coarse grid (e.g. 24×16), with a fixed number of tower slots (~20). `action_masks()` removes unaffordable, unplaceable and locked actions.
- **Observation:** a vector (money, lives, round, upcoming composition, slot table, map one-hot) + a small grid image (path, towers, bloon density).
- **Reward:** + per round survived, − per life lost, − small for a failed action, ± large at the end.
- **Training:** a scripted baseline first, then MaskablePPO. Optional behavior-cloning warm start from scripted or manual logs.

---

## Phase 0 — Scaffold + Mac feasibility
- [x] 0.1 Write CLAUDE.md, START-HERE.md, PLAN.md, RESEARCH.md, handoffs/
- [x] 0.2 Mac setup: Python 3.11+, deps, Screen Recording + Accessibility permissions. Throwaway script: find the window, capture a frame, send a synthetic click + `Q` key. **Gate: if input is ignored, stop and re-plan (HID fallback).**
- [x] 0.3 Test every hotkey in RESEARCH.md and fill in the status column
- [x] 0.4 Measure capture FPS and OCR latency. Fix the window size used for all calibration and record it in START-HERE
- [x] 0.5 `git init` the repo structure, plus `requirements.txt`

## Phase 1 — Platform + vision basics
- [x] 1.1 `platform_mac.py`: `find_window()`, `grab()`, `click(x,y)`, `drag(a,b)`, `key(k)` (normalized coords)
- [x] 1.2 Capture fixtures: HUD at various values, every popup type, victory, defeat, the upgrade panel → `data/fixtures/`
- [ ] 1.3 HUD OCR: money, lives, round (digit whitelist + sanity filter) + offline tests
- [ ] 1.4 Template library + `match(name)`: start / FF / FF-active buttons, popups, victory/defeat
- [ ] 1.5 Round-state + outcome detection + offline tests

## Phase 2 — Static game data
- [ ] 2.1 `towers.json`: every tower's base cost, upgrade costs per path/tier, base range + range modifiers, abilities, hotkey, footprint class, land/water — *costs, upgrade names and hotkeys done via `scripts/fetch_wiki_data.py`; range/abilities/footprint/land-water still to add*
- [ ] 2.2 `heroes.json`: cost, level-up costs, abilities by level — *cost + xp_scale done; level-up costs and abilities still to add*
- [ ] 2.3 `rounds.json`: Standard rounds 1–140 (types, counts, properties)
- [x] 2.4 Cost helper `cost(base, difficulty)` + crosspath rule `upgrade_allowed(tiers, path)` + tests
- [ ] 2.5 Stamp the game version. Spot-check 10 costs against the in-game panel

## Phase 3 — Map calibration (Monkey Meadow, Tree Stump, Town Center, Logs)
- [ ] 3.1 `ui.json`: shared UI coords (tower shop, upgrade panel buttons, sell, targeting, ability bar, settings/auto-start, FF)
- [ ] 3.2 `calibrate.py mask <map>`: grid sweep while holding a tower, reading the red tint → placeable masks per footprint (land/water)
- [ ] 3.3 `calibrate.py path <map>`: frame-difference bloons on round 1 → polyline, then a hand-correct click tool
- [ ] 3.4 Obstacles: click points + IDs per map
- [ ] 3.5 Calibrate all 4 maps and save `data/maps/<map>.json`

## Phase 4 — Harness actions
- [ ] 4.1 `BloonsHarness` skeleton, `ActionResult`, tower registry, hotkey-or-click helper
- [ ] 4.2 `place_tower`, `place_hero`, `sell`
- [ ] 4.3 `upgrade`, `buy_hero_level`
- [ ] 4.4 `start_round`, `set_fast_forward`, `set_auto_start`
- [ ] 4.5 `use_ability`, `use_ability_of`, `place_ability_target`
- [ ] 4.6 `set_targeting`, `set_target_point`, `set_flight_path`, `set_patrol_points`
- [ ] 4.7 `remove_obstacle`
- [ ] 4.8 `handle_prompts` (template → default click, overridable)
- [ ] 4.9 `new_game`, `restart`, `go_home`
- [ ] 4.10 `tools/play.py` REPL. Drive every action by hand on Monkey Meadow

## Phase 5 — Full observation
- [ ] 5.1 `GameState` dataclass + `observe()` (HUD, round state, outcome, registry, masks, path)
- [ ] 5.2 Bloon detector (HSV classes first; small YOLO only if HSV falls short) + `round_composition`
- [ ] 5.3 `upgrade_options` (table + rules + panel OCR verification)
- [ ] 5.4 Ability bar reading (ready + cooldown fraction)
- [ ] 5.5 Range: table value + circle-measure verification
- [ ] 5.6 `GameState.to_vector()` + grid image

## Phase 6 — Scripted baseline
- [ ] 6.1 Hand-written strategy using only the harness API
- [ ] 6.2 Beat Easy on all 4 maps with outcome == "win" detected. Log (obs, action) pairs for BC

## Phase 7 — RL (Dom's)
- [ ] 7.1 `env.py` (Gymnasium) + `action_masks()`. `check_env` passes
- [ ] 7.2 `train.py` with MaskablePPO, checkpoints, TensorBoard logging, multi-map sampling
- [ ] 7.3 Optional BC warm start from the Phase 6 logs
- [ ] 7.4 Eval script: win rate + mean round reached per map

## Phase 8 — Expand
- [ ] 8.1 More maps, Medium/Hard, other modes
- [ ] 8.2 Hero choice and late-game strategy (rounds 40+, MOAB-class)

---

## Verification
- `pytest tests/test_offline.py`: OCR, templates and data rules on fixtures (Windows or Mac).
- Phase 4 gate, in `tools/play.py`: `place_tower("dart", .4, .5)`, `upgrade(0, 0)`, `start_round()`, `observe()`. Each must match the screen.
- Phase 6 gate: the scripted baseline wins Easy on every calibrated map.
- Phase 7 gate: `gymnasium.utils.env_checker.check_env` passes, and a short PPO run steps without harness errors.

## Risks
- BTD6+ ignores synthetic input → Phase 0 gate. Fallback: HID-level injection.
- Game updates move UI or change costs → everything lives in JSON, data is version-stamped, OCR cross-checks flag drift.
- Training is bound by real time → macro actions, masking, a scripted warm start, Easy first.
