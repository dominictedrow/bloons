"""BloonsHarness: the action/observation surface for a person or an RL loop (PLAN Phase 4).

Portable: `game` is anything with platform_mac.Game's methods (grab, read_hud, click, move,
key, scroll), so offline tests pass a fake. Coordinates are normalized content coords.

Step 4.1 is the skeleton the actions build on:
- data: towers / heroes / account / ui.json, the map file (scale, path keep-out) and its
  learned-spots memory (<map>.spots.json);
- the tower registry (guards.TowerRec per tid, plus the hero) and what the game has seen
  bought this episode;
- `guard_state()` / `place_context()` / `available_actions()` for guards.py and
  placement.can_place (Dom's action mask is built from `available_actions`);
- input: `press(action)` uses a confirmed hotkey (ui.json `hotkeys`, towers.json `hotkey`)
  or else clicks the UI point; `select_shop(kind)` picks a tower or the hero from the shop,
  scrolling it for the towers without a hotkey.

Actions (4.2+) call their guard first and return its refusal unchanged, without touching the
game, and return ActionResult rather than raising on game-side failures.
"""
import json
import time
from pathlib import Path

from . import guards, ui
from .hud import HudFilter
from .placement import (PathKeepout, PlaceContext, Placed, SpotMemory, can_place, record_placement,
                        tint_at, unit_norm)
from .result import ActionResult

DATA = Path(__file__).parent / "data"
SCROLL_LINES = 200        # past the shop's full length (~30 events x 5 lines, RESEARCH 3.1)
HERO_TID = "hero"         # the hero's id in place contexts and can_sell
PARK = (0.92, 0.5)        # cursor rest point over the shop: off the map, for the before-hold frame
SETTLE_S = 0.08           # after moving a held tower: the tint follows within ~20 ms (3.2)
CONFIRM_TRIES = 4         # HUD reads to see the money change after placing / selling


def _read_panel(frame):
    from .state import read_screen
    return None if frame is None else read_screen(frame).panel


def _read_kind(frame):
    from .state import read_screen
    return None if frame is None else read_screen(frame).kind


def _read_button(frame):
    from .vision import button_state
    return None if frame is None else button_state(frame)


def _read_probe(name):
    def read(frame):
        from .vision import probe
        return None if frame is None else probe(frame, name).label
    return read


def _icon_diff(a, b):
    import numpy as np
    if a is None or b is None or a.shape != b.shape or a.size == 0:
        return 0.0
    return float(np.abs(a.astype(np.int16) - b.astype(np.int16)).mean())


def _load(name):
    return json.loads((DATA / name).read_text())


