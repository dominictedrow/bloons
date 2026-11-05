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
- 2026-11-04 — **Standard game follow-up (Monkey Meadow, Easy).** Space starts the round and toggles fast-forward. **Synthetic modifier combos don't work:** Ctrl+Tab did nothing via either method, sent either as a flagged event or as a real Ctrl down → Tab → Ctrl up. Worse, flagged combos can leave the game thinking Ctrl is held, which made plain Tab stop working until an explicit Ctrl key-up (keycode 59, flags 0) was sent. The harness should avoid modifier hotkeys and use the UI instead. (The key-up reset idea was wrong; see the platform-layer entry below.)
  - The upgrade panel opens on the **opposite side** of the screen from the selected tower: on the left for a tower on the right half, and on the right (next to the shop) for a tower on the left half. Vision has to find the panel; it can't use a fixed region.
  - Targeting can also be changed with the ◀ ▶ arrows on either side of the targeting label in the panel.
- 2026-11-04 — **Capture + OCR benchmark (step 0.4)**, `scripts/bench_capture_ocr.py`, MacBook Air M3, windowed 1470×830 pt:
  - mss full-window grab: median 21 ms (~47 FPS). HUD-box grab: 17 ms (the fixed per-call overhead dominates, so a grab costs about the same at any size).
  - **HUD OCR: Apple Vision (`VNRecognizeTextRequest`, accurate, language correction off)** reads lives / money / round correctly (`178`, `$1,552`, `8/40`, checked against the screenshot) in a median of 16 ms per field. That holds even under the dimmed pause overlay. Vision *fast* mode returned nothing useful. Tesseract 5.5 (`--psm 7`, digit whitelist) took 55 ms per field via the CLI and misread two of the three (`''` for money, `8740` for `8/40`). **Decision: Vision accurate.** One grab plus 3 fields ≈ 70 ms, so the HUD can be read about 14×/s, far more than a decision loop needs.
  - Capture is at 1 px per point (not Retina 2×); Vision copes with that fine.
  - HUD boxes (window pt, title bar included, 1470×830): lives (125,42)-(200,84), money (280,42)-(445,84), round (1100,52)-(1182,88). These belong in `data/ui.json` in step 1.3.
  - **The game seems to pause itself when it loses focus.** It was on the pause menu when Claude brought it to the front after Dom's session. The harness should keep the game frontmost during a run and check for the pause menu (close it with Esc) before acting.
- 2026-11-04 — **Platform layer (step 1.1) findings.** These correct some earlier entries:
  - **Correction to the Ctrl+Tab entry above: never send any modifier event.** A lone Ctrl, Shift, Cmd or Option key-up, sent via PostToPid with flags 0, makes BTD6+ ignore every plain hotkey afterwards. (Tab "recovering" earlier was probably luck.) The only reliable recovery found is **losing and regaining focus**: activate Finder, then the game. `Game.refocus()` does this.
  - **Input needs the game to be the active app.** With Finder active, PostToPid keys and clicks did nothing (the game kept running). Capture, though, works in the background.
  - **Background capture:** `CGWindowListCreateImage(kCGWindowListOptionIncludingWindow, wid)` returns the game window while it's covered or behind other apps, at **2× Retina (2940×1660 px for 1470×830 pt)**, in ~40–60 ms. That beats mss, which grabs whatever is on screen at 1 px/pt. The API is deprecated; ScreenCaptureKit is the fallback if it's removed.
  - **Detecting the active app:** `NSWorkspace.frontmostApplication()` goes stale in a script with no run loop, so spin `NSRunLoop` for 10 ms first. The on-screen window order is *not* a valid proxy: activating Finder (no windows) leaves the game's window on top.
  - **Stage Manager is on on this Mac.** Activating the game can slide its window in from off-screen; bounds read mid-animation were (−120, 33) and (1554, 33). `ensure_front()` waits until the bounds stop changing (~330 ms total from the background, ~1 ms if already in front).
  - Vision OCR needs a model load on its first call (~400 ms); after that it's ~15 ms per field on 2× crops. The round box was widened to x 1050 so two-digit rounds (`12/40`) fit.
  - The game does **not** pause itself on focus loss. The earlier "found paused" was the Esc sent by the feasibility script.
  - Defeat screen: "DEFEAT", round reached, Bloons Leaked, with buttons Home / Restart / Review Map / Continue ($100). Restart asks for confirmation (Cancel / Restart). Fixtures are saved in `bloons/data/fixtures/`.
