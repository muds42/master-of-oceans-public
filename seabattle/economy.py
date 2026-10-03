"""Campaign economy: currencies, fleet upgrades and the shipyard catalog.

Currencies are earned by solving math problems in the workshop (see
``problems/``: each topic pays out in one currency) and spent on upgrades,
new ships and repairs.

Upgrades are fleet-wide technology levels, like research in Master of Orion:
buying "Heavier Shells" makes every gun in the fleet hit harder. ``refit``
applies a set of levels to a ship design.

Plasma, the fifth currency, opens with its two math topics when the player
wins super mission 10, the end of Act I (the campaign reaches ``PLASMA_MISSION``).
It pays for the Future Tech upgrades (lasers, force fields and the rest), each
of which needs Act I upgrades first: the tech tree. The Plasma ship classes open
when the player wins super mission 20, the end of Act II (``PLASMA_SHIPS_MISSION``).

Retrofits take future tech further on one of Act I's ship classes: a Laser
Battery or a Field Generator of its own, like the Plasma classes are built
with. ``retrofit`` applies them to a class's design, before ``refit``.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass, field, replace

from .components import WEAPONS, Weapon
from .design import MAX_MOUNTS, ShipDesign, WeaponMount
from .designs import (
    AEGIS_CRUISER, BATTLESHIP, DESTROYER, HYDROFOIL_RAIDER, LIGHT_CRUISER, MISSILE_CRUISER, PICKET, RED_SHIPS,
    STORMBREAKER, TORPEDO_BOAT,
)

Cost = dict[str, int]

CURRENCIES = ("steel", "powder", "fuel", "blueprints", "plasma")
CURRENCY_NAMES = {"steel": "Steel", "powder": "Powder", "fuel": "Fuel", "blueprints": "Blueprints", "plasma": "Plasma"}
CURRENCY_USES = {
    "steel": "hulls and armor",
    "powder": "guns and warheads",
    "fuel": "torpedoes, missiles and engines",
    "blueprints": "electronics and new ship classes",
    "plasma": "future tech: lasers, force fields and the new ship classes",
}
# Plasma, its math topics and the Future Tech upgrades open when the campaign reaches this mission: when the
# player wins super mission 10. The Plasma ship classes open when the player wins super mission 20.
PLASMA_MISSION = 11
PLASMA_SHIPS_MISSION = 21
FUTURE = "Future"  # the upgrade category of every future tech

# --------------------------------------------------------------------------- upgrades


@dataclass(frozen=True)
class Track:
    id: str
    name: str
    category: str
    effect: str  # what each level does (future tech: what the levels do, in full)
    max_level: int
    base_cost: Cost  # price of level 1
    growth: float = 2.0  # each further level costs twice the one before
    requires: dict[str, int] = field(default_factory=dict, hash=False)  # other tracks and the level each needs
    requires_mission: int = 1  # the campaign must have reached this mission

    @property
    def future(self) -> bool:
        return self.category == FUTURE

    def cost(self, level: int) -> Cost:
        """Price of buying ``level`` (1 = the first level)."""
        factor = self.growth ** (level - 1)
        return {c: int(round(v * factor / 5) * 5) for c, v in self.base_cost.items()}


TRACKS: dict[str, Track] = {
    t.id: t
    for t in [
        Track("caliber", "Heavier Shells", "Guns", "+1 damage for every gun", 4, {"powder": 80}),
        Track("turrets", "Extra Turrets", "Guns", "+1 gun in every gun mount", 3, {"powder": 100, "steel": 60}),
        Track("rangefinders", "Rangefinders", "Guns", "+1 range for every gun", 2, {"blueprints": 90, "powder": 40}),
        Track("fire_control", "Fire Control", "Guns", "+10% to hit with every weapon", 3, {"blueprints": 80}),
        Track("warheads", "Bigger Warheads", "Torpedoes", "+3 torpedo and missile damage", 3, {"powder": 70, "fuel": 40}),
        Track("tubes", "More Torpedo Tubes", "Torpedoes", "+1 torpedo per launcher", 2, {"fuel": 100, "steel": 50}),
        Track("torp_speed", "Faster Torpedoes", "Torpedoes", "+1 torpedo speed", 3, {"fuel": 80}),
        Track("torp_range", "Longer-Range Torpedoes", "Torpedoes", "+2 torpedo range", 2, {"fuel": 70}),
        Track("engines", "Engines", "Hull", "+1 speed for every ship", 2, {"steel": 80, "fuel": 80}),
        Track("armor", "Armor Plate", "Hull", "+25% hull strength", 4, {"steel": 90}),
        Track("belt", "Armor Belt", "Hull", "-1 damage from every gun and missile hit", 3, {"steel": 100}),
        Track(
            "damage_control", "Damage Control", "Systems", "repairs 8% of a damaged ship's hull each turn", 3,
            {"steel": 70, "blueprints": 70},
        ),
        Track(
            "interdiction", "Torpedo Interdiction", "Systems", "15% chance to shoot down each incoming torpedo or missile", 4,
            {"blueprints": 80, "powder": 40},
        ),
        # ---- Future Tech (Act II): Plasma plus the Act I currency that matches, and Act I upgrades first
        Track(
            "lasers", "Laser Cannons", FUTURE,
            "Fits lasers in every ship's free mount: 6 damage, +3 to hit, range 6, and they burn straight through "
            "armor belts. Levels 2 and 3: +2 laser damage. Opens the Laser Battery retrofit.", 3,
            {"plasma": 150, "powder": 60}, requires={"fire_control": 3, "rangefinders": 2},
            requires_mission=PLASMA_MISSION,
        ),
        Track(
            "ion", "Ion Beams", FUTURE, "Laser hits drain force fields twice as fast (level 1) or three times (level 2).", 2,
            {"plasma": 150, "blueprints": 60}, requires={"lasers": 1},
            requires_mission=PLASMA_MISSION,
        ),
        Track(
            "graviton", "Graviton Beams", FUTURE,
            "Half (level 1) or all (level 2) of a laser's overkill carries into the next ship of the stack.", 2,
            {"plasma": 250, "powder": 100}, requires={"lasers": 2, "fields": 1},
            requires_mission=PLASMA_MISSION,
        ),
        Track(
            "railguns", "Railguns", FUTURE, "Level 1: guns halve armor belts. Level 2: +1 range for every gun.", 2,
            {"plasma": 200, "steel": 100}, requires={"caliber": 4, "rangefinders": 2},
            requires_mission=PLASMA_MISSION,
        ),
        Track(
            "plasma_torps", "Plasma Torpedoes", FUTURE,
            "+6 torpedo damage per level, but a torpedo loses 1 damage for every tile it runs.", 2,
            {"plasma": 150, "fuel": 80}, requires={"warheads": 3},
            requires_mission=PLASMA_MISSION,
        ),
        Track(
            "fields", "Force Fields", FUTURE,
            "A field of 10% of each ship's hull per level. It soaks up gun, laser and missile damage before the hull "
            "and refills every turn. Torpedoes run under it. Opens the Field Generator retrofit.", 4,
            {"plasma": 150, "steel": 80}, requires={"belt": 3, "damage_control": 1},
            requires_mission=PLASMA_MISSION,
        ),
        Track(
            "point_defense", "Point-Defense Lasers", FUTURE,
            "+10% interception per level. Level 2 also guards the stacks next to yours, at half the chance.", 2,
            {"plasma": 150, "blueprints": 60}, requires={"interdiction": 4, "lasers": 1},
            requires_mission=PLASMA_MISSION,
        ),
        Track(
            "decoys", "Holographic Decoys", FUTURE,
            "10% per level of the shots, torpedoes and missiles aimed at your ships hit a hologram instead.", 3,
            {"plasma": 120, "blueprints": 60}, requires={"fire_control": 2, "interdiction": 2},
            requires_mission=PLASMA_MISSION,
        ),
        Track(
            "nanite", "Nanite Repair", FUTURE,
            "+5% of the hull repaired each turn per level, and a wreck costs 1/12 (level 1) or 1/16 (level 2) of a new "
            "ship to repair instead of 1/8.", 2,
            {"plasma": 120, "steel": 80}, requires={"damage_control": 3, "armor": 2},
            requires_mission=PLASMA_MISSION,
        ),
    ]
}

CATEGORIES = ("Guns", "Torpedoes", "Hull", "Systems")
LASERS_PER_HULL = {"corvette": 1, "destroyer": 2, "cruiser": 4, "battleship": 8, "dreadnought": 12, "fortress": 20}
FIELD_PER_LEVEL = 0.10  # force field strength per level, as a share of the hull


def refit(design: ShipDesign, levels: dict[str, int]) -> ShipDesign:
    """Return ``design`` with the fleet's upgrade levels applied.

    Damage control, nanite repair and force field generators can't keep up with
    a super ship's size: super ships never repair themselves in battle, and
    keep only the force field they were built with."""

    def lv(track: str) -> int:
        return max(0, min(levels.get(track, 0), TRACKS[track].max_level))

    def laser(w: Weapon) -> Weapon:
        bonus = 2 * max(0, lv("lasers") - 1)
        return replace(w, damage=(w.damage[0] + bonus, w.damage[1] + bonus), field_factor=1 + lv("ion"),
                       carry=0.5 * lv("graviton"))

    mounts = []
    for m in design.mounts:
        w, count = m.weapon, m.count
        if w.kind == "gun":
            bonus = lv("caliber")
            reach = lv("rangefinders") + (1 if lv("railguns") >= 2 else 0)
            w = replace(w, damage=(w.damage[0] + bonus, w.damage[1] + bonus), range=w.range + reach)
            if lv("railguns"):
                w = replace(w, belt_pierce=max(w.belt_pierce, 0.5))
            count += lv("turrets")
        elif w.kind == "laser":
            w = laser(w)
        else:
            bonus = 3 * lv("warheads")
            w = replace(w, damage=(w.damage[0] + bonus, w.damage[1] + bonus))
            if w.kind == "torpedo":
                w = replace(w, speed=w.speed + lv("torp_speed"), range=w.range + 2 * lv("torp_range"))
                count += lv("tubes")
                if lv("plasma_torps"):
                    plasma = 6 * lv("plasma_torps")
                    w = replace(w, name="Plasma Torpedo", damage=(w.damage[0] + plasma, w.damage[1] + plasma), fade=1)
        mounts.append(WeaponMount(w, count))
    if lv("lasers") and not design.has_lasers and len(mounts) < MAX_MOUNTS:  # lasers take the free mount
        mounts.append(WeaponMount(laser(WEAPONS["laser"]), LASERS_PER_HULL.get(design.hull.id, 1)))
    small = not design.hull.super_ship
    return replace(
        design,
        mounts=tuple(mounts),
        speed_bonus=design.speed_bonus + lv("engines"),
        attack_bonus=design.attack_bonus + lv("fire_control"),
        belt_bonus=design.belt_bonus + lv("belt"),
        hp_bonus=design.hp_bonus + 0.25 * lv("armor"),
        auto_repair=design.auto_repair + lv("damage_control") if small else 0,
        interdiction=design.interdiction + lv("interdiction"),
        field_bonus=design.field_bonus + (FIELD_PER_LEVEL * lv("fields") if small else 0),
        point_defense=design.point_defense + lv("point_defense"),
        decoys=design.decoys + lv("decoys"),
        nanite=design.nanite + lv("nanite") if small else 0,
    )


# --------------------------------------------------------------------------- shipyard


REPAIR_SHARE = 1 / 8  # repairing a wreck costs this share of a new ship's price...
NANITE_REPAIR_SHARE = {1: 1 / 12, 2: 1 / 16}  # ...or less with Nanite Repair


@dataclass(frozen=True)
class ShipClass:
    id: str
    design: ShipDesign
    blurb: str
    price: Cost
    unlock: Cost  # one-time cost to be able to build it; empty = available from the start
    requires_mission: int = 1  # the campaign must have reached this mission (only the Plasma classes wait)
    knots: int = 30  # top speed and crew, used in the word problems
    crew: int = 100
    limit: int = 0  # most ships of this class the fleet may hold (0: the usual limit)

    @property
    def name(self) -> str:
        return self.design.name

    @property
    def future(self) -> bool:
        """Act III classes, unlocked with Plasma."""
        return "plasma" in self.unlock

    @property
    def retrofittable(self) -> bool:
        """Act I's classes can be retrofitted with future tech; the Plasma classes are built with it."""
        return not self.future

    @property
    def repair_cost(self) -> Cost:
        """Repairing a wreck costs an eighth of a new ship's price, in each of its currencies (rounded up)."""
        return self.repair_cost_at(REPAIR_SHARE)

    def repair_cost_at(self, share: float) -> Cost:
        return {c: math.ceil(v * share - 1e-9) for c, v in self.price.items() if v}


