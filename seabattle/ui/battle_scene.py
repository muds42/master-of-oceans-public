"""The tactical battle screen.

The scene owns a :class:`Battle` plus a *visual* copy of every ship. The rules
engine resolves actions instantly and returns events; the scene turns each
event into a short animation and plays them one after another, updating the
visual copy as it goes so what you see matches the order things happened.

With Math Boost on (campaign missions, chosen on the briefing), every action is
previewed first. When it brings a big hit, the action plays up to that hit and
freezes just before it lands (shells in the air, torpedoes at the ship), with a
MATH BOOST box beside the ship about to be hit. Clicking the box (or B) opens a
7th-grade problem: a right answer makes the hit 30% stronger (your hit) or
weaker (theirs), a wrong one 15% weaker or stronger. Left alone for a few
seconds (or passed with Space), the hit lands as it was rolled. The side
panel's button turns the boost off for the rest of the mission.
"""

from __future__ import annotations

import math
import random
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Optional

import pygame

from ..ai import SimpleAI, expected_damage
from ..boost import BOOST, PENALTY, BigHit, MathBoost
from ..debrief import Debrief, debrief
from ..battle import (
    Action,
    Battle,
    BattleOver,
    EndTurn,
    Event,
    Fire,
    GunsFired,
    IllegalAction,
    Move,
    Moved,
    Pos,
    FieldRestored,
    Repaired,
    Retreat,
    RoundStarted,
    Stack,
    StackActivated,
    StackRetreated,
    StackSunk,
    SalvoHit,
    SalvoLaunched,
    SalvoLost,
    SalvoMoved,
    Withdraw,
    distance,
)
from ..campaign import mission
from ..problems.dinomath import DinoProblem
from . import sound
from . import theme as T
from .draw import (
    HULL_SHAPES, Button, Waves, bar, draw_island, draw_ship, draw_torpedo, island_shape, mtext, mwrap, ocean_surface, panel,
    text, wrap,
)
from .figures import draw_figure, draw_number_line

LOG_COLORS = [(140, 188, 248), (244, 150, 130)]
CHANCE_SECONDS = 5.0  # how long a MATH BOOST box waits for a click before the hit lands
GUN_HOLD = 0.17  # a boosted volley freezes this far in: the first shells nearly there
FIELD_COLOR = (120, 220, 255)  # force fields and holograms
LASER_COLORS = [(110, 200, 255), (255, 110, 150)]  # Blue beams, Red beams


def tile_to_screen(x: float, y: float) -> tuple[float, float]:
    return T.MAP_X + (x + 0.5) * T.TILE, T.MAP_Y + (y + 0.5) * T.TILE


def lerp(a, b, f: float):
    return (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)


def turn_toward(angle: float, target: float, max_step: float) -> float:
    diff = (target - angle + math.pi) % math.tau - math.pi
    return angle + max(-max_step, min(max_step, diff))


# --------------------------------------------------------------------------- visual state


@dataclass
class ShipVisual:
    side: int
    hull: str
    x: float
    y: float
    angle: float
    count: int
    hp: int
    max_hp: int
    missiles: bool = False
    alpha: float = 255
    visible: bool = True
    field: int = 0  # force field left on the top ship
    max_field: int = 0

    @property
    def screen(self) -> tuple[float, float]:
        return tile_to_screen(self.x, self.y)

    def stern(self) -> tuple[float, float]:
        half = HULL_SHAPES[self.hull][0] * T.TILE / 2
        cx, cy = self.screen
        return cx - math.cos(self.angle) * half, cy - math.sin(self.angle) * half


@dataclass
class TorpVisual:
    side: int
    x: float
    y: float
    angle: float
    count: int
    kind: str = "torpedo"
    alpha: float = 255

    @property
    def screen(self) -> tuple[float, float]:
        return tile_to_screen(self.x, self.y)


@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    life: float
    radius: float
    color: tuple
    grow: float = 0.0
    above: bool = True
    age: float = 0.0

    def update(self, dt: float) -> bool:
        self.age += dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vx *= 1 - min(1, 3 * dt)
        self.vy *= 1 - min(1, 3 * dt)
        self.radius += self.grow * dt
        return self.age < self.life

    def draw(self, layer: pygame.Surface) -> None:
        a = max(0.0, 1 - self.age / self.life)
        pygame.draw.circle(layer, (*self.color, round(210 * a)), (self.x, self.y), max(1, self.radius))


@dataclass
class FloatText:
    x: float
    y: float
    text: str
    color: tuple
    size: int = 26
    life: float = 1.4
    age: float = 0.0


# --------------------------------------------------------------------------- animations


class Anim:
    """One step of playback. ``duration`` is in (speed-scaled) seconds. With ``hold`` set the
    animation stops at that time until the scene clears it (a Math Boost chance)."""

    duration = 0.3
    text = ""
    color = T.DIM

    def __init__(self) -> None:
        self.t = 0.0
        self.hold: Optional[float] = None

    @property
    def frozen(self) -> bool:
        return self.hold is not None and self.t >= self.hold

    def begin(self, scene: "BattleScene") -> None:
        pass

    def step(self, scene: "BattleScene", dt: float) -> bool:
        if self.frozen:
            return False
        t = self.t + dt
        if self.hold is not None and t >= self.hold:
            t, dt = self.hold, self.hold - self.t
        self.t = t
        self.update(scene, min(1.0, self.t / self.duration) if self.duration > 0 else 1.0, dt)
        return self.t >= self.duration and not self.frozen

    def update(self, scene: "BattleScene", f: float, dt: float) -> None:
        pass

    def end(self, scene: "BattleScene") -> None:
        pass

    def draw(self, scene: "BattleScene", layer: pygame.Surface) -> None:
        pass


class PauseAnim(Anim):
    def __init__(self, duration: float, focus: Optional[int] = None) -> None:
        super().__init__()
        self.duration = duration
        self.focus = focus

    def begin(self, scene):
        if self.focus is not None:
            scene.focus_id = self.focus


class BannerAnim(Anim):
    duration = 0.75

    def __init__(self, title: str) -> None:
        super().__init__()
        self.title = title

    def draw(self, scene, layer):
        f = self.t / self.duration
        a = min(1.0, f / 0.2, (1 - f) / 0.3)
        r = scene.map_rect
        band = pygame.Rect(r.x, r.centery - 34, r.width, 68)
        pygame.draw.rect(layer, (6, 12, 20, round(150 * a)), band)
        size = 56 if len(self.title) < 20 else 44
        img = T.font(size).render(self.title, True, T.ACCENT)
        img.set_alpha(round(255 * a))
        layer.blit(img, img.get_rect(center=band.center))


class MoveAnim(Anim):
    SECONDS_PER_TILE = 0.16

    def __init__(self, ev: Moved) -> None:
        super().__init__()
        self.ev = ev
        self.duration = self.SECONDS_PER_TILE * (len(ev.path) - 1)
        self.wake_timer = 0.0

    def begin(self, scene):
        scene.focus_id = self.ev.stack_id

    def update(self, scene, f, dt):
        v = scene.visuals[self.ev.stack_id]
        path = self.ev.path
        seg = f * (len(path) - 1)
        i = min(int(seg), len(path) - 2)
        a, b = path[i], path[i + 1]
        v.x, v.y = lerp(a, b, seg - i)
        v.angle = turn_toward(v.angle, math.atan2(b[1] - a[1], b[0] - a[0]), dt * 9)
        self.wake_timer -= dt
        if self.wake_timer <= 0:
            self.wake_timer = 0.025
            scene.wake(*v.stern())

    def end(self, scene):
        v = scene.visuals[self.ev.stack_id]
        v.x, v.y = self.ev.path[-1]


class GunAnim(Anim):
    duration = 0.7
    FLIGHT = 0.22

    def __init__(self, ev: GunsFired) -> None:
        super().__init__()
        self.ev = ev
        self.applied = False
        self.shells: list[list] = []

    def begin(self, scene):
        ev = self.ev
        scene.focus_id = ev.attacker_id
        weapon = scene.battle.stacks[ev.attacker_id].design.mounts[ev.mount].weapon
        self.laser = ev.kind == "laser"
        self.side = scene.battle.stacks[ev.attacker_id].side
        self.width = 3 if weapon.damage[1] >= 15 else 2 if weapon.damage[1] >= 5 else 1
        sound.play("laser" if self.laser else sound.gun_sound(weapon.damage[1]), 0.5 if self.laser else 0.55)
        rng = scene.fx_rng
        self.src = scene.visuals[ev.attacker_id].screen
        dst = scene.visuals[ev.target_id].screen
        n = min(ev.shots, 10)
        n_hits = 0 if ev.hits == 0 else max(1, round(n * ev.hits / ev.shots))
        for k in range(n):
            hit = k < n_hits
            if hit:
                off = (rng.uniform(-10, 10), rng.uniform(-8, 8))
            else:
                a, d = rng.uniform(0, math.tau), rng.uniform(16, 30)
                off = (math.cos(a) * d, math.sin(a) * d)
            start = (self.src[0] + rng.uniform(-8, 8), self.src[1] + rng.uniform(-6, 6))
            self.shells.append([start, (dst[0] + off[0], dst[1] + off[1]), k * 0.03, hit, False])
        rng.shuffle(self.shells)
        for k, s in enumerate(self.shells):
            s[2] = k * 0.03

    def update(self, scene, f, dt):
        for s in self.shells:
            if not s[4] and self.t >= s[2] + self.FLIGHT:
                s[4] = True
                if s[3]:
                    scene.flash(*s[1], 0.6)
                else:
                    scene.splash(*s[1], 5, 0.6)
        if not self.applied and self.t >= 0.32:
            self.apply(scene)

    def apply(self, scene):
        self.applied = True
        ev = self.ev
        v = scene.visuals[ev.target_id]
        v.count, v.hp = ev.target_count, ev.target_hp
        x, y = v.screen
        v.field = ev.target_field
        if ev.damage > 0:
            scene.float_text(x, y - 20, f"-{ev.damage}", T.BAD)
        elif ev.absorbed:
            scene.float_text(x, y - 20, "FIELD HOLDS", FIELD_COLOR, 20)
        elif ev.hits > 0:
            scene.float_text(x, y - 20, "BELT HOLDS", T.DIM, 20)
        elif ev.decoyed and not ev.fired:
            scene.float_text(x, y - 20, "HOLOGRAMS", FIELD_COLOR, 20)
        else:
            scene.float_text(x, y - 20, "MISS", T.FOAM, 20)
            if not self.laser:
                sound.play("splash", 0.35)
        if ev.kills:
            scene.float_text(x, y + 2, f"{ev.kills} sunk", T.WARN, 20)

    def end(self, scene):
        if not self.applied:
            self.apply(scene)

    def draw(self, scene, layer):
        if self.laser:  # beams: there the moment they fire, gone a moment later
            color = LASER_COLORS[self.side]
            for start, end, delay, _hit, _landed in self.shells:
                p = (self.t - delay) / self.FLIGHT
                if 0 <= p <= 1.4:
                    a = round(255 * min(1.0, 1.4 - p))
                    pygame.draw.line(layer, (*color, a), start, end, 3)
                    pygame.draw.line(layer, (255, 255, 255, a), start, end, 1)
            return
        for start, end, delay, _hit, _landed in self.shells:
            p = (self.t - delay) / self.FLIGHT
            if 0 <= p <= 1:
                head, tail = lerp(start, end, p), lerp(start, end, max(0.0, p - 0.2))
                pygame.draw.line(layer, (255, 236, 170, 255), tail, head, self.width)
        if self.t < 0.12:
            pygame.draw.circle(layer, (255, 214, 120, 180), self.src, 10 + self.width * 3)


