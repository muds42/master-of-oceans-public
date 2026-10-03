"""Tactical battle rules. Pure game logic: no graphics, no input handling.

A battle is fought on a small grid (MOO1 style). Each side brings up to six
*stacks*; a stack is a group of identical ships that moves and fires together.
Every round, each stack gets one activation, in initiative order (fastest
first). During its activation a stack may move up to its speed and fire each
of its weapon mounts once, in any order. Torpedoes and missiles are launched as
salvos that travel across the map and home in on their target.

Every hit goes through the same steps: the target's holographic decoys may
draw it off, then it has to hit; the armor belt takes a fixed amount off
(lasers and torpedoes ignore it); a force field soaks up what it can (torpedoes
run under it); and the rest comes off the hull of the top ship. Damage past what
sinks that ship is wasted, unless a graviton beam carries it into the next one.

Controllers (the human UI or an AI) drive the battle by passing actions to
:meth:`Battle.apply`, which returns a list of events describing what happened.
The UI animates those events; the headless runner just prints their text.

:meth:`Battle.preview` works out what an action would do without doing it, and
``apply`` can scale the damage of chosen hits: the Math Boost uses both, to
find the big hits before they land and to make them hit harder (or softer).
"""

from __future__ import annotations

import copy
import random
from dataclasses import dataclass, field
from typing import Iterable, Optional, Union

from .components import Weapon
from .design import ShipDesign

Pos = tuple[int, int]
HitKey = tuple  # one volley or salvo in an action: ("guns", attacker id, mount) or ("salvo", salvo id)

