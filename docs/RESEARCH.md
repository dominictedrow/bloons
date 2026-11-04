# Research — Bloons TD 6+ (Apple Arcade) automation

Living document. Add findings with dates. Mark each item **CONFIRMED**, **UNVERIFIED** or **FALSE**.

## Platform
- BTD6+ shipped on Apple Arcade for iOS and macOS in Feb 2022. The App Store listing requires macOS 11+. **CONFIRMED** ([App Store](https://apps.apple.com/kw/app/bloons-td-6/id1584423325), [Bloons wiki: BTD6+](https://www.bloonswiki.com/Bloons_TD_6%2B))
- It's a signed, sandboxed Mac App Store app, so MelonLoader and BTD6 Mod Helper (Steam modding) can't be used. Ninja Kiwi also disallows mods outside Steam. The harness therefore uses **pixels and synthetic input only**.
- iPad/iPhone isn't a target. iOS blocks programmatic touches without a jailbreak, capture card or HID emulator.

## Tooling (macOS Python)
| Need | Library | Notes |
|---|---|---|
| Find window | `pyobjc-framework-Quartz` `CGWindowListCopyWindowInfo` | match the owner name containing "Bloons" |
| Capture | `mss` | needs the Screen Recording permission |
| Input | Quartz `CGEventCreateMouseEvent` / `CGEventCreateKeyboardEvent` + `CGEventPost` | needs the Accessibility permission. **UNVERIFIED** that BTD6+ accepts it |
| OCR | `ocrmac` (Apple Vision) | fast and local. Restrict to digits/`$` for the HUD |
| Vision | `opencv-python`, `numpy` | template matching, HSV bloon classes |
| RL | `gymnasium`, `stable-baselines3`, `sb3-contrib` (MaskablePPO) | |

Fallback if CGEvent input is ignored: a HID-level virtual keyboard/mouse (e.g. Karabiner-DriverKit), or an external microcontroller acting as a USB HID device.

## Prior art (Steam BTD6, same approach)
- [Schnurzel700/BTD6bot](https://github.com/Schnurzel700/BTD6bot): OCR + keyboard/mouse automation + scripted strategies. Last release targeted game version 54.
- [GraemeIBB/BloonPlayer](https://github.com/GraemeIBB/BloonPlayer): OpenCV-only autoplayer, best run round 104 on Meadows.
- [Runeste3/cvbot](https://github.com/Runeste3/cvbot): generic CV + OCR desktop automation.

## Hotkeys (BTD6+ 57.4 on Mac, checked 2026-11-04)
Bindings read from the in-game Settings → Hotkeys page (defaults; Dom hasn't changed them). "Confirmed" = Claude sent the key via `CGEventPostToPid` in a Monkey Meadow sandbox and checked the effect in a screenshot.

| Action | Key | Status |
|---|---|---|
| Hero | U | confirmed (selected Benjamin) |
| Dart / Boomerang / Bomb / Tack / Ice / Glue | Q / W / E / R / T / Y | all confirmed |
| Sniper / Sub / Buccaneer / Ace / Heli / Mortar / Dartling | Z / X / C / V / B / N / M | all confirmed |
| Wizard / Super / Ninja / Alchemist / Druid | A / S / D / F / G | all confirmed |
| Farm / Spike Factory / Village / Engineer | H / J / K / L | all confirmed |
| Beast Handler | I | confirmed |
| Desperado / Mermonkey / Skywarden | **unbound** (red in the menu) | click the shop, or bind keys in Settings |
| Upgrade path 1 / 2 / 3 | `,` / `.` / `/` | all confirmed (needs the tower selected) |
| Sell | Backspace | confirmed (paid the 70% sell value) |
| Change targeting | Tab | confirmed (First → Last) |
| Reverse targeting | Ctrl+Tab | **doesn't work** via PostToPid or HID, even with a real Ctrl down/up. Use the ◀ arrow on the panel's targeting label |
| Pause | Backquote (opens) / Esc (toggles) | both confirmed; Backquote doesn't close the menu |
| Play / fast-forward | Space | confirmed in a Standard game: starts the round, then toggles fast-forward (the ▶▶ arrows switch between dark and bright). Did nothing in the sandbox, where the button already showed ▶▶ |
| Activated abilities 1–12 | 1–0, Minus, Equals | not tested yet (no ability tower affordable early). Test when the harness first uses one |
| Monkey Special / Special 2 | PageDown / PageUp | not tested |
| Powers (Road Spikes … Cash Drop) | Shift+1 … Shift+RightBracket | not tested; modifier combos look unreliable (see Ctrl+Tab), so plan to click |
| Sandbox: send bloon | Ctrl+1 … | no visible effect via either method |

Rule: once a key is confirmed, the harness uses it, otherwise it clicks the UI coordinate from `data/maps/*.json` / `data/ui.json`.

## Game mechanics the harness relies on
- **Rounds are deterministic in Standard mode.** Bloon types, counts, spacing and properties (camo, regrow, fortified) are fixed per round. They go into `rounds.json` from the wiki, so the bloon type is known exactly and vision only has to supply positions.
- **Upgrades:** 3 paths × 5 tiers. Crosspath rule: at most 2 paths upgraded, and only one beyond tier 2 (e.g. 5-2-0). Only one tier-5 per path per tower type on the map (Paragons excepted).
- **Costs:** base cost × difficulty multiplier. Easy 0.85, Medium 1.0, Hard 1.08, Impoppable 1.2, rounded to the nearest $5 with ties going to the even multiple (so $42.50 → $40, $127.50 → $130). Cross-check against OCR of the upgrade panel. Ninja Kiwi rebalances often, so stamp the game version on the data.
- **Sell value:** 70% of money spent by default (more with some upgrades/villages). The harness tracks money spent per tower.
- **Placement:** while a tower is held, an invalid spot tints the range circle red. That's how the per-map placeable mask is calibrated. Land, water and both-type towers need separate masks.
- **Ranges:** base range per tower plus upgrade modifiers. A selected tower shows its circle, which can be measured to verify.
- **Heroes:** level up from XP each round. The upgrade panel lets you buy levels with money.
- **Abilities:** these show in an ability bar with cooldown overlays. Some need a target point.
- **Configurable towers:** Ace (flight pattern, centered path), Heli (lock/pursuit/patrol points), Mortar / Dartling / Sniper Elite targeting (target point), Spike Factory (placement target), plus the general targeting modes First/Last/Close/Strong.
- **Removable obstacles:** click the obstacle → a panel shows the removal cost → confirm. Varies per map.
- **Round flow:** the start button becomes fast-forward while a round is running, which is how round end is detected. Auto-start is a Settings toggle. Victory and defeat screens are template-matched.
- **Popups to handle:** level-up, insta-monkey / reward collection, "continue to freeplay?", confirm dialogs, event/collection notices.

## Findings log
- 2026-11-03: Initial research. No direct confirmation found of hotkey support in BTD6+ Mac. A Steam user reported hotkeys working on a MacBook Air, but that was the Steam build ([thread](https://steamcommunity.com/app/960090/discussions/0/5226999188079746942)).
- 2026-11-03: The Bloons Wiki keeps tower, upgrade and hero data in Cargo tables that `api.php?action=cargoquery` can read without a login (`Special:CargoExport` is behind Cloudflare). `scripts/fetch_wiki_data.py` builds `bloons/data/towers.json` and `heroes.json` from them. The tables have no range, footprint, land/water, ability, hero level-cost or round data. The wiki's cost module (`Module:BTD6_costs`) rounds ties to the even multiple of $5, which matches Python `round(x/5)*5` exactly. The data covers 26 towers including Skywarden ($205); Monkey Academy is listed with no cost and is skipped.
- 2026-11-04 — **Phase 0 gate passed: BTD6+ (57.4) accepts synthetic CGEvent input.** Results from `scripts/feasibility_mac.py` and follow-up checks in a Monkey Meadow sandbox:
  - Click via `CGEventPost(kCGHIDEventTap)`: YES. Placed a held Dart Monkey; Dom confirmed.
  - Click via `CGEventPostToPid`: YES. Placed a held Dart Monkey; Dom confirmed.
  - Key via `CGEventPostToPid`: YES. `Q` selected the Dart Monkey (checked against before/after screenshots).
  - Key via HID tap: YES. `Esc` opened the pause menu. (`Q` via HID wasn't isolated cleanly: it was sent while the monkey was already held.)
  - The HID tap moves the real cursor, so the user can't use the mouse while the bot runs. PostToPid might avoid that; check this in step 1.1.
  - Keys sent by HID go to the frontmost app. Bring the game to the front *after* any terminal interaction, or the key lands in the terminal.
  - Esc toggles pause; it doesn't cancel a held tower. The red ✕ to the left of the shop's tower-name label cancels.
  - Window: the game runs windowed or full screen; seen at 1470×988 and 1470×830 pt. `kCGWindowListOptionAll` + largest layer-0 window finds it in either mode. The mss capture of the window rect came out at 1 px per point on this Retina Mac, and the rect includes the 33 pt title bar. The calibration window size is still to be decided (step 0.4).
  - Accessibility permission is granted to the host app (VS Code here). `CGPreflightPostEventAccess()` reports it, and it took effect without relaunching VS Code.
- 2026-11-04 — **Hotkey sweep (step 0.3).** See the hotkey table: all 24 bound tower/hero keys, the upgrade keys, Sell, Tab and Pause work through `CGEventPostToPid` (no need to take over the cursor for keys). Other findings:
  - Clicking right after a tower key can be ignored. One placement failed when Q and the click came back to back; with ~0.5 s between key and click it worked. The harness should wait, or confirm the held tower is showing before clicking.
  - Placing a tower: tower key → click a map spot. Clicking a placed tower opens the upgrade panel on the **left** side of the window (it shows the 3 paths with prices, the targeting mode, and the sell value). The upgrade keys and Sell act on the selected tower.
  - A closed path ("PATH CLOSED", the crosspath rule) silently ignores its upgrade key.
  - Water towers (Sub, Buccaneer) held over land show a red-tinted range circle, which confirms the placement-mask approach.
  - The shop list scrolls; hotkeys select towers that are scrolled out of view.
  - Settings → Hotkeys lists every binding and scrolls with wheel events (`CGEventCreateScrollWheelEvent` via HID).
- 2026-11-04 — **Standard game follow-up (Monkey Meadow, Easy).** Space starts the round and toggles fast-forward. **Synthetic modifier combos don't work:** Ctrl+Tab did nothing via either method, sent either as a flagged event or as a real Ctrl down → Tab → Ctrl up. Worse, flagged combos can leave the game thinking Ctrl is held, which made plain Tab stop working until an explicit Ctrl key-up (keycode 59, flags 0) was sent. The harness should avoid modifier hotkeys, use the UI instead, and send a Ctrl/Shift key-up at startup as a safety reset.
  - The upgrade panel opens on the **opposite side** of the screen from the selected tower: on the left for a tower on the right half, and on the right (next to the shop) for a tower on the left half. Vision has to find the panel; it can't use a fixed region.
  - Targeting can also be changed with the ◀ ▶ arrows on either side of the targeting label in the panel.
- 2026-11-04 — **Capture + OCR benchmark (step 0.4)**, `scripts/bench_capture_ocr.py`, MacBook Air M3, windowed 1470×830 pt:
  - mss full-window grab: median 21 ms (~47 FPS). HUD-box grab: 17 ms (the fixed per-call overhead dominates, so a grab costs about the same at any size).
  - **HUD OCR: Apple Vision (`VNRecognizeTextRequest`, accurate, language correction off)** reads lives / money / round correctly (`178`, `$1,552`, `8/40`, checked against the screenshot) in a median of 16 ms per field. That holds even under the dimmed pause overlay. Vision *fast* mode returned nothing useful. Tesseract 5.5 (`--psm 7`, digit whitelist) took 55 ms per field via the CLI and misread two of the three (`''` for money, `8740` for `8/40`). **Decision: Vision accurate.** One grab plus 3 fields ≈ 70 ms, so the HUD can be read about 14×/s, far more than a decision loop needs.
  - Capture is at 1 px per point (not Retina 2×); Vision copes with that fine.
  - HUD boxes (window pt, title bar included, 1470×830): lives (125,42)-(200,84), money (280,42)-(445,84), round (1100,52)-(1182,88). These belong in `data/ui.json` in step 1.3.
  - **The game seems to pause itself when it loses focus.** It was on the pause menu when Claude brought it to the front after Dom's session. The harness should keep the game frontmost during a run and check for the pause menu (close it with Esc) before acting.