SHIP_CLASSES: dict[str, ShipClass] = {
    c.id: c
    for c in [
        ShipClass(
            "picket", PICKET, "Cheap, fast gunboat. Good against other small boats.", {"steel": 30, "powder": 15}, {},
            knots=25, crew=12,
        ),
        ShipClass(
            "torpedo_boat", TORPEDO_BOAT, "Fragile, but its torpedoes can sink anything.", {"steel": 25, "fuel": 30}, {},
            knots=30, crew=20,
        ),
        ShipClass(
            "destroyer", DESTROYER, "Guns and torpedoes on a fast, sturdy hull.",
            {"steel": 80, "powder": 40, "fuel": 30}, {"blueprints": 60}, knots=32, crew=300,
        ),
        ShipClass(
            "light_cruiser", LIGHT_CRUISER, "Long-range 6-inch guns and a medium armor belt.",
            {"steel": 200, "powder": 120, "fuel": 40}, {"blueprints": 150}, knots=32, crew=400,
        ),
        ShipClass(
            "battleship", BATTLESHIP, "Huge guns, heavy armor, slow. The queen of the sea.",
            {"steel": 600, "powder": 350, "fuel": 80}, {"blueprints": 300}, knots=28, crew=1800,
        ),
        ShipClass(
            "missile_cruiser", MISSILE_CRUISER, "Fires fast, long-range missiles. The ultimate warship.",
            {"steel": 350, "powder": 150, "fuel": 250, "blueprints": 150}, {"blueprints": 500}, knots=33, crew=550,
        ),
        # ---- Act III: unlocked with Plasma
        ShipClass(
            "hydrofoil", HYDROFOIL_RAIDER, "Skims the waves at speed 5: close enough to launch on the first turn.",
            {"steel": 40, "fuel": 40, "plasma": 20}, {"plasma": 150}, requires_mission=PLASMA_SHIPS_MISSION, knots=45, crew=16,
        ),
        ShipClass(
            "aegis_cruiser", AEGIS_CRUISER, "Force field and point-defense lasers that guard the ships beside it.",
            {"steel": 300, "powder": 100, "blueprints": 100, "plasma": 80}, {"plasma": 300}, requires_mission=PLASMA_SHIPS_MISSION,
            knots=31, crew=450,
        ),
        ShipClass(
            "stormbreaker", STORMBREAKER, "Your own super ship: 16-inch guns behind a force field. At most two.",
            {"steel": 1200, "powder": 600, "fuel": 150, "plasma": 400}, {"plasma": 800, "blueprints": 500},
            requires_mission=PLASMA_SHIPS_MISSION, knots=27, crew=2600, limit=2,
        ),
    ]
}