MAX_STACKS_PER_SIDE = 6
DIRECTIONS = [(dx, dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if (dx, dy) != (0, 0)]


def distance(a: Pos, b: Pos) -> int:
    """Grid distance with diagonal moves costing the same as straight ones."""
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def hit_chance(attack: int, defense: int) -> float:
    """50% base, +/-10% per level of attack over defense, clamped to 5..95%."""
    return min(0.95, max(0.05, 0.5 + 0.1 * (attack - defense)))


def _sign(v: int) -> int:
    return (v > 0) - (v < 0)


def step_toward(a: Pos, b: Pos) -> Pos:
    return (a[0] + _sign(b[0] - a[0]), a[1] + _sign(b[1] - a[1]))


class IllegalAction(Exception):
    pass


# --------------------------------------------------------------------------- state


@dataclass
class Stack:
    id: int
    side: int
    design: ShipDesign
    count: int
    pos: Pos
    top_hp: int = 0  # hit points of the ship currently taking damage
    top_field: int = 0  # force field points left on that ship (refill at the start of the stack's turn)
    start_count: int = 0
    status: str = "active"  # "active" | "sunk" | "retreated"
    ammo: list[int] = field(default_factory=list)  # per mount; -1 = unlimited
    moves_left: int = 0
    fired: list[bool] = field(default_factory=list)  # per mount, this activation

    def __post_init__(self) -> None:
        self.top_hp = self.design.max_hp
        self.top_field = self.design.max_field
        self.start_count = self.count
        self.ammo = [m.weapon.ammo if m.weapon.is_projectile else -1 for m in self.design.mounts]
        self.fired = [False] * len(self.design.mounts)

    @property
    def alive(self) -> bool:
        return self.status == "active"

    @property
    def total_hp(self) -> int:
        if self.count <= 0:
            return 0
        return (self.count - 1) * self.design.max_hp + self.top_hp

    @property
    def label(self) -> str:
        return f"{self.design.name} x{self.count}"

    def mount_ready(self, mount: int) -> bool:
        """Mount has not fired this activation and has ammunition left."""
        return not self.fired[mount] and self.ammo[mount] != 0


@dataclass
class Salvo:
    id: int
    side: int
    launcher_id: int
    target_id: int
    weapon: Weapon
    count: int
    pos: Pos
    fuel: int  # tiles it can still travel
    attack: int  # attack level fixed at launch


# --------------------------------------------------------------------------- actions


@dataclass(frozen=True)
class Move:
    dest: Pos


@dataclass(frozen=True)
class Fire:
    mount: int  # index into design.mounts
    target: int  # stack id


@dataclass(frozen=True)
class Retreat:
    pass


@dataclass(frozen=True)
class EndTurn:
    pass


@dataclass(frozen=True)
class Withdraw:
    """Every ship of the active stack's side leaves the battle at once."""


Action = Union[Move, Fire, Retreat, EndTurn, Withdraw]


# --------------------------------------------------------------------------- events


@dataclass(frozen=True)
class Event:
    text: str  # human-readable log line; empty for purely visual events


@dataclass(frozen=True)
class RoundStarted(Event):
    round: int


@dataclass(frozen=True)
class StackActivated(Event):
    stack_id: int


@dataclass(frozen=True)
class Moved(Event):
    stack_id: int
    path: tuple[Pos, ...]  # includes the starting tile


@dataclass(frozen=True)
class GunsFired(Event):
    attacker_id: int
    target_id: int
    mount: int
    shots: int
    hits: int
    damage: int
    kills: int
    target_count: int  # target ships left afterwards
    target_hp: int  # target's top ship hp afterwards
    chance: float = 0.0  # chance for each shot to hit
    fired: int = 0  # shots that got a roll to hit (the target was afloat and they didn't hit a hologram)
    blocked: int = 0  # damage the target's armor belt stopped
    wasted: int = 0  # damage beyond what sank a ship (overkill)
    kind: str = "gun"  # "gun" or "laser"
    absorbed: int = 0  # damage the target's force field soaked up
    decoyed: int = 0  # shots that hit a hologram
    carried: int = 0  # overkill a graviton beam carried into the next ship
    target_field: int = 0  # target's top ship force field afterwards
    boost: float = 1.0  # what a math boost multiplied the damage of every hit by

    @property
    def key(self) -> HitKey:
        return ("guns", self.attacker_id, self.mount)


@dataclass(frozen=True)
class SalvoLaunched(Event):
    salvo_id: int
    attacker_id: int
    target_id: int
    count: int
    pos: Pos
    kind: str  # "torpedo" or "missile"


@dataclass(frozen=True)
class SalvoMoved(Event):
    salvo_id: int
    path: tuple[Pos, ...]  # includes the starting tile


@dataclass(frozen=True)
class SalvoHit(Event):
    salvo_id: int
    target_id: int
    count: int
    intercepted: int  # shot down by the target's interdiction before they could hit
    hits: int
    damage: int
    kills: int
    target_count: int
    target_hp: int
    chance: float = 0.0  # chance for each torpedo or missile that gets past interception to hit
    rolled: int = 0  # torpedoes or missiles that got past interception and decoys while the target was afloat
    blocked: int = 0  # damage the target's armor belt stopped (missiles only)
    wasted: int = 0  # damage beyond what sank a ship (overkill)
    absorbed: int = 0  # damage the target's force field soaked up (missiles only)
    decoyed: int = 0  # torpedoes or missiles that went for a hologram
    target_field: int = 0
    boost: float = 1.0  # what a math boost multiplied the damage of every hit by

    @property
    def key(self) -> HitKey:
        return ("salvo", self.salvo_id)


@dataclass(frozen=True)
class SalvoLost(Event):
    salvo_id: int
    pos: Pos
    count: int = 0  # torpedoes or missiles lost
    reason: str = ""  # "target" (it was sunk or left) or "range" (they ran out of fuel)


@dataclass(frozen=True)
class Repaired(Event):
    stack_id: int
    amount: int
    target_hp: int  # top ship hp afterwards


@dataclass(frozen=True)
class FieldRestored(Event):
    stack_id: int
    amount: int
    field: int  # top ship's force field afterwards


@dataclass(frozen=True)
class StackSunk(Event):
    stack_id: int


@dataclass(frozen=True)
class StackRetreated(Event):
    stack_id: int


@dataclass(frozen=True)
class BattleOver(Event):
    winner: Optional[int]  # side index, or None for a draw


# --------------------------------------------------------------------------- battle

Fleet = list[tuple[ShipDesign, int]]


class Battle:
    def __init__(
        self,
        fleets: tuple[Fleet, Fleet] | list[Fleet],
        *,
        width: int = 14,
        height: int = 9,
        islands: Iterable[Pos] = (),
        seed: Optional[int] = None,
        side_names: tuple[str, str] = ("Blue", "Red"),
        max_rounds: int = 40,
    ) -> None:
        if len(fleets) != 2:
            raise ValueError("a battle needs exactly two fleets")
        self.width = width
        self.height = height
        self.seed = seed
        self.rng = random.Random(seed)
        self.side_names = side_names
        self.max_rounds = max_rounds
        self.islands: set[Pos] = {p for p in islands if self.in_bounds(p)}
        self.stacks: dict[int, Stack] = {}
        self.salvos: dict[int, Salvo] = {}
        self._next_salvo_id = 1
        self.round = 0
        self.order: list[int] = []
        self._turn_index = -1
        self.active_id: Optional[int] = None
        self.started = False
        self.over = False
        self.winner: Optional[int] = None
        self.events: list[Event] = []  # everything that has happened, for the debrief
        self._boosts: dict[HitKey, float] = {}  # damage multipliers for hits of the action being applied
        for side, fleet in enumerate(fleets):
            self._deploy(side, fleet)

    def _deploy(self, side: int, fleet: Fleet) -> None:
        if len(fleet) > MAX_STACKS_PER_SIDE:
            raise ValueError(f"at most {MAX_STACKS_PER_SIDE} stacks per side")
        column = 1 if side == 0 else self.width - 2
        n = len(fleet)
        for i, (design, count) in enumerate(fleet):
            if count < 1:
                raise ValueError("a stack needs at least one ship")
            pos = (column, int((i + 0.5) * self.height / n))
            self.islands.discard(pos)
            sid = len(self.stacks) + 1
            self.stacks[sid] = Stack(sid, side, design, count, pos)

    # ---- queries ---------------------------------------------------------------

    @property
    def active(self) -> Optional[Stack]:
        return self.stacks.get(self.active_id) if self.active_id is not None else None

    def alive_stacks(self, side: Optional[int] = None) -> list[Stack]:
        return [s for s in self.stacks.values() if s.alive and (side is None or s.side == side)]

    def enemies_of(self, stack: Stack) -> list[Stack]:
        return self.alive_stacks(1 - stack.side)

    def stack_at(self, pos: Pos) -> Optional[Stack]:
        for s in self.stacks.values():
            if s.alive and s.pos == pos:
                return s
        return None

    def in_bounds(self, pos: Pos) -> bool:
        return 0 <= pos[0] < self.width and 0 <= pos[1] < self.height

    def passable(self, pos: Pos) -> bool:
        return self.in_bounds(pos) and pos not in self.islands and self.stack_at(pos) is None

    def reachable(self, stack: Stack, moves: Optional[int] = None) -> dict[Pos, tuple[Pos, ...]]:
        """Tiles the stack can end its move on, mapped to the path taken.

        The stack's own tile is included with an empty path. Paths exclude the
        starting tile. Islands and other stacks block movement.
        """
        budget = stack.moves_left if moves is None else moves
        paths: dict[Pos, tuple[Pos, ...]] = {stack.pos: ()}
        frontier = [stack.pos]
        for _ in range(budget):
            nxt = []
            for pos in frontier:
                for dx, dy in DIRECTIONS:
                    p = (pos[0] + dx, pos[1] + dy)
                    if p not in paths and self.passable(p):
                        paths[p] = paths[pos] + (p,)
                        nxt.append(p)
            frontier = nxt
        return paths

    def gun_hit_chance(self, attacker: Stack, weapon: Weapon, target: Stack) -> float:
        return hit_chance(attacker.design.attack + weapon.accuracy, target.design.defense)

    def projectile_hit_chance(self, attack: int, target: Stack) -> float:
        """Chance for a torpedo or missile that reaches its target to hit (after interception)."""
        return hit_chance(attack, target.design.torpedo_defense + target.design.defense)

    def can_fire(self, stack: Stack, mount: int, target: Optional[Stack]) -> bool:
        return (
            target is not None
            and target.alive
            and stack.alive
            and target.side != stack.side
            and 0 <= mount < len(stack.design.mounts)
            and stack.mount_ready(mount)
            and distance(stack.pos, target.pos) <= stack.design.mounts[mount].weapon.range
        )

    def targets(self, stack: Stack, mount: int) -> list[Stack]:
        return [t for t in self.enemies_of(stack) if self.can_fire(stack, mount, t)]

    def mounts_that_can_fire(self, stack: Stack, target: Stack) -> list[int]:
        return [i for i in range(len(stack.design.mounts)) if self.can_fire(stack, i, target)]

    def can_act(self, stack: Stack) -> bool:
        """Whether the stack has anything left to do this activation."""
        if len(self.reachable(stack)) > 1:
            return True
        return any(self.mounts_that_can_fire(stack, t) for t in self.enemies_of(stack))

    def incoming_salvos(self, target_id: int) -> list[Salvo]:
        return [s for s in self.salvos.values() if s.target_id == target_id]

    def summary(self) -> list[list[tuple[str, int, int, str]]]:
        """Per side: (design name, ships at start, ships left, status) for each stack."""
        result: list[list[tuple[str, int, int, str]]] = [[], []]
        for s in self.stacks.values():
            result[s.side].append((s.design.name, s.start_count, max(0, s.count), s.status))
        return result

    def _side_label(self, stack: Stack) -> str:
        return f"{self.side_names[stack.side]} {stack.label}"

    # ---- turn flow -------------------------------------------------------------

    def start(self) -> list[Event]:
        if self.started:
            raise IllegalAction("battle already started")
        self.started = True
        events: list[Event] = []
        if not self._check_over(events):
            self._advance(events)
        self.events += events
        return events

    def apply(self, action: Action, boosts: Optional[dict[HitKey, float]] = None) -> list[Event]:
        """Carry out ``action`` for the active stack. ``boosts`` multiplies the damage of every hit
        of chosen volleys and salvos (their event's ``key``); the dice roll as they would without it."""
        self._boosts = dict(boosts or {})
        try:
            return self._apply(action)
        finally:
            self._boosts = {}

    def preview(self, action: Action) -> list[Event]:
        """The events ``action`` would bring, worked out on a copy: this battle doesn't change.
        The copy rolls the same dice, so applying the action next brings the same events
        (unless a boost changes how many ships are left to shoot at)."""
        memo: dict[int, object] = {id(self.events): []}
        for s in self.stacks.values():
            memo[id(s.design)] = s.design
        for salvo in self.salvos.values():
            memo[id(salvo.weapon)] = salvo.weapon
        return copy.deepcopy(self, memo)._apply(action)

    def _apply(self, action: Action) -> list[Event]:
        if not self.started:
            raise IllegalAction("call start() first")
        if self.over:
            raise IllegalAction("the battle is over")
        stack = self.active
        assert stack is not None
        events: list[Event] = []
        if isinstance(action, Move):
            self._move(stack, action.dest, events)
        elif isinstance(action, Fire):
            self._fire(stack, action.mount, action.target, events)
            self._check_over(events)
        elif isinstance(action, Retreat):
            stack.status = "retreated"
            events.append(StackRetreated(f"{self._side_label(stack)} retreats.", stack.id))
            if not self._check_over(events):
                self._advance(events)
        elif isinstance(action, EndTurn):
            self._advance(events)
        elif isinstance(action, Withdraw):
            for s in self.alive_stacks(stack.side):
                s.status = "retreated"
                events.append(StackRetreated(f"{self._side_label(s)} withdraws.", s.id))
            self._check_over(events)
        else:
            raise IllegalAction(f"unknown action {action!r}")
        self.events += events
        return events

    def _advance(self, events: list[Event]) -> None:
        """Activate the next living stack, starting new rounds as needed."""
        self.active_id = None
        while not self.over:
            self._turn_index += 1
            if self._turn_index >= len(self.order):
                self._begin_round(events)
                continue
            stack = self.stacks[self.order[self._turn_index]]
            if stack.alive:
                stack.moves_left = stack.design.speed
                stack.fired = [False] * len(stack.design.mounts)
                self.active_id = stack.id
                events.append(StackActivated("", stack.id))
                self._repair(stack, events)
                return

    def _repair(self, stack: Stack, events: list[Event]) -> None:
        """At the start of the stack's turn damage control patches up the damaged ship
        and the force field comes back to full strength."""
        amount = min(stack.design.repair_per_round, stack.design.max_hp - stack.top_hp)
        if amount > 0:
            stack.top_hp += amount
            text = f"{self._side_label(stack)} damage control repairs {amount} hull."
            events.append(Repaired(text, stack.id, amount, stack.top_hp))
        field = stack.design.max_field - stack.top_field
        if field > 0:
            stack.top_field += field
            events.append(FieldRestored("", stack.id, field, stack.top_field))

    def _begin_round(self, events: list[Event]) -> None:
        if self.round >= self.max_rounds:
            self._finish(None, events, f"Both fleets disengage after {self.round} rounds.")
            return
        self.round += 1
        events.append(RoundStarted(f"--- Round {self.round} ---", self.round))
        for salvo in sorted(self.salvos.values(), key=lambda s: s.id):
            self._run_salvo(salvo, events)
        if self._check_over(events):
            return
        # Initiative: fastest first, then best fire control, ties broken randomly.
        rolls = {s.id: self.rng.random() for s in self.alive_stacks()}
        self.order = sorted(
            rolls, key=lambda i: (-self.stacks[i].design.speed, -self.stacks[i].design.attack, rolls[i])
        )
        self._turn_index = -1

    def _check_over(self, events: list[Event]) -> bool:
        if self.over:
            return True
        alive = [bool(self.alive_stacks(side)) for side in (0, 1)]
        if all(alive):
            return False
        if any(alive):
            winner = 0 if alive[0] else 1
            self._finish(winner, events, f"{self.side_names[winner]} fleet holds the sea. Victory for {self.side_names[winner]}!")
        else:
            self._finish(None, events, "No ships remain on either side. The battle is a draw.")
        return True

    def _finish(self, winner: Optional[int], events: list[Event], text: str) -> None:
        self.over = True
        self.winner = winner
        self.active_id = None
        events.append(BattleOver(text, winner))

    # ---- action resolution -----------------------------------------------------

    def _move(self, stack: Stack, dest: Pos, events: list[Event]) -> None:
        paths = self.reachable(stack)
        if dest == stack.pos or dest not in paths:
            raise IllegalAction(f"{stack.label} cannot move to {dest}")
        path = (stack.pos,) + paths[dest]
        stack.pos = dest
        stack.moves_left -= len(path) - 1
        events.append(Moved("", stack.id, path))

    def _fire(self, stack: Stack, mount: int, target_id: int, events: list[Event]) -> None:
        target = self.stacks.get(target_id)
        if not self.can_fire(stack, mount, target):
            raise IllegalAction(f"{stack.label} cannot fire mount {mount} at stack {target_id}")
        assert target is not None
        stack.fired[mount] = True
        m = stack.design.mounts[mount]
        if m.weapon.is_projectile:
            self._launch(stack, mount, target, events)
        else:
            self._shoot(stack, mount, target, events)

    def _damage(self, target: Stack, amount: int) -> tuple[int, int]:
        """Apply one hit to the top ship. Excess damage is wasted (MOO1 rule)."""
        applied = min(amount, target.top_hp)
        target.top_hp -= applied
        if target.top_hp > 0:
            return applied, 0
        target.count -= 1
        if target.count > 0:
            target.top_hp = target.design.max_hp
            target.top_field = target.design.max_field
        else:
            target.top_hp = 0
            target.status = "sunk"
        return applied, 1

    @staticmethod
    def _scaled(dmg: int, scale: float, carry: float) -> tuple[int, float]:
        """One hit's damage times a boost's ``scale``. The fraction left over carries to the next hit,
        so over a volley the damage comes out ``scale`` times as big, however small the hits."""
        if scale == 1.0 or dmg <= 0:
            return dmg, carry
        exact = dmg * scale + carry
        return int(exact), exact - int(exact)

    def _strike(self, target: Stack, dmg: int, weapon: Weapon) -> tuple[int, int, int, int, int]:
        """One hit that got past the armor belt: the force field soaks up what it can, then the hull
        takes the rest. Returns (hull damage, ships sunk, absorbed by the field, carried on, wasted)."""
        damage = kills = absorbed = carried = wasted = 0
        while dmg > 0 and target.alive:
            if target.top_field and not weapon.under_field:
                soak = min(target.top_field, dmg * weapon.field_factor)  # ion beams drain fields faster
                target.top_field -= soak
                used = -(-soak // weapon.field_factor)
                absorbed += used
                dmg -= used
                if dmg <= 0:
                    break
            applied, sunk = self._damage(target, dmg)
            damage += applied
            kills += sunk
            left = dmg - applied
            dmg = int(left * weapon.carry) if sunk and target.alive else 0  # graviton beams carry overkill on
            carried += dmg
            wasted += left - dmg
        return damage, kills, absorbed, carried, wasted

    def _shoot(self, stack: Stack, mount: int, target: Stack, events: list[Event]) -> None:
        m = stack.design.mounts[mount]
        weapon = m.weapon
        target_label = self._side_label(target)
        shots = m.count * stack.count
        chance = self.gun_hit_chance(stack, weapon, target)
        belt = weapon.belt_against(target.design.belt)
        decoy = target.design.decoy_chance
        scale, rest = self._boosts.get(("guns", stack.id, mount), 1.0), 0.0
        hits = damage = kills = fired = blocked = wasted = absorbed = decoyed = carried = 0
        for _ in range(shots):
            if not target.alive:
                break
            if decoy and self.rng.random() < decoy:
                decoyed += 1
                continue
            fired += 1
            if self.rng.random() >= chance:
                continue
            hits += 1
            raw = self.rng.randint(*weapon.damage)
            dmg = raw - belt
            blocked += min(raw, belt)
            dmg, rest = self._scaled(dmg, scale, rest)
            if dmg > 0:
                d, k, a, c, w = self._strike(target, dmg, weapon)
                damage, kills, absorbed, carried, wasted = damage + d, kills + k, absorbed + a, carried + c, wasted + w
        text = (
            f"{self._side_label(stack)} fires {shots} {weapon.name} at {target_label}: "
            f"{hits} hit{'s' if hits != 1 else ''}, {damage} damage"
        )
        if decoyed:
            text += f", {decoyed} at holograms"
        if absorbed:
            text += f", {absorbed} stopped by force fields"
        if kills:
            text += f", {kills} sunk"
        events.append(
            GunsFired(
                text + ".", stack.id, target.id, mount, shots, hits, damage, kills, target.count, target.top_hp,
                chance, fired, blocked, wasted, weapon.kind, absorbed, decoyed, carried, target.top_field, scale,
            )
        )
        if not target.alive:
            events.append(StackSunk(f"{self.side_names[target.side]} {target.design.name} group is lost!", target.id))

    def _launch(self, stack: Stack, mount: int, target: Stack, events: list[Event]) -> None:
        m = stack.design.mounts[mount]
        if stack.ammo[mount] > 0:
            stack.ammo[mount] -= 1
        salvo = Salvo(
            id=self._next_salvo_id,
            side=stack.side,
            launcher_id=stack.id,
            target_id=target.id,
            weapon=m.weapon,
            count=m.count * stack.count,
            pos=stack.pos,
            fuel=m.weapon.range,
            attack=stack.design.attack + m.weapon.accuracy,
        )
        self._next_salvo_id += 1
        self.salvos[salvo.id] = salvo
        events.append(
            SalvoLaunched(
                f"{self._side_label(stack)} launches {salvo.count} {m.weapon.plural} at {self._side_label(target)}.",
                salvo.id, stack.id, target.id, salvo.count, salvo.pos, m.weapon.kind,
            )
        )
        self._run_salvo(salvo, events)

    def _run_salvo(self, salvo: Salvo, events: list[Event]) -> None:
        """Move a salvo toward its target; detonate on arrival or sink when out of fuel."""
        target = self.stacks[salvo.target_id]
        if not target.alive:
            self._lose_salvo(salvo, events, "lose their target", "target")
            return
        path = [salvo.pos]
        for _ in range(salvo.weapon.speed):
            if salvo.pos == target.pos or salvo.fuel <= 0:
                break
            salvo.pos = step_toward(salvo.pos, target.pos)
            salvo.fuel -= 1
            path.append(salvo.pos)
        if len(path) > 1:
            events.append(SalvoMoved("", salvo.id, tuple(path)))
        if salvo.pos == target.pos:
            self._impact(salvo, target, events)
        elif salvo.fuel <= 0:
            self._lose_salvo(salvo, events, "run out of range", "range")

    def _lose_salvo(self, salvo: Salvo, events: list[Event], why: str, reason: str) -> None:
        del self.salvos[salvo.id]
        text = f"{self.side_names[salvo.side]} {salvo.weapon.plural} {why}."
        events.append(SalvoLost(text, salvo.id, salvo.pos, salvo.count, reason))

    def cover_chance(self, target: Stack) -> float:
        """The best point-defense cover a friendly stack next to ``target`` gives it."""
        return max(
            (s.design.cover_chance for s in self.alive_stacks(target.side) if s is not target and distance(s.pos, target.pos) <= 1),
            default=0.0,
        )

    def intercept_chance(self, target: Stack) -> float:
        """Chance to shoot down each torpedo or missile aimed at ``target``: its own interdiction,
        or the cover of point-defense lasers next to it, whichever is better."""
        return max(target.design.intercept_chance, self.cover_chance(target))

    def _impact(self, salvo: Salvo, target: Stack, events: list[Event]) -> None:
        del self.salvos[salvo.id]
        target_label = self._side_label(target)
        weapon = salvo.weapon
        chance = self.projectile_hit_chance(salvo.attack, target)
        intercept = self.intercept_chance(target)
        decoy = target.design.decoy_chance
        # Torpedoes strike below the armor belt, so only missiles are slowed by it.
        belt = weapon.belt_against(target.design.belt)
        fade = weapon.fade * (weapon.range - salvo.fuel)  # plasma loses punch with every tile it runs
        scale, rest = self._boosts.get(("salvo", salvo.id), 1.0), 0.0
        intercepted = hits = damage = kills = rolled = blocked = wasted = absorbed = decoyed = 0
        for _ in range(salvo.count):
            if not target.alive:
                break
            if intercept and self.rng.random() < intercept:
                intercepted += 1
                continue
            if decoy and self.rng.random() < decoy:
                decoyed += 1
                continue
            rolled += 1
            if self.rng.random() >= chance:
                continue
            hits += 1
            raw = max(1, self.rng.randint(*weapon.damage) - fade)
            dmg = raw - belt
            blocked += min(raw, belt)
            dmg, rest = self._scaled(dmg, scale, rest)
            if dmg > 0:
                d, k, a, c, w = self._strike(target, dmg, weapon)
                damage, kills, absorbed, wasted = damage + d, kills + k, absorbed + a, wasted + w
        text = f"{salvo.count} {self.side_names[salvo.side]} {weapon.plural} reach {target_label}: "
        if intercepted:
            text += f"{intercepted} shot down, "
        if decoyed:
            text += f"{decoyed} at holograms, "
        text += f"{hits} hit, {damage} damage"
        if absorbed:
            text += f", {absorbed} stopped by force fields"
        if kills:
            text += f", {kills} sunk"
        events.append(
            SalvoHit(
                text + ".", salvo.id, target.id, salvo.count, intercepted, hits, damage, kills,
                target.count, target.top_hp, chance, rolled, blocked, wasted, absorbed, decoyed, target.top_field, scale,
            )
        )
        if not target.alive:
            events.append(StackSunk(f"{self.side_names[target.side]} {target.design.name} group is lost!", target.id))
