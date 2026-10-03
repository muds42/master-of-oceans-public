"""Computer-controlled fleet commanders.

``SimpleAI`` is a small *utility* AI. At the start of each activation it
scores every tile the stack could move to:

    score = offense(tile) - caution * danger(tile) - approach(tile)

* offense: enemy firepower we expect to knock out by firing from that tile
  (expected damage, weighted towards targets that are dangerous to us and
  low on hit points, i.e. "focus fire").
* danger: our own firepower we expect to lose next round if we end the turn
  there (every enemy that could move into range of that tile shoots us).
* approach: a small pull towards the enemy so fleets don't sit apart forever.

It also considers "fire from here, then move" so it will shoot and fall back
out of range when that is better (kiting). Caution fades as rounds pass so a
standoff eventually turns into a fight. It retreats when its fleet is hopelessly
outmatched.

Anything with a ``choose_action(battle, stack)`` method can be a controller,
so smarter AIs can be dropped in later without touching the rules.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol

from .battle import Action, Battle, EndTurn, Fire, Move, Pos, Retreat, Stack, distance
from .components import Weapon


class Controller(Protocol):
    def choose_action(self, battle: Battle, stack: Stack) -> Action: ...


# --------------------------------------------------------------------------- estimates


def per_hit_damage(weapon: Weapon, target: Stack, travel: int = 0) -> float:
    """Average damage of one hit after the armor belt, capped at one ship's hp (overkill on a
    single hit is wasted, unless a graviton beam carries some of it on). ``travel``: tiles a
    plasma torpedo runs, losing punch as it goes."""
    belt = weapon.belt_against(target.design.belt)
    lo, hi = weapon.damage
    cap = target.design.max_hp
    fade = weapon.fade * travel

    def dealt(d: int) -> float:
        d = max(1, d - fade) - belt if fade else d - belt
        return min(max(d, 0), cap) + weapon.carry * max(d - cap, 0)

    return sum(dealt(d) for d in range(lo, hi + 1)) / (hi - lo + 1)


def expected_per_shot(battle: Battle, attacker: Stack, mount: int, target: Stack, travel: int = 0) -> float:
    return per_hit_damage(attacker.design.mounts[mount].weapon, target, travel)


def projectile_chance(battle: Battle, attack: int, target: Stack) -> float:
    """Chance a torpedo or missile gets past interception and decoys, and then hits."""
    through = (1 - battle.intercept_chance(target)) * (1 - target.design.decoy_chance)
    return battle.projectile_hit_chance(attack, target) * through


def expected_damage(battle: Battle, attacker: Stack, mount: int, target: Stack, from_pos: Optional[Pos] = None) -> float:
    """Expected damage of one mount's volley (every ship in the stack fires) to the target's hull.
    The target's force field soaks up the first part, unless torpedoes run under it."""
    m = attacker.design.mounts[mount]
    travel = distance(from_pos or attacker.pos, target.pos) if m.weapon.fade else 0
    if m.weapon.is_projectile:
        chance = projectile_chance(battle, attacker.design.attack + m.weapon.accuracy, target)
    else:
        chance = battle.gun_hit_chance(attacker, m.weapon, target) * (1 - target.design.decoy_chance)
    shots = m.count * attacker.count
    dmg = shots * chance * expected_per_shot(battle, attacker, mount, target, travel)
    if not m.weapon.under_field:
        dmg -= target.top_field / m.weapon.field_factor
    return min(max(dmg, 0.0), target.total_hp)


def threat_to(battle: Battle, stack: Stack, victims: list[Stack]) -> float:
    """Damage per round this stack could deal to the most vulnerable of ``victims``."""
    best = 0.0
    for v in victims:
        dmg = sum(
            expected_damage(battle, stack, i, v)
            for i in range(len(stack.design.mounts))
            if stack.ammo[i] != 0
        )
        best = max(best, dmg)
    return best


def fleet_strength(battle: Battle, side: int) -> float:
    """Lanchester-style strength: firepower x staying power, summed over stacks."""
    enemies = battle.alive_stacks(1 - side)
    return sum(threat_to(battle, s, enemies) * s.total_hp for s in battle.alive_stacks(side))


# --------------------------------------------------------------------------- the AI


@dataclass
class _Plan:
    dest: Pos
    fire_first: bool
    retreat: bool = False
    moved: bool = False