STARTING_CLASSES = [c.id for c in SHIP_CLASSES.values() if not c.unlock]


def ship_design(ship_id: str) -> ShipDesign:
    """Base design for any ship id: a shipyard class or one of Red's super ships."""
    return SHIP_CLASSES[ship_id].design if ship_id in SHIP_CLASSES else RED_SHIPS[ship_id]


def class_of(design_name: str) -> ShipClass:
    return next(c for c in SHIP_CLASSES.values() if c.name == design_name)


def cost_text(cost: Cost) -> str:
    return ", ".join(f"{v} {CURRENCY_NAMES[c]}" for c, v in cost.items() if v)


# --------------------------------------------------------------------------- retrofits


@dataclass(frozen=True)
class Retrofit:
    """Future tech fitted to one of Act I's classes: every ship of that class gets it, now and later.

    Future Tech reaches the whole fleet (lasers in each ship's free mount, a field of 10% of the hull
    per level); a retrofit goes further on one class, the way the Plasma classes are built."""

    id: str
    name: str
    effect: str
    requires: str  # the future tech it needs, at level 1
    base_cost: Cost  # for a corvette class; bigger hulls pay RETROFIT_SCALE times as much

    def cost(self, hull: str) -> Cost:
        return {c: v * RETROFIT_SCALE[hull] for c, v in self.base_cost.items()}


