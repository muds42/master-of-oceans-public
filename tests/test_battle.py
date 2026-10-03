import pytest

from seabattle.battle import (
    Battle,
    BattleOver,
    EndTurn,
    Fire,
    GunsFired,
    IllegalAction,
    Move,
    Repaired,
    Retreat,
    SalvoHit,
    SalvoLaunched,
    SalvoLost,
    StackRetreated,
    Withdraw,
    distance,
    hit_chance,
)
from seabattle.design import make_design
from seabattle.designs import ALL_DESIGNS, BATTLESHIP, DESTROYER, MISSILE_CRUISER, PICKET, TORPEDO_BOAT

LIGHT_CRUISER_NO_BELT = make_design("Unbelted Cruiser", "cruiser", [("gun6", 2)], plating="plate_steel")


class AlwaysHit:
    """Stand-in RNG: every shot hits for maximum damage."""

    def random(self):
        return 0.0

    def randint(self, lo, hi):
        return hi


class AlwaysMiss(AlwaysHit):
    def random(self):
        return 0.999


def duel(blue, red, *, islands=(), seed=1, **kw):
    battle = Battle([blue, red], islands=islands, seed=seed, **kw)
    battle.start()
    return battle


def place(battle, stack_id, pos):
    battle.stacks[stack_id].pos = pos


def test_preset_designs_fit_their_hulls():
    for design in ALL_DESIGNS.values():
        assert design.validate() == [], design.name


def test_overfull_design_is_rejected():
    design = make_design("Overloaded", "corvette", [("gun12", 1)])
    assert any("space" in p for p in design.validate())


def test_hit_chance_is_clamped():
    assert hit_chance(0, 0) == 0.5
    assert hit_chance(2, 0) == pytest.approx(0.7)
    assert hit_chance(20, 0) == 0.95
    assert hit_chance(0, 20) == 0.05


def test_deployment_and_initiative():
    battle = duel([(BATTLESHIP, 1), (PICKET, 3)], [(DESTROYER, 2)])
    assert [s.pos[0] for s in battle.stacks.values()] == [1, 1, battle.width - 2]
    # Fastest stacks act first: pickets and destroyers (speed 4) before the battleship (speed 2).
    order_speeds = [battle.stacks[i].design.speed for i in battle.order]
    assert order_speeds == sorted(order_speeds, reverse=True)
    assert battle.active.design.speed == 4


def test_islands_on_deployment_tiles_are_cleared():
    battle = Battle([[(PICKET, 1)], [(PICKET, 1)]], islands={(1, 4), (5, 5)})
    assert (1, 4) not in battle.islands
    assert (5, 5) in battle.islands


def test_movement_respects_speed_islands_and_ships():
    battle = duel([(PICKET, 1)], [(PICKET, 1)], islands={(2, 4)})
    stack = battle.active
    reach = battle.reachable(stack)
    assert (2, 4) not in reach
    assert all(distance(stack.pos, p) <= stack.design.speed for p in reach)
    other = next(s for s in battle.stacks.values() if s is not stack)
    assert other.pos not in reach

    dest = (stack.pos[0] + 2, stack.pos[1] + 1)
    battle.apply(Move(dest))
    assert stack.pos == dest
    assert stack.moves_left == stack.design.speed - 2
    with pytest.raises(IllegalAction):
        battle.apply(Move((dest[0] + 5, dest[1])))


def test_guns_need_range_and_fire_once_per_turn():
    battle = duel([(PICKET, 1)], [(PICKET, 1)])
    shooter = battle.active
    target = next(s for s in battle.stacks.values() if s is not shooter)
    with pytest.raises(IllegalAction):
        battle.apply(Fire(0, target.id))  # 10 tiles away
    place(battle, target.id, (shooter.pos[0] + 2, shooter.pos[1]))
    battle.apply(Fire(0, target.id))
    with pytest.raises(IllegalAction):
        battle.apply(Fire(0, target.id))
    with pytest.raises(IllegalAction):
        battle.apply(Fire(1, target.id))  # machine guns only reach 1 tile


def test_armor_belt_reduces_each_gun_hit():
    battle = duel([(PICKET, 1)], [(DESTROYER, 1)])
    battle.rng = AlwaysHit()
    picket = next(s for s in battle.stacks.values() if s.design is PICKET)
    destroyer = next(s for s in battle.stacks.values() if s.design is DESTROYER)
    battle.active_id = picket.id
    place(battle, destroyer.id, (picket.pos[0] + 1, picket.pos[1]))
    events = battle.apply(Fire(0, destroyer.id))  # 2x 4" gun, max 6 damage, belt 1
    gun = next(e for e in events if isinstance(e, GunsFired))
    assert gun.hits == 2 and gun.damage == 2 * (6 - DESTROYER.belt)


