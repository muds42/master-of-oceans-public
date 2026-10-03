"""Ship designs: a hull plus systems and up to four weapon mounts (as in MOO1)."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .components import DEFAULT_SYSTEMS, HULLS, SLOTS, SYSTEMS, WEAPONS, Hull, System, Weapon

MAX_MOUNTS = 4
REPAIR_PER_LEVEL = 0.08  # damage control: share of a ship's hull repaired each round, per level
NANITE_PER_LEVEL = 0.05  # nanite repair: more hull repaired each round, per level
INTERCEPT_PER_LEVEL = 0.15  # interdiction: chance per level to shoot down each incoming projectile
INTERCEPT_MAX = 0.75
POINT_DEFENSE_PER_LEVEL = 0.10  # point-defense lasers: more interception on top of interdiction, per level
DECOY_PER_LEVEL = 0.10  # holographic decoys: share of shots aimed at the ship that hit a hologram, per level


@dataclass(frozen=True)
class WeaponMount:
    weapon: Weapon
    count: int  # weapons of this type on each ship


@dataclass(frozen=True)
class ShipDesign:
    name: str
    hull: Hull
    mounts: tuple[WeaponMount, ...]
    systems: dict[str, System] = field(default_factory=dict, hash=False, compare=False)
    # Refit bonuses from fleet upgrades (see economy.refit). Most base designs leave these at zero;
    # a few Act III designs are built with a force field or point defense of their own.
    speed_bonus: int = 0
    attack_bonus: int = 0
    belt_bonus: int = 0
    hp_bonus: float = 0.0  # +25% hull = 0.25
    auto_repair: int = 0  # damage control level
    interdiction: int = 0  # point defense level against torpedoes and missiles
    field_bonus: float = 0.0  # force field strength as a share of the hull (0.2 = a field of 20% of max hp)
    point_defense: int = 0  # point-defense laser level; level 2 also guards the stacks next to it
    decoys: int = 0  # holographic decoy level
    nanite: int = 0  # nanite repair level

    def __post_init__(self) -> None:
        # Fill any unspecified slot with its default so lookups never fail.
        filled = {slot: SYSTEMS[DEFAULT_SYSTEMS[slot]] for slot in SLOTS}
        filled.update(self.systems)
        object.__setattr__(self, "systems", filled)

    # ---- derived combat stats -------------------------------------------------

    @property
    def max_hp(self) -> int:
        return max(1, round(self.hull.hp * self.systems["plating"].hp_multiplier * (1 + self.hp_bonus)))

    @property
    def attack(self) -> int:
        return self.systems["fire_control"].attack + self.attack_bonus

    @property
    def defense(self) -> int:
        return self.hull.defense + self.systems["propulsion"].defense

    @property
    def belt(self) -> int:
        return self.systems["belt"].belt + self.belt_bonus

    @property
    def torpedo_defense(self) -> int:
        return self.systems["countermeasures"].torpedo_defense

    @property
    def speed(self) -> int:
        return self.hull.speed + self.systems["propulsion"].speed + self.speed_bonus

    @property
    def repair_per_round(self) -> int:
        """Hull points damage control (and nanite repair) restores to a damaged ship each round."""
        share = REPAIR_PER_LEVEL * self.auto_repair + NANITE_PER_LEVEL * self.nanite
        return math.ceil(self.max_hp * share) if share else 0

    @property
    def max_field(self) -> int:
        """Force field points: they soak up damage before the hull and refill at the start of each turn."""
        return math.ceil(self.max_hp * self.field_bonus) if self.field_bonus > 0 else 0

    @property
    def intercept_chance(self) -> float:
        """Chance to shoot down each torpedo or missile aimed at this ship."""
        return min(INTERCEPT_MAX, INTERCEPT_PER_LEVEL * self.interdiction) + POINT_DEFENSE_PER_LEVEL * self.point_defense

    @property
    def cover_chance(self) -> float:
        """Point-defense lasers at level 2 also shoot at salvos aimed at the stacks next to this one, at half the chance."""
        return self.intercept_chance / 2 if self.point_defense >= 2 else 0.0

    @property
    def decoy_chance(self) -> float:
        """Chance that a shot, torpedo or missile aimed at this ship hits a hologram instead."""
        return DECOY_PER_LEVEL * self.decoys

    @property
    def has_missiles(self) -> bool:
        return any(m.weapon.kind == "missile" for m in self.mounts)

    @property
    def has_lasers(self) -> bool:
        return any(m.weapon.kind == "laser" for m in self.mounts)

    # ---- construction budget --------------------------------------------------

    @property
    def space_used(self) -> int:
        systems = sum(s.space for s in self.systems.values()) * self.hull.scale
        weapons = sum(m.weapon.space * m.count for m in self.mounts)
        return systems + weapons

    @property
    def cost(self) -> int:
        systems = sum(s.cost for s in self.systems.values()) * self.hull.scale
        weapons = sum(m.weapon.cost * m.count for m in self.mounts)
        return self.hull.cost + systems + weapons

    @property
    def firepower(self) -> float:
        """Raw average damage per turn of one ship, ignoring hit chance and armor."""
        return sum(m.weapon.avg_damage * m.count for m in self.mounts)

    def validate(self) -> list[str]:
        """Return a list of problems; empty means the design can be built."""
        problems = []
        if len(self.mounts) > MAX_MOUNTS:
            problems.append(f"at most {MAX_MOUNTS} weapon mounts allowed")
        if any(m.count < 1 for m in self.mounts):
            problems.append("weapon mounts need at least one weapon")
        for slot, system in self.systems.items():
            if system.slot != slot:
                problems.append(f"{system.name} does not fit the {slot} slot")
        if self.space_used > self.hull.space:
            problems.append(f"needs {self.space_used} space but hull has {self.hull.space}")
        return problems


def make_design(name: str, hull: str, weapons: list[tuple[str, int]], **systems: str) -> ShipDesign:
    """Convenience constructor using component ids.

    >>> make_design("Picket", "corvette", [("gun4", 2)], fire_control="fc_rangefinder")
    """
    unknown = set(systems) - set(SLOTS)
    if unknown:
        raise ValueError(f"unknown system slot(s): {sorted(unknown)}")
    return ShipDesign(
        name=name,
        hull=HULLS[hull],
        mounts=tuple(WeaponMount(WEAPONS[w], n) for w, n in weapons),
        systems={slot: SYSTEMS[sid] for slot, sid in systems.items()},
    )