class SalvoLaunchAnim(Anim):
    duration = 0.3

    def __init__(self, ev: SalvoLaunched) -> None:
        super().__init__()
        self.ev = ev

    def begin(self, scene):
        ev = self.ev
        scene.focus_id = ev.attacker_id
        attacker = scene.visuals[ev.attacker_id]
        target = scene.visuals[ev.target_id]
        angle = math.atan2(target.y - attacker.y, target.x - attacker.x)
        scene.torps[ev.salvo_id] = TorpVisual(attacker.side, attacker.x, attacker.y, angle, ev.count, ev.kind)
        if ev.kind == "missile":
            scene.flash(*attacker.screen, 0.5)
        else:
            scene.splash(*attacker.screen, 6, 0.5)
        sound.play("missile" if ev.kind == "missile" else "launch", 0.5)


class SalvoMoveAnim(Anim):
    SECONDS_PER_TILE = 0.13

    def __init__(self, ev: SalvoMoved) -> None:
        super().__init__()
        self.ev = ev
        self.duration = self.SECONDS_PER_TILE * (len(ev.path) - 1)

    def update(self, scene, f, dt):
        tv = scene.torps.get(self.ev.salvo_id)
        if tv is None:
            return
        path = self.ev.path
        seg = f * (len(path) - 1)
        i = min(int(seg), len(path) - 2)
        a, b = path[i], path[i + 1]
        tv.x, tv.y = lerp(a, b, seg - i)
        tv.angle = math.atan2(b[1] - a[1], b[0] - a[0])
        if tv.kind == "missile":
            x, y = tv.screen
            scene.particles.append(Particle(x, y, 0, -6, 0.9, 3, (190, 190, 196), 7))
        elif scene.fx_rng.random() < 0.5:
            scene.wake(*tv.screen, small=True)


class SalvoHitAnim(Anim):
    """The salvo strikes on the first frame (so a Math Boost can hold it at the ship)."""

    duration = 0.75

    def __init__(self, ev: SalvoHit) -> None:
        super().__init__()
        self.ev = ev
        self.landed = False

    def update(self, scene, f, dt):
        if not self.landed:
            self.land(scene)

    def end(self, scene):
        if not self.landed:
            self.land(scene)

    def land(self, scene):
        self.landed = True
        ev = self.ev
        scene.torps.pop(ev.salvo_id, None)
        v = scene.visuals[ev.target_id]
        x, y = v.screen
        scene.splash(x, y, 26, 1.4)
        if ev.hits:
            scene.flash(x, y, 1.4)
        sound.play("explosion" if ev.hits else "splash", 0.7 if ev.hits else 0.45)
        v.count, v.hp, v.field = ev.target_count, ev.target_hp, ev.target_field
        if ev.damage:
            scene.float_text(x, y - 22, f"-{ev.damage}", T.BAD)
        elif ev.absorbed:
            scene.float_text(x, y - 22, "FIELD HOLDS", FIELD_COLOR, 20)
        elif ev.hits:
            scene.float_text(x, y - 22, "BELT HOLDS", T.DIM, 20)
        else:
            scene.float_text(x, y - 22, "ALL MISS", T.FOAM, 20)
        if ev.intercepted:
            scene.float_text(x, y - 44, f"{ev.intercepted} shot down", T.ACCENT, 20)
        elif ev.decoyed:
            scene.float_text(x, y - 44, f"{ev.decoyed} at holograms", FIELD_COLOR, 20)
        if ev.kills:
            scene.float_text(x, y + 2, f"{ev.kills} sunk", T.WARN, 20)


class RepairAnim(Anim):
    duration = 0.4

    def __init__(self, ev: Repaired) -> None:
        super().__init__()
        self.ev = ev

    def begin(self, scene):
        v = scene.visuals[self.ev.stack_id]
        v.hp = self.ev.target_hp
        x, y = v.screen
        scene.float_text(x, y - 20, f"+{self.ev.amount}", T.GOOD, 22)


class FieldAnim(Anim):
    """The force field comes back to full strength at the start of the stack's turn."""

    duration = 0.0

    def __init__(self, ev: FieldRestored) -> None:
        super().__init__()
        self.ev = ev

    def begin(self, scene):
        scene.visuals[self.ev.stack_id].field = self.ev.field


class SalvoLostAnim(Anim):
    duration = 0.4

    def __init__(self, ev: SalvoLost) -> None:
        super().__init__()
        self.ev = ev

    def update(self, scene, f, dt):
        tv = scene.torps.get(self.ev.salvo_id)
        if tv:
            tv.alpha = 255 * (1 - f)

    def end(self, scene):
        scene.torps.pop(self.ev.salvo_id, None)


class SinkAnim(Anim):
    duration = 1.0

    def __init__(self, stack_id: int) -> None:
        super().__init__()
        self.stack_id = stack_id

    def begin(self, scene):
        x, y = scene.visuals[self.stack_id].screen
        scene.float_text(x, y - 36, "SUNK", T.BAD, 28)
        sound.play("sink", 0.6)

    def update(self, scene, f, dt):
        v = scene.visuals[self.stack_id]
        v.alpha = 255 * (1 - f)
        if scene.fx_rng.random() < 0.6:
            x, y = v.screen
            r = scene.fx_rng
            scene.particles.append(Particle(x + r.uniform(-20, 20), y + r.uniform(-8, 8), 0, -10, 1.0, 2, T.FOAM, 2))
            scene.particles.append(Particle(x + r.uniform(-10, 10), y, r.uniform(-8, 8), -25, 1.2, 5, (60, 60, 66), 9))

    def end(self, scene):
        scene.visuals[self.stack_id].visible = False


class RetreatAnim(Anim):
    duration = 0.9

    def __init__(self, stack_id: int) -> None:
        super().__init__()
        self.stack_id = stack_id

    def begin(self, scene):
        v = scene.visuals[self.stack_id]
        self.start = (v.x, v.y)
        self.dx = -3 if v.side == 0 else 3
        v.angle = math.pi if v.side == 0 else 0.0

    def update(self, scene, f, dt):
        v = scene.visuals[self.stack_id]
        v.x = self.start[0] + self.dx * f
        v.alpha = 255 * (1 - f)
        if scene.fx_rng.random() < 0.7:
            scene.wake(*v.stern())

    def end(self, scene):
        scene.visuals[self.stack_id].visible = False


class EndAnim(Anim):
    duration = 0.9

    def end(self, scene):
        scene.battle_finished()
        scene.show_result = True
        winner = scene.battle.winner
        if winner is not None:
            sound.play("victory" if winner in scene.human_sides else "defeat", 0.6)


# --------------------------------------------------------------------------- math boost


@dataclass
class BoostChance:
    """A big hit held back for Math Boost. The action is previewed but not yet applied: its
    events play up to the hit, whose animation freezes just before it lands while the MATH BOOST
    box waits. Taken, the box opens a problem; once that is answered (or the box is passed or
    left alone) the action is applied and the hit lands."""

    action: Action
    hit: BigHit
    anim: Anim  # the hit's animation, frozen just before it lands
    index: int  # where the hit comes in the action's events
    wait: float = CHANCE_SECONDS  # left before the hit lands by itself
    shown: bool = False  # the box has come up
    problem: Optional[DinoProblem] = None  # once the box is taken
    picked: Optional[int] = None
    boosts: dict = field(default_factory=dict)  # for Battle.apply, once answered
    show_hint: bool = False
    auto: float = 0.0  # a right answer carries on by itself after this long

    @property
    def right(self) -> bool:
        return self.problem is not None and self.picked == self.problem.answer


# --------------------------------------------------------------------------- the scene