def test_overkill_on_one_hit_is_wasted():
    battle = duel([(PICKET, 5)], [(PICKET, 1)])
    stack = battle.stacks[1]
    applied, killed = battle._damage(stack, 100)
    assert (applied, killed) == (PICKET.max_hp, 1)
    assert stack.count == 4 and stack.top_hp == PICKET.max_hp


def test_torpedoes_travel_ignore_belt_and_use_ammo():
    battle = duel([(TORPEDO_BOAT, 1)], [(BATTLESHIP, 1)])
    battle.rng = AlwaysHit()
    boat = battle.stacks[1]
    battleship = battle.stacks[2]
    battle.active_id = boat.id
    place(battle, battleship.id, (boat.pos[0] + 6, boat.pos[1]))  # beyond one turn of travel
    events = battle.apply(Fire(0, battleship.id))
    assert any(isinstance(e, SalvoLaunched) for e in events)
    assert not any(isinstance(e, SalvoHit) for e in events)
    assert boat.ammo[0] == TORPEDO_BOAT.mounts[0].weapon.ammo - 1
    (salvo,) = battle.salvos.values()
    assert distance(salvo.pos, battleship.pos) == 2

    # The salvo finishes its run at the start of the next round.
    events = []
    while battle.round == 1:
        events += battle.apply(EndTurn())
    hit = next(e for e in events if isinstance(e, SalvoHit))
    assert hit.damage == 2 * 16  # full damage: the belt does not apply
    assert not battle.salvos


def test_torpedoes_lose_a_retreated_target():
    battle = duel([(TORPEDO_BOAT, 1)], [(DESTROYER, 1), (DESTROYER, 1)])
    boat = battle.stacks[1]
    target = battle.stacks[2]
    battle.active_id = boat.id
    place(battle, target.id, (boat.pos[0] + 6, boat.pos[1]))
    battle.apply(Fire(0, target.id))
    target.status = "retreated"
    events = []
    while battle.round == 1:
        events += battle.apply(EndTurn())
    assert any(isinstance(e, SalvoLost) for e in events)


def test_battle_ends_when_a_side_is_gone():
    battle = duel([(PICKET, 1)], [(PICKET, 1)])
    battle.rng = AlwaysHit()
    shooter = battle.active
    target = next(s for s in battle.stacks.values() if s is not shooter)
    place(battle, target.id, (shooter.pos[0] + 1, shooter.pos[1]))
    events = battle.apply(Fire(0, target.id))
    assert battle.over and battle.winner == shooter.side
    assert isinstance(events[-1], BattleOver)
    with pytest.raises(IllegalAction):
        battle.apply(EndTurn())


def test_retreating_every_stack_concedes():
    battle = duel([(PICKET, 1)], [(PICKET, 1)])
    loser = battle.active.side
    battle.apply(Retreat())
    assert battle.over and battle.winner == 1 - loser


def test_round_limit_is_a_draw():
    battle = duel([(PICKET, 1)], [(PICKET, 1)], max_rounds=3)
    battle.rng.random = AlwaysMiss().random
    for _ in range(50):
        if battle.over:
            break
        battle.apply(EndTurn())
    assert battle.over and battle.winner is None and battle.round == 3


def test_same_seed_same_battle():
    from seabattle.headless import run_battle
    from seabattle.scenarios import SCENARIOS

    logs = []
    for _ in range(2):
        log = []
        run_battle(SCENARIOS["skirmish"].build(42), on_event=lambda e, log=log: log.append(e.text))
        logs.append(log)
    assert logs[0] == logs[1]


# --------------------------------------------------------------------------- campaign additions


def test_interdiction_shoots_down_projectiles():
    from seabattle.economy import refit

    target_design = refit(BATTLESHIP, {"interdiction": 4})
    battle = duel([(TORPEDO_BOAT, 1)], [(target_design, 1)])
    battle.rng = AlwaysHit()  # random() == 0.0, so every interception roll succeeds
    boat, target = battle.stacks[1], battle.stacks[2]
    battle.active_id = boat.id
    place(battle, target.id, (boat.pos[0] + 2, boat.pos[1]))
    events = battle.apply(Fire(0, target.id))
    hit = next(e for e in events if isinstance(e, SalvoHit))
    assert hit.intercepted == hit.count and hit.hits == 0 and hit.damage == 0


def test_missiles_are_reduced_by_armor_belts_but_torpedoes_are_not():
    battle = duel([(MISSILE_CRUISER, 1)], [(BATTLESHIP, 1)])
    battle.rng = AlwaysHit()
    cruiser, target = battle.stacks[1], battle.stacks[2]
    battle.active_id = cruiser.id
    place(battle, target.id, (cruiser.pos[0] + 5, cruiser.pos[1]))
    events = battle.apply(Fire(0, target.id))
    hit = next(e for e in events if isinstance(e, SalvoHit))
    missile = MISSILE_CRUISER.mounts[0]
    assert hit.damage == missile.count * (missile.weapon.damage[1] - BATTLESHIP.belt)


