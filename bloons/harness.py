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
        self.auto_start = None        # the game's Auto Start setting once read (a setting, not per game)
        self.new_episode()

    # --- episode state ----------------------------------------------------------------------
    def new_episode(self):
        """Forget everything about the current game (call when a new game starts)."""
        self.registry = {}            # tid -> guards.TowerRec
        self.hero = None              # guards.HeroRec once placed
        self.bought = set()           # tower kinds bought at least once this game
        self.abilities = []           # [guards.Ability], read off the ability bar
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
        return HERO_TID

    def record_upgrade(self, tid, path, price):
        t = self.registry[tid]
        tiers = list(t.tiers)
        tiers[path] += 1
        t.tiers, t.spent = tuple(tiers), t.spent + int(price)

    def unregister(self, tid):
        """Forget a sold tower (or the hero, tid 'hero')."""
        if tid == HERO_TID:
            self.hero = None
        else:
            self.registry.pop(tid)

    # --- contexts for guards / placement ----------------------------------------------------
    def guard_state(self):
        """guards.GuardState from what the harness knows now. Unknown money counts as $0, so
        nothing that costs money is offered until the HUD has been read."""
        return guards.GuardState(
            money=self.money or 0, difficulty=self.difficulty, towers=self.towers, heroes=self.heroes,
            account=self.account, registry=self.registry, hero=self.hero, hero_choice=self.hero_choice,
            bought=self.bought, abilities=self.abilities, round_active=self.round_active, locked=self.locked)

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
            return k[path] if path is not None else None
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
        Nothing on screen confirms the send there; round_active isn't tracked in Sandbox."""
        g = guards.can_start_round(self.guard_state())
        if not g:
            return g
        if self.mode == "sandbox":
            r = self.sandbox_panel("bloons")
            if not r:
                return r
            if not self.game.click(*self.ui["buttons"]["sandbox_send_round"]):
                return ActionResult(False, "not_front")
            self.sleep(self.ui["timing_s"]["after_click"])
            r = self.sandbox_panel("shop")
            return ActionResult(True, "sent", 0) if r else r
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
