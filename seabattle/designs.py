"""Preset ship designs used by the scenarios until a ship designer exists."""

from __future__ import annotations

from dataclasses import replace

from .design import ShipDesign, make_design

PICKET = make_design(
    "Picket Boat", "corvette", [("gun4", 2), ("mg", 2)],
    fire_control="fc_rangefinder", plating="plate_steel",
    countermeasures="cm_smoke", propulsion="prop_turbine",
)

TORPEDO_BOAT = make_design(
    "Torpedo Boat", "corvette", [("torpedo", 2), ("mg", 1)],
    fire_control="fc_rangefinder", countermeasures="cm_smoke", propulsion="prop_turbine",
)

DESTROYER = make_design(
    "Destroyer", "destroyer", [("gun4", 4), ("torpedo", 2), ("mg", 2)],
    fire_control="fc_director", belt="belt_light", plating="plate_steel",
    countermeasures="cm_smoke", propulsion="prop_geared",
)

LIGHT_CRUISER = make_design(
    "Light Cruiser", "cruiser", [("gun6", 6), ("gun4", 4), ("torpedo", 2)],
    fire_control="fc_director", belt="belt_medium", plating="plate_steel",
    countermeasures="cm_smoke", propulsion="prop_turbine",
)

BATTLESHIP = make_design(
    "Battleship", "battleship", [("gun12", 6), ("gun6", 8), ("mg", 4)],
    fire_control="fc_radar", belt="belt_heavy", plating="plate_krupp",
    countermeasures="cm_smoke",
)

MISSILE_CRUISER = make_design(
    "Missile Cruiser", "cruiser", [("missile", 3), ("gun6", 4), ("mg", 4)],
    fire_control="fc_radar", belt="belt_medium", plating="plate_steel",
    countermeasures="cm_decoys", propulsion="prop_geared",
)

# ---- Act III: classes unlocked with Plasma. Every one leaves a mount free for lasers.

HYDROFOIL_RAIDER = make_design(
    "Hydrofoil Raider", "corvette", [("torpedo", 2), ("mg", 1)],
    fire_control="fc_rangefinder", countermeasures="cm_smoke", propulsion="prop_hydrofoil",
)

AEGIS_CRUISER = replace(
    make_design(
        "Aegis Cruiser", "cruiser", [("gun6", 4), ("mg", 6)],
        fire_control="fc_director", belt="belt_medium", plating="plate_steel",
        countermeasures="cm_decoys", propulsion="prop_turbine",
    ),
    field_bonus=0.2, point_defense=2,  # its own force field, and point defense that guards its neighbours
)

STORMBREAKER = replace(
    make_design(
        "Stormbreaker", "dreadnought", [("gun16", 6), ("gun6", 8), ("mg", 6)],
        fire_control="fc_radar", belt="belt_heavy", plating="plate_krupp", countermeasures="cm_smoke",
    ),
    field_bonus=0.2,
)

# The quick-battle designs: Act I's classes.
ALL_DESIGNS: dict[str, ShipDesign] = {
    d.name: d for d in [PICKET, TORPEDO_BOAT, DESTROYER, LIGHT_CRUISER, BATTLESHIP, MISSILE_CRUISER]
}

# ---- Red's super ships: late-campaign enemies the player can never build ----

DREADNOUGHT = make_design(
    "Dreadnought", "dreadnought", [("gun16", 8), ("gun6", 12), ("mg", 8)],
    fire_control="fc_radar", belt="belt_heavy", plating="plate_krupp", countermeasures="cm_smoke",
)

LEVIATHAN = make_design(
    "Leviathan", "dreadnought", [("missile", 6), ("gun12", 6), ("gun6", 6), ("mg", 6)],
    fire_control="fc_radar", belt="belt_heavy", plating="plate_krupp",
    countermeasures="cm_decoys", propulsion="prop_geared",
)

KRAKEN = make_design(
    "Kraken", "fortress", [("gun16", 12), ("missile", 8), ("gun6", 16), ("mg", 12)],
    fire_control="fc_radar", belt="belt_heavy", plating="plate_krupp", countermeasures="cm_decoys",
)

# Act III: Red's future-tech super ships. Each leaves a mount free for Red's lasers, or carries its own.

TEMPEST = make_design(
    "Tempest", "dreadnought", [("laser", 16), ("gun16", 6), ("gun6", 8)],
    fire_control="fc_radar", belt="belt_heavy", plating="plate_krupp", countermeasures="cm_decoys",
)

LEVIATHAN_MK2 = replace(
    make_design(
        "Leviathan Mk II", "dreadnought", [("missile", 8), ("gun12", 8), ("gun6", 8)],
        fire_control="fc_radar", belt="belt_heavy", plating="plate_krupp",
        countermeasures="cm_decoys", propulsion="prop_geared",
    ),
    field_bonus=0.1,
)

MAELSTROM = replace(
    make_design(
        "Maelstrom", "fortress", [("gun16", 12), ("missile", 8), ("gun6", 16)],
        fire_control="fc_radar", belt="belt_heavy", plating="plate_krupp", countermeasures="cm_decoys",
    ),
    field_bonus=0.1,
)

RED_SHIPS: dict[str, ShipDesign] = {
    "dreadnought": DREADNOUGHT, "leviathan": LEVIATHAN, "kraken": KRAKEN,
    "tempest": TEMPEST, "leviathan_mk2": LEVIATHAN_MK2, "maelstrom": MAELSTROM,
}