def test_damage_control_repairs_at_the_start_of_each_turn():
    from seabattle.economy import refit

    tough = refit(DESTROYER, {"damage_control": 2})
    battle = Battle([[(tough, 1)], [(PICKET, 1)]], seed=3)
    stack = battle.stacks[1]
    stack.top_hp = 5
    events = battle.start()
    while battle.active is not stack:
        events = battle.apply(EndTurn())
    repaired = next(e for e in events if isinstance(e, Repaired))
    assert repaired.amount == tough.repair_per_round and stack.top_hp == 5 + tough.repair_per_round


def test_withdraw_pulls_out_the_whole_side():
    battle = duel([(PICKET, 1), (DESTROYER, 1)], [(PICKET, 1)])
    side = battle.active.side
    events = battle.apply(Withdraw())
    assert battle.over and battle.winner == 1 - side
    assert all(s.status == "retreated" for s in battle.stacks.values() if s.side == side)
    assert sum(isinstance(e, StackRetreated) for e in events) == len([s for s in battle.stacks.values() if s.side == side])


# --------------------------------------------------------------------------- Act II: future tech


def _fire_at(battle, attacker, target, mount=0, gap=2):
    battle.active_id = attacker.id
    place(battle, target.id, (attacker.pos[0] + gap, attacker.pos[1]))
    return battle.apply(Fire(mount, target.id))


def test_lasers_burn_through_armor_belts():
    from seabattle.economy import refit

    lasers = refit(make_design("Laser Boat", "destroyer", [("gun4", 2)]), {"lasers": 1})
    assert lasers.mounts[-1].weapon.kind == "laser" and lasers.mounts[-1].count == 2
    battle = duel([(lasers, 1)], [(BATTLESHIP, 1)])
    battle.rng = AlwaysHit()
    boat, target = battle.stacks[1], battle.stacks[2]
    shot = next(e for e in _fire_at(battle, boat, target, mount=1) if isinstance(e, GunsFired))
    assert BATTLESHIP.belt > 0 and shot.kind == "laser"
    assert shot.damage == 2 * 6 and shot.blocked == 0


def test_force_fields_soak_up_damage_first_and_refill_every_turn():
    from seabattle.battle import FieldRestored
    from seabattle.economy import refit

    shielded = refit(LIGHT_CRUISER_NO_BELT, {"fields": 2})
    assert shielded.max_field == 18  # 20% of 90
    gunboat = make_design("Gunboat", "cruiser", [("gun6", 5)])
    battle = duel([(gunboat, 1)], [(shielded, 2)])
    battle.rng = AlwaysHit()
    boat, target = battle.stacks[1], battle.stacks[2]
    shot = next(e for e in _fire_at(battle, boat, target) if isinstance(e, GunsFired))
    assert shot.absorbed == 18 and shot.damage == 5 * 10 - 18 and target.top_field == 0
    assert target.top_hp == 90 - 32
    events = battle.apply(EndTurn())
    while battle.active is not target:
        events += battle.apply(EndTurn())
    restored = next(e for e in events if isinstance(e, FieldRestored))
    assert restored.amount == 18 and target.top_field == 18


def test_torpedoes_run_under_force_fields():
    from seabattle.economy import refit

    shielded = refit(BATTLESHIP, {"fields": 4})
    battle = duel([(TORPEDO_BOAT, 1)], [(shielded, 1)])
    battle.rng = AlwaysHit()
    boat, target = battle.stacks[1], battle.stacks[2]
    hit = next(e for e in _fire_at(battle, boat, target) if isinstance(e, SalvoHit))
    assert hit.absorbed == 0 and hit.damage == 2 * 16 and target.top_field == shielded.max_field


def test_ion_beams_drain_force_fields_faster():
    from seabattle.economy import refit

    shielded = refit(BATTLESHIP, {"fields": 1})  # a field of 40
    for ion, absorbed in ((0, 40), (2, 14)):  # x3: 14 damage takes down 42 field points
        lasers = refit(make_design("Laser Boat", "cruiser", [("gun4", 1)]), {"lasers": 1, "ion": ion})
        battle = duel([(lasers, 2)], [(shielded, 1)])
        battle.rng = AlwaysHit()
        boat, target = battle.stacks[1], battle.stacks[2]
        shot = next(e for e in _fire_at(battle, boat, target, mount=1) if isinstance(e, GunsFired))
        assert shot.absorbed == absorbed and shot.damage == 8 * 6 - absorbed, ion
        assert target.top_field == 0