class BattleScene:
    def __init__(
        self, app, battle: Battle, *, scenario_id: Optional[str] = None, campaign=None, skirmish: Optional[int] = None,
    ) -> None:
        """A quick battle (``scenario_id`` set), a campaign mission (``campaign`` set), or a
        skirmish replay of a mission already won (``skirmish`` too). The player always commands Blue (side 0)."""
        self.app = app
        self.scenario_id = scenario_id
        self.campaign = campaign
        self.skirmish = skirmish
        self.report = None  # campaign.Report once the mission is over
        self.debrief: Optional[Debrief] = None  # what happened and what to learn, once the battle is over
        seed = battle.seed or 0
        self.seed = seed
        self.human_sides = {0}
        self.battle = battle
        # In a campaign mission Red fights to the last ship: a retreat shouldn't hand you the mission.
        self.ai = {0: SimpleAI(), 1: SimpleAI(retreat_ratio=0) if campaign else SimpleAI()}
        self.auto_sides: set[int] = set()
        self.auto_key: Optional[tuple[int, int]] = None
        self.held: dict[int, set[int]] = {}
        # Math Boost: on for a campaign mission if the briefing said so (more of them in a super mission)
        m = None if campaign is None else campaign.mission if skirmish is None else mission(skirmish)
        self.boost: Optional[MathBoost] = None
        if m is not None and campaign.boost:
            # Seeded from the battle, so a battle's seed also replays which hits offer a boost and the problems.
            self.boost = MathBoost.for_battle(battle, rng=random.Random(f"boost/{seed}"), super_mission=m.is_super)
        self.chance: Optional[BoostChance] = None
        self.pending: deque[Action] = deque()  # the rest of a click's fire orders, while a boost waits for its answer
        self.prompt_hits: list[tuple[pygame.Rect, Callable[[], None]]] = []
        self.box_rect: Optional[pygame.Rect] = None  # the MATH BOOST box, where it was last drawn
        self.boost_button: Optional[Button] = None  # the side panel's "Turn off"
        self.boost_confirm = 0.0

        self.visuals: dict[int, ShipVisual] = {
            s.id: ShipVisual(
                s.side, s.design.hull.id, s.pos[0], s.pos[1], 0.0 if s.side == 0 else math.pi,
                s.count, s.top_hp, s.design.max_hp, s.design.has_missiles,
                field=s.top_field, max_field=s.design.max_field,
            )
            for s in self.battle.stacks.values()
        }
        self.torps: dict[int, TorpVisual] = {}
        self.particles: list[Particle] = []
        self.texts: list[FloatText] = []
        self.anims: deque[Anim] = deque()
        self.current: Optional[Anim] = None
        self.log: list[tuple[str, tuple]] = []
        self.focus_id: Optional[int] = None
        self.fx_rng = random.Random(seed)

        self.time = 0.0
        self.speed = 1
        self.paused = False
        self.ai_wait = 0.0
        self.show_help = False
        self.show_result = False
        self.retreat_confirm = 0.0
        self.withdraw_confirm = 0.0
        self.mouse = (0, 0)

        w, h = self.battle.width * T.TILE, self.battle.height * T.TILE
        self.map_rect = pygame.Rect(T.MAP_X, T.MAP_Y, w, h)
        self.ocean = ocean_surface(w, h, grid=T.TILE, seed=seed)
        for x, y in sorted(self.battle.islands):  # islands never move: paint them into the background
            center = ((x + 0.5) * T.TILE, (y + 0.5) * T.TILE)
            draw_island(self.ocean, island_shape(center, T.TILE * 0.36, seed * 131 + x * 17 + y))
        self.waves = Waves(self.map_rect, 90, seed)
        self.fx = pygame.Surface(T.WINDOW, pygame.SRCALPHA)
        self.weapon_rects: list[tuple[pygame.Rect, int]] = []
        self._build_buttons()
        if m is not None:
            title = f"{'Skirmish - ' if skirmish else ''}{m.title}: {m.name}"
            banner = BannerAnim(title)
            banner.duration = 1.4
            banner.text = f"{title}. {m.briefing}"
            self.anims.append(banner)
        self.queue(self.battle.start())

    # ---- controls --------------------------------------------------------------

    def _build_buttons(self) -> None:
        gap, h = 8, 44
        w = (T.PANEL_W - 24 - 2 * gap) // 3
        x0 = T.PANEL_X + 12
        y1 = T.PANEL_Y + T.PANEL_H - 2 * h - gap - 12
        y2 = y1 + h + gap

        def rect(col: int, row: int) -> pygame.Rect:
            return pygame.Rect(x0 + col * (w + gap), (y1, y2)[row], w, h)

        self.buttons: dict[str, Button] = {}
        self.buttons["end"] = Button(rect(0, 0), "End Turn", self.end_turn, "Space")
        self.buttons["auto"] = Button(rect(1, 0), "Auto Ship", self.auto_ship, "A")
        self.buttons["retreat"] = Button(rect(2, 0), "Retreat", self.retreat, "R")
        self.buttons["fleet"] = Button(rect(0, 1), "Fleet Auto", self.toggle_fleet_auto, "Z")
        self.buttons["speed"] = Button(rect(1, 1), "Speed x1", self.toggle_speed, "F")
        if self.campaign:
            self.buttons["withdraw"] = Button(rect(2, 1), "Withdraw", self.withdraw, "W")
        else:
            self.buttons["menu"] = Button(rect(2, 1), "Menu", self.app.to_title, "Esc")

        cx, cy = self.map_rect.centerx, self.map_rect.centery
        if self.campaign:
            self.result_buttons = [
                Button(pygame.Rect(cx - 130, cy + 118, 260, 44), "Return to Workshop", self.to_workshop, "Enter"),
            ]
        else:
            self.result_buttons = [
                Button(pygame.Rect(cx - 250, cy + 118, 160, 44), "Rematch", self.rematch, "same seed (R)"),
                Button(pygame.Rect(cx - 80, cy + 118, 160, 44), "New Battle", self.new_battle, "new seed (N)"),
                Button(pygame.Rect(cx + 90, cy + 118, 160, 44), "Menu", self.app.to_title, "Esc"),
            ]

    def human_turn(self) -> Optional[Stack]:
        """The active stack if the player should be giving it orders now."""
        if self.current or self.anims or self.battle.over or self.chance or self.pending:
            return None
        stack = self.battle.active
        if stack is None or self.ai_controlled(stack):
            return None
        return stack

    def ai_controlled(self, stack: Stack) -> bool:
        return (
            stack.side not in self.human_sides
            or stack.side in self.auto_sides
            or self.auto_key == (self.battle.round, stack.id)
        )

    def act(self, action) -> None:
        """Carry out an action. With Math Boost on it is previewed first, and if it brings a big
        hit it is held back: its events play up to the hit, which freezes there with the MATH BOOST
        box beside it (see :class:`BoostChance`)."""
        if self.boost is not None and self.boost.active:
            try:
                preview = self.battle.preview(action)
            except IllegalAction:
                return
            hit = self.boost.big_hit(self.battle, preview)
            if hit is not None:
                k = next(i for i, e in enumerate(preview) if e is hit.event)
                self.queue(preview[:k])
                anim = self._anim(hit.event)
                assert anim is not None
                anim.hold = GUN_HOLD if isinstance(hit.event, GunsFired) else 0.0
                self.anims.append(anim)  # no log line yet: the boost may change the damage
                self.chance = BoostChance(action, hit, anim, k)
                return
        try:
            self.queue(self.battle.apply(action))
        except IllegalAction:
            pass

    def _pump(self) -> None:
        """Carry out waiting fire orders until one stops for a Math Boost."""
        while self.pending and self.chance is None:
            action = self.pending.popleft()
            if self.battle.over:
                self.pending.clear()
                return
            self.act(action)

    # ---- math boost ------------------------------------------------------------

    @property
    def frozen_hit(self) -> bool:
        """A big hit is on screen, frozen just before it lands, waiting on Math Boost."""
        c = self.chance
        return c is not None and self.current is c.anim and c.anim.frozen

    @property
    def box_open(self) -> bool:
        """The MATH BOOST box is up beside a frozen hit, waiting for a click."""
        return self.frozen_hit and self.chance is not None and self.chance.problem is None

    @property
    def prompt_open(self) -> bool:
        """The box was taken: its problem is on screen."""
        return self.frozen_hit and self.chance is not None and self.chance.problem is not None

    @property
    def prompt(self) -> Optional[BoostChance]:
        """The chance whose problem is on screen, if any."""
        return self.chance if self.prompt_open else None

    def take_boost(self) -> None:
        """Click on the MATH BOOST box (or B): put a problem to the player."""
        if not self.box_open:
            return
        assert self.chance is not None and self.boost is not None
        self.chance.problem = self.boost.pose()

    def pass_boost(self) -> None:
        """Let the frozen hit land as it was rolled (Space, or the box's time runs out)."""
        if self.box_open:
            self.land()

    def answer_boost(self, i: int) -> None:
        c = self.prompt
        if c is None or c.problem is None or c.picked is not None or not 0 <= i < len(c.problem.choices):
            return
        c.picked = i
        assert self.boost is not None
        c.boosts = self.boost.boosts(c.hit, c.right)
        if self.campaign is not None:
            self.campaign.record_boost(c.right)
        if c.right:
            c.auto = 2.0
            sound.play("right", 0.5)
        else:
            sound.play("wrong", 0.5)

    def land(self) -> None:
        """Settle the chance: apply the held action, boosted if its problem was answered, and
        let the frozen hit go on to land with the damage it really does. A problem on screen
        waits for its answer (unless the boost was turned off)."""
        c = self.chance
        if c is None or (c.problem is not None and c.picked is None and self.boost is not None and self.boost.on):
            return
        self.chance = None
        self.box_rect = None
        try:
            events = self.battle.apply(c.action, c.boosts)
        except IllegalAction:
            events = []
        k = next((i for i, e in enumerate(events) if type(e) is type(c.hit.event) and e.key == c.hit.key), None)
        if k is None:  # the preview foretold the hit, so this shouldn't happen: drop the frozen one
            if self.current is c.anim:
                self.current = None
            elif c.anim in self.anims:
                self.anims.remove(c.anim)
            self.queue(events[c.index:])
            self._pump()
            return
        real = events[k]
        c.anim.ev = real  # type: ignore[attr-defined]
        c.anim.hold = None
        if c.boosts and self.boost is not None:
            change = self.boost.landed(c.hit, events)
            x, y = self.visuals[real.target_id].screen
            if c.right:
                line = f"Math Boost: {change} {'more' if c.hit.offense else 'less'} damage." if change else "Math Boost: right answer."
                self.float_text(x, y - 40, f"BOOST {'+' if c.hit.offense else '−'}{BOOST:.0%}", T.GOOD, 24)
            else:
                line = f"Math Boost, wrong answer: {change} {'less' if c.hit.offense else 'more'} damage." if change \
                    else "Math Boost: wrong answer."
                self.float_text(x, y - 40, f"{'−' if c.hit.offense else '+'}{PENALTY:.0%} DAMAGE", T.BAD, 22)
            self.log.append((line, T.GOOD if c.right else T.BAD))
        if self.current is c.anim:  # its log line waited for the real damage
            self.log.append((real.text, self._log_color(real.text)))
        else:
            c.anim.text = real.text
        self.queue(events[k + 1:])
        self._pump()

    def continue_battle(self) -> None:
        """Close an answered problem and let the hit land."""
        if self.prompt_open:
            self.land()

    def turn_boost_off(self, confirm: bool = False) -> None:
        """Math Boost off for the rest of the mission. The side panel's button asks first (``confirm``)."""
        if self.boost is None or not self.boost.on or self.battle.over:
            return
        if confirm and self.boost_confirm <= 0:
            self.boost_confirm = 3.0
            return
        self.boost_confirm = 0.0
        self.boost.turn_off()
        self.log.append(("Math Boost is off for the rest of this mission.", T.DIM))
        if self.chance is not None:
            self.land()

    def end_turn(self) -> None:
        if self.human_turn():
            self.act(EndTurn())

    def auto_ship(self) -> None:
        stack = self.human_turn()
        if stack:
            self.auto_key = (self.battle.round, stack.id)

    def retreat(self) -> None:
        stack = self.human_turn()
        if not stack:
            return
        if self.retreat_confirm > 0:
            self.retreat_confirm = 0
            self.act(Retreat())
        else:
            self.retreat_confirm = 3.0

    def toggle_fleet_auto(self) -> None:
        for side in self.human_sides:
            self.auto_sides ^= {side}

    def toggle_speed(self) -> None:
        self.speed = 3 if self.speed == 1 else 1

    def toggle_pause(self) -> None:
        self.paused = not self.paused

    def withdraw(self) -> None:
        """Pull the whole fleet out of a campaign battle (press twice)."""
        if not self.human_turn():
            return
        if self.withdraw_confirm > 0:
            self.withdraw_confirm = 0
            self.act(Withdraw())
        else:
            self.withdraw_confirm = 3.0

    def rematch(self) -> None:
        self.app.start_battle(self.scenario_id, self.seed)

    def new_battle(self) -> None:
        self.app.start_battle(self.scenario_id, random.randrange(100_000))

    def to_workshop(self) -> None:
        self.app.open_workshop(self.campaign)

    def battle_finished(self) -> None:
        """Called once when the ending animation finishes: debrief, settle the campaign and save."""
        if self.debrief is None:
            self.debrief = debrief(self.battle, 0, campaign=self.campaign is not None)
        if self.campaign and self.report is None:
            from .. import campaign as campaign_mod

            self.report = self.campaign.apply_result(self.battle, self.skirmish)
            self.campaign.lessons = list(self.debrief.lessons)  # shown again at the next briefing
            problem = campaign_mod.try_save(self.campaign)
            if problem:
                self.app.notice = (problem, 8.0)

    def fireable(self, stack: Stack, target: Stack) -> list[int]:
        held = self.held.get(stack.id, set())
        return [i for i in self.battle.mounts_that_can_fire(stack, target) if i not in held]

    def screen_to_tile(self, pos) -> Optional[Pos]:
        if not self.map_rect.collidepoint(pos):
            return None
        return ((pos[0] - T.MAP_X) // T.TILE, (pos[1] - T.MAP_Y) // T.TILE)

    def handle(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEMOTION:
            self.mouse = event.pos
        elif event.type == pygame.KEYDOWN:
            self._key(event.key)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.mouse = event.pos
            self._click(event.pos)

    def _key(self, key: int) -> None:
        if self.show_help:
            self.show_help = False
            return
        if self.prompt_open:
            self._prompt_key(key)
            return
        if self.box_open and key == pygame.K_b:
            self.take_boost()
            return
        if self.box_open and key == pygame.K_SPACE:
            self.pass_boost()
            return
        if self.show_result:
            if self.campaign:
                actions = {pygame.K_RETURN: self.to_workshop, pygame.K_ESCAPE: self.to_workshop,
                           pygame.K_SPACE: self.to_workshop}
            else:
                actions = {pygame.K_r: self.rematch, pygame.K_n: self.new_battle, pygame.K_ESCAPE: self.app.to_title,
                           pygame.K_RETURN: self.app.to_title}
            if key in actions:
                actions[key]()
            return
        actions = {
            pygame.K_SPACE: self.end_turn, pygame.K_RETURN: self.end_turn, pygame.K_a: self.auto_ship,
            pygame.K_r: self.retreat, pygame.K_z: self.toggle_fleet_auto, pygame.K_f: self.toggle_speed,
            pygame.K_p: self.toggle_pause,
            pygame.K_ESCAPE: self.withdraw if self.campaign else self.app.to_title,
        }
        if self.campaign:
            actions[pygame.K_w] = self.withdraw
        if key == pygame.K_h:
            self.show_help = True
        elif key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4):
            self._toggle_hold(key - pygame.K_1)
        elif key in actions:
            actions[key]()

    def _prompt_key(self, key: int) -> None:
        p = self.prompt
        assert p is not None
        numbers = {pygame.K_1: 0, pygame.K_2: 1, pygame.K_3: 2, pygame.K_4: 3,
                   pygame.K_KP1: 0, pygame.K_KP2: 1, pygame.K_KP3: 2, pygame.K_KP4: 3}
        if p.picked is None:
            if key in numbers:
                self.answer_boost(numbers[key])
            elif key == pygame.K_h:
                p.show_hint = not p.show_hint
        elif key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER, pygame.K_ESCAPE):
            self.continue_battle()

    def _toggle_hold(self, mount: int) -> None:
        stack = self.human_turn()
        if stack and mount < len(stack.design.mounts):
            self.held.setdefault(stack.id, set()).symmetric_difference_update({mount})

    def _click(self, pos) -> None:
        if self.show_help:
            self.show_help = False
            return
        if self.prompt_open:
            for rect, fn in self.prompt_hits:
                if rect.collidepoint(pos):
                    fn()
                    return
            return
        if self.box_open and self.box_rect is not None and self.box_rect.collidepoint(pos):
            self.take_boost()
            return
        if self.show_result:
            for b in self.result_buttons:
                b.click(pos)
            return
        if self.boost_button is not None and self.boost is not None and self.boost.on and self.boost_button.click(pos):
            return
        for b in self.buttons.values():
            if b.click(pos):
                return
        for rect, mount in self.weapon_rects:
            if rect.collidepoint(pos):
                self._toggle_hold(mount)
                return
        stack = self.human_turn()
        tile = self.screen_to_tile(pos)
        if stack is None or tile is None:
            return
        target = self.battle.stack_at(tile)
        if target is not None and target.side != stack.side:
            self.pending.extend(Fire(mount, target.id) for mount in self.fireable(stack, target))
            self._pump()
        elif tile != stack.pos and tile in self.battle.reachable(stack):
            self.act(Move(tile))

    # ---- event playback --------------------------------------------------------

    def queue(self, events: list[Event]) -> None:
        for e in events:
            anim = self._anim(e)
            if anim is not None:
                anim.text = e.text
                self.anims.append(anim)

    def _anim(self, e: Event) -> Optional[Anim]:
        """The animation that shows an event (None for one with nothing to show)."""
        if isinstance(e, RoundStarted):
            return BannerAnim(f"Round {e.round}")
        if isinstance(e, StackActivated):
            stack = self.battle.stacks[e.stack_id]
            return PauseAnim(0.25 if self.ai_controlled(stack) else 0.0, e.stack_id)
        if isinstance(e, Moved):
            return MoveAnim(e)
        if isinstance(e, GunsFired):
            return GunAnim(e)
        if isinstance(e, SalvoLaunched):
            return SalvoLaunchAnim(e)
        if isinstance(e, SalvoMoved):
            return SalvoMoveAnim(e)
        if isinstance(e, SalvoHit):
            return SalvoHitAnim(e)
        if isinstance(e, SalvoLost):
            return SalvoLostAnim(e)
        if isinstance(e, StackSunk):
            return SinkAnim(e.stack_id)
        if isinstance(e, Repaired):
            return RepairAnim(e)
        if isinstance(e, FieldRestored):
            return FieldAnim(e)
        if isinstance(e, StackRetreated):
            return RetreatAnim(e.stack_id)
        if isinstance(e, BattleOver):
            return EndAnim()
        return None

    def _log_color(self, line: str) -> tuple:
        words = line.split()
        if line.startswith("---") or not words:
            return T.ACCENT
        for side, name in enumerate(self.battle.side_names):
            if words[0] == name or (len(words) > 1 and words[1] == name):
                return LOG_COLORS[side]
        return T.TEXT

    # ---- effects ---------------------------------------------------------------

    def splash(self, x: float, y: float, n: int, power: float) -> None:
        r = self.fx_rng
        for _ in range(n):
            a = r.uniform(0, math.tau)
            s = r.uniform(20, 70) * power
            self.particles.append(Particle(x, y, math.cos(a) * s, math.sin(a) * s - 20 * power, r.uniform(0.4, 0.8), r.uniform(2, 4) * power, T.FOAM, 6 * power))

    def flash(self, x: float, y: float, power: float) -> None:
        r = self.fx_rng
        for color in [(255, 220, 120), (255, 150, 60), (255, 90, 40)]:
            self.particles.append(Particle(x + r.uniform(-4, 4), y + r.uniform(-4, 4), 0, 0, 0.25, 7 * power, color, 30 * power))
        for _ in range(2):
            self.particles.append(Particle(x, y, r.uniform(-10, 10), -20, 1.1, 4 * power, (70, 70, 76), 10 * power))

    def wake(self, x: float, y: float, small: bool = False) -> None:
        r = self.fx_rng
        self.particles.append(
            Particle(x + r.uniform(-2, 2), y + r.uniform(-2, 2), 0, 0, 1.0 if small else 1.4, 2 if small else 3, T.FOAM, 3, above=False)
        )

    def float_text(self, x: float, y: float, s: str, color, size: int = 26) -> None:
        # Text drifts ~30px upwards while it fades; near the top edge show it below the ship instead.
        if y < self.map_rect.top + 40:
            y += 60
        self.texts.append(FloatText(x, y, s, color, size))

    # ---- update ----------------------------------------------------------------

    def update(self, dt: float) -> None:
        self.time += dt
        if self.retreat_confirm > 0:
            self.retreat_confirm -= dt
        if self.withdraw_confirm > 0:
            self.withdraw_confirm -= dt
        if self.boost_confirm > 0:
            self.boost_confirm -= dt
        game_dt = 0.0 if self.paused else dt * self.speed
        self.particles = [p for p in self.particles if p.update(game_dt)]
        for t in self.texts:
            t.age += game_dt
        self.texts = [t for t in self.texts if t.age < t.life]
        if self.paused:
            return

        if self.current is None and self.anims:
            self.current = self.anims.popleft()
            if self.current.text:
                self.log.append((self.current.text, self._log_color(self.current.text)))
            self.current.begin(self)
        if self.frozen_hit:
            self._wait_on_chance(dt)
        if self.current is not None:
            if self.current.step(self, game_dt):
                self.current.end(self)
                self.current = None
            return
        if self.chance is not None:  # its hit is still to come
            return

        stack = self.battle.active
        if self.battle.over or stack is None:
            return
        if self.ai_controlled(stack):
            self.ai_wait -= game_dt
            if self.ai_wait <= 0:
                self.act(self.ai[stack.side].choose_action(self.battle, stack))
                self.ai_wait = 0.12
        else:
            self.focus_id = stack.id
            if not self.battle.can_act(stack):
                self.act(EndTurn())

    def _wait_on_chance(self, dt: float) -> None:
        """A hit is frozen for Math Boost: count the box down (not while the mouse is on it or
        the help is open), or after a right answer carry on by itself."""
        c = self.chance
        assert c is not None
        if not c.shown:
            c.shown = True
            self.log.append((f"MATH BOOST: {c.hit.story()}", T.ACCENT))
            sound.play("boost", 0.5)
        if c.problem is None:
            if not self.show_help and not (self.box_rect is not None and self.box_rect.collidepoint(self.mouse)):
                c.wait -= dt
            if c.wait <= 0:
                self.pass_boost()
        elif c.picked is not None and c.auto > 0:
            c.auto -= dt
            if c.auto <= 0:
                self.continue_battle()

    # ---- drawing ---------------------------------------------------------------

    def draw(self, surf: pygame.Surface) -> None:
        surf.fill(T.BG)
        surf.blit(self.ocean, self.map_rect)
        self.waves.draw(surf, self.time)
        stack = self.human_turn()
        hover_tile = self.screen_to_tile(self.mouse)

        # below ships: move highlights, focus marker, wakes
        self.fx.fill((0, 0, 0, 0))
        if stack:
            self._draw_reach(stack, hover_tile)
        if self.focus_id in self.visuals and self.visuals[self.focus_id].visible and not self.show_result:
            v = self.visuals[self.focus_id]
            rect = pygame.Rect(0, 0, T.TILE - 4, T.TILE - 4)
            rect.center = v.screen
            pulse = 0.5 + 0.5 * math.sin(self.time * 5)
            pygame.draw.rect(self.fx, (*T.ACCENT, 40), rect, border_radius=10)
            pygame.draw.rect(self.fx, (*T.ACCENT, round(140 + 115 * pulse)), rect, 2, border_radius=10)
        for p in self.particles:
            if not p.above:
                p.draw(self.fx)
        surf.blit(self.fx, (0, 0))

        for v in self.visuals.values():
            if v.visible:
                draw_ship(surf, v.screen, v.hull, v.side, v.angle, v.alpha, missiles=v.missiles)
        for tv in self.torps.values():
            draw_torpedo(surf, tv.screen, tv.angle, tv.side, tv.alpha, kind=tv.kind)
            if tv.count > 1 and tv.alpha > 100:
                text(surf, f"x{tv.count}", (tv.screen[0] + 10, tv.screen[1] + 6), 16, T.FOAM)
        for v in self.visuals.values():
            if v.visible and v.alpha > 200:
                self._draw_ship_badges(surf, v)

        # above ships: targeting marks, shells, splashes, banners
        self.fx.fill((0, 0, 0, 0))
        if stack:
            self._draw_targets(stack, hover_tile)
        for p in self.particles:
            if p.above:
                p.draw(self.fx)
        if self.current:
            self.current.draw(self, self.fx)
        surf.blit(self.fx, (0, 0))
        for t in self.texts:
            f = t.age / t.life
            img = T.font(t.size).render(t.text, True, t.color)
            img.set_alpha(round(255 * min(1.0, (1 - f) / 0.4)))
            surf.blit(img, img.get_rect(center=(t.x, t.y - 28 * f)))

        self._draw_top_bar(surf)
        self._draw_panel(surf, stack)
        self._draw_log(surf)
        if stack and hover_tile and not self.show_help:
            self._draw_tooltip(surf, stack, hover_tile)
        if self.box_open:
            self._draw_boost_box(surf)
        if self.paused:
            text(surf, "PAUSED  (P to resume)", (self.map_rect.centerx, self.map_rect.y + 24), 30, T.ACCENT, "center")
        if self.show_help:
            self._draw_help(surf)
        elif self.show_result:
            self._draw_result(surf)
        elif self.prompt_open:
            self._draw_prompt(surf)

    def _draw_reach(self, stack: Stack, hover_tile: Optional[Pos]) -> None:
        reach = self.battle.reachable(stack)
        for pos in reach:
            if pos == stack.pos:
                continue
            x, y = tile_to_screen(*pos)
            rect = pygame.Rect(0, 0, T.TILE - 6, T.TILE - 6)
            rect.center = (x, y)
            pygame.draw.rect(self.fx, (*T.REACH, 34), rect, border_radius=8)
            pygame.draw.rect(self.fx, (*T.REACH, 70), rect, 1, border_radius=8)
        if hover_tile in reach and hover_tile != stack.pos:
            for p in reach[hover_tile]:
                pygame.draw.circle(self.fx, (*T.REACH, 220), tile_to_screen(*p), 5)

    def _draw_targets(self, stack: Stack, hover_tile: Optional[Pos]) -> None:
        pulse = 0.5 + 0.5 * math.sin(self.time * 6)
        for enemy in self.battle.enemies_of(stack):
            if not self.fireable(stack, enemy):
                continue
            x, y = tile_to_screen(*enemy.pos)
            hovered = hover_tile == enemy.pos
            half = T.TILE / 2 - 3 - (0 if hovered else 3 * pulse)
            color = (*T.BAD, 255 if hovered else 200)
            for sx in (-1, 1):
                for sy in (-1, 1):
                    cx, cy = x + sx * half, y + sy * half
                    pygame.draw.line(self.fx, color, (cx, cy), (cx - sx * 14, cy), 3)
                    pygame.draw.line(self.fx, color, (cx, cy), (cx, cy - sy * 14), 3)

    def _draw_ship_badges(self, surf: pygame.Surface, v: ShipVisual) -> None:
        x, y = v.screen
        half = T.TILE / 2
        if v.max_field and v.field > 0:  # a shimmering ring while the force field holds
            ring = pygame.Surface((T.TILE, T.TILE), pygame.SRCALPHA)
            shimmer = 0.75 + 0.25 * math.sin(self.time * 4 + x)
            alpha = round((70 + 150 * v.field / v.max_field) * shimmer)
            pygame.draw.circle(ring, (*FIELD_COLOR, alpha), (T.TILE / 2, T.TILE / 2), T.TILE / 2 - 3, 2)
            surf.blit(ring, (x - T.TILE / 2, y - T.TILE / 2))
        hp = pygame.Rect(0, 0, T.TILE - 20, 6)
        hp.midbottom = (x, y + half - 4)
        bar(surf, hp, v.hp / v.max_hp)
        img = T.render(f"x{v.count}", 18, T.TEXT)
        badge = img.get_rect(topright=(x + half - 4, y - half + 4)).inflate(8, 4)
        pygame.draw.rect(surf, T.SIDE_STYLE[v.side]["dark"], badge, border_radius=5)
        pygame.draw.rect(surf, T.SIDE_STYLE[v.side]["trim"], badge, 1, border_radius=5)
        surf.blit(img, img.get_rect(center=badge.center))

    def _draw_top_bar(self, surf: pygame.Surface) -> None:
        b = self.battle
        text(surf, f"ROUND {max(1, b.round)}", (T.MAP_X, 16), 34, T.ACCENT)
        focus = b.stacks.get(self.focus_id) if self.focus_id else None
        if b.over:
            status = "Battle over"
        elif focus:
            who = "Your" if focus.side in self.human_sides and focus.side not in self.auto_sides else "Computer's"
            status = f"{who} move: {b.side_names[focus.side]} {focus.design.name} x{focus.count}"
        else:
            status = ""
        text(surf, status, (T.MAP_X + 150, 21), 24, T.TEXT)
        x = T.PANEL_X + T.PANEL_W
        text(surf, "H  help", (x, 21), 20, T.DIM, "topright")
        for side in (1, 0):
            ships = sum(s.count for s in b.alive_stacks(side))
            r = text(surf, f"{b.side_names[side]} {ships} ships", (x - 90, 21), 22, LOG_COLORS[side], "topright")
            x = r.left + 60

    def _draw_panel(self, surf: pygame.Surface, human_stack: Optional[Stack]) -> None:
        rect = pygame.Rect(T.PANEL_X, T.PANEL_Y, T.PANEL_W, T.PANEL_H)
        panel(surf, rect)
        self.weapon_rects = []
        y = rect.y + 10
        if self.show_result and self.debrief:
            self._draw_debrief(surf, rect)
        else:
            focus = self.battle.stacks.get(self.focus_id) if self.focus_id else None
            if focus and focus.alive:
                y = self._draw_card(surf, focus, y, "ACTING", editable=human_stack is focus)
            hover = self.battle.stack_at(self.screen_to_tile(self.mouse) or (-1, -1))
            pygame.draw.line(surf, T.PANEL_EDGE, (rect.x + 12, y + 4), (rect.right - 12, y + 4))
            y += 14
            if hover and hover is not focus:
                y = self._draw_card(surf, hover, y, "INSPECT", editable=False)
                if human_stack and hover.side != human_stack.side:
                    self._draw_fire_preview(surf, human_stack, hover, y)
            elif human_stack:
                hints = [
                    "Click a highlighted tile to move.",
                    "Click an enemy in red brackets to fire every ready weapon at it.",
                    "Click a weapon line (or press 1-4) to hold its fire.",
                    "Hover any ship to inspect it.",
                ]
                for hint in hints:
                    for line in wrap(hint, 19, T.PANEL_W - 28):
                        text(surf, line, (rect.x + 14, y), 19, T.DIM)
                        y += 19
                    y += 5

        self.buttons["end"].enabled = bool(human_stack)
        self.buttons["auto"].enabled = bool(human_stack)
        self.buttons["retreat"].enabled = bool(human_stack)
        self.buttons["retreat"].toggled = self.retreat_confirm > 0
        self.buttons["retreat"].hint = "R again!" if self.retreat_confirm > 0 else "R"
        self.buttons["fleet"].toggled = bool(self.auto_sides)
        if "withdraw" in self.buttons:
            self.buttons["withdraw"].enabled = bool(human_stack)
            self.buttons["withdraw"].toggled = self.withdraw_confirm > 0
            self.buttons["withdraw"].hint = "W again!" if self.withdraw_confirm > 0 else "W"
        self.buttons["speed"].label = f"Speed x{self.speed}"
        self.buttons["speed"].toggled = self.speed > 1
        for b in self.buttons.values():
            b.draw(surf, self.mouse)
        if self.boost is not None and not self.show_result:
            self._draw_boost_status(surf, rect)

    def _draw_boost_status(self, surf: pygame.Surface, rect: pygame.Rect) -> None:
        """Math Boost's line above the buttons: the score so far and a button to turn it off."""
        b = self.boost
        assert b is not None
        y = self.buttons["end"].rect.y - 30
        x = rect.x + 14
        pygame.draw.line(surf, T.PANEL_EDGE, (rect.x + 12, y - 8), (rect.right - 12, y - 8))
        if not b.on:
            text(surf, "Math Boost is off for this mission.", (x, y), 18, T.FAINT)
            return
        r = text(surf, "MATH BOOST ON", (x, y), 18, T.ACCENT)
        score = f"{b.right} of {b.answered} right" if b.answered else "no boosts yet"
        text(surf, score, (r.right + 10, y), 18, T.TEXT)
        if self.boost_button is None:
            self.boost_button = Button(pygame.Rect(0, 0, 112, 26), "", lambda: self.turn_boost_off(confirm=True), size=17)
        btn = self.boost_button
        btn.rect.topright = (rect.right - 12, y - 5)
        btn.label = "Click again" if self.boost_confirm > 0 else "Turn off"
        btn.toggled = self.boost_confirm > 0
        btn.draw(surf, self.mouse)

    def _box_place(self, tx: float, ty: float, size: tuple[int, int]) -> pygame.Rect:
        """Where the MATH BOOST box goes: above the ship about to be hit, else below, beside or
        on a diagonal, whichever covers no ship (never that one), or the fewest."""
        area = self.map_rect.inflate(-12, -12)
        w, h = size
        gap, side = T.TILE / 2 + 22, T.TILE / 2 + 8
        ships = []
        for v in self.visuals.values():
            if v.visible:
                r = pygame.Rect(0, 0, T.TILE, T.TILE)
                r.center = v.screen
                ships.append(r)
        target = pygame.Rect(0, 0, T.TILE, T.TILE)
        target.center = (round(tx), round(ty))
        above, below = -gap - h / 2, gap + h / 2
        centers = [(0, above), (0, below), (gap + w / 2, 0), (-gap - w / 2, 0),  # where the box's center goes
                   (side + w / 2, above), (-side - w / 2, above), (side + w / 2, below), (-side - w / 2, below)]
        best: Optional[tuple[tuple, pygame.Rect]] = None
        for i, (dx, dy) in enumerate(centers):
            box = pygame.Rect((0, 0), size)
            box.center = (round(tx + dx), round(ty + dy))
            box.clamp_ip(area)
            room = box.inflate(16, 16)  # with its glow
            score = (room.colliderect(target), sum(room.colliderect(r) for r in ships), i)
            if best is None or score < best[0]:
                best = (score, box)
        assert best is not None
        return best[1]

    def _draw_boost_box(self, surf: pygame.Surface) -> None:
        """The MATH BOOST box beside the ship a frozen hit is about to land on, tied to it by a
        line, with gold brackets on the ship and a bar counting down until the hit lands."""
        c = self.chance
        assert c is not None
        hit = c.hit
        tx, ty = self.visuals[hit.event.target_id].screen
        pulse = 0.5 + 0.5 * math.sin(self.time * 6)
        half = T.TILE / 2 + 2 + 4 * pulse
        for sx in (-1, 1):
            for sy in (-1, 1):
                cx, cy = tx + sx * half, ty + sy * half
                pygame.draw.line(surf, T.ACCENT, (cx, cy), (cx - sx * 16, cy), 4)
                pygame.draw.line(surf, T.ACCENT, (cx, cy), (cx, cy - sy * 16), 4)

        box = self._box_place(tx, ty, (286, 96))
        self.box_rect = box
        px, py = min(max(tx, box.left), box.right), min(max(ty, box.top), box.bottom)  # the box's nearest point
        end = (min(max(px, tx - half), tx + half), min(max(py, ty - half), ty + half))
        pygame.draw.line(surf, T.ACCENT, (px, py), end, 3)

        hovered = box.collidepoint(self.mouse)
        glow = pygame.Surface(box.inflate(16, 16).size, pygame.SRCALPHA)
        pygame.draw.rect(glow, (*T.ACCENT, round(40 + 60 * pulse)), glow.get_rect(), border_radius=16)
        surf.blit(glow, box.inflate(16, 16))
        pygame.draw.rect(surf, (92, 74, 26) if hovered else (52, 42, 18), box, border_radius=10)
        pygame.draw.rect(surf, T.ACCENT, box, 3, border_radius=10)
        x = box.x + 14
        text(surf, "MATH BOOST", (x, box.y + 10), 34, T.ACCENT)
        key = pygame.Rect(box.right - 40, box.y + 10, 28, 26)
        pygame.draw.rect(surf, (10, 16, 26), key, border_radius=5)
        text(surf, "B", key.center, 20, T.ACCENT, "center")
        what = f"Make this hit {BOOST:.0%} {'stronger' if hit.offense else 'weaker'}"
        text(surf, what, (x, box.y + 40), 20, T.GOOD)
        text(surf, "Click for a problem  -  Space: let it land", (x, box.y + 62), 16, T.DIM)
        left = max(0.0, c.wait / CHANCE_SECONDS)
        track = pygame.Rect(box.x + 10, box.bottom - 10, box.width - 20, 4)
        pygame.draw.rect(surf, (30, 26, 14), track, border_radius=2)
        pygame.draw.rect(surf, T.ACCENT, pygame.Rect(track.x, track.y, round(track.width * left), track.height), border_radius=2)

    def _draw_card(self, surf: pygame.Surface, s: Stack, y: int, title: str, editable: bool) -> int:
        d = s.design
        x, w = T.PANEL_X + 14, T.PANEL_W - 28
        side_color = LOG_COLORS[s.side]
        text(surf, f"{title} - {self.battle.side_names[s.side].upper()}", (x, y), 17, side_color)
        y += 17
        text(surf, d.name, (x, y), 30, T.TEXT)
        text(surf, f"x{s.count}", (x + w, y), 30, T.TEXT, "topright")
        y += 26
        text(surf, f"{d.hull.name} hull  -  {s.start_count - s.count} lost of {s.start_count}", (x, y), 18, T.DIM)
        y += 20
        bar(surf, pygame.Rect(x, y + 2, w - 110, 10), s.top_hp / d.max_hp)
        text(surf, f"hull {s.top_hp}/{d.max_hp}", (x + w, y), 18, T.DIM, "topright")
        y += 20
        moves = f" ({s.moves_left} left)" if s.id == self.battle.active_id and not self.battle.over else ""
        text(surf, f"Speed {d.speed}{moves}   Fire control +{d.attack}   Evasion {d.defense}", (x, y), 18, T.TEXT)
        y += 18
        text(surf, f"Armor belt {d.belt}   Countermeasures {d.torpedo_defense}", (x, y), 18, T.TEXT)
        y += 18
        extras = []
        if d.max_field:
            extras.append(f"Field {s.top_field}/{d.max_field}")
        if d.intercept_chance:
            extras.append(f"Shoots down {self.battle.intercept_chance(s):.0%}")
        if d.decoys:
            extras.append(f"Decoys {d.decoy_chance:.0%}")
        if extras:
            text(surf, "   ".join(extras), (x, y), 18, FIELD_COLOR)
            y += 18
        y += 4
        held = self.held.get(s.id, set())
        for i, m in enumerate(d.mounts):
            wpn = m.weapon
            line = pygame.Rect(x - 4, y - 2, w + 8, 20)
            if editable and line.collidepoint(self.mouse):
                pygame.draw.rect(surf, T.BUTTON_HOVER, line, border_radius=4)
            text(surf, f"{i + 1}. {m.count}x {wpn.name}", (x, y), 19, T.TEXT)
            stats = f"{wpn.damage[0]}-{wpn.damage[1]}  rng {wpn.range}"
            text(surf, stats, (x + 170, y), 18, T.DIM)
            if wpn.is_projectile:
                status, color = f"{s.ammo[i]} left", T.DIM
            else:
                status, color = "", T.DIM
            if s.id == self.battle.active_id:
                if s.fired[i]:
                    status, color = "fired", T.FAINT
                elif s.ammo[i] == 0:
                    status, color = "empty", T.FAINT
                elif i in held:
                    status, color = "HOLD", T.WARN
                elif not status:
                    status, color = "ready", T.GOOD
            elif i in held:
                status, color = "HOLD", T.WARN
            text(surf, status, (x + w, y), 18, color, "topright")
            if editable:
                self.weapon_rects.append((line, i))
            y += 20
        return y

    def _draw_fire_preview(self, surf: pygame.Surface, attacker: Stack, target: Stack, y: int) -> None:
        x, w = T.PANEL_X + 14, T.PANEL_W - 28
        y += 6
        text(surf, f"YOUR FIRE AT RANGE {distance(attacker.pos, target.pos)}", (x, y), 17, T.ACCENT)
        y += 19
        held = self.held.get(attacker.id, set())
        for i, m in enumerate(attacker.design.mounts):
            wpn = m.weapon
            text(surf, f"{m.count * attacker.count}x {wpn.name}", (x, y), 18, T.TEXT)
            if attacker.fired[i] or attacker.ammo[i] == 0:
                note, color = "fired" if attacker.fired[i] else "empty", T.FAINT
            elif distance(attacker.pos, target.pos) > wpn.range:
                note, color = "out of range", T.FAINT
            else:
                if wpn.is_projectile:
                    chance = self.battle.projectile_hit_chance(attacker.design.attack + wpn.accuracy, target)
                else:
                    chance = self.battle.gun_hit_chance(attacker, wpn, target)
                exp = expected_damage(self.battle, attacker, i, target)
                note = f"{chance:.0%} to hit, ~{exp:.0f} dmg"
                color = T.WARN if i in held else T.GOOD
                if i in held:
                    note += " (held)"
            text(surf, note, (x + w, y), 18, color, "topright")
            y += 19

    def _draw_log(self, surf: pygame.Surface) -> None:
        rect = pygame.Rect(T.LOG_RECT)
        panel(surf, rect)
        lines: list[tuple[str, tuple]] = []
        for msg, color in self.log[-8:]:
            lines += [(line, color) for line in wrap(msg, 19, rect.width - 20)]
        lines = lines[-((rect.height - 12) // 19):]
        y = rect.y + 8
        for i, (line, color) in enumerate(lines):
            faded = tuple(round(c * (0.55 + 0.45 * (i + 1) / len(lines))) for c in color)
            text(surf, line, (rect.x + 10, y), 19, faded)
            y += 19

    def _draw_tooltip(self, surf: pygame.Surface, stack: Stack, tile: Pos) -> None:
        target = self.battle.stack_at(tile)
        tip = ""
        if target is not None and target.side != stack.side:
            mounts = self.fireable(stack, target)
            if mounts:
                exp = sum(expected_damage(self.battle, stack, i, target) for i in mounts)
                tip = f"Fire {len(mounts)} weapon group{'s' if len(mounts) > 1 else ''}: ~{exp:.0f} damage"
            else:
                tip = "No ready weapon in range"
        elif target is None:
            path = self.battle.reachable(stack).get(tile)
            if path:
                tip = f"Move here ({len(path)} of {stack.moves_left} moves)"
        if not tip:
            return
        img = T.render(tip, 19, T.TEXT)
        rect = img.get_rect(topleft=(self.mouse[0] + 16, self.mouse[1] + 18)).inflate(12, 8)
        rect.clamp_ip(self.map_rect)
        pygame.draw.rect(surf, (8, 14, 22), rect, border_radius=5)
        pygame.draw.rect(surf, T.PANEL_EDGE, rect, 1, border_radius=5)
        surf.blit(img, img.get_rect(center=rect.center))

    def _overlay_box(self, surf: pygame.Surface, w: int, h: int) -> pygame.Rect:
        shade = pygame.Surface(self.map_rect.size, pygame.SRCALPHA)
        shade.fill((4, 8, 14, 150))
        surf.blit(shade, self.map_rect)
        box = pygame.Rect(0, 0, w, h)
        box.center = self.map_rect.center
        panel(surf, box, radius=12)
        return box

    def _draw_result(self, surf: pygame.Surface) -> None:
        b = self.battle
        box = self._overlay_box(surf, 600, 380)
        withdrew = self.report is not None and self.report.outcome == "withdrew"
        if b.winner is None:
            title, color = "DRAW", T.ACCENT
        elif b.winner in self.human_sides:
            title, color = "VICTORY", T.GOOD
        elif withdrew:
            title, color = "WITHDRAWN", T.WARN
        else:
            title, color = "DEFEAT", T.BAD
        text(surf, title, (box.centerx, box.y + 22), 60, color, "midtop")
        if self.report is not None:
            y = box.y + 90
            summary = [self.boost.summary()] if self.boost is not None and self.boost.summary() else []
            for line in self.report.lines() + summary:
                for part in wrap(line, 21, box.width - 60):
                    text(surf, part, (box.centerx, y), 21, T.TEXT, "midtop")
                    y += 25
                y += 8
            for button in self.result_buttons:
                button.draw(surf, self.mouse)
            return
        last = next((m for m, _ in reversed(self.log) if m and not m.startswith("---")), "")
        text(surf, last, (box.centerx, box.y + 72), 19, T.DIM, "midtop")
        summary = b.summary()
        for side in (0, 1):
            x = box.x + 30 + side * 290
            y = box.y + 104
            text(surf, f"{b.side_names[side]} fleet", (x, y), 24, LOG_COLORS[side])
            y += 26
            for name, start, left, status in summary[side]:
                text(surf, name, (x, y), 19, T.TEXT)
                note = f"{left}/{start}"
                ncolor = T.TEXT
                if status == "sunk":
                    note, ncolor = f"0/{start} sunk", T.BAD
                elif status == "retreated":
                    note, ncolor = f"{left}/{start} fled", T.WARN
                text(surf, note, (x + 250, y), 19, ncolor, "topright")
                y += 21
        for button in self.result_buttons:
            button.draw(surf, self.mouse)

    def _prompt_button(self, surf: pygame.Surface, rect: pygame.Rect, label: str, fn: Callable[[], None], hint: str = "",
                       toggled: bool = False) -> None:
        b = Button(rect, label, fn, hint, toggled=toggled, size=19)
        b.draw(surf, self.mouse)
        self.prompt_hits.append((rect, fn))

    def _draw_prompt(self, surf: pygame.Surface) -> None:
        """The Math Boost popup: what's about to happen, the problem and its four choices;
        after a wrong answer, what went wrong and the working."""
        p = self.prompt
        assert p is not None and p.problem is not None
        prob, hit = p.problem, p.hit
        self.prompt_hits = []
        shade = pygame.Surface(T.WINDOW, pygame.SRCALPHA)
        shade.fill((4, 8, 14, 150))
        surf.blit(shade, (0, 0))
        box = pygame.Rect(0, 0, 900, 650)
        box.center = (T.WINDOW[0] // 2, T.WINDOW[1] // 2)
        panel(surf, box, radius=12)
        x, w = box.x + 28, box.width - 56
        side = T.GOOD if hit.offense else T.BAD

        # what's about to happen
        y = box.y + 16
        text(surf, "MATH BOOST", (x, y), 22, T.ACCENT)
        text(surf, f"{prob.topic}  -  level {prob.level + 1}", (x + w, y + 3), 18, T.DIM, "topright")
        y += 28
        r = text(surf, hit.headline(), (x, y), 36, side)
        story = wrap(hit.story(), 20, x + w - r.right - 16)[:2]
        for i, line in enumerate(story):
            text(surf, line, (r.right + 16, y + (10 if len(story) == 1 else 1) + i * 20), 20, T.TEXT)
        y += 38
        if p.picked is None:
            stakes, color = hit.stakes(), T.ACCENT
        else:
            stakes, color = hit.outcome(p.right), T.GOOD if p.right else T.BAD
        text(surf, stakes, (x, y), 22, color)
        y += 30
        pygame.draw.line(surf, T.PANEL_EDGE, (x, y), (x + w, y))
        y += 12

        # the problem, with its sketch on the right
        fig = prob.fig
        fig_w = 250 if fig else 0
        qw = w - (fig_w + 20 if fig else 0)
        top, room = y, 150
        if fig:
            fig_box = pygame.Rect(x + w - fig_w, top, fig_w, room)
            panel(surf, fig_box, (14, 22, 34))
            draw_figure(surf, fig_box.inflate(-10, -10), fig)
        ask = "" if prob.words and prob.ask in ("= ?", "→ ?") else prob.ask
        if prob.ask.startswith("Graph"):
            ask = "Which number line shows it?"
        if prob.words:
            for size in (21, 19, 17, 16):
                lines = mwrap(prob.question, size, qw)
                if len(lines) * (size + 6) + (size + 12 if ask else 0) <= room:
                    break
            for line in lines:
                mtext(surf, line, (x, y), size, T.TEXT)
                y += size + 6
            if ask:
                mtext(surf, ask, (x, y + 4), size + 2, T.TEXT, bold=True)
        else:
            joined = prob.ask.startswith(("=", "→"))
            first = f"{prob.question} {prob.ask}" if joined else prob.question
            size = 32
            while size > 20 and T.math_font(size, True).size(first)[0] > qw:
                size -= 2
            cx = x + qw // 2
            mtext(surf, first, (cx, y + 18), size, T.ACCENT, "midtop", bold=True)
            if not joined:
                mtext(surf, ask, (cx, y + 30 + size), 24 if not ask.startswith("Which") else 20, T.TEXT, "midtop", bold=True)
        y = top + room + 12

        # the four choices, 2 x 2
        cw = (w - 12) // 2
        for i, choice in enumerate(prob.choices):
            rect = pygame.Rect(x + (i % 2) * (cw + 12), y + (i // 2) * 66, cw, 58)
            if p.picked is None:
                fill, edge = (T.BUTTON_HOVER if rect.collidepoint(self.mouse) else T.BUTTON), T.PANEL_EDGE
            elif i == prob.answer:
                fill, edge = (34, 92, 56), T.GOOD
            elif i == p.picked:
                fill, edge = (110, 40, 36), T.BAD
            else:
                fill, edge = (22, 30, 42), T.PANEL_EDGE
            pygame.draw.rect(surf, fill, rect, border_radius=8)
            pygame.draw.rect(surf, edge, rect, 2, border_radius=8)
            key = pygame.Rect(rect.x + 10, rect.centery - 13, 26, 26)
            pygame.draw.rect(surf, (10, 16, 26), key, border_radius=5)
            text(surf, str(i + 1), key.center, 20, T.ACCENT, "center")
            faded = p.picked is not None and i not in (prob.answer, p.picked)
            ink = T.FAINT if faded else T.TEXT
            if choice.graph:
                at, rel, lo, hi = choice.graph
                draw_number_line(surf, pygame.Rect(rect.x + 48, rect.y + 5, rect.width - 96, rect.height - 10), at, rel, lo, hi, ink, fill)
            else:
                csize = 22
                lines = mwrap(choice.text, csize, rect.width - 96)
                if len(lines) > 1:
                    csize = 16
                    lines = mwrap(choice.text, csize, rect.width - 96)[:2]
                for j, line in enumerate(lines):
                    cy = rect.centery + (j - (len(lines) - 1) / 2) * (csize + 3)
                    mtext(surf, line, (rect.x + 48, cy), csize, ink, "midleft")
            if p.picked is not None and i in (prob.answer, p.picked):
                mark, color = ("✓", T.GOOD) if i == prob.answer else ("✗", T.BAD)
                mtext(surf, mark, (rect.right - 14, rect.centery), 28, color, "midright", bold=True)
            if p.picked is None:
                self.prompt_hits.append((rect, lambda k=i: self.answer_boost(k)))
        y += 2 * 66 + 8

        # below: the hint and the buttons, or after a miss what went wrong and the working
        bottom = box.bottom - 16
        buttons_y = bottom - 40
        if p.picked is None:
            if p.show_hint:
                text(surf, "HINT", (x, y), 17, T.ACCENT)
                for line in mwrap(prob.hint, 18, w - 60):
                    mtext(surf, line, (x + 50, y), 18, T.TEXT)
                    y += 23
            else:
                text(surf, f"Answer with 1-4 or a click. One try: a right answer helps by {BOOST:.0%}, "
                           f"a wrong one hurts by {PENALTY:.0%}. H for a hint.", (x, y), 18, T.DIM)
            self._prompt_button(surf, pygame.Rect(x, buttons_y, 170, 40), "Hint", lambda: setattr(p, "show_hint", not p.show_hint),
                                "H", toggled=p.show_hint)
            self._prompt_button(surf, pygame.Rect(x + w - 340, buttons_y, 340, 40), "Turn off Math Boost for this mission",
                                self.turn_boost_off)
            return
        if not p.right:
            reason = p.problem.reason(p.picked)
            if reason:
                text(surf, "WHAT WENT WRONG", (x, y), 17, T.BAD)
                for line in mwrap(reason, 17, w - 170):
                    mtext(surf, line, (x + 160, y), 17, (250, 190, 180))
                    y += 21
                y += 6
            text(surf, "WORKING", (x, y), 17, T.ACCENT)
            for math_part, note in prob.steps:  # the math, then what it does in grey
                if y > buttons_y - 22:
                    break
                r = mtext(surf, math_part, (x + 160, y), 17, T.TEXT)
                if note:
                    notes = mwrap(note, 16, x + w - r.right - 18)
                    if r.right + 18 + T.math_font(16).size(notes[0])[0] <= x + w and len(notes) == 1:
                        mtext(surf, notes[0], (r.right + 18, y + 1), 16, T.DIM)
                    else:
                        for part in mwrap(note, 16, w - 190)[:2]:
                            y += 20
                            mtext(surf, part, (x + 180, y + 1), 16, T.DIM)
                y += 22
        else:
            text(surf, "Carrying on in a moment...", (x, y), 18, T.DIM)
        self._prompt_button(surf, pygame.Rect(x + w - 200, buttons_y, 200, 40), "Continue", self.continue_battle, "Enter")
        self._prompt_button(surf, pygame.Rect(x, buttons_y, 340, 40), "Turn off Math Boost for this mission", self.turn_boost_off)

    def _draw_debrief(self, surf: pygame.Surface, rect: pygame.Rect) -> None:
        """After the battle: the lessons, then how each weapon did against the odds."""
        d = self.debrief
        x, w = rect.x + 14, rect.width - 28
        bottom = self.buttons["end"].rect.y - 10
        y = rect.y + 12
        text(surf, "DEBRIEF", (x, y), 26, T.ACCENT)
        y += 34

        def para(s: str, color, size: int = 18, indent: int = 0) -> bool:
            nonlocal y
            for line in wrap(s, size, w - indent):
                if y > bottom - size:
                    return False
                text(surf, line, (x + indent, y), size, color)
                y += size
            return True

        text(surf, "WHAT TO TAKE FROM IT", (x, y), 17, T.DIM)
        y += 22
        for lesson in d.lessons:
            pygame.draw.circle(surf, T.ACCENT, (x + 4, y + 7), 3)
            if not para(lesson, T.TEXT, indent=14):
                return
            y += 8
        odds = d.odds()
        if odds:
            y += 6
            text(surf, "HITS AGAINST THE ODDS", (x, y), 17, T.DIM)
            y += 22
            for line, verdict in odds:
                if not para(line, T.TEXT):
                    return
                good, bad = verdict.startswith("Lucki"), verdict.startswith("Unlucki")
                if not para(verdict, T.GOOD if good else T.BAD if bad else T.DIM):
                    return
                y += 8

    def _draw_help(self, surf: pygame.Surface) -> None:
        box = self._overlay_box(surf, 740, 560)
        x, y = box.x + 28, box.y + 22
        text(surf, "HOW TO PLAY", (x, y), 34, T.ACCENT)
        y += 40
        rules = [
            "Each round every group of ships (a stack) acts once, fastest first. On your stack's turn, "
            "move up to its speed and fire each weapon group once, in any order.",
            "Click a blue tile to move. Click an enemy in red brackets to fire all ready weapons at it.",
            "Hit chance is 50%, +10% per point of your fire control above the target's evasion.",
            "An armor belt subtracts from every gun hit. Torpedoes strike below the belt and ignore it, "
            "but they take time to cross the map, can be outrun, and each ship carries only a couple of salvos.",
            "Missiles are fast and long-ranged, but armor belts reduce their damage. "
            "Torpedo interdiction can shoot down incoming torpedoes and missiles.",
            "Lasers are accurate and burn through armor belts. A force field (the blue ring) soaks up gun, laser "
            "and missile damage and refills every turn; torpedoes run under it.",
            "Damage goes to the top ship of a stack; damage beyond what sinks it is wasted.",
        ]
        for rule in rules:
            for line in wrap(rule, 20, box.width - 56):
                text(surf, line, (x, y), 20, T.TEXT)
                y += 21
            y += 6
        y += 8
        keys = [
            ("Space / Enter", "end this stack's turn", "1 - 4", "hold / release a weapon group"),
            ("A", "computer plays this stack", "Z", "computer plays your whole fleet"),
            ("R  (twice)", "retreat this stack", "F", "faster animations"),
            ("P", "pause", "Esc", "withdraw the fleet" if self.campaign else "back to the menu"),
        ]
        keys.append(("M", "sound on / off", *(("W  (twice)", "withdraw the fleet") if self.campaign else ("", ""))))
        if self.boost is not None:
            keys.append(("B / Space", "take / pass a Math Boost", "", ""))
        for k1, d1, k2, d2 in keys:
            text(surf, k1, (x, y), 20, T.ACCENT)
            text(surf, d1, (x + 130, y), 20, T.TEXT)
            text(surf, k2, (x + 350, y), 20, T.ACCENT)
            text(surf, d2, (x + 420, y), 20, T.TEXT)
            y += 24
        text(surf, "Press any key or click to close.", (box.centerx, box.bottom - 34), 19, T.DIM, "midtop")
