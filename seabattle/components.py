"""Ship components: hulls, weapons and ship systems.

The numbers are loosely modelled on Master of Orion (1993) ship design,
re-themed for surface naval combat:

    MOO1              here
    ----------------  ----------------------------------------------------
    beam weapons      guns (fire instantly, limited range)
    missiles          torpedoes (travel across the map, limited ammo) and,
                      late in the game, real missiles (fast, long-ranged)
    battle computer   fire control (+attack)
    shields           armor belt (flat reduction of every gun hit;
                      torpedoes strike below the belt and ignore it)
    armor             hull plating (hit point multiplier)
    ECM               countermeasures (defense against torpedoes and missiles)
    engine/maneuver   propulsion (combat speed and evasion)

Act II brings MOO1's own future tech back (see ``economy.py`` for the
upgrades that fit it): laser cannons (beam weapons that burn through armor
belts), and, as refit bonuses on a design, force fields, holographic decoys
and the rest.

Everything here is plain data so a ship designer screen can be built on top
of it later without touching the battle rules.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Hull:
    id: str
    name: str
    space: int  # room for systems and weapons
    hp: int  # hit points per ship before plating
    defense: int  # evasion; bigger ships are easier to hit
    speed: int  # combat speed (tiles per turn) before propulsion
    cost: int
    scale: int  # systems (fire control, belt...) cost space and money x scale
    super_ship: bool = False  # too big for damage control to keep up with


@dataclass(frozen=True)
class Weapon:
    id: str
    name: str
    kind: str  # "gun", "laser", "torpedo" or "missile"
    damage: tuple[int, int]  # inclusive min, max per shot
    range: int  # guns and lasers: max firing range; projectiles: max travel distance
    space: int
    cost: int
    accuracy: int = 0  # bonus attack levels
    speed: int = 0  # projectiles only: tiles travelled per turn
    ammo: int = 0  # projectiles only: salvos per battle (0 = unlimited)
    belt_pierce: float = 0.0  # share of the armor belt it ignores (torpedoes and lasers: all of it)
    field_factor: int = 1  # damage multiplier against force fields (ion beams)
    carry: float = 0.0  # share of overkill that carries into the next ship of the stack (graviton beams)
    fade: int = 0  # projectiles only: damage lost per tile travelled (plasma torpedoes)

    @property
    def is_projectile(self) -> bool:
        """Torpedoes and missiles travel across the map as salvos."""
        return self.kind in ("torpedo", "missile")

    @property
    def ignores_belt(self) -> bool:
        return self.belt_pierce >= 1

    @property
    def under_field(self) -> bool:
        """Torpedoes run below the waterline, under force fields as well as armor belts."""
        return self.kind == "torpedo"

    def belt_against(self, belt: int) -> int:
        """How much of an armor belt stops this weapon's hits (a halved belt rounds down)."""
        return int(belt * (1 - self.belt_pierce))

    @property
    def plural(self) -> str:
        return {"torpedo": "torpedoes", "missile": "missiles", "laser": "beams"}.get(self.kind, "shells")

    @property
    def avg_damage(self) -> float:
        return (self.damage[0] + self.damage[1]) / 2


@dataclass(frozen=True)
class System:
    """One option for one of the five system slots on a design.

    Only the effect fields relevant to the slot are non-zero.
    """

    id: str
    name: str
    slot: str
    space: int  # per point of hull scale
    cost: int  # per point of hull scale
    attack: int = 0
    belt: int = 0
    hp_multiplier: float = 1.0
    torpedo_defense: int = 0
    speed: int = 0
    defense: int = 0


