"""Title screen, quick-battle picker and campaign save slots."""

from __future__ import annotations

import math
import random
from datetime import datetime

import pygame

from .. import campaign as campaign_mod
from ..economy import CURRENCIES
from ..scenarios import SCENARIOS
from . import theme as T
from .draw import Button, Waves, draw_ship, money, ocean_surface, panel, text, wrap


class _Backdrop:
    """Ocean, waves and a small squadron steaming across the top of the screen."""

    def __init__(self) -> None:
        self.time = 0.0
        self.mouse = (0, 0)
        self.bg = ocean_surface(*T.WINDOW, seed=7)
        self.waves = Waves(pygame.Rect(0, 0, *T.WINDOW), 220, 3)

    def update(self, dt: float) -> None:
        self.time += dt

    def draw_backdrop(self, surf: pygame.Surface, title: str, subtitle: str) -> None:
        surf.blit(self.bg, (0, 0))
        self.waves.draw(surf, self.time)
        for i, (hull, dy) in enumerate([("destroyer", 0), ("cruiser", 38), ("battleship", 76), ("destroyer", 114)]):
            x = (self.time * 28 + i * 70) % (T.WINDOW[0] + 400) - 200
            y = 40 + dy + math.sin(self.time + i) * 2
            draw_ship(surf, (x, y), hull, 0, 0.0, 110, 1.2)
        text(surf, title, (T.WINDOW[0] // 2 + 3, 88), 92, (0, 0, 0), "midtop")
        text(surf, title, (T.WINDOW[0] // 2, 85), 92, T.ACCENT, "midtop")
        text(surf, subtitle, (T.WINDOW[0] // 2, 160), 24, T.TEXT, "midtop")


class TitleScene(_Backdrop):
    def __init__(self, app) -> None:
        super().__init__()
        self.app = app
        cx = T.WINDOW[0] // 2
        self.buttons = [
            Button(pygame.Rect(cx - 200, 250, 400, 80), "Campaign", app.to_slots, "Build your fleet in the workshop (C)", size=34),
            Button(pygame.Rect(cx - 200, 346, 400, 64), "Quick Battle", app.to_quick_battle, "Preset fleets (B)", size=28),
            Button(pygame.Rect(cx - 200, 426, 400, 50), "Quit", self.quit, "Esc", size=24),
        ]

    def quit(self) -> None:
        self.app.running = False

    def handle(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEMOTION:
            self.mouse = event.pos
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for b in self.buttons:
                if b.click(event.pos):
                    return
        elif event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_c, pygame.K_RETURN, pygame.K_SPACE):
                self.app.to_slots()
            elif event.key == pygame.K_b:
                self.app.to_quick_battle()
            elif event.key in (pygame.K_ESCAPE, pygame.K_q):
                self.quit()

    def draw(self, surf: pygame.Surface) -> None:
        self.draw_backdrop(surf, "MASTER OF OCEANS", "Tactical naval battles in the spirit of Master of Orion (1993)")
        for b in self.buttons:
            b.draw(surf, self.mouse)
        lines = [
            "Solve math problems in the workshop to earn steel, powder, fuel and blueprints.",
            "Spend them on upgrades and new ships, then take on ever stronger Red fleets.",
            "",
            "M turns the sound on and off, anywhere in the game.",
        ]
        for i, line in enumerate(lines):
            text(surf, line, (T.WINDOW[0] // 2, 510 + i * 24), 20, T.DIM, "midtop")


class QuickBattleScene(_Backdrop):
    """Pick one of the preset scenarios. You always command Blue."""

    def __init__(self, app) -> None:
        super().__init__()
        self.app = app
        self.ids = list(SCENARIOS)
        self.selected = self.ids.index(app.settings["scenario"]) if app.settings["scenario"] in self.ids else 0
        self.seed = random.randrange(100_000)
        self.cards = [pygame.Rect(90, 236 + i * 96, 620, 84) for i in range(len(self.ids))]
        right = pygame.Rect(770, 236, 420, 380)
        self.right = right
        self.seed_button = Button(pygame.Rect(right.x + 250, right.y + 56, 150, 40), "New Seed", self.reroll, "")
        self.start_button = Button(pygame.Rect(right.x + 20, right.y + 130, 380, 60), "Start Battle", self.start, "Enter", size=26)
        self.back_button = Button(pygame.Rect(right.x + 20, right.y + 204, 380, 44), "Back", app.to_title, "Esc")
        self.buttons = [self.seed_button, self.start_button, self.back_button]

    def reroll(self) -> None:
        self.seed = random.randrange(100_000)

    def start(self) -> None:
        sid = self.ids[self.selected]
        self.app.start_battle(sid, self.seed)

    def handle(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEMOTION:
            self.mouse = event.pos
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i, rect in enumerate(self.cards):
                if rect.collidepoint(event.pos):
                    if i == self.selected:
                        self.start()
                    self.selected = i
                    return
            for b in self.buttons:
                if b.click(event.pos):
                    return
        elif event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_UP, pygame.K_w):
                self.selected = (self.selected - 1) % len(self.ids)
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.selected = (self.selected + 1) % len(self.ids)
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self.start()
            elif event.key == pygame.K_n:
                self.reroll()
            elif event.key == pygame.K_ESCAPE:
                self.app.to_title()

    def draw(self, surf: pygame.Surface) -> None:
        self.draw_backdrop(surf, "QUICK BATTLE", "You command the Blue fleet against the computer's Red fleet")
        text(surf, "CHOOSE A BATTLE", (self.cards[0].x, self.cards[0].y - 26), 22, T.DIM)
        for i, (sid, rect) in enumerate(zip(self.ids, self.cards)):
            sc = SCENARIOS[sid]
            chosen = i == self.selected
            hover = rect.collidepoint(self.mouse)
            panel(surf, rect, (40, 56, 76) if chosen else (18, 28, 42) if not hover else (28, 40, 56), T.ACCENT if chosen else T.PANEL_EDGE)
            text(surf, sc.name, (rect.x + 18, rect.y + 12), 30, T.ACCENT if chosen else T.TEXT)
            for j, line in enumerate(wrap(sc.description, 20, rect.width - 36)[:2]):
                text(surf, line, (rect.x + 18, rect.y + 42 + j * 19), 20, T.DIM)
        panel(surf, self.right)
        x = self.right.x + 20
        text(surf, "BATTLE SEED", (x, self.right.y + 42), 22, T.DIM)
        text(surf, str(self.seed), (x, self.right.y + 64), 34, T.TEXT)
        for b in self.buttons:
            b.draw(surf, self.mouse)
        text(surf, "Up/Down choose  -  Enter start  -  N new seed  -  Esc back", (self.right.centerx, self.right.bottom - 36), 18, T.FAINT, "midtop")


class SlotScene(_Backdrop):
    """Three campaign save slots: continue, start over or delete."""

    def __init__(self, app) -> None:
        super().__init__()
        self.app = app
        self.saves: dict[int, campaign_mod.Campaign | None] = {}
        self.problems: dict[int, campaign_mod.SaveError] = {}  # slots that can't be played, and why
        for slot in campaign_mod.SLOTS:
            self._open(slot)
        self.cards = [pygame.Rect(70 + i * 390, 220, 360, 380) for i in range(len(campaign_mod.SLOTS))]
        self.confirm: tuple[str, int] | None = None  # ("new" | "delete", slot) awaiting a second click
        self.hits: list[tuple[pygame.Rect, callable]] = []
        self.back = Button(pygame.Rect(T.WINDOW[0] // 2 - 100, 640, 200, 44), "Back", app.to_title, "Esc")

    def _open(self, slot: int) -> None:
        self.problems.pop(slot, None)
        try:
            self.saves[slot] = campaign_mod.load(slot)
        except campaign_mod.SaveError as exc:
            self.saves[slot] = None
            self.problems[slot] = exc

    def _locked(self, slot: int) -> bool:
        """The slot holds a file that must be kept: unreadable just now, or from a newer version of the game."""
        return slot in self.problems and not self.problems[slot].free

    def _continue(self, slot: int) -> None:
        self.app.open_workshop(self.saves[slot])

    def _new(self, slot: int) -> None:
        if self._locked(slot):
            self._open(slot)  # try again: another program may have let go of the file
            return
        if self.saves[slot] is not None and self.confirm != ("new", slot):
            self.confirm = ("new", slot)
            return
        try:
            campaign_mod.delete(slot)  # the old campaign and its backup
        except OSError as exc:
            self.app.notice = (f"Couldn't remove the old campaign ({exc.strerror or exc}).", 6.0)
            return
        campaign = campaign_mod.Campaign(slot=slot)
        problem = campaign_mod.try_save(campaign)
        if problem:
            self.app.notice = (problem, 8.0)
            return
        self.app.open_workshop(campaign)

    def _delete(self, slot: int) -> None:
        if self.confirm != ("delete", slot):
            self.confirm = ("delete", slot)
            return
        try:
            campaign_mod.delete(slot)
        except OSError as exc:
            self.app.notice = (f"Couldn't delete the campaign ({exc.strerror or exc}).", 6.0)
            return
        self.saves[slot] = None
        self.problems.pop(slot, None)
        self.confirm = None

    def handle(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEMOTION:
            self.mouse = event.pos
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.back.click(event.pos):
                return
            for rect, fn in self.hits:
                if rect.collidepoint(event.pos):
                    fn()
                    return
            self.confirm = None
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.app.to_title()
            elif event.key in (pygame.K_1, pygame.K_2, pygame.K_3):
                slot = event.key - pygame.K_0
                self._continue(slot) if self.saves.get(slot) else self._new(slot)

    def _button(self, surf, rect, label, fn, hint="", danger=False) -> None:
        b = Button(rect, label, fn, hint)
        b.toggled = danger
        b.draw(surf, self.mouse)
        self.hits.append((rect, fn))

    def draw(self, surf: pygame.Surface) -> None:
        self.draw_backdrop(surf, "CAMPAIGN", "Choose a save slot. Progress is saved automatically.")
        self.hits = []
        for slot, rect in zip(campaign_mod.SLOTS, self.cards):
            c = self.saves[slot]
            panel(surf, rect, (22, 34, 50))
            text(surf, f"SLOT {slot}", (rect.x + 20, rect.y + 16), 30, T.ACCENT)
            x, y = rect.x + 20, rect.y + 58
            if slot in self.problems:
                problem = self.problems[slot]
                text(surf, "Can't open this save" if self._locked(slot) else "Save set aside", (x, y), 26, T.WARN)
                for i, line in enumerate(wrap(str(problem), 19, rect.width - 40)[:7]):
                    text(surf, line, (x, y + 36 + i * 22), 19, T.DIM)
                label = "Try Again" if self._locked(slot) else "New Campaign"
                self._button(surf, pygame.Rect(x, rect.bottom - 70, rect.width - 40, 50), label, lambda s=slot: self._new(s), f"key {slot}")
                continue
            if c is None:
                text(surf, "Empty", (x, y), 26, T.DIM)
                text(surf, "Start with a few small boats", (x, y + 34), 19, T.FAINT)
                text(surf, "and build a navy.", (x, y + 56), 19, T.FAINT)
                self._button(surf, pygame.Rect(x, rect.bottom - 70, rect.width - 40, 50), "New Campaign", lambda s=slot: self._new(s), f"key {slot}")
                continue
            m = c.mission
            text(surf, m.title, (x, y), 26, T.WARN if m.is_super else T.TEXT)
            for line in wrap(m.name, 20, rect.width - 40)[:1]:
                text(surf, line, (x, y + 30), 20, T.DIM)
            ships = sum(c.fleet.values())
            wrecks = sum(c.wrecks.values())
            text(surf, f"{ships} ships ready" + (f", {wrecks} need repairs" if wrecks else ""), (x, y + 62), 19, T.TEXT)
            solved = sum((c.stats.get("solved") or {}).values())
            text(surf, f"{solved} problems solved", (x, y + 86), 19, T.TEXT)
            for i, cur in enumerate(CURRENCIES):
                money(surf, (x + (i % 2) * 150, y + 128 + (i // 2) * 28), cur, c.balance(cur))
            try:
                when = datetime.fromisoformat(c.updated).strftime("%b %d, %H:%M")
            except ValueError:
                when = c.updated
            text(surf, f"Last played {when}", (x, y + 190), 17, T.FAINT)
            by = rect.bottom - 118
            self._button(surf, pygame.Rect(x, by, rect.width - 40, 50), "Continue", lambda s=slot: self._continue(s), f"key {slot}")
            half = (rect.width - 50) // 2
            new_label = "Sure? Click again" if self.confirm == ("new", slot) else "Start Over"
            del_label = "Sure? Click again" if self.confirm == ("delete", slot) else "Delete"
            self._button(surf, pygame.Rect(x, by + 60, half, 40), new_label, lambda s=slot: self._new(s), danger=self.confirm == ("new", slot))
            self._button(surf, pygame.Rect(x + half + 10, by + 60, half, 40), del_label, lambda s=slot: self._delete(s), danger=self.confirm == ("delete", slot))
        self.back.draw(surf, self.mouse)
        where = f"Save files: {campaign_mod.save_dir()}"
        if self.app.moved_saves:
            where += "  (your earlier saves were moved here)"
        text(surf, where, (T.WINDOW[0] // 2, 612), 16, T.FAINT, "midtop")