- 2026-11-04 — **Fixture collection (step 1.2)**, from a scripted Easy run on Monkey Meadow:
  - **When the upgrade panel opens on the right, the round counter moves left**, to about x 810–880 pt instead of 1100–1180. HUD OCR must either read the HUD with the panel closed or know about the shifted position. With the panel on the left, lives and money move right instead (`upgrade_panel_left.png`).
  - **Game hint banner:** with "Game Hints" on, a blue tip banner appears at the bottom centre of the map for a few seconds. It may block clicks there. Consider turning hints off in Settings for bot runs.
  - Unaffordable towers show a red price and a greyed icon in the shop, which gives a free affordability signal.
  - **Screen lock / display sleep:** the Mac locked mid-run because Dom closed the lid (not an idle timeout; correction from Dom). While locked, window capture returns solid white and input is ignored. `Game.screen_locked()` makes `grab()` return None and `ensure_front()` return False, so the bot stops instead of acting blind. Runs need the lid open. `caffeinate -dis` is harmless but optional.
  - A simple scripted build held Easy Monkey Meadow at 200 lives through at least round 35: 2 Dart, Tack 3-0-1, Ninja 3-0-1, Bomb 0-4-0, Super 2-0-0.
  - Menus: Home → Play (map grid, paged) → map → difficulty (Easy/Medium/Hard) → mode (Standard / Primary Only / Deflation / Sandbox) → game. The home and difficulty screens show player names, so they aren't saved as fixtures (the repo is on GitHub).

- 2026-11-04 — **Victory screen (step 1.2 finish)**, Monkey Meadow Easy, two more wins with the same scripted build (185 and 200 lives):
  - **The HUD stays readable behind the victory screen.** Lives, money and round (`40/40`) still OCR correctly through the dimmed overlay, so "round unreadable" does **not** detect the end of a game. Detect victory by template-matching the banner (`fixtures/victory_banner.png`), or by "round 40/40 and the play button is not ▶▶".
  - The overlay appears about 10 s after round 40's last bloon pops (on fast-forward). It shows "VICTORY", a stats card **with the player name** (so only the banner and the Next button are committed as crops), and a single **Next** button at about (0.50, 0.84) in content coordinates. What follows Next hasn't been captured yet (in handoff 011 the collection-event popup followed).
  - The mode screen lists $22 Monkey Money for an Easy Standard win; the home balance went $4,880 → $4,904 across the first win (source of the extra $2 unknown).
  - Menu click points (content coords, windowed 1470×830): Home Play (0.50, 0.872); Monkey Meadow tile, page 1 Beginner (0.2875, 0.235); Easy (0.3325, 0.374); Standard (0.336, 0.544). The map takes ~10 s to load.