HULLS: dict[str, Hull] = {
    h.id: h
    for h in [
        Hull("corvette", "Corvette", space=40, hp=6, defense=3, speed=3, cost=8, scale=1),
        Hull("destroyer", "Destroyer", space=120, hp=20, defense=2, speed=3, cost=25, scale=3),
        Hull("cruiser", "Cruiser", space=320, hp=60, defense=1, speed=2, cost=70, scale=8),
        Hull("battleship", "Battleship", space=1000, hp=200, defense=0, speed=2, cost=200, scale=25),
        # Super ships: Red's, and in Act III your Stormbreaker.
        Hull("dreadnought", "Dreadnought", space=2600, hp=450, defense=0, speed=2, cost=500, scale=50, super_ship=True),
        Hull("fortress", "Sea Fortress", space=5200, hp=1000, defense=0, speed=1, cost=1200, scale=90, super_ship=True),
    ]
}

WEAPONS: dict[str, Weapon] = {
    w.id: w
    for w in [
        Weapon("mg", "Machine Gun", "gun", (1, 3), range=1, space=3, cost=1, accuracy=1),
        Weapon("gun4", '4" Gun', "gun", (2, 6), range=2, space=8, cost=3),
        Weapon("gun6", '6" Gun', "gun", (4, 10), range=3, space=20, cost=8),
        Weapon("gun12", '12" Gun', "gun", (8, 20), range=4, space=60, cost=25),
        Weapon("gun16", '16" Gun', "gun", (12, 28), range=5, space=100, cost=45),
        Weapon(
            "torpedo", "Torpedo", "torpedo", (10, 16), range=6, space=12, cost=6,
            accuracy=1, speed=4, ammo=2, belt_pierce=1.0,
        ),
        Weapon(
            "missile", "Missile", "missile", (14, 22), range=10, space=30, cost=15,
            accuracy=2, speed=7, ammo=2,
        ),
        # Act II: fitted to every ship's free mount by the Laser Cannons upgrade.
        Weapon("laser", "Laser Cannon", "laser", (6, 6), range=6, space=10, cost=6, accuracy=3, belt_pierce=1.0),
    ]
}

SLOTS = ("fire_control", "belt", "plating", "countermeasures", "propulsion")

SYSTEMS: dict[str, System] = {
    s.id: s
    for s in [
        # Fire control
        System("fc_none", "No Fire Control", "fire_control", 0, 0),
        System("fc_rangefinder", "Rangefinder", "fire_control", 2, 2, attack=1),
        System("fc_director", "Gun Director", "fire_control", 3, 4, attack=2),
        System("fc_radar", "Radar Fire Control", "fire_control", 4, 6, attack=3),
        # Armor belt
        System("belt_none", "No Belt", "belt", 0, 0),
        System("belt_light", "Light Belt", "belt", 2, 2, belt=1),
        System("belt_medium", "Medium Belt", "belt", 4, 4, belt=2),
        System("belt_heavy", "Heavy Belt", "belt", 6, 6, belt=3),
        # Hull plating
        System("plate_iron", "Iron Plating", "plating", 0, 0),
        System("plate_steel", "Steel Plating", "plating", 3, 2, hp_multiplier=1.5),
        System("plate_krupp", "Krupp Armor", "plating", 6, 5, hp_multiplier=2.0),
        # Countermeasures
        System("cm_none", "No Countermeasures", "countermeasures", 0, 0),
        System("cm_smoke", "Smoke Screen", "countermeasures", 1, 1, torpedo_defense=1),
        System("cm_decoys", "Acoustic Decoys", "countermeasures", 2, 2, torpedo_defense=2),
        # Propulsion
        System("prop_recip", "Triple-Expansion Engine", "propulsion", 0, 0),
        System("prop_turbine", "Steam Turbine", "propulsion", 2, 2, speed=1),
        System("prop_geared", "Geared Turbine", "propulsion", 4, 4, speed=1, defense=1),
        System("prop_hydrofoil", "Hydrofoil Drive", "propulsion", 6, 6, speed=2, defense=1),
    ]
}

# Default (empty) choice for each slot.
DEFAULT_SYSTEMS: dict[str, str] = {
    "fire_control": "fc_none",
    "belt": "belt_none",
    "plating": "plate_iron",
    "countermeasures": "cm_none",
    "propulsion": "prop_recip",
}


def systems_for_slot(slot: str) -> list[System]:
    return [s for s in SYSTEMS.values() if s.slot == slot]