def test_graviton_beams_carry_overkill_into_the_next_ship():
    from dataclasses import replace

    from seabattle.components import WEAPONS
    from seabattle.design import WeaponMount
    from seabattle.economy import refit

    lasers = refit(make_design("Laser Boat", "corvette", [("mg", 1)]), {"lasers": 1, "graviton": 1})
    assert lasers.mounts[-1].weapon.carry == 0.5
    base = make_design("Big Gun", "cruiser", [("gun16", 1)])
    # One 28-damage hit on torpedo boats of 6 hull: 22 left after the first sinks.
    for carry, sunk, damage, carried in ((0.0, 1, 6, 0), (0.5, 2, 14, 11 + 2), (1.0, 4, 28, 22 + 16 + 10 + 4)):
        design = replace(base, mounts=(WeaponMount(replace(WEAPONS["gun16"], carry=carry), 1),))
        battle = duel([(design, 1)], [(TORPEDO_BOAT, 5)])
        battle.rng = AlwaysHit()
        boat, target = battle.stacks[1], battle.stacks[2]
        shot = next(e for e in _fire_at(battle, boat, target) if isinstance(e, GunsFired))
        assert (shot.kills, shot.damage, shot.carried) == (sunk, damage, carried), carry
        assert shot.damage + shot.wasted == 28


def test_railguns_halve_armor_belts():
    from seabattle.economy import refit

    rails = refit(make_design("Rail Boat", "cruiser", [("gun6", 1)]), {"railguns": 1})
    battle = duel([(rails, 1)], [(BATTLESHIP, 1)])  # belt 3: railguns leave 1 of it
    battle.rng = AlwaysHit()
    boat, target = battle.stacks[1], battle.stacks[2]
    shot = next(e for e in _fire_at(battle, boat, target) if isinstance(e, GunsFired))
    assert shot.blocked == 1 and shot.damage == 10 - 1


def test_plasma_torpedoes_fade_with_distance():
    from seabattle.economy import refit

    plasma = refit(TORPEDO_BOAT, {"plasma_torps": 1})
    assert plasma.mounts[0].weapon.name == "Plasma Torpedo" and plasma.mounts[0].weapon.fade == 1
    damage = {}
    for gap in (1, 4):
        battle = duel([(plasma, 1)], [(BATTLESHIP, 1)])
        battle.rng = AlwaysHit()
        boat, target = battle.stacks[1], battle.stacks[2]
        hit = next(e for e in _fire_at(battle, boat, target, gap=gap) if isinstance(e, SalvoHit))
        damage[gap] = hit.damage
    assert damage == {1: 2 * (16 + 6 - 1), 4: 2 * (16 + 6 - 4)}


def test_holographic_decoys_draw_fire_however_accurate():
    from seabattle.economy import refit

    decoyed = refit(BATTLESHIP, {"decoys": 3})
    battle = duel([(DESTROYER, 1)], [(decoyed, 1)])
    battle.rng = AlwaysHit()  # random() == 0.0: every decoy roll succeeds
    boat, target = battle.stacks[1], battle.stacks[2]
    shot = next(e for e in _fire_at(battle, boat, target) if isinstance(e, GunsFired))
    assert shot.decoyed == shot.shots and shot.hits == 0 and shot.fired == 0


def test_point_defense_guards_the_stack_next_door():
    from seabattle.designs import AEGIS_CRUISER

    battle = duel([(TORPEDO_BOAT, 1)], [(BATTLESHIP, 1), (AEGIS_CRUISER, 1)])
    boat, target, aegis = battle.stacks[1], battle.stacks[2], battle.stacks[3]
    place(battle, target.id, (5, 4))
    place(battle, aegis.id, (9, 9))
    assert battle.intercept_chance(target) == 0
    place(battle, aegis.id, (6, 5))
    assert AEGIS_CRUISER.cover_chance > 0
    assert battle.intercept_chance(target) == pytest.approx(AEGIS_CRUISER.intercept_chance / 2)
    battle.rng = AlwaysHit()
    battle.active_id = boat.id
    place(battle, boat.id, (3, 4))
    hit = next(e for e in battle.apply(Fire(0, target.id)) if isinstance(e, SalvoHit))
    assert hit.intercepted == hit.count


def test_nanite_repair_adds_to_damage_control():
    from seabattle.design import NANITE_PER_LEVEL, REPAIR_PER_LEVEL
    from seabattle.economy import refit

    d = refit(BATTLESHIP, {"damage_control": 3, "nanite": 2})
    assert d.repair_per_round == round(d.max_hp * (3 * REPAIR_PER_LEVEL + 2 * NANITE_PER_LEVEL))