class BloonsHarness:
    def __init__(self, game, map_name, difficulty="easy", hero=None, account=True, sleep=time.sleep,
                 spots_path=None, mode="standard"):
        """`mode`: 'standard' or 'sandbox' (rounds are sent from the Sandbox bloon panel).
        `hero`: heroes.json key chosen for this game (placeable once), or None.
        `account`: apply data/account.json Monkey Knowledge to prices (False = none).
        `sleep`: injectable for tests. `spots_path`: learned-spots file (default
        data/maps/<map>.spots.json; tests and trial runs point it elsewhere)."""
        if mode not in ("standard", "sandbox"):
            raise ValueError(mode)
        self.game = game
        self.mode = mode
        self.map_name = map_name
        self.difficulty = difficulty
        self.hero_choice = hero
        self.sleep = sleep
        self.ui = ui.UI
        self.towers = _load("towers.json")["towers"]
        self.heroes = _load("heroes.json")["heroes"]
        ha = _load("hero_abilities.json")
        self.hero_abilities, self.default_cooldown = ha["heroes"], ha["_meta"]["default_cooldown_s"]
        self.clock = time.monotonic     # ability cooldown estimates; tests swap it
        self.account = _load("account.json") if account else None
        if hero is not None and hero not in self.heroes:
            raise KeyError(hero)
        self.map = _load(f"maps/{map_name}.json")
        self.unit = unit_norm(self.map)
        self.keepout = PathKeepout.from_json(self.map["path"], self.unit) if "path" in self.map else None
        self.memory = SpotMemory.load(spots_path or DATA / "maps" / f"{map_name}.spots.json")
        if not self.memory.meta:
            self.memory.meta = {"map": map_name, "game_version": self.map["_meta"]["game_version"]}
        self.hud = HudFilter()
        self.tint = tint_at       # (base, held, x, y) -> 'ok' | 'blocked' | 'none'; tests swap it
        self.read_panel = _read_panel   # content frame -> 'left' | 'right' | None; tests swap it
        self.read_kind = _read_kind     # content frame -> state.Screen kind ('game', 'pause', ...)
        self.read_button = _read_button  # -> 'idle' / 'ff_off' / 'ff_on' / None
        self.read_auto_start = _read_probe("auto_start_toggle")   # pause menu -> 'on' / 'off' / None
        self.read_sandbox_panel = _read_probe("sandbox_panel")    # -> 'shop' / 'bloons' / None
        self.icon_diff = _icon_diff     # (before, after) slot crops -> mean |diff|; tests swap it
        self.read_targeting = self._ocr_targeting   # panel side -> label text ('' if none)
        self.prompt_actions = {k: v for k, v in self.ui["prompts"].items()
                               if not k.startswith("_") and k not in ("max_steps", "after_click_s")}
        self.auto_start = None        # the game's Auto Start setting once read (a setting, not per game)
        self.new_episode()

    # --- episode state ----------------------------------------------------------------------
    def new_episode(self):
        """Forget everything about the current game (call when a new game starts)."""
        self.registry = {}            # tid -> guards.TowerRec
        self.hero = None              # guards.HeroRec once placed
        self.bought = set()           # tower kinds bought at least once this game
        # Ability bar slots in order of first gain. The game groups identical abilities into one
        # icon (with a ready-count badge), so a slot is an ability name with its instances:
        # {name, cooldown, between_rounds, inst: {(tid, path): ready_at}}.
        self.ability_slots = []
        self.round_active = False     # Standard: set by start_round; the round loop clears it
        self.fast_forward = None      # last FF state read or set
        self.locked = set()          # tower kinds not available (mode / unlocks)
        self.shop_layout = None       # 'top' / 'bottom' once we've scrolled the shop
        self._next_tid = 1
        self.hud.reset()

    @property
    def money(self):
        """Last accepted HUD money, or None before the first good read."""
        return self.hud.current.money

    def refresh_hud(self, frame=None):
        """Read the HUD once and feed the filter -> the smoothed Hud."""
        return self.hud.update(self.game.read_hud(frame))

    # --- registry ---------------------------------------------------------------------------
    def register(self, kind, xy, spent):
        """Record a tower we placed -> its tid."""
        if kind not in self.towers:
            raise KeyError(kind)
        tid = self._next_tid
        self._next_tid += 1
        self.registry[tid] = guards.TowerRec(tid, kind, tuple(xy), (0, 0, 0), int(spent))
        self.bought.add(kind)
        return tid

    def register_hero(self, xy, spent):
        if self.hero_choice is None:
            raise ValueError("no hero chosen for this game")
        self.hero = guards.HeroRec(self.hero_choice, tuple(xy), 1, 0, int(spent))
        self._gain_hero_abilities(1)
        return HERO_TID

    def record_upgrade(self, tid, path, price):
        t = self.registry[tid]
        tiers = list(t.tiers)
        tiers[path] += 1
        t.tiers, t.spent = tuple(tiers), t.spent + int(price)
        for a in (self.towers[t.kind].get("stats") or {}).get("abilities") or []:
            if a["path"] == path and a["tier"] == tiers[path]:
                self._gain_ability(tid, a["name"], a.get("cooldown"), a.get("between_rounds", True), path)

    def unregister(self, tid):
        """Forget a sold tower (or the hero, tid 'hero')."""
        if tid == HERO_TID:
            self.hero = None
        else:
            self.registry.pop(tid)
        self._drop_abilities(lambda key: key[0] == tid)

    # --- contexts for guards / placement ----------------------------------------------------
    def guard_state(self):
        """guards.GuardState from what the harness knows now. Unknown money counts as $0, so
        nothing that costs money is offered until the HUD has been read."""
        return guards.GuardState(
            money=self.money or 0, difficulty=self.difficulty, towers=self.towers, heroes=self.heroes,
            account=self.account, registry=self.registry, hero=self.hero, hero_choice=self.hero_choice,
            bought=self.bought, abilities=self.abilities, round_active=self.round_active, locked=self.locked)

    # --- abilities (bar order = the order they were gained) ---------------------------------
    def _gain_ability(self, tid, name, cooldown, between_rounds=True, path=None):
        """A tower tier or hero level added an activated ability. A tower's later tier on the
        same path (e.g. Turbo -> Perma Charge) replaces its earlier one. New abilities start
        on cooldown (seen live, step 4.5)."""
        if path is not None:
            self._drop_abilities(lambda key: key == (tid, path))
        cd = float(cooldown) if cooldown else float(self.default_cooldown)
        slot = next((a for a in self.ability_slots if a["name"] == name), None)
        if slot is None:
            slot = {"name": name, "cooldown": cd, "between_rounds": bool(between_rounds), "inst": {}}
            self.ability_slots.append(slot)
        slot["inst"][(tid, path)] = self.clock() + cd

    def _drop_abilities(self, match):
        for a in self.ability_slots:
            a["inst"] = {k: v for k, v in a["inst"].items() if not match(k)}
        self.ability_slots = [a for a in self.ability_slots if a["inst"]]

    def _gain_hero_abilities(self, level):
        for a in self.hero_abilities.get(self.hero_choice) or []:
            if a["level"] == level:
                self._gain_ability(HERO_TID, a["name"], a["cooldown_s"])

    @property
    def abilities(self):
        """[guards.Ability] in bar order. `ready` is an estimate from the cooldown (game seconds
        counted as wall seconds: conservative with fast-forward on) until the bar is read
        from pixels (step 5.4)."""
        now = self.clock()
        return [guards.Ability(i, a["name"], any(now >= t for t in a["inst"].values()), a["between_rounds"],
                               next(iter(a["inst"]))[0])
                for i, a in enumerate(self.ability_slots)]

    def place_context(self):
        placed = [Placed(t.kind, t.xy, t.tiers, t.tid) for t in self.registry.values()]
        if self.hero is not None:
            placed.append(Placed(self.hero.name, self.hero.xy, tid=HERO_TID))
        return PlaceContext(self.towers, self.unit, placed, self.keepout, self.memory, self.heroes)

    def available_actions(self):
        """Legal actions right now with their costs (guards.available_actions)."""
        return guards.available_actions(self.guard_state())

    # --- input ------------------------------------------------------------------------------
    def key_for(self, action, path=None):
        """The confirmed hotkey for `action` ('hero', 'upgrade' + path, 'sell', 'play_ff', ...,
        or a towers.json key), or None if there isn't one (then click the UI point)."""
        if action in self.towers:
            k = self.towers[action].get("hotkey")
            return k.lower() if k else None
        k = self.ui["hotkeys"].get(action)
        if isinstance(k, list):
            return k[path] if path is not None and path < len(k) else None
        return k

    def press(self, action, xy=None, path=None, wait=None):
        """Hotkey if confirmed, else click `xy`. ok=False with 'no_input' if neither exists,
        'not_front' if the game didn't take the input."""
        k = self.key_for(action, path)
        if k is not None:
            sent = self.game.key(k)
        elif xy is not None:
            sent = self.game.click(*xy)
        else:
            return ActionResult(False, "no_input")
        if not sent:
            return ActionResult(False, "not_front")
        self.sleep(self.ui["timing_s"]["after_click"] if wait is None else wait)
        return ActionResult(True, action)

    def select_shop(self, kind):
        """Pick up a tower (towers.json key) or the hero ('hero') from the shop. Uses the
        hotkey when there is one; otherwise scrolls the shop to the layout showing it and
        clicks its cell."""
        if kind != "hero" and kind not in self.towers:
            return ActionResult(False, "unknown_tower")
        wait = self.ui["timing_s"]["after_tower_key"]
        if self.key_for(kind) is not None:
            return self.press(kind, wait=wait)
        if self.mode == "sandbox":
            r = self.sandbox_panel("shop")      # a new Sandbox opens on the bloon panel
            if not r:
                return r
        layout, xy = ui.shop_cell(kind)
        if layout != self.shop_layout:
            sx, sy = self.ui["shop"]["scroll_point"]
            if not self.game.scroll(sx, sy, SCROLL_LINES if layout == "top" else -SCROLL_LINES):
                return ActionResult(False, "not_front")
            self.shop_layout = layout
            self.sleep(0.5)
        if not self.game.click(*xy):
            return ActionResult(False, "not_front")
        self.sleep(wait)
        return ActionResult(True, kind)

    def content(self):
        """The current content-area frame (BGR), or None if it can't be captured."""
        f = self.game.grab()
        return None if f is None else f.content_bgr()

    def cancel_hold(self):
        """Drop a held tower with the cancel button (not Escape: with nothing held, Escape
        opens the pause menu)."""
        return self.press("cancel_placement", xy=tuple(self.ui["buttons"]["cancel_placement"]))

    def _hud_money(self):
        """One raw HUD money read (also fed to the filter); if unreadable, the filter's last
        accepted value (may be None)."""
        r = self.game.read_hud()
        self.hud.update(r)
        return r.money if r.money is not None else self.money

    def _money_moved(self, before, delta):
        """Wait for the HUD money to move by about `delta` (< 0 spent, > 0 refund) from
        `before`. Pop income can come in meanwhile, so half the amount counts."""
        for _ in range(CONFIRM_TRIES):
            m = self._hud_money()
            if m is not None and before is not None and (m - before) * (1 if delta > 0 else -1) >= abs(delta) / 2:
                return True
            self.sleep(0.15)
        return False

    # --- 4.2 placing and selling ------------------------------------------------------------
    def _place(self, shop_key, kind, x, y, price):
        """Hold `shop_key` from the shop over (x, y), read the tint once, and click if it's ok.
        -> ActionResult (ok = placed; the caller registers it)."""
        ctx = self.place_context()
        p = can_place(kind, x, y, ctx)
        if not p:
            return p
        before = self._hud_money()
        if not self.game.move(*PARK):
            return ActionResult(False, "not_front")
        self.sleep(0.2)
        base = self.content()
        tint = "none"
        for _ in range(2):                       # a dropped hold reads 'none': pick it up again
            r = self.select_shop(shop_key)
            if not r:
                return r
            self.game.move(x, y)
            self.sleep(SETTLE_S)
            tint = self.tint(base, self.content(), x, y)
            if tint != "none":
                break
        if tint != "ok":
            self.cancel_hold()
            if tint == "blocked":
                record_placement(ctx, kind, x, y, False)
                return ActionResult(False, "blocked", price)
            return ActionResult(False, "no_hold", price)
        if not self.game.click(x, y):
            return ActionResult(False, "not_front")
        self.sleep(self.ui["timing_s"]["after_click"])
        if not self._money_moved(before, -price):
            # The money didn't drop: not placed. If the tower is still held, the spot refused it.
            still = self.tint(base, self.content(), x, y)
            if still != "none":
                self.cancel_hold()
                record_placement(ctx, kind, x, y, False)
                return ActionResult(False, "blocked", price)
            return ActionResult(False, "unconfirmed", price)
        record_placement(ctx, kind, x, y, True)
        return ActionResult(True, "placed", price)

    def place_tower(self, kind, x, y):
        """Buy a `kind` tower and place it at (x, y). ok -> value is the new tid.
        Refusals: the guard's ('no_money', 'unknown_tower'), can_place's ('off_map', 'path',
        'overlaps_tower:<tid>', 'memory_blocked', ...), or 'blocked' (the tint said no; the
        spot is remembered), 'no_hold', 'unconfirmed', 'not_front'."""
        g = guards.can_buy_tower(kind, self.guard_state())
        if not g:
            return g
        r = self._place(kind, kind, x, y, g.cost)
        if not r:
            return r
        return ActionResult(True, "placed", g.cost, self.register(kind, (x, y), g.cost))

    def place_hero(self, x, y):
        """Place the hero chosen for this game at (x, y). ok -> value 'hero'."""
        g = guards.can_place_hero(self.guard_state())
        if not g:
            return g
        r = self._place("hero", self.hero_choice, x, y, g.cost)
        if not r:
            return r
        return ActionResult(True, "placed", g.cost, self.register_hero((x, y), g.cost))

    def select_tower(self, tid):
        """Click a placed tower (or the hero) to open its panel."""
        t = self.hero if tid == HERO_TID else self.registry.get(tid)
        if t is None:
            return ActionResult(False, "no_tower")
        if not self.game.click(*t.xy):
            return ActionResult(False, "not_front")
        self.sleep(self.ui["timing_s"]["after_click"])
        return ActionResult(True, "selected")

    def sell(self, tid):
        """Sell a tower (or the hero, tid 'hero'): select it, then the sell key. ok -> cost is
        the refund as a negative number."""
        g = guards.can_sell(tid, self.guard_state())
        if not g:
            return g
        before = self._hud_money()
        r = self.select_tower(tid)
        if not r:
            return r
        r = self.press("sell", xy=tuple(self.ui["upgrade_panel"]["left"]["sell"]))
        if not r:
            return r
        if not self._money_moved(before, -g.cost):
            return ActionResult(False, "unconfirmed", g.cost)
        self.unregister(tid)
        return ActionResult(True, "sold", g.cost)

    # --- 4.3 upgrades -----------------------------------------------------------------------
    def panel_side(self, tries=3):
        """Which side the selection panel is open on ('left' / 'right'), or None."""
        for _ in range(tries):
            side = self.read_panel(self.content())
            if side:
                return side
            self.sleep(0.15)
        return None

    def close_panel(self, side):
        return self.press("close_panel", xy=tuple(ui.panel(side)["close"]))

    def _panel_buy(self, tid, guard, press):
        """Select `tid`, find its panel, run `press(side)`, confirm the money drop on the HUD,
        close the panel. -> ActionResult (ok = paid)."""
        before = self._hud_money()
        r = self.select_tower(tid)
        if not r:
            return r
        side = self.panel_side()
        if side is None:
            return ActionResult(False, "no_panel", guard.cost)
        r = press(side)
        self.close_panel(side)          # first: a panel on the left covers the HUD money
        if not r:
            return r
        ok = self._money_moved(before, -guard.cost)
        return ActionResult(ok, "bought" if ok else "unconfirmed", guard.cost)

    def upgrade(self, tid, path):
        """Buy the next tier on `path` (0-2) for tower `tid`: guard (crosspath, tier <= 5, one
        tier 5 per path per type, money), then the path's hotkey with the panel open.
        ok -> value is the tower's new tiers."""
        g = guards.can_upgrade(tid, path, self.guard_state())
        if not g:
            return g
        r = self._panel_buy(tid, g, lambda side: self.press(
            "upgrade", xy=tuple(ui.panel(side)["path_buttons"][path]), path=path))
        if not r:
            return r
        self.record_upgrade(tid, path, g.cost)
        return ActionResult(True, "upgraded", g.cost, self.registry[tid].tiers)

    def buy_hero_level(self):
        """Buy the hero's next level with the panel's level-up button. ok -> value is the new
        level. (The harness assumes no XP earned toward it, so the guard's price is an upper
        bound; the HUD confirms what was paid.)"""
        g = guards.can_buy_hero_level(self.guard_state())
        if not g:
            return g
        r = self._panel_buy(HERO_TID, g, lambda side: self.press(
            "hero_level_up", xy=tuple(ui.panel(side)["hero_level_up"])))
        if not r:
            return r
        h = self.hero
        h.level, h.xp_into_level, h.spent = h.level + 1, 0, h.spent + g.cost
        self._gain_hero_abilities(h.level)
        return ActionResult(True, "leveled", g.cost, h.level)


    # --- 4.4 rounds, fast-forward, auto start -----------------------------------------------
    def _poll(self, read, want=None, tries=4, wait=0.15):
        """Read the current frame with `read` until it gives a value (or `want(value)`
        holds), at most `tries` times -> the last value."""
        v = None
        for i in range(tries):
            v = read(self.content())
            if (want(v) if want else v is not None):
                return v
            if i < tries - 1:
                self.sleep(wait)
        return v

    def sandbox_panel(self, side):
        """Sandbox: show the tower shop ('shop') or the bloon-send panel ('bloons'); one
        button toggles them. ok=False 'no_panel' if neither is recognised."""
        cur = self._poll(self.read_sandbox_panel)
        if cur is None:
            return ActionResult(False, "no_panel")
        if cur != side:
            if not self.game.click(*self.ui["buttons"]["powers"]):
                return ActionResult(False, "not_front")
            self.shop_layout = None             # don't trust the shop's scroll after a toggle
            self.sleep(self.ui["timing_s"]["panel_toggle"])
            if self._poll(self.read_sandbox_panel, lambda v: v == side) != side:
                return ActionResult(False, "no_panel")
        return ActionResult(True, side)

    def start_round(self):
        """Start the next round.
        Standard: only from idle (▶); play_ff, then the button must turn to ▶▶.
        Sandbox: the ▶▶ button shows all the time and Space doesn't send bloons, so this
        switches to the bloon panel, clicks its send button and switches back to the shop.
        Nothing on screen confirms the send or the round's end there, so a send always goes
        (Sandbox can stack rounds) and sets round_active for good: round-only abilities stay
        allowed for the rest of the Sandbox game."""
        if self.mode == "sandbox":
            r = self.sandbox_panel("bloons")
            if not r:
                return r
            if not self.game.click(*self.ui["buttons"]["sandbox_send_round"]):
                return ActionResult(False, "not_front")
            self.sleep(self.ui["timing_s"]["after_click"])
            self.round_active = True
            r = self.sandbox_panel("shop")
            return ActionResult(True, "sent", 0) if r else r
        g = guards.can_start_round(self.guard_state())
        if not g:
            return g
        b = self._poll(self.read_button)
        if b is None:
            return ActionResult(False, "no_button")
        if b != "idle":
            self.round_active, self.fast_forward = True, b == "ff_on"
            return ActionResult(False, "round_active")
        r = self.press("play_ff", xy=tuple(self.ui["buttons"]["play_ff"]))
        if not r:
            return r
        b = self._poll(self.read_button, lambda v: v in ("ff_off", "ff_on"), tries=6)
        if b not in ("ff_off", "ff_on"):
            return ActionResult(False, "unconfirmed")
        self.round_active, self.fast_forward = True, b == "ff_on"
        return ActionResult(True, "started", 0)

    def set_fast_forward(self, on):
        """Fast-forward on/off. Reads the button first and presses only if it differs.
        Refused at idle ('round_idle'): the same press would start the round."""
        want = "ff_on" if on else "ff_off"
        b = self._poll(self.read_button)
        if b is None:
            return ActionResult(False, "no_button")
        if b == "idle":
            return ActionResult(False, "round_idle")
        if b != want:
            r = self.press("play_ff", xy=tuple(self.ui["buttons"]["play_ff"]))
            if not r:
                return r
            if self._poll(self.read_button, lambda v: v == want, tries=6) != want:
                self.fast_forward = None
                return ActionResult(False, "unconfirmed")
        self.fast_forward = bool(on)
        return ActionResult(True, "set" if b != want else "unchanged", 0, bool(on))

    def set_auto_start(self, on):
        """Set the game's Auto Start (a game setting, kept across games). Opens the pause menu
        with the gear button (Escape would only deselect a selected tower), reads the toggle,
        clicks it only if it differs, and closes the menu with Continue unless it was already
        open. Tell any RoundTracker the new value."""
        t = self.ui["timing_s"]
        was_paused = self._poll(self.read_kind, tries=1) == "pause"
        if not was_paused:
            if not self.game.click(*self.ui["buttons"]["settings"]):
                return ActionResult(False, "not_front")
            self.sleep(t["pause_open"])
            if self._poll(self.read_kind, lambda v: v == "pause") != "pause":
                return ActionResult(False, "no_pause_menu")
        want = "on" if on else "off"
        cur = self._poll(self.read_auto_start)
        result = None
        if cur is None:
            result = ActionResult(False, "unreadable")
        elif cur != want:
            self.game.click(*self.ui["pause"]["auto_start_toggle"])
            self.sleep(t["panel_toggle"])
            if self._poll(self.read_auto_start, lambda v: v == want) != want:
                self.auto_start = None
                result = ActionResult(False, "unconfirmed")
        if not was_paused:
            self.game.click(*self.ui["pause"]["continue"])
            self.sleep(t["pause_open"])
            if self._poll(self.read_kind, lambda v: v != "pause") == "pause":
                return ActionResult(False, "pause_stuck")
        if result is not None:
            return result
        self.auto_start = bool(on)
        return ActionResult(True, "set" if cur != want else "unchanged", 0, bool(on))

    # --- 4.5 abilities ----------------------------------------------------------------------
    def slot_crop(self, frame, slot, panel_side=None):
        """The ability bar icon for `slot` cut from a content frame (bottom clipped at the
        screen edge), or None."""
        if frame is None:
            return None
        h, w = frame.shape[:2]
        x, y = ui.ability_slot(slot, panel_side)
        hx, hy = self.ui["ability_bar"]["icon_half"]
        return frame[max(round((y - hy) * h), 0):h, max(round((x - hx) * w), 0):min(round((x + hx) * w), w)]

    def _ability_fired(self, slot, before):
        """Did the slot's icon change like a use does (ring over a darkened icon)?"""
        need = self.ui["ability_bar"]["used_min_diff"]
        for _ in range(3):
            if self.icon_diff(before, self.slot_crop(self.content(), slot)) >= need:
                return True
            self.sleep(0.15)
        return False

    def _after_use(self, slot, fired, key=None):
        """Book the use on one instance: `key` (use_ability_of), else the instance that has been
        ready longest. Not fired: probably still cooling down (the estimate was early), so every
        instance backs off a little."""
        a, now = self.ability_slots[slot], self.clock()
        if not fired:
            for k, t in a["inst"].items():
                a["inst"][k] = max(t, now + 3.0)
            return ActionResult(False, "unconfirmed", 0)
        if key is None:
            key = min(a["inst"], key=a["inst"].get)
        a["inst"][key] = now + a["cooldown"]
        return ActionResult(True, "used", 0, a["name"])

    def use_ability(self, slot, target=None):
        """Activate ability bar slot `slot` (0-based; one icon per ability name, in order of first gain; a press uses one instance):
        its hotkey if confirmed, else a click on the icon. `target` (x, y): click it next, for
        abilities that ask for a point. Confirmed by the icon changing. ok -> value is the
        ability's name. With no panel open (actions close theirs), the bar is in place."""
        g = guards.can_use_ability(slot, self.guard_state())
        if not g:
            return g
        before = self.slot_crop(self.content(), slot)
        r = self.press("ability", xy=ui.ability_slot(slot), path=slot)
        if not r:
            return r
        if target is not None:
            if not self.game.click(*target):
                return ActionResult(False, "not_front")
            self.sleep(self.ui["timing_s"]["after_click"])
        return self._after_use(slot, self._ability_fired(slot, before))

    def place_ability_target(self, slot, x, y):
        """Activate a targeted ability and click its target point (x, y)."""
        return self.use_ability(slot, target=(x, y))

    def use_ability_of(self, tid):
        """Activate tower `tid`'s (or the hero's) ability from its panel: the big ability icon
        next to the panel. A tower with two abilities uses the first. Confirmed on the bar
        after the panel is closed."""
        found = [(i, k) for i, a in enumerate(self.ability_slots) for k in a["inst"] if k[0] == tid]
        slot, key = found[0] if found else (None, None)
        if slot is None:
            return ActionResult(False, "no_ability" if tid in self.registry or tid == HERO_TID else "no_tower")
        if not self.round_active and not self.ability_slots[slot]["between_rounds"]:
            return ActionResult(False, "round_only")
        if self.clock() < self.ability_slots[slot]["inst"][key]:
            return ActionResult(False, "cooldown")
        before = self.slot_crop(self.content(), slot)
        r = self.select_tower(tid)
        if not r:
            return r
        side = self.panel_side()
        if side is None:
            return ActionResult(False, "no_panel")
        clicked = self.game.click(*ui.panel(side)["ability_icon"])
        self.sleep(self.ui["timing_s"]["after_click"])
        self.close_panel(side)
        if not clicked:
            return ActionResult(False, "not_front")
        return self._after_use(slot, self._ability_fired(slot, before), key)

    # --- 4.6 targeting and target points ----------------------------------------------------
    def _ocr_targeting(self, side):
        f = self.game.grab()
        return "" if f is None else self.game.ocr(f, ui.panel(side)["targeting_label"])

    def targeting_label(self, mode):
        """The panel text for a towers.json targeting mode ('lock_in_place' -> 'LOCK IN PLACE')."""
        return self.ui["targeting"]["labels"].get(mode, mode.replace("_", " ").upper())

    @staticmethod
    def _same_text(a, b):
        """OCR-tolerant label comparison (letters only, case-insensitive, ratio >= 0.8)."""
        import difflib
        norm = lambda t: "".join(c for c in t.upper() if c.isalpha())
        a, b = norm(a), norm(b)
        return bool(a) and difflib.SequenceMatcher(None, a, b).ratio() >= 0.8

    def _label_is(self, text, mode):
        return self._same_text(text, self.targeting_label(mode))

    def _choose_mode(self, tid, mode):
        """Select `tid` and Tab through its targeting until the label reads `mode`. Leaves the
        panel open. -> (ActionResult, side); side is None if no panel was opened."""
        t = self.registry.get(tid)
        if t is None:
            return ActionResult(False, "no_tower"), None
        r = self.select_tower(tid)
        if not r:
            return r, None
        side = self.panel_side()
        if side is None:
            return ActionResult(False, "no_panel"), None
        first = None
        for _ in range(self.ui["targeting"]["max_presses"] + 1):
            text = ""
            for _ in range(3):
                text = self.read_targeting(side)
                if text:
                    break
                self.sleep(0.15)
            if not text:
                return ActionResult(False, "no_targeting"), side
            if self._label_is(text, mode):
                return ActionResult(True, "chosen", 0, mode), side
            if first is None:
                first = text
            elif self._same_text(text, first):
                break                               # back at the first label: mode not offered
            r = self.press("targeting_next", xy=tuple(ui.panel(side)["targeting_next"]), wait=0.35)
            if not r:
                return r, side
        return ActionResult(False, "no_such_mode"), side

    def set_targeting(self, tid, mode):
        """Set tower `tid`'s targeting to a towers.json mode ('first', 'strong', 'circle', ...):
        Tab until the panel's label reads it (upgrades can add modes, so the label is read
        each time, not counted). ok -> value is the mode."""
        r, side = self._choose_mode(tid, mode)
        if side is not None:
            self.close_panel(side)
        if not r:
            return r
        self.registry[tid].targeting = mode
        return ActionResult(True, "set", 0, mode)

    def set_flight_path(self, tid, pattern):
        """Monkey Ace flight pattern ('circle', 'figure_infinite', 'figure_eight'): a
        targeting mode on the Ace's panel."""
        return self.set_targeting(tid, pattern)

    def _set_points(self, tid, mode, points):
        """Choose a point mode, click its button (the label spot), click `points` on the map,
        and confirm by the panel reopening on the same side."""
        need = self.ui["targeting"]["point_modes"].get(mode)
        if need is None:
            return ActionResult(False, "not_point_mode")
        if len(points) != need:
            return ActionResult(False, "bad_points")
        r, side = self._choose_mode(tid, mode)
        if not r:
            if side is not None:
                self.close_panel(side)
            return r
        x0, y0, x1, y1 = ui.panel(side)["targeting_label"]
        if not self.game.click((x0 + x1) / 2, (y0 + y1) / 2):
            return ActionResult(False, "not_front")
        self.sleep(self.ui["timing_s"]["after_click"])
        if self.panel_side(tries=2) is not None:      # the button should close the panel
            self.close_panel(side)
            return ActionResult(False, "no_point_button")
        for x, y in points:
            if not self.game.click(x, y):
                return ActionResult(False, "not_front")
            self.sleep(self.ui["timing_s"]["after_click"])
        back = self.panel_side()
        if back is None:
            self.cancel_hold()                         # leave point mode (cancel button)
            return ActionResult(False, "unconfirmed")
        self.close_panel(back)
        self.registry[tid].targeting = mode
        return ActionResult(True, "set", 0, [tuple(p) for p in points])

    def set_target_point(self, tid, x, y):
        """Point the tower at (x, y): Mortar's Set Target, Heli's Lock in Place (ui.json
        targeting.point_mode_of)."""
        t = self.registry.get(tid)
        if t is None:
            return ActionResult(False, "no_tower")
        mode = self.ui["targeting"]["point_mode_of"].get(t.kind)
        if mode is None:
            return ActionResult(False, "no_target_point")
        return self._set_points(tid, mode, [(x, y)])

    def set_patrol_points(self, tid, points):
        """Heli Pilot patrol between two points [(x, y), (x, y)]."""
        t = self.registry.get(tid)
        if t is None:
            return ActionResult(False, "no_tower")
        if t.kind != "heli_pilot":
            return ActionResult(False, "no_patrol")
        return self._set_points(tid, "patrol_points", list(points))

    # --- 4.8 prompts ------------------------------------------------------------------------
    def _ui_point(self, ref):
        section, key = ref.split(".")
        return tuple(self.ui[section][key])

    def handle_prompts(self, overrides=None):
        """Clear popups and overlays with their default button (ui.json `prompts`; override per
        harness via `prompt_actions` or per call: {kind: 'section.key' | None}). Repeats while
        a handled prompt shows, since one can follow another (e.g. restart confirm over pause).
        -> the screen kinds acted on, in order. Prompts mapped to None (victory, defeat) are
        left for the caller, and the loop stops there."""
        actions = dict(self.prompt_actions, **(overrides or {}))
        cfg = self.ui["prompts"]
        handled = []
        for _ in range(cfg["max_steps"]):
            kind = self._poll(self.read_kind, tries=1)
            ref = actions.get(kind)
            if ref is None:
                break
            if not self.game.click(*self._ui_point(ref)):
                break
            handled.append(kind)
            self.sleep(cfg["after_click_s"])
        return handled
