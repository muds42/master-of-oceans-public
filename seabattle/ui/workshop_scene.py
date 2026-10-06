"""The workshop: solve math problems to earn currency, then upgrade, build and repair the fleet.

Pages (tabs across the top):

* Math Station: multiple-choice problems from Fleet Algebra and Broadside, with
  topic switches and a difficulty slider. Harder problems pay more; wrong
  answers cost 35% of a problem's pay. Keys 1-4 answer. After a wrong answer
  the working opens and says what the mistake was, and that kind of problem
  comes back for review a couple of problems later. T opens the trig table.
* Upgrades: fleet-wide technology tracks, and (with Plasma) Future Tech.
* Shipyard: unlock and buy ship classes, Act I's and the Plasma ones, and
  (with Plasma) retrofit Act I's classes with a Laser Battery or a Field Generator.
* Fleet & Repairs: repair wrecks, choose which squadrons sail, see the next
  mission and campaign progress. Click a mission already won to replay it as a
  skirmish.
* Logbook: how each topic is going, the skills that need work, and records.

"Set Sail" opens the mission briefing and launches the battle. The briefing is
also where Math Boost is switched on or off (B): with it on, a MATH BOOST box
comes up on the battle's big hits, and a click on it opens a 7th-grade problem.
The campaign is saved after every answer and every purchase.
"""

from __future__ import annotations

import random
from collections import deque
from typing import Callable, Optional

import pygame

from .. import campaign as campaign_mod
from ..boost import BOOST, PENALTY
from ..campaign import MISSION_COUNT, Campaign, mission
from ..economy import (
    CATEGORIES, CURRENCY_NAMES, CURRENCY_USES, PLASMA_MISSION, RETROFITS, SHIP_CLASSES, TRACKS,
    cost_text, light_guns, refit, retrofit, ship_design,
)
from ..problems import (
    LEVEL_NAMES, SCHOOLS, TIER_NAMES, TIER_PAY, TOPICS, WRONG_PENALTY, Posed, briefing, choose, level_pay, penalty, reward,
    skill_title, streak_bonus,
)
from ..problems.broadside import SMALL_TAN, TRIG
from . import sound
from . import theme as T
from .draw import Slider, bar, cost_row, currency_icon, draw_ship, mtext, mwrap, panel, text, wrap

try:  # figures for Broadside problems (optional)
    from .figures import draw_figure
except ImportError:  # pragma: no cover
    draw_figure = None

CHEERS = ["Direct hit!", "Aye aye!", "On target!", "Steady as she goes!", "Well plotted!", "Bravo Zulu!", "Shipshape!"]
MISSES = ["Splash - short!", "Off the mark.", "Recalculate!", "Not this time, sailor."]
TABS = [
    ("math", "Math Station"), ("upgrades", "Upgrades"), ("shipyard", "Shipyard"), ("fleet", "Fleet & Repairs"),
    ("log", "Logbook"),
]
CONTENT = pygame.Rect(16, 116, 1248, 596)
BOOST_H = 88  # the Math Boost settings on the mission briefing
SUPER_FAINT = (170, 118, 66)  # a super mission still to come, in the campaign list
SUPER_NOTE = ("Super mission. {opens} Red's biggest fleet yet, and a long, hard battle: spend extra time in the "
              "workshop first, and expect it to take more than one try. Twice the prize money, half your sunk ships "
              "repaired for free, and with Math Boost on, up to {boosts} big hits.")