- 2026-11-04 — **HUD OCR parsing (step 1.3)**, `bloons/hud.py`, checked on every fixture frame:
  - Vision reads clean HUDs exactly (`200`, `$1,357`, `39/40`). The padded round crop also picks up the "ROUND" label as a low-confidence junk line in Latin or Cyrillic look-alikes (`KOMID`, `КОМПВ`). The parser keeps only a well-formed `N/M` token.
  - **Upgrade panel open = HUD partly unreadable at the ui.json boxes.** Panel on the left: money reads `20` (no `$`, clipped) and lives read nothing. Panel on the right: round reads `TINYN`. Requiring the `$` and a valid `N/M` turns all of these into None rather than wrong numbers. Read the HUD with the panel closed, or rely on `HudFilter` holding the last good value.
  - Defeat screen and restart confirm: lives read nothing, while money and round still read. Menus and the collection popup read nothing at all.
  - Across all 17 full frames, the parser returned no wrong value: each field was either correct or None.
  - Open: how the HUD shows freeplay rounds past 40 (whether it's still `N/M`). Not captured yet.

- 2026-11-04 — **Template matching (step 1.4)**, `bloons/vision.py` + `data/templates.json`, 14 templates and 17 test frames:
  - Matching runs on the content area resized to 735 px wide (TM_CCOEFF_NORMED, BGR, within the box ± 0.02, or an explicit search box). Matches score 0.965–1.00 and non-matches at most 0.61 (`menu_map_select` against the mode screen), so every threshold is 0.8. Caveat: most matches are a template against its own source frame. Real generalization so far is shown only by `btn_ff` (0.98 on 9 other frames) and `sell_button` (cut from the right-hand panel, 0.99 on the left-hand one). Check live in 1.5.
  - **Fast-forward on vs off differs only in colour**: the green lightens from BGR (76, 227, 137) to (76, 236, 152). Normalized matching can't see that, so a colour probe on the button classifies idle (9, 224, 97) / ff_off / ff_on within distance 2.5. Only **one** ff_off frame exists so far: confirm live in 1.5.
  - **Overlays dim the play button, but the match ignores brightness**: under victory or pause, `btn_play` still scores 1.00. The probe returns None there (distance ≥ 98), so `button_state()` is None. Outcome detection must check the victory/defeat/popup templates first, not the button.
  - `defeat_buttons` scores 0.78 behind the restart-confirm popup, just under the threshold. Check `restart_confirm` before `defeat_*`.
  - The one `sell_button` template finds the upgrade panel on either side, and its match centre gives the side. `victory_next` centres at (0.50, 0.84), matching the click point measured by hand.
  - Defeat screen HUD: lives show a dimmed `0` that Vision doesn't read (so `lives=None`).
  - Speed per 2× frame: `Frame.content_bgr()` 37 ms (Quartz redraw at full size), resize 6 ms, all 14 templates + probe 7 ms. Drawing straight to work size would cut the first part if it ever matters.
  - Test frames are committed as JPEG q90 (1.45 MB for 17 instead of 6.5 MB as PNG; worst match 0.965, probe distance ≤ 2.6). The victory stats card (player name) is greyed out.

- 2026-11-04 — **Round state + outcome (step 1.5)**, `bloons/state.py`, offline:
  - `read_screen()` classifies all 17 test frames correctly: game (with button state and upgrade panel side), pause, victory, defeat, restart confirm, collection event, map select, mode select. The overlay order (restart confirm → victory → defeat → collection → pause → menus → button) handles both the dimmed play button still matching and the defeat screen behind the restart popup.
  - **Auto-start is passed in explicitly** (`RoundTracker(auto_start=...)`). With it off, a round ends when the button goes running → idle. With it on, the button never goes idle, so a round ends when the HUD round number goes up. Inferring auto-start from timing was dropped because a lagging HUD read would fire a false `round_ended`.
  - Assumption still to check live: the HUD round counter shows the next round to play and goes up when a round ends (`1/40` at idle before round 1 is consistent with that).

- 2026-11-04 — **Live check of 1.5**: one scripted Easy Monkey Meadow game (scratch driver + `scripts/watch_state.py` alongside), 1,516 driver loops and 2,611 watcher loops, launched from a cold start:
  - **Templates generalize to fresh frames.** The lowest match was `btn_ff` at 0.98. The menus scored ≥ 0.999, `defeat_title` 0.996, `defeat_buttons` 0.988, `pause_title` 1.0, and `sell_button` caught the upgrade panel on both sides (24 left, 32 right). The highest non-match anywhere was 0.599 (`btn_play` on ▶▶). Not yet seen live: victory, restart confirm, collection popup.
  - **The FF colour probe holds**: ff_off / ff_on / idle all classified correctly through toggles. A manual start with Space runs at normal speed (`ff_off`).
  - **HUD round counter timing.** With auto-start on, it goes up when the next round starts, and the button shows idle ▶ for about 1 s between rounds. With auto-start off, it goes up when the player starts the next round: at idle after round 5 it still reads `5/40`. Before round 1 it reads `1/40`. `round_ended` fired exactly once for each of rounds 1–29 across both modes. The HUD round at the moment it fires differs by mode, though (auto: the new round; manual: the round that just ended). The harness should count completions itself rather than trust that number.
  - **Bug found and fixed: `HudFilter` froze money.** During a round, money changes on almost every read (pop income), so exact two-read confirmation never succeeded. Money stuck at $356 for several rounds, the driver "bought" 10 upgrades it couldn't afford, and the weakened build lost at round 30. The fix: for money, two consecutive reads agreeing within max($20, 10%) is enough, and an agreeing run keeps tracking every read (regression test from the live values).
  - **The play button can glow brighter than any probe class**: BGR (109, 241, 172), one frame. `read_screen` now returns `game` with `button=None` when the ▶/▶▶ shape matches but the colour doesn't (before, it returned `unknown`).
  - **FF switched itself on twice** (20:12:04 in round 2 and 20:21:22 in round 21) with no script input; the visual change from dark to bright ▶▶ is real. Cause unknown; ask Dom whether he clicked it. The harness shouldn't assume FF stays where it was set: read `button_state` before toggling.
  - The defeat screen animates in: 2 `unknown` frames, then `defeat`, confirmed as `loss` on the 2nd frame. On the defeat screen, lives read nothing.
  - The **auto-start toggle** in the pause menu is at (0.70, 0.285) (now `ui.json` `buttons.pause_auto_start_toggle`). Turning it off and back on was checked in frames, so Dom's setting is unchanged. Esc closes the pause menu.
  - Whatever runs `RoundTracker` must know the auto-start setting: the watcher assumed it was off and so only counted the 5 manual rounds. `watch_state.py` now defaults to auto-start on.