RETROFIT_SCALE = {"corvette": 1, "destroyer": 2, "cruiser": 4, "battleship": 8}  # a retrofit's price, by hull
RETROFIT_FIELD = 0.2  # a Field Generator's own force field, as a share of the hull (the Aegis Cruiser's)

RETROFITS: dict[str, Retrofit] = {
    r.id: r
    for r in [
        Retrofit(
            "laser_battery", "Laser Battery",
            "The lightest guns come out and a second battery of lasers goes in: twice the lasers.",
            "lasers", {"plasma": 30, "powder": 20},
        ),
        Retrofit(
            "field_generator", "Field Generator",
            "A force field generator of its own, like the Aegis Cruiser's: a field of 20% of the hull, on top of "
            "Force Fields.",
            "fields", {"plasma": 30, "steel": 25},
        ),
    ]
}


def light_guns(design: ShipDesign) -> WeaponMount | None:
    """The gun mount a Laser Battery replaces: the lightest guns aboard."""
    guns = [m for m in design.mounts if m.weapon.kind == "gun"]
    return min(guns, key=lambda m: m.weapon.avg_damage) if guns else None


def retrofit(design: ShipDesign, fitted: Iterable[str]) -> ShipDesign:
    """``design`` with the retrofits ``fitted`` (ids in RETROFITS). Apply it before ``refit``: a Laser
    Battery's lasers then improve with Laser Cannons, and a Field Generator's field adds to Force Fields."""
    fitted = set(fitted)
    if "laser_battery" in fitted:
        light = light_guns(design)
        mounts = tuple(m for m in design.mounts if m is not light)
        lasers = WeaponMount(WEAPONS["laser"], 2 * LASERS_PER_HULL.get(design.hull.id, 1))
        design = replace(design, mounts=mounts + (lasers,))
    if "field_generator" in fitted:
        design = replace(design, field_bonus=design.field_bonus + RETROFIT_FIELD)
    return design