class WorkshopScene:
    def __init__(self, app, campaign: Campaign) -> None:
        self.app = app
        self.c = campaign
        self.tab = "math"
        self.upgrade_view = "act1"  # "act1" or "future"
        self.shipyard_view = "act1"
        self.school = app.settings.get("school", "algebra")
        self.rng = random.Random()
        self.recent: deque = deque(maxlen=8)
        self.mouse = (0, 0)
        self.time = 0.0
        self.hits: list[tuple[pygame.Rect, Callable[[], None]]] = []
        self.toast = ""
        self.toast_time = 0.0
        self.show_briefing = False  # mission briefing overlay
        self.skirmish: Optional[int] = None  # the mission being briefed is a skirmish replay of this one
        self.mission_rows: dict[int, pygame.Rect] = {}  # campaign list rows that start a skirmish
        self.show_help = False  # problem help overlay
        self.show_trig = False  # trig table overlay
        # current problem
        self.posed: Optional[Posed] = None
        self.reviewing = False  # the current problem is a second go at a kind the player missed
        self.picked: Optional[int] = None  # the choice the player clicked
        self.show_working = False
        self.show_equation = False
        self.feedback = ("", T.TEXT)
        self.auto_next = 0.0
        self.sliders: dict[str, Slider] = {}
        self._make_sliders()
        self.new_problem()
        if campaign.notice:
            self.flash(campaign.notice, 6.0)
            campaign.notice = ""
            self.save()

    # ---- helpers ----------------------------------------------------------------

    def save(self) -> None:
        problem = campaign_mod.try_save(self.c)
        if problem:
            self.flash(problem, 6.0)

    def flash(self, message: str, seconds: float = 2.8) -> None:
        self.toast, self.toast_time = message, seconds

    def button(
        self, surf: pygame.Surface, rect: pygame.Rect, label: str, fn: Callable[[], None], *,
        enabled: bool = True, toggled: bool = False, size: int = 20, hint: str = "", color=None,
    ) -> None:
        hover = enabled and rect.collidepoint(self.mouse)
        fill = color or (T.BUTTON_HOVER if hover else T.BUTTON)
        if toggled:
            fill = (86, 72, 30) if not hover else (110, 92, 40)
        if color and hover:
            fill = tuple(min(255, v + 25) for v in color)
        pygame.draw.rect(surf, fill, rect, border_radius=6)
        pygame.draw.rect(surf, T.ACCENT if toggled else T.PANEL_EDGE, rect, 1, border_radius=6)
        fg = T.TEXT if enabled else T.FAINT
        if hint:
            text(surf, label, (rect.centerx, rect.centery - 8), size, fg, "center")
            text(surf, hint, (rect.centerx, rect.centery + 10), 15, T.DIM if enabled else T.FAINT, "center")
        else:
            text(surf, label, rect.center, size, fg, "center")
        if enabled:
            self.hits.append((rect, fn))

    # ---- math station -------------------------------------------------------------

    def _make_sliders(self) -> None:
        x, w = 910, 336
        level = self.c.difficulty.get(self.school, 2)
        self.sliders["difficulty"] = Slider(pygame.Rect(x, 156, w, 24), list(LEVEL_NAMES), level - 1, self._set_level)

    def _set_level(self, level) -> None:
        self.c.set_difficulty(self.school, level)
        self.save()
        if self.picked is None:  # an unanswered problem is swapped for one at the new level
            self.new_problem()

    def set_school(self, school: str) -> None:
        if school == self.school:
            return
        self.school = school
        self.app.settings["school"] = school
        self._make_sliders()
        self.new_problem()

    def toggle_topic(self, topic: str) -> None:
        error = self.c.toggle_topic(topic)
        if error:
            self.flash(error)
            return
        self.save()
        if self.posed and self.posed.topic.id not in self.c.topics and self.picked is None:
            self.new_problem()

    def new_problem(self) -> None:
        ctx = self.c.problem_context(self.rng)
        topics = self.c.school_topics(self.school)
        due = self.c.due_review(topics)
        self.posed = choose(self.rng, topics, self.c.difficulty.get(self.school, 2), ctx, self.recent, generator=due)
        self.reviewing = due is not None
        self.picked = None
        self.show_working = False
        self.show_equation = self.school == "algebra"  # Broadside keeps its equation hidden until asked
        self.feedback = ("", T.TEXT)
        self.auto_next = 0.0

    def answer(self, i: int) -> None:
        if self.posed is None or self.picked is not None or i >= 4:
            return
        self.picked = i
        correct = i == self.posed.answer
        change = self.c.answer(self.posed.topic.id, self.posed.tier, correct, generator=self.posed.generator.key)
        cur = CURRENCY_NAMES[self.posed.topic.currency]
        if correct:
            streak = f"   streak {self.c.streak}" if self.c.streak >= 3 else ""
            self.feedback = (f"{self.rng.choice(CHEERS)}  +{change} {cur}{streak}", T.GOOD)
            self.auto_next = 1.6
            sound.play("right", 0.7)
        else:
            lost = f"  -{-change} {cur}" if change else ""
            self.feedback = (f"{self.rng.choice(MISSES)}{lost}", T.BAD)
            self.show_working = True  # a miss is the moment to see how it's done
            sound.play("wrong", 0.5)
        self.save()

    def next_problem(self) -> None:
        if self.picked is not None:
            self.new_problem()

    # ---- other pages ------------------------------------------------------------------

    def _bought(self, error: Optional[str], message: str) -> None:
        self.flash(error or message)
        sound.play("error" if error else "buy", 0.5)
        if not error:
            self.save()

    def buy_upgrade(self, track: str) -> None:
        error = self.c.buy_upgrade(track)
        self._bought(error, f"{TRACKS[track].name} upgraded to level {self.c.level(track)}!")

    def buy_ship(self, class_id: str) -> None:
        error = self.c.buy_ship(class_id)
        self._bought(error, f"New {SHIP_CLASSES[class_id].name} joins the fleet!")

    def unlock(self, class_id: str) -> None:
        error = self.c.unlock_class(class_id)
        self._bought(error, f"You can now build the {SHIP_CLASSES[class_id].name}.")

    def buy_retrofit(self, class_id: str, retrofit_id: str) -> None:
        error = self.c.buy_retrofit(class_id, retrofit_id)
        self._bought(error, f"Every {SHIP_CLASSES[class_id].name} now has a {RETROFITS[retrofit_id].name}!")

    def toggle_port(self, class_id: str) -> None:
        error = self.c.toggle_port(class_id)
        if error:
            self.flash(error)
            sound.play("error", 0.5)
            return
        self.save()

    def repair(self, class_id: str, all_of_them: bool = False) -> None:
        repaired = 0
        error = None
        while self.c.wrecks.get(class_id, 0) > 0:
            error = self.c.repair(class_id)
            if error:
                break
            repaired += 1
            if not all_of_them:
                break
        if repaired:
            self.save()
            sound.play("buy", 0.5)
            name = SHIP_CLASSES[class_id].name
            self.flash(f"Repaired {repaired} {name}{'s' if repaired > 1 else ''}." + (f" {error}" if error else ""))
        elif error:
            self.flash(error)

    def set_sail(self) -> None:
        self.skirmish = None
        self.show_briefing = True

    def open_skirmish(self, number: int) -> None:
        """Brief a replay of a mission already won."""
        self.skirmish = number
        self.show_briefing = True

    def toggle_boost(self) -> None:
        self.c.boost = not self.c.boost
        self.save()

    def close_briefing(self) -> None:
        self.show_briefing = False
        self.skirmish = None

    def launch(self) -> None:
        if not self.c.ready_fleet():
            self.flash("You have no seaworthy ships. Repair or buy ships first.")
            sound.play("error", 0.5)
            return
        self.save()
        sound.play("horn", 0.5)
        self.app.start_mission(self.c, self.skirmish)

    def exit(self) -> None:
        self.save()
        self.app.to_title()

    # ---- events -------------------------------------------------------------------

    def handle(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEMOTION:
            self.mouse = event.pos
        if self.tab == "math" and not (self.show_briefing or self.show_help or self.show_trig):
            for s in self.sliders.values():
                if s.handle(event):
                    return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.mouse = event.pos
            for rect, fn in reversed(self.hits):
                if rect.collidepoint(event.pos):
                    fn()
                    return
            if self.show_help or self.show_trig:
                self.show_help = self.show_trig = False
        elif event.type == pygame.KEYDOWN:
            self._key(event)

    def _key(self, event: pygame.event.Event) -> None:
        key = event.key
        if self.show_help:
            if key in (pygame.K_ESCAPE, pygame.K_h, pygame.K_SLASH, pygame.K_RETURN, pygame.K_SPACE):
                self.show_help = False
            return
        if self.show_trig:
            if key in (pygame.K_ESCAPE, pygame.K_t, pygame.K_RETURN, pygame.K_SPACE):
                self.show_trig = False
            return
        if self.show_briefing:
            if key in (pygame.K_RETURN, pygame.K_SPACE):
                self.launch()
            elif key == pygame.K_ESCAPE:
                self.close_briefing()
            elif key == pygame.K_b:
                self.toggle_boost()
            return
        if key == pygame.K_ESCAPE:
            self.exit()
            return
        if key == pygame.K_TAB:
            names = [t for t, _ in TABS]
            self.tab = names[(names.index(self.tab) + 1) % len(names)]
            return
        if self.tab != "math":
            return
        if key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_KP1, pygame.K_KP2, pygame.K_KP3, pygame.K_KP4):
            idx = (key - pygame.K_1) if key <= pygame.K_4 else (key - pygame.K_KP1)
            self.answer(idx)
        elif key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
            self.next_problem()
        elif key in (pygame.K_h, pygame.K_SLASH) or event.unicode == "?":
            self.show_help = True
        elif key == pygame.K_w and self.picked is not None:  # the working is the answer: only after answering
            self.show_working = True
        elif key == pygame.K_e:
            self.show_equation = True
        elif key == pygame.K_t and self.school == "broadside":
            self.show_trig = True

    def update(self, dt: float) -> None:
        self.time += dt
        if self.toast_time > 0:
            self.toast_time -= dt
        if self.auto_next > 0 and not self.show_working and not self.show_help and not self.show_trig:
            self.auto_next -= dt
            if self.auto_next <= 0:
                self.new_problem()

    # ---- drawing ----------------------------------------------------------------------

    def draw(self, surf: pygame.Surface) -> None:
        self.hits = []
        surf.fill(T.BG)
        self._draw_header(surf)
        if self.tab == "math":
            self._draw_math(surf)
        elif self.tab == "upgrades":
            self._draw_upgrades(surf)
        elif self.tab == "shipyard":
            self._draw_shipyard(surf)
        elif self.tab == "log":
            self._draw_logbook(surf)
        else:
            self._draw_fleet(surf)
        if self.show_help:
            self._draw_help(surf)
        elif self.show_trig:
            self._draw_trig_table(surf)
        elif self.show_briefing:
            self.hits = []  # only the briefing's own buttons work while it is open
            self._draw_briefing(surf)
        if self.toast_time > 0 and self.toast:
            lines = wrap(self.toast, 20, 760)
            h = 16 + 22 * len(lines)
            box = pygame.Rect(0, 0, 800, h)
            box.midbottom = (T.WINDOW[0] // 2, T.WINDOW[1] - 14)
            panel(surf, box, (30, 44, 62), T.ACCENT)
            for i, line in enumerate(lines):
                text(surf, line, (box.centerx, box.y + 8 + i * 22), 20, T.TEXT, "midtop")

    def _draw_header(self, surf: pygame.Surface) -> None:
        text(surf, "WORKSHOP", (16, 12), 38, T.ACCENT)
        m = self.c.mission
        text(surf, f"Slot {self.c.slot}  -  next: {m.title}, {m.name}", (18, 44), 17, T.DIM)
        currencies = self.c.currencies
        wide = len(currencies) <= 4
        x, w = (400, 168) if wide else (344, 150)
        for cur in currencies:
            pill = pygame.Rect(x, 12, w, 38)
            pygame.draw.rect(surf, (20, 32, 48), pill, border_radius=19)
            pygame.draw.rect(surf, T.CURRENCY_COLORS[cur], pill, 1, border_radius=19)
            currency_icon(surf, (pill.x + 20, pill.centery), cur, 10)
            if wide:
                text(surf, str(self.c.balance(cur)), (pill.x + 38, pill.centery - 9), 26, T.TEXT, "midleft")
                text(surf, CURRENCY_NAMES[cur], (pill.right - 12, pill.centery + 8), 15, T.CURRENCY_COLORS[cur], "midright")
            else:  # five pills: the amount over the name
                text(surf, str(self.c.balance(cur)), (pill.x + 38, pill.centery - 7), 22, T.TEXT, "midleft")
                text(surf, CURRENCY_NAMES[cur], (pill.x + 38, pill.centery + 10), 13, T.CURRENCY_COLORS[cur], "midleft")
            if pill.collidepoint(self.mouse):
                self._tooltip(surf, f"{CURRENCY_NAMES[cur]}: for {CURRENCY_USES[cur]}. Earned from " + " and ".join(
                    t.name for t in TOPICS.values() if t.currency == cur) + ".")
            x += w + (10 if wide else 8)
        self.button(surf, pygame.Rect(1134, 12, 130, 38), "Save & Exit", self.exit, size=19)
        for i, (tab, label) in enumerate(TABS):
            rect = pygame.Rect(16 + i * 190, 66, 178, 40)
            self.button(surf, rect, label, lambda t=tab: setattr(self, "tab", t), toggled=self.tab == tab, size=21)
        ready = bool(self.c.ready_fleet())
        self.button(
            surf, pygame.Rect(1000, 66, 264, 40), f"Set Sail: {m.title}", self.set_sail,
            size=21, color=(40, 96, 60) if ready else None,
        )

    def _tooltip(self, surf: pygame.Surface, tip: str) -> None:
        lines = wrap(tip, 18, 360)
        box = pygame.Rect(self.mouse[0] + 14, self.mouse[1] + 18, 380, 12 + 20 * len(lines))
        box.clamp_ip(pygame.Rect(0, 0, *T.WINDOW))
        pygame.draw.rect(surf, (8, 14, 22), box, border_radius=6)
        pygame.draw.rect(surf, T.PANEL_EDGE, box, 1, border_radius=6)
        for i, line in enumerate(lines):
            text(surf, line, (box.x + 10, box.y + 7 + i * 20), 18, T.TEXT)

    # ---- math page ----

    def _draw_math(self, surf: pygame.Surface) -> None:
        card = pygame.Rect(16, 116, 860, 596)
        panel(surf, card)
        x0 = card.x + 16
        for i, school in enumerate(SCHOOLS.values()):
            rect = pygame.Rect(x0 + i * 300, card.y + 12, 290, 40)
            self.button(surf, rect, f"{school.name}  ({school.subject})", lambda s=school.id: self.set_school(s),
                        toggled=self.school == school.id, size=20)
        topics = [t for t in TOPICS.values() if t.school == self.school and self.c.topic_open(t.id)]
        chip = (card.width - 32 - 7 * (len(topics) - 1)) // len(topics)
        for i, topic in enumerate(topics):
            rect = pygame.Rect(x0 + i * (chip + 7), card.y + 60, chip, 34)
            on = topic.id in self.c.topics
            self.button(surf, rect, "", lambda t=topic.id: self.toggle_topic(t), toggled=on)
            currency_icon(surf, (rect.x + 16, rect.centery), topic.currency, 8)
            text(surf, topic.short, (rect.x + 30, rect.centery), 18 if len(topics) <= 4 else 17, T.TEXT if on else T.FAINT,
                 "midleft")
        self._draw_problem(surf, pygame.Rect(card.x + 16, card.y + 104, card.width - 32, card.height - 116))
        self._draw_math_side(surf, pygame.Rect(892, 116, 372, 596))

    def _draw_problem(self, surf: pygame.Surface, area: pygame.Rect) -> None:
        p = self.posed
        if p is None:
            return
        prob = p.problem
        y = area.y
        badge = f"{p.topic.name}  -  {TIER_NAMES[p.tier]}"
        r = text(surf, badge.upper(), (area.x, y), 17, T.CURRENCY_COLORS[p.topic.currency])
        if self.reviewing:
            text(surf, "REVIEW: you missed one like this. Try again!", (r.right + 16, y), 17, T.ACCENT)
        self.button(surf, pygame.Rect(area.right - 110, y - 4, 110, 28), "? Help (H)", lambda: setattr(self, "show_help", True), size=17)
        if p.topic.id == "trig":
            self.button(surf, pygame.Rect(area.right - 250, y - 4, 132, 28), "Trig table (T)",
                        lambda: setattr(self, "show_trig", True), size=17)
        y += 28
        # Choices and feedback sit at the bottom; the story and equation fill the space above.
        choices_top = area.bottom - 186
        for size in (20, 18, 17, 16):
            story = mwrap(prob.story, size, area.width)
            ask = mwrap(prob.ask, size + 1, area.width, bold=True)
            expr = prob.expr.split("\n") if self.show_equation else []
            needed = len(story) * (size + 6) + len(ask) * (size + 7) + len(expr) * 38 + (22 if prob.note and self.show_equation else 0) + 44
            if y + needed <= choices_top:
                break
        for line in story:
            mtext(surf, line, (area.x, y), size, T.TEXT)
            y += size + 6
        y += 8
        if self.show_equation:
            for line in expr:
                mtext(surf, line, (area.centerx, y), 28, T.ACCENT, "midtop", bold=True)
                y += 38
            if prob.note:
                mtext(surf, prob.note, (area.centerx, y), 16, T.DIM, "midtop")
                y += 22
        else:
            self.button(surf, pygame.Rect(area.centerx - 130, y, 260, 30), "Show the equation (E)",
                        lambda: setattr(self, "show_equation", True), size=18)
            y += 38
        y += 4
        for line in ask:
            mtext(surf, line, (area.x, y), size + 1, T.TEXT, bold=True)
            y += size + 7

        # the four choices, 2 x 2
        w = (area.width - 12) // 2
        for i, choice in enumerate(p.choices):
            rect = pygame.Rect(area.x + (i % 2) * (w + 12), choices_top + (i // 2) * 68, w, 58)
            if self.picked is None:
                fill = T.BUTTON_HOVER if rect.collidepoint(self.mouse) else T.BUTTON
                edge = T.PANEL_EDGE
            elif i == p.answer:
                fill, edge = (34, 92, 56), T.GOOD
            elif i == self.picked:
                fill, edge = (110, 40, 36), T.BAD
            else:
                fill, edge = (22, 30, 42), T.PANEL_EDGE
            pygame.draw.rect(surf, fill, rect, border_radius=8)
            pygame.draw.rect(surf, edge, rect, 2, border_radius=8)
            key = pygame.Rect(rect.x + 10, rect.centery - 13, 26, 26)
            pygame.draw.rect(surf, (10, 16, 26), key, border_radius=5)
            text(surf, str(i + 1), key.center, 20, T.ACCENT, "center")
            if self.picked is not None and i in (p.answer, self.picked):  # marks, not just colours
                mark, color = ("✓", T.GOOD) if i == p.answer else ("✗", T.BAD)
                mtext(surf, mark, (rect.right - 16, rect.centery), 28, color, "midright", bold=True)
            lines = mwrap(choice, 21, rect.width - 90)
            csize = 21 if len(lines) == 1 else 16
            lines = mwrap(choice, csize, rect.width - 90)[:2]
            for j, line in enumerate(lines):
                cy = rect.centery + (j - (len(lines) - 1) / 2) * (csize + 3)
                mtext(surf, line, (rect.x + 48, cy), csize, T.TEXT if self.picked is None or i in (p.answer, self.picked) else T.FAINT, "midleft")
            if self.picked is None:
                self.hits.append((rect, lambda k=i: self.answer(k)))

        # feedback row
        fy = area.bottom - 40
        message, color = self.feedback
        if self.picked is None:
            topic = p.topic
            pay = reward(topic.id, p.tier, self.c.streak + 1)
            r = text(surf, f"Answer with 1-4 or a click.   Right: +{pay}", (area.x, fy + 8), 19, T.DIM)
            currency_icon(surf, (r.right + 14, r.centery), topic.currency, 8)
            r = text(surf, CURRENCY_NAMES[topic.currency], (r.right + 26, fy + 8), 19, T.CURRENCY_COLORS[topic.currency])
            text(surf, f"   Wrong: -{penalty(topic.id, p.tier)}", (r.right, fy + 8), 19, T.DIM)
        else:
            mark = "✓" if self.picked == p.answer else "✗"
            r = mtext(surf, mark, (area.x, fy + 4), 24, color, bold=True)
            text(surf, message, (r.right + 8, fy + 6), 24, color)
            if not self.show_working:
                self.button(surf, pygame.Rect(area.right - 330, fy, 200, 36), "Show the working (W)",
                            lambda: setattr(self, "show_working", True), size=18)
            self.button(surf, pygame.Rect(area.right - 120, fy, 120, 36), "Next  (Enter)", self.next_problem, size=18)

    def _draw_math_side(self, surf: pygame.Surface, area: pygame.Rect) -> None:
        panel(surf, area)
        x = area.x + 18
        school = SCHOOLS[self.school]
        level = self.c.difficulty.get(self.school, 2)
        slider = self.sliders["difficulty"]
        if not slider.dragging:
            slider.index = level - 1
        text(surf, f"DIFFICULTY - {school.name.upper()}", (x, area.y + 12), 17, T.DIM)
        text(surf, f"{level}: {LEVEL_NAMES[level]}", (area.right - 18, area.y + 12), 19, T.ACCENT, "topright")
        self.sliders["difficulty"].draw(surf, [str(n) for n in LEVEL_NAMES])
        mix = {1: "one-step problems", 2: "mostly one-step, some multi-step", 3: "a mix of everything",
               4: "mostly multi-step problems", 5: "the hardest multi-step problems"}[level]
        text(surf, mix, (x, area.y + 88), 17, T.FAINT)
        text(surf, "PAY", (x, area.y + 118), 17, T.DIM)
        text(surf, f"about x{round(level_pay(level), 1):g} at this level", (area.right - 18, area.y + 118), 19, T.ACCENT, "topright")
        tiers = "   ".join(f"{TIER_NAMES[t]} x{TIER_PAY[t]:g}" for t in TIER_PAY)
        text(surf, tiers, (x, area.y + 140), 17, T.TEXT)
        text(surf, f"A wrong answer costs {WRONG_PENALTY:.0%} of the pay, so guessing", (x, area.y + 160), 16, T.FAINT)
        text(surf, "doesn't pay off.", (x, area.y + 177), 16, T.FAINT)
        streak = self.c.streak
        bonus = streak_bonus(streak + 1)
        text(surf, f"Streak {streak}" + (f"  (next answer +{bonus:.0%})" if bonus else ""), (x, area.y + 206), 19, T.TEXT)
        records = self.c.stats.get("records", {})
        text(surf, f"Best {records.get('best_streak', 0)}", (area.right - 18, area.y + 206), 19, T.DIM, "topright")

        # figure (Broadside) or worked solution
        box = pygame.Rect(area.x + 12, area.y + 236, area.width - 24, area.height - 248)
        p = self.posed
        if p is None:
            return
        if self.show_working:
            panel(surf, box, (14, 22, 34))
            y = box.y + 10
            reason = p.reason(self.picked) if self.picked is not None else ""
            if reason:
                text(surf, "WHAT WENT WRONG", (box.x + 12, y), 17, T.BAD)
                y += 22
                for line in mwrap(reason, 16, box.width - 24):
                    mtext(surf, line, (box.x + 12, y), 16, (250, 190, 180))
                    y += 21
                y += 10
            text(surf, "WORKING", (box.x + 12, y), 17, T.ACCENT)
            y += 24
            for n, step in enumerate(p.problem.solution, 1):
                lines = mwrap(f"{n}. {step}", 16, box.width - 24)
                for line in lines:
                    if y > box.bottom - 20:
                        break
                    mtext(surf, line, (box.x + 12, y), 16, T.TEXT)
                    y += 21
                y += 4
            room = pygame.Rect(box.x + 8, y + 4, box.width - 16, box.bottom - y - 12)
            if p.problem.fig and draw_figure is not None and room.height >= 130:  # the figure too, if it fits
                draw_figure(surf, room, p.problem.fig)
        elif p.problem.fig and draw_figure is not None:
            panel(surf, box, (14, 22, 34))
            draw_figure(surf, box.inflate(-16, -16), p.problem.fig)
        else:
            y = box.y + 6
            tips = [
                "Each topic pays one currency:",
            ]
            for tip in tips:
                text(surf, tip, (box.x + 4, y), 18, T.DIM)
                y += 26
            for cur in self.c.currencies:
                currency_icon(surf, (box.x + 14, y + 10), cur, 8)
                names = " / ".join(t.short for t in TOPICS.values() if t.currency == cur)
                text(surf, CURRENCY_NAMES[cur], (box.x + 30, y), 18, T.CURRENCY_COLORS[cur])
                for line in wrap(names, 16, box.width - 40):
                    y += 18
                    text(surf, line, (box.x + 30, y), 16, T.FAINT)
                y += 28

    def _draw_help(self, surf: pygame.Surface) -> None:
        p = self.posed
        b = briefing(p) if p else None
        shade = pygame.Surface(T.WINDOW, pygame.SRCALPHA)
        shade.fill((4, 8, 14, 170))
        surf.blit(shade, (0, 0))
        box = pygame.Rect(0, 0, 820, 600)
        box.center = (T.WINDOW[0] // 2, T.WINDOW[1] // 2 + 20)
        panel(surf, box, radius=12)
        x, y, w = box.x + 28, box.y + 20, box.width - 56
        if b is None:
            text(surf, "No briefing for this one.", (x, y), 26, T.TEXT)
            return
        mtext(surf, b.title, (x, y), 28, T.ACCENT, bold=True)
        y += 44
        sections = [("WHAT'S GOING ON", [b.concept]), ("HOW TO ATTACK IT", [f"{i}. {s}" for i, s in enumerate(b.steps, 1)]),
                    ("WORKED EXAMPLE", [b.example]), ("HINT FOR THIS PROBLEM", [p.problem.hint])]
        for title, paras in sections:
            text(surf, title, (x, y), 17, T.DIM)
            y += 22
            for para in paras:
                for line in mwrap(para, 17, w):
                    mtext(surf, line, (x, y), 17, T.TEXT)
                    y += 22
            y += 10
        text(surf, "Using the briefing never costs you anything. Press H or Esc to close.", (box.centerx, box.bottom - 30), 17, T.FAINT, "midtop")
        self.hits.append((box, lambda: setattr(self, "show_help", False)))

    def _draw_trig_table(self, surf: pygame.Surface) -> None:
        """The table every Broadside trig answer is worked out from."""
        shade = pygame.Surface(T.WINDOW, pygame.SRCALPHA)
        shade.fill((4, 8, 14, 170))
        surf.blit(shade, (0, 0))
        box = pygame.Rect(0, 0, 700, 540)
        box.center = (T.WINDOW[0] // 2, T.WINDOW[1] // 2 + 20)
        panel(surf, box, radius=12)
        x, y = box.x + 28, box.y + 20
        text(surf, "TRIG TABLE", (x, y), 34, T.ACCENT)
        y += 40
        for line in wrap("Every answer uses these values, rounded to 2 decimals. A calculator's last digit can be "
                         "a little different: go with the table.", 18, box.width - 56):
            text(surf, line, (x, y), 18, T.DIM)
            y += 21
        y += 12
        cols = [x + 10, x + 110, x + 200, x + 290]
        for cx, head in zip(cols, ("angle", "sin", "cos", "tan")):
            text(surf, head, (cx, y), 19, T.ACCENT)
        y += 28
        for i, (angle, (sin, cos, tan)) in enumerate(TRIG.items()):
            if i % 2 == 0:
                pygame.draw.rect(surf, (24, 36, 52), (x, y - 3, 370, 26), border_radius=4)
            for cx, cell in zip(cols, (f"{angle}°", f"{sin:g}", f"{cos:g}", f"{tan:g}")):
                mtext(surf, cell, (cx, y), 17, T.TEXT)
            y += 26
        sx, sy = x + 420, box.y + 124
        text(surf, "SMALL ANGLES", (sx, sy), 19, T.ACCENT)
        text(surf, "for the stadimeter", (sx, sy + 22), 16, T.DIM)
        sy += 50
        for cx, head in zip((sx + 10, sx + 110), ("angle", "tan")):
            text(surf, head, (cx, sy), 19, T.ACCENT)
        sy += 28
        for i, (angle, tan) in enumerate(SMALL_TAN.items()):
            if i % 2 == 0:
                pygame.draw.rect(surf, (24, 36, 52), (sx, sy - 3, 200, 26), border_radius=4)
            mtext(surf, f"{angle}°", (sx + 10, sy), 17, T.TEXT)
            mtext(surf, f"{tan:g}", (sx + 110, sy), 17, T.TEXT)
            sy += 26
        tips = ["sin = opposite ÷ hypotenuse", "cos = adjacent ÷ hypotenuse", "tan = opposite ÷ adjacent"]
        for i, tip in enumerate(tips):
            mtext(surf, tip, (sx, sy + 24 + i * 24), 16, T.DIM)
        text(surf, "Press T or Esc to close.", (box.centerx, box.bottom - 30), 17, T.FAINT, "midtop")
        self.hits.append((box, lambda: setattr(self, "show_trig", False)))

    # ---- upgrades page ----

    def _view_switch(self, surf: pygame.Surface, attr: str, views: list[tuple[str, str]]) -> None:
        """Buttons at the top right of a page that switch between its views."""
        x = CONTENT.right
        for view, label in reversed(views):
            rect = pygame.Rect(x - 170, CONTENT.y - 6, 170, 30)
            self.button(surf, rect, label, lambda v=view: setattr(self, attr, v), toggled=getattr(self, attr) == view, size=18)
            x -= 178

    def _draw_upgrades(self, surf: pygame.Surface) -> None:
        self._view_switch(surf, "upgrade_view", [("act1", "Act I upgrades"), ("future", "Future Tech")])
        if self.upgrade_view == "future":
            self._draw_future_tech(surf)
            return
        text(surf, "Upgrades apply to every ship in your fleet, and to ships you build later.", (CONTENT.x, CONTENT.y), 19, T.DIM)
        col_w = (CONTENT.width - 3 * 16) // 4
        for ci, cat in enumerate(CATEGORIES):
            x = CONTENT.x + ci * (col_w + 16)
            y = CONTENT.y + 30
            text(surf, cat.upper(), (x, y), 22, T.ACCENT)
            y += 30
            for track in (t for t in TRACKS.values() if t.category == cat):
                rect = pygame.Rect(x, y, col_w, 124)
                self._upgrade_card(surf, rect, track)
                y += 134

    def _draw_future_tech(self, surf: pygame.Surface) -> None:
        intro = "Future Tech costs Plasma, and each one builds on Act I upgrades."
        if not self.c.plasma_open:
            intro = f"Future Tech opens with Plasma when you win mission {PLASMA_MISSION - 1}. Here is what's coming."
        text(surf, intro, (CONTENT.x, CONTENT.y), 19, T.DIM)
        tracks = [t for t in TRACKS.values() if t.future]
        cols, gap, h = 3, 16, 172
        w = (CONTENT.width - (cols - 1) * gap) // cols
        for i, track in enumerate(tracks):
            rect = pygame.Rect(CONTENT.x + (i % cols) * (w + gap), CONTENT.y + 36 + (i // cols) * (h + 10), w, h)
            self._upgrade_card(surf, rect, track)

    def _upgrade_card(self, surf: pygame.Surface, rect: pygame.Rect, track) -> None:
        needs = self.c.upgrade_needs(track.id)
        panel(surf, rect, (16, 22, 32) if needs else T.PANEL_BG)
        level = self.c.level(track.id)
        text(surf, track.name, (rect.x + 12, rect.y + 10), 22, T.TEXT if not needs else T.DIM)
        for i in range(track.max_level):
            cx = rect.right - 14 - (track.max_level - 1 - i) * 14
            pygame.draw.circle(surf, T.ACCENT if i < level else T.PANEL_EDGE, (cx, rect.y + 20), 5)
        effect = track.effect if track.future else track.effect + " per level"
        for j, line in enumerate(wrap(effect, 17, rect.width - 24)[:4 if track.future else 2]):
            text(surf, line, (rect.x + 12, rect.y + 38 + j * 19), 17, (190, 202, 216))
        cost = self.c.upgrade_cost(track.id)
        if cost is None:
            text(surf, "FULLY UPGRADED", (rect.x + 12, rect.bottom - 30), 18, T.GOOD)
            return
        if needs:
            for j, line in enumerate(reversed(wrap("Needs " + ", ".join(needs), 17, rect.width - 24)[:2])):
                text(surf, line, (rect.x + 12, rect.bottom - 26 - j * 19), 17, T.WARN)
            return
        cost_row(surf, (rect.x + 12, rect.bottom - 22), cost, self.c.currency, size=19)
        afford = self.c.can_afford(cost)
        self.button(surf, pygame.Rect(rect.right - 84, rect.bottom - 40, 74, 32), "Buy", lambda t=track.id: self.buy_upgrade(t),
                    enabled=afford, size=19, color=(40, 96, 60) if afford else None)

    # ---- shipyard page ----

    def _draw_shipyard(self, surf: pygame.Surface) -> None:
        self._view_switch(surf, "shipyard_view", [("act1", "Act I ships"), ("future", "Plasma ships"),
                                                  ("retrofits", "Retrofits")])
        if self.shipyard_view == "retrofits":
            self._draw_retrofits(surf)
            return
        future = self.shipyard_view == "future"
        intro = ("Act III classes, unlocked with Plasma." if future
                 else "Build new ships. Bigger classes unlock with blueprints.")
        text(surf, intro, (CONTENT.x, CONTENT.y), 19, T.DIM)
        y = CONTENT.y + 28
        for cls in (c for c in SHIP_CLASSES.values() if c.future == future):
            rect = pygame.Rect(CONTENT.x, y, CONTENT.width, 88)
            self._ship_row(surf, rect, cls)
            y += 94

    def _ship_row(self, surf: pygame.Surface, rect: pygame.Rect, cls) -> None:
        state = self.c.class_state(cls.id)
        panel(surf, rect, (20, 30, 44) if state == "available" else (16, 22, 32))
        design = self.c.class_design(cls.id)
        draw_ship(surf, (rect.x + 80, rect.centery), design.hull.id, 0, 0.0, 255 if state == "available" else 110, 1.7,
                  missiles=design.has_missiles)
        x = rect.x + 170
        r = text(surf, cls.name, (x, rect.y + 10), 26, T.TEXT if state == "available" else T.DIM)
        fitted = self.c.retrofits.get(cls.id, [])
        if fitted:
            text(surf, " + ".join(RETROFITS[k].name for k in fitted), (r.right + 14, r.centery), 17, T.ACCENT, "midleft")
        text(surf, cls.blurb, (x, rect.y + 36), 18, T.DIM)
        stats = f"{self._stats(design)}   {self._weapons(design)}"
        text(surf, stats, (x, rect.y + 60), 17, T.FAINT if state != "available" else T.TEXT)
        ready, wrecked = self.c.fleet.get(cls.id, 0), self.c.wrecks.get(cls.id, 0)
        owned = f"In fleet: {ready}" + (f"  (+{wrecked} wrecked)" if wrecked else "")
        text(surf, owned, (rect.right - 440, rect.y + 12), 18, T.TEXT if ready else T.FAINT)
        if state == "available":
            cost_row(surf, (rect.right - 440, rect.y + 58), cls.price, self.c.currency, size=19)
            afford = self.c.can_afford(cls.price)
            self.button(surf, pygame.Rect(rect.right - 124, rect.y + 24, 110, 40), "Build", lambda c=cls.id: self.buy_ship(c),
                        enabled=afford, color=(40, 96, 60) if afford else None)
        elif state == "unlockable":
            text(surf, "Unlock:", (rect.right - 440, rect.y + 48), 18, T.DIM)
            cost_row(surf, (rect.right - 370, rect.y + 58), cls.unlock, self.c.currency, size=19)
            afford = self.c.can_afford(cls.unlock)
            self.button(surf, pygame.Rect(rect.right - 124, rect.y + 24, 110, 40), "Unlock", lambda c=cls.id: self.unlock(c),
                        enabled=afford, color=(40, 70, 110) if afford else None)
        else:
            text(surf, f"Win mission {cls.requires_mission - 1} to unlock", (rect.right - 440, rect.y + 48), 18, T.FAINT)

    @staticmethod
    def _stats(design) -> str:
        field = f"   Field {design.max_field}" if design.max_field else ""
        return f"Hull {design.max_hp}   Speed {design.speed}   Belt {design.belt}{field}"

    @staticmethod
    def _weapons(design) -> str:
        return ", ".join(f"{m.count}x {m.weapon.name}" for m in design.mounts)

    # ---- retrofits (a view of the shipyard) ----

    def _draw_retrofits(self, surf: pygame.Surface) -> None:
        intro = "Fit future tech to every ship of an older class, now and later. Bigger hulls cost more."
        if not self.c.plasma_open:
            intro = f"Retrofits open with Plasma when you win mission {PLASMA_MISSION - 1}. Here is what's coming."
        text(surf, intro, (CONTENT.x, CONTENT.y), 19, T.DIM)
        y = CONTENT.y + 28
        tips: list[str] = []
        for cls in (c for c in SHIP_CLASSES.values() if c.retrofittable):
            self._retrofit_row(surf, pygame.Rect(CONTENT.x, y, CONTENT.width, 88), cls, tips)
            y += 94
        if tips:  # over the rows below, not under them
            self._tooltip(surf, tips[0])

    def _retrofit_row(self, surf: pygame.Surface, rect: pygame.Rect, cls, tips: list[str]) -> None:
        state = self.c.class_state(cls.id)
        panel(surf, rect, (20, 30, 44) if state == "available" else (16, 22, 32))
        design = self.c.class_design(cls.id)
        draw_ship(surf, (rect.x + 80, rect.centery), design.hull.id, 0, 0.0, 255 if state == "available" else 110, 1.7,
                  missiles=design.has_missiles)
        cell_w, gap = 330, 10
        x, room = rect.x + 170, rect.width - 170 - 2 * (cell_w + gap) - 14
        text(surf, cls.name, (x, rect.y + 8), 24, T.TEXT if state == "available" else T.DIM)
        ships = self.c.ships(cls.id)
        text(surf, f"{ships} in the fleet" if ships else "none in the fleet", (x + room, rect.y + 13), 16,
             T.DIM if ships else T.FAINT, "topright")
        color = T.TEXT if state == "available" else T.FAINT
        for j, line in enumerate([self._stats(design)] + wrap(self._weapons(design), 16, room)[:2]):
            text(surf, line, (x, rect.y + 36 + j * 17), 16, color)
        for i, rid in enumerate(RETROFITS):
            cell = pygame.Rect(rect.right - 2 * (cell_w + gap) + i * (cell_w + gap), rect.y + 6, cell_w, rect.height - 12)
            self._retrofit_cell(surf, cell, cls, rid)
            if cell.collidepoint(self.mouse):
                r = RETROFITS[rid]
                cost = cost_text(self.c.retrofit_cost(cls.id, rid))
                tips.append(f"{r.name}: {r.effect} Needs {TRACKS[r.requires].name}. {cost} for the whole class.")

    def _retrofit_change(self, class_id: str, retrofit_id: str) -> str:
        """What the retrofit does to this class, with the fleet's upgrades (and at least level 1 of its tech)."""
        r = RETROFITS[retrofit_id]
        levels = dict(self.c.upgrades)
        levels[r.requires] = max(1, levels.get(r.requires, 0))
        others = [k for k in self.c.retrofits.get(class_id, []) if k != retrofit_id]
        base = retrofit(SHIP_CLASSES[class_id].design, others)
        before, after = refit(base, levels), refit(retrofit(base, others + [retrofit_id]), levels)
        if retrofit_id == "field_generator":
            return f"Field {before.max_field} → {after.max_field} a ship"

        def lasers(d) -> int:
            return sum(m.count for m in d.mounts if m.weapon.kind == "laser")

        change = f"Lasers {lasers(before)} → {lasers(after)} a ship"
        light = light_guns(base)
        if light is not None:
            out = next(m for m in before.mounts if m.weapon.id == light.weapon.id)
            change += f", {out.count}x {out.weapon.name} out"
        return change

    def _retrofit_cell(self, surf: pygame.Surface, cell: pygame.Rect, cls, retrofit_id: str) -> None:
        r = RETROFITS[retrofit_id]
        fitted = self.c.has_retrofit(cls.id, retrofit_id)
        needs = self.c.retrofit_needs(cls.id, retrofit_id)
        panel(surf, cell, (30, 46, 40) if fitted else (14, 22, 34), T.GOOD if fitted else T.PANEL_EDGE)
        text(surf, r.name, (cell.x + 10, cell.y + 6), 20, T.TEXT if fitted or not needs else T.DIM)
        change = self._retrofit_change(cls.id, retrofit_id)
        size = next((n for n in (15, 14, 13) if T.math_font(n).size(change)[0] <= cell.width - 20), 12)
        mtext(surf, change, (cell.x + 10, cell.y + 31), size, (190, 202, 216) if fitted or not needs else T.FAINT)
        bottom = cell.bottom - 14
        if fitted:
            text(surf, "FITTED", (cell.x + 10, bottom), 18, T.GOOD, "midleft")
        elif needs:
            text(surf, "Needs " + ", ".join(needs), (cell.x + 10, bottom), 16, T.WARN, "midleft")
        else:
            cost = self.c.retrofit_cost(cls.id, retrofit_id)
            cost_row(surf, (cell.x + 10, bottom), cost, self.c.currency, size=18)
            afford = self.c.can_afford(cost)
            self.button(surf, pygame.Rect(cell.right - 70, cell.bottom - 32, 62, 26), "Fit",
                        lambda c=cls.id, k=retrofit_id: self.buy_retrofit(c, k), enabled=afford, size=18,
                        color=(40, 96, 60) if afford else None)

    # ---- fleet page ----

    def _draw_fleet(self, surf: pygame.Surface) -> None:
        left = pygame.Rect(CONTENT.x, CONTENT.y, 620, CONTENT.height)
        panel(surf, left)
        text(surf, "YOUR FLEET", (left.x + 16, left.y + 12), 22, T.ACCENT)
        share = {1: "a twelfth", 2: "a sixteenth"}.get(self.c.level("nanite"), "an eighth")
        text(surf, f"Wrecks are towed home. Repairing one costs {share} of a new ship's price.", (left.x + 16, left.y + 32), 17, T.DIM)
        text(surf, "Six squadrons can sail at once: click Sails / In port to choose.", (left.x + 16, left.y + 50), 17, T.DIM)
        y = left.y + 76
        owned = [cls for cls in SHIP_CLASSES.values() if self.c.fleet.get(cls.id, 0) or self.c.wrecks.get(cls.id, 0)]
        rh = 70 if len(owned) <= 6 else 52
        sailing = {cls.id for cls, _ in self.c.sailing_fleet()}
        for cls in owned:
            ready, wrecked = self.c.fleet.get(cls.id, 0), self.c.wrecks.get(cls.id, 0)
            row = pygame.Rect(left.x + 12, y, left.width - 24, rh)
            panel(surf, row, (22, 32, 46))
            draw_ship(surf, (row.x + 56, row.centery), cls.design.hull.id, 0, 0.0, 255, 1.3 if rh > 60 else 1.0,
                      missiles=cls.design.has_missiles)
            top, low = row.y + (10 if rh > 60 else 5), row.bottom - (32 if rh > 60 else 25)
            text(surf, cls.name, (row.x + 120, top), 22 if rh > 60 else 20, T.TEXT)
            r = text(surf, f"{ready} ready", (row.x + 120, low + 3), 18 if rh > 60 else 16, T.GOOD if ready else T.FAINT)
            if wrecked:
                text(surf, f"{wrecked} wrecked", (r.right + 12, low + 3), 18 if rh > 60 else 16, T.BAD)
                cost = self.c.repair_cost(cls.id)
                r = text(surf, "Repair each:", (row.x + 300, top + 2), 16, T.DIM)
                cost_row(surf, (r.right + 8, r.centery), cost, self.c.currency, size=17)
                afford = self.c.can_afford(cost)
                self.button(surf, pygame.Rect(row.right - 196, low - 2, 88, 26), "Repair", lambda c=cls.id: self.repair(c),
                            enabled=afford, size=17, color=(40, 96, 60) if afford else None)
                self.button(surf, pygame.Rect(row.right - 100, low - 2, 92, 26), "Repair all", lambda c=cls.id: self.repair(c, True),
                            enabled=afford, size=17)
            if ready:
                sails = cls.id in sailing
                self.button(surf, pygame.Rect(row.x + 300, low - 2, 96, 26), "Sails" if sails else "In port",
                            lambda c=cls.id: self.toggle_port(c), toggled=sails, size=17)
            y += rh + (8 if rh > 60 else 4)
        if not owned:
            text(surf, "No ships! Build some in the Shipyard.", (left.x + 16, y), 22, T.BAD)

        right = pygame.Rect(left.right + 16, CONTENT.y, CONTENT.right - left.right - 16, CONTENT.height)
        panel(surf, right)
        m = self.c.mission
        x, w = right.x + 16, right.width - 32
        text(surf, f"NEXT: {m.title.upper()}", (x, right.y + 12), 22, T.WARN if m.is_super else T.ACCENT)
        text(surf, m.name, (x, right.y + 40), 28, T.TEXT)
        y = right.y + 74
        for line in wrap(m.briefing, 18, w):
            text(surf, line, (x, y), 18, T.DIM)
            y += 21
        y += 6
        y = self._enemy_list(surf, x, y, m, width=w)
        y += 16
        text(surf, "CAMPAIGN", (x, y), 20, T.ACCENT)
        if self.c.can_skirmish(1):
            text(surf, "Click a mission you've won to replay it", (x + w, y + 3), 15, T.DIM, "topright")
        y += 26
        self.mission_rows = {}
        col_w = w // 3  # a column for each act
        for n in range(1, MISSION_COUNT + 1):
            col, row = (n - 1) // 10, (n - 1) % 10
            pos = (x + col * col_w, y + row * 20)
            done = self.c.can_skirmish(n)
            if done:
                rect = self.mission_rows[n] = pygame.Rect(pos[0] - 4, pos[1] - 2, col_w - 4, 20)
                self.hits.append((rect, lambda n=n: self.open_skirmish(n)))
                if rect.collidepoint(self.mouse):
                    pygame.draw.rect(surf, T.BUTTON_HOVER, rect, border_radius=4)
            color = T.GOOD if done else T.ACCENT if n == self.c.mission_number else SUPER_FAINT if mission(n).is_super else T.FAINT
            text(surf, f"{n}. {mission(n).name}", pos, 15, color)
        if self.c.mission_number > MISSION_COUNT:
            text(surf, f"Endless patrols: {self.c.mission_number - MISSION_COUNT} so far", (x, right.bottom - 36), 18, T.ACCENT)

    # ---- logbook page ----

    def _skill_records(self) -> list[tuple[str, int, int]]:
        """(skill, right, tried) over the latest answers, for kinds of problem that share a briefing."""
        right: dict[str, int] = {}
        tried: dict[str, int] = {}
        for key, results in self.c.skills.items():
            title = skill_title(key)
            right[title] = right.get(title, 0) + results.count("1")
            tried[title] = tried.get(title, 0) + len(results)
        return [(t, right[t], tried[t]) for t in tried]

    def _draw_logbook(self, surf: pygame.Surface) -> None:
        left = pygame.Rect(CONTENT.x, CONTENT.y, 700, CONTENT.height)
        panel(surf, left)
        x, y = left.x + 16, left.y + 12
        text(surf, "HOW EACH TOPIC IS GOING", (x, y), 22, T.ACCENT)
        text(surf, "all your answers so far", (left.right - 16, y + 4), 16, T.DIM, "topright")
        y += 34
        for school in SCHOOLS.values():
            text(surf, f"{school.name} ({school.subject})", (x, y), 19, T.DIM)
            y += 26
            for topic in (t for t in TOPICS.values() if t.school == school.id):
                solved, tried = self.c.record("topic", topic.id)
                currency_icon(surf, (x + 10, y + 10), topic.currency, 8)
                text(surf, topic.name, (x + 26, y + 2), 19, T.TEXT if tried else T.FAINT)
                bar(surf, pygame.Rect(x + 300, y + 4, 180, 14), solved / tried if tried else 0.0,
                    T.GOOD if tried and solved / tried >= 0.8 else T.ACCENT if tried and solved / tried >= 0.5 else T.BAD)
                score = f"{solved} of {tried} right" if tried else "not tried yet"
                if not self.c.topic_open(topic.id):
                    score = f"opens after mission {PLASMA_MISSION - 1}"
                text(surf, score, (left.right - 16, y + 2), 18, T.TEXT if tried else T.FAINT, "topright")
                tiers = []
                for tier, name in TIER_NAMES.items():
                    s_, t_ = self.c.record("tier", f"{topic.id}:{tier}")
                    if t_:
                        tiers.append(f"{name} {s_ / t_:.0%} ({t_})")
                if tiers:
                    text(surf, "   ".join(tiers), (x + 26, y + 22), 15, T.DIM)
                y += 44
            y += 6

        right = pygame.Rect(left.right + 16, CONTENT.y, CONTENT.right - left.right - 16, CONTENT.height)
        panel(surf, right)
        x, y, w = right.x + 16, right.y + 12, right.width - 32
        skills = self._skill_records()
        weak = sorted((s for s in skills if s[2] >= 3 and s[1] / s[2] < 0.7), key=lambda s: (s[1] / s[2], -s[2]))[:5]
        strong = sorted((s for s in skills if s[2] >= 5 and s[1] / s[2] >= 0.9), key=lambda s: -s[2])[:4]
        text(surf, "NEEDS WORK", (x, y), 22, T.BAD)
        text(surf, "your latest answers", (x + w, y + 4), 16, T.DIM, "topright")
        y += 30
        if not weak:
            for line in wrap("Nothing here yet. Kinds of problem you keep missing show up here; the briefing (H) "
                             "for each one explains how it works.", 17, w):
                text(surf, line, (x, y), 17, T.FAINT)
                y += 20
        for title, ok, tried in weak:
            mtext(surf, title, (x, y), 15, T.TEXT)
            text(surf, f"{ok} of {tried} right", (x + w, y + 1), 17, T.BAD, "topright")
            y += 24
        y += 12
        waiting = len(self.c.review)
        text(surf, "WAITING FOR REVIEW", (x, y), 20, T.ACCENT)
        text(surf, f"{waiting} kind{'s' if waiting != 1 else ''} of problem" if waiting else "none", (x + w, y + 2), 18,
             T.TEXT, "topright")
        y += 26
        if waiting:
            for line in wrap("Kinds of problem you got wrong come back a couple of problems later, with new numbers, "
                             "until you get one right.", 16, w):
                text(surf, line, (x, y), 16, T.DIM)
                y += 19
        y += 14
        text(surf, "GOING WELL", (x, y), 20, T.GOOD)
        y += 28
        if not strong:
            text(surf, "Get five in a row of a kind right to see it here.", (x, y), 17, T.FAINT)
            y += 22
        for title, ok, tried in strong:
            mtext(surf, title, (x, y), 15, T.TEXT)
            text(surf, f"{ok} of {tried}", (x + w, y + 1), 17, T.GOOD, "topright")
            y += 24
        y = max(y + 14, right.bottom - 128)
        text(surf, "RECORDS", (x, y), 20, T.ACCENT)
        y += 28
        stats = self.c.stats
        solved = sum((stats.get("solved") or {}).values())
        tried = sum((stats.get("attempted") or {}).values())
        battles = stats.get("battles") or {}
        rows = [
            (f"Problems solved: {solved} of {tried}", f"Best streak: {(stats.get('records') or {}).get('best_streak', 0)}"),
            (f"Missions won: {self.c.mission_number - 1}", f"Battles lost: {battles.get('lost', 0)}"),
            (f"Earned: {sum((stats.get('earned') or {}).values())}", f"Lost to mistakes: {sum((stats.get('lost') or {}).values())}"),
        ]
        boost = stats.get("boost") or {}
        if boost.get("attempted"):
            rows.append((f"Math Boost: {boost.get('solved', 0)} of {boost['attempted']} right", ""))
        for a, b in rows:
            text(surf, a, (x, y), 17, T.TEXT)
            text(surf, b, (x + w // 2 + 20, y), 17, T.TEXT)
            y += 22

    def _enemy_list(self, surf: pygame.Surface, x: int, y: int, m, width: int = 560, below: int = 0) -> int:
        """Red's ships (super ships in red), then its upgrades, starting no higher than ``below``. For the
        campaign's next mission, less the ships earlier lost tries sank for good."""
        text(surf, "Red fleet:", (x, y), 19, (244, 150, 130))
        y += 24
        fleet = self.c.red_fleet() if m.number == self.c.mission_number else list(m.enemy)
        for (cid, n), (_, full) in zip(fleet, m.enemy):
            shown = text(surf, f"{n} x {ship_design(cid).name}", (x + 12, y), 19, T.TEXT if cid in SHIP_CLASSES else T.BAD)
            if n < full:
                text(surf, f"({full - n} still sunk)", (shown.right + 10, y + 2), 17, T.GOOD)
            y += 22
        y = max(y, below)
        if m.tech:
            techs = ", ".join(f"{TRACKS[t].name} {lv}" for t, lv in m.tech.items())
            for line in wrap("Red upgrades: " + techs, 17, width):
                text(surf, line, (x, y + 4), 17, T.WARN)
                y += 20
        return y

    def _draw_boost_setting(self, surf: pygame.Surface, box: pygame.Rect, y: int) -> None:
        """Math Boost on or off, just above the launch button."""
        x, w = box.x + 28, box.width - 56
        pygame.draw.line(surf, T.PANEL_EDGE, (x, y), (x + w, y))
        y += 12
        on = self.c.boost
        m = self.c.mission if self.skirmish is None else mission(self.skirmish)
        text(surf, "MATH BOOST", (x, y + 4), 22, T.ACCENT)
        self.button(surf, pygame.Rect(x + 150, y - 2, 110, 32), "ON  (B)" if on else "OFF  (B)", self.toggle_boost,
                    toggled=on, size=18)
        text(surf, "Problems from all five levels, mostly level 3", (x + 280, y + 6), 18, T.TEXT if on else T.FAINT)
        y += 38
        pct, miss = f"{BOOST:.0%}", f"{PENALTY:.0%}"
        how_many = f"up to {m.boosts} in this super mission" if m.is_super else "about 5-10 a battle"
        if on:
            about = (f"On a big hit ({how_many}) a MATH BOOST box comes up by the ship about to be hit: click it "
                     f"for a 7th-grade problem. Right: {pct} better (your hit harder, Red's softer). Wrong: {miss} worse.")
        else:
            about = (f"Turn it on for a 7th-grade problem on the battle's big hits: right answers make your hits {pct} "
                     f"stronger and Red's {pct} weaker, wrong ones {miss} the other way.")
        for line in wrap(about, 17, w)[:2]:
            text(surf, line, (x, y), 17, T.TEXT if on else T.DIM)
            y += 19

    def _draw_briefing(self, surf: pygame.Surface) -> None:
        shade = pygame.Surface(T.WINDOW, pygame.SRCALPHA)
        shade.fill((4, 8, 14, 170))
        surf.blit(shade, (0, 0))
        lessons = wrap("Last battle: " + self.c.lessons[0], 18, 700) if self.c.lessons else []
        m = self.c.mission if self.skirmish is None else mission(self.skirmish)
        # (a skirmish has its own note instead, and no room for both)
        super_note = wrap(SUPER_NOTE.format(opens=m.opens, boosts=m.boosts), 18, 704) if m.is_super and self.skirmish is None else []
        box = pygame.Rect(0, 0, 760, (470 if self.skirmish is None else 540) + BOOST_H + 22 * len(lessons) + (12 if lessons else 0)
                          + 22 * len(super_note))
        box.center = (T.WINDOW[0] // 2, T.WINDOW[1] // 2 + 20)
        panel(surf, box, radius=12)
        x = box.x + 28
        text(surf, f"{'SKIRMISH - ' if self.skirmish else ''}{m.title.upper()}", (x, box.y + 20), 22, T.WARN if m.is_super else T.DIM)
        text(surf, m.name, (x, box.y + 44), 40, T.ACCENT)
        y = box.y + 92
        for line in wrap(m.briefing, 20, box.width - 56):
            text(surf, line, (x, y), 20, T.TEXT)
            y += 24
        if super_note:
            y += 4
            for line in super_note:
                text(surf, line, (x, y), 18, T.WARN)
                y += 22
        if self.skirmish is not None:
            note = (f"A practice battle. A win pays a tenth of the prize money ({cost_text(m.skirmish_prize)}). "
                    "Sunk ships come home repaired for free, and your campaign stays where it is.")
            y += 6
            for line in wrap(note, 18, box.width - 56):
                text(surf, line, (x, y), 18, T.ACCENT)
                y += 22
        y += 12
        top = y
        fx = box.centerx + 20
        text(surf, "Your fleet:", (fx, top), 19, (140, 188, 248))
        y = top + 24
        sailing = self.c.sailing_fleet()
        for cls, n in sailing:
            text(surf, f"{n} x {cls.name}", (fx + 12, y), 19, T.TEXT)
            y += 22
        if not sailing:
            text(surf, "No seaworthy ships!", (fx + 12, y), 19, T.BAD)
            y += 22
        sail_ids = {cls.id for cls, _ in sailing}
        in_port = [cls.name for cls, _ in self.c.ready_fleet() if cls.id not in sail_ids]
        if in_port:
            text(surf, f"(In port: {', '.join(in_port)})", (fx, y + 2), 17, T.FAINT)
            y += 22
        wrecks = sum(self.c.wrecks.values())
        if wrecks:
            text(surf, f"({wrecks} wrecked ships stay in port)", (fx, y + 2), 17, T.FAINT)
            y += 22
        self._enemy_list(surf, x, top, m, width=box.width - 56, below=y + 4)
        for i, line in enumerate(lessons):  # what the last debrief said, right when it's useful
            text(surf, line, (x, box.bottom - 88 - BOOST_H - 22 * (len(lessons) - i)), 18, T.ACCENT)
        self._draw_boost_setting(surf, box, box.bottom - 80 - BOOST_H)
        ready = bool(self.c.ready_fleet())
        label = "Launch Battle" if self.skirmish is None else "Launch Skirmish"
        self.button(surf, pygame.Rect(box.centerx - 250, box.bottom - 70, 240, 48), label, self.launch,
                    enabled=ready, hint="Enter", color=(40, 96, 60) if ready else None)
        self.button(surf, pygame.Rect(box.centerx + 10, box.bottom - 70, 240, 48), "Not yet", self.close_briefing, hint="Esc")