class SimpleAI:
    def __init__(self, caution: float = 0.6, retreat_ratio: float = 0.08) -> None:
        self.caution = caution
        self.retreat_ratio = retreat_ratio
        self._plans: dict[tuple[int, int], _Plan] = {}

    # ---- controller interface --------------------------------------------------

    def choose_action(self, battle: Battle, stack: Stack) -> Action:
        key = (battle.round, stack.id)
        plan = self._plans.get(key)
        if plan is None:
            self._plans = {k: v for k, v in self._plans.items() if k[0] == battle.round}
            plan = self._plans[key] = self._make_plan(battle, stack)
        if plan.retreat:
            return Retreat()
        if plan.fire_first or plan.moved:
            fire = self.best_fire(battle, stack)
            if fire:
                return fire
        if not plan.moved:
            plan.moved = True
            if plan.dest != stack.pos and plan.dest in battle.reachable(stack):
                return Move(plan.dest)
            fire = self.best_fire(battle, stack)
            if fire:
                return fire
        return EndTurn()

    # ---- targeting -------------------------------------------------------------

    def _priorities(self, battle: Battle, side: int) -> dict[int, float]:
        """How much we want each enemy dead: its threat to us per hit point."""
        ours = battle.alive_stacks(side)
        return {
            e.id: (threat_to(battle, e, ours) + 1.0) / max(1, e.total_hp)
            for e in battle.alive_stacks(1 - side)
        }

    def fire_value(
        self, battle: Battle, stack: Stack, mount: int, target: Stack, priority: float, from_pos: Pos
    ) -> float:
        """Expected enemy firepower removed by firing ``mount`` at ``target``."""
        weapon = stack.design.mounts[mount].weapon
        dmg = expected_damage(battle, stack, mount, target, from_pos)
        if weapon.is_projectile:
            # Torpedoes and missiles are scarce: only use them where they are likely to hit,
            # won't be mostly wasted as overkill, and aren't already on the way.
            chance = projectile_chance(battle, stack.design.attack + weapon.accuracy, target)
            if chance < 0.25:
                return 0.0
            travel = distance(from_pos, target.pos)
            if expected_per_shot(battle, stack, mount, target, travel) < 0.45 * weapon.avg_damage:
                return 0.0
            incoming = sum(
                expected_damage_of_salvo(battle, s.attack, s.weapon, s.count, target,
                                         s.weapon.range - s.fuel + distance(s.pos, target.pos))
                for s in battle.incoming_salvos(target.id)
            )
            dmg = min(dmg, target.total_hp - incoming)
            if dmg <= 0:
                return 0.0
            if distance(from_pos, target.pos) > weapon.speed:
                dmg *= 0.2 if target.design.speed >= weapon.speed else 0.7  # may be outrun
        return dmg * priority

    def best_fire(self, battle: Battle, stack: Stack) -> Optional[Fire]:
        """The single most valuable shot available right now, if any."""
        priorities = self._priorities(battle, stack.side)
        best: Optional[Fire] = None
        best_value = 0.0
        for mount in range(len(stack.design.mounts)):
            for target in battle.targets(stack, mount):
                value = self.fire_value(battle, stack, mount, target, priorities[target.id], stack.pos)
                if value > best_value:
                    best, best_value = Fire(mount, target.id), value
        return best

    # ---- movement planning -----------------------------------------------------

    def _should_retreat(self, battle: Battle, side: int) -> bool:
        if battle.round < 2:
            return False
        ours = fleet_strength(battle, side)
        theirs = fleet_strength(battle, 1 - side)
        return theirs > 0 and ours < self.retreat_ratio * theirs

    def _make_plan(self, battle: Battle, stack: Stack) -> _Plan:
        if self._should_retreat(battle, stack.side):
            return _Plan(stack.pos, False, retreat=True)

        enemies = battle.enemies_of(stack)
        priorities = self._priorities(battle, stack.side)
        mounts = [i for i in range(len(stack.design.mounts)) if stack.mount_ready(i)]
        ranges = {i: stack.design.mounts[i].weapon.range for i in mounts}

        def offense(pos: Pos) -> float:
            total = 0.0
            for i in mounts:
                in_range = [e for e in enemies if distance(pos, e.pos) <= ranges[i]]
                if in_range:
                    total += max(self.fire_value(battle, stack, i, e, priorities[e.id], pos) for e in in_range)
            return total

        # Damage each enemy mount could do to us next round, and how far it reaches.
        # Its fire is shared among all of our stacks within that reach.
        friends = [s for s in battle.alive_stacks(stack.side) if s is not stack]
        dangers = []
        for e in enemies:
            for i, m in enumerate(e.design.mounts):
                if e.ammo[i] != 0:
                    reach = e.design.speed + m.weapon.range
                    exposed = 1 + sum(1 for f in friends if distance(f.pos, e.pos) <= reach)
                    dangers.append((e.pos, reach, expected_damage(battle, e, i, stack) / exposed))
        my_value = (threat_to(battle, stack, enemies) + 1.0) / max(1, stack.total_hp)

        def danger(pos: Pos) -> float:
            return my_value * sum(dmg for epos, reach, dmg in dangers if distance(pos, epos) <= reach)

        # What we could hit next round from a tile (after another full move).
        # This balances danger: an even exchange of fire scores about zero.
        speed = stack.design.speed
        best_value = {
            (i, e.id): self.fire_value(battle, stack, i, e, priorities[e.id], e.pos) for i in mounts for e in enemies
        }

        def follow_up(pos: Pos) -> float:
            total = 0.0
            for i in mounts:
                values = [best_value[i, e.id] for e in enemies if distance(pos, e.pos) <= speed + ranges[i]]
                total += max(values, default=0.0)
            return total

        # Pull towards the enemy, scaled to what one full volley is worth to us.
        best_range = max(ranges.values(), default=1)
        volley = sum(max((best_value[i, e.id] for e in enemies), default=0.0) for i in mounts)

        def approach(pos: Pos) -> float:
            gap = min((max(0, distance(pos, e.pos) - best_range) for e in enemies), default=0)
            return 0.05 * volley * gap

        caution = self.caution * max(0.0, 1 - battle.round / 12)
        here = offense(stack.pos)
        best_plan, best_score = _Plan(stack.pos, False), float("-inf")
        for dest, path in battle.reachable(stack).items():
            base = 0.5 * follow_up(dest) - caution * danger(dest) - approach(dest) - 0.001 * len(path)
            options = [(offense(dest), False)]
            if here > 0:
                options.append((here, True))
            for off, fire_first in options:
                if off + base > best_score:
                    best_plan, best_score = _Plan(dest, fire_first), off + base
        return best_plan


def expected_damage_of_salvo(
    battle: Battle, attack: int, weapon: Weapon, count: int, target: Stack, travel: int = 0
) -> float:
    return count * projectile_chance(battle, attack, target) * per_hit_damage(weapon, target, travel)
