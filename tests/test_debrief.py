"""The after-action debrief: its numbers add up, and its lessons fit what happened."""

import math

import pytest

from seabattle import campaign as cm
from seabattle.battle import Battle, EndTurn, Fire, GunsFired, SalvoHit
from seabattle.debrief import KINDS, Tally, debrief
from seabattle.designs import BATTLESHIP, DESTROYER, PICKET, TORPEDO_BOAT
from seabattle.headless import run_battle
from seabattle.scenarios import SCENARIOS


def start_hp(battle):
    return {s.id: s.start_count * s.design.max_hp for s in battle.stacks.values()}


@pytest.mark.parametrize("scenario", sorted(SCENARIOS))
@pytest.mark.parametrize("seed", [1, 2, 3])
def test_damage_adds_up(scenario, seed):
    """What one side dealt is exactly what the other lost, plus what it repaired."""
    battle = SCENARIOS[scenario].build(seed)
    before = start_hp(battle)
    run_battle(battle)
    d = debrief(battle)
    for side in (0, 1):
        lost = sum(before[s.id] - s.total_hp for s in battle.stacks.values() if s.side == side)
        assert lost + d.repaired[side] == sum(d.of(1 - side, k).damage for k in KINDS)
    guns = [e for e in battle.events if isinstance(e, GunsFired) and battle.stacks[e.attacker_id].side == 0]
    t = d.of(0, "gun")
    assert t.hits == sum(e.hits for e in guns) and t.rolled == sum(e.fired for e in guns)
    assert math.isclose(t.expected, sum(e.fired * e.chance for e in guns))
    assert d.lessons and all(line.endswith((".", "!")) for line in d.lessons)


def test_the_usual_range_is_two_standard_deviations():
    t = Tally()
    t.roll(100, 0.5)  # mean 50, standard deviation 5
    assert t.expected == 50 and t.usual == (40, 60)
    t = Tally()
    t.roll(10, 0.95)
    assert t.usual[1] >= 10 and t.usual[0] <= 9


def test_belts_soaking_up_small_guns_is_a_lesson():
    """Machine guns and 4-inch guns against a battleship's heavy belt mostly bounce off."""
    battle = SCENARIOS["mosquito"].build(3)
    run_battle(battle)
    d = debrief(battle)
    assert d.of(0, "gun").blocked > 0
    assert any("armor belts stopped" in lesson and "Torpedoes strike below the belt" in lesson for lesson in d.lessons)


def test_overkill_is_a_lesson():
    """Battleship broadsides against a swarm of picket boats waste much of each hit."""
    battle = Battle([[(BATTLESHIP, 2)], [(PICKET, 20)]], seed=4)
    battle.start()
    ship, boats = battle.stacks[1], battle.stacks[2]
    boats.pos = (ship.pos[0] + 3, ship.pos[1])
    battle.active_id = ship.id
    battle.apply(Fire(0, boats.id))  # 12 twelve-inch shells at 9-hp boats
    d = debrief(battle)
    guns = d.of(0, "gun")
    assert guns.kills and guns.wasted >= 0.3 * (guns.wasted + guns.damage)
    assert any("wasted on ships that were already sinking" in lesson for lesson in d.lessons)


def test_torpedoes_that_run_dry_are_a_lesson():
    battle = Battle([[(TORPEDO_BOAT, 8)], [(DESTROYER, 1)]], seed=2)
    battle.start()
    boats, target = battle.stacks[1], battle.stacks[2]
    target.pos = (boats.pos[0] + 6, boats.pos[1])
    battle.active_id = boats.id
    battle.apply(Fire(0, target.id))  # 16 torpedoes at the edge of their range...
    target.pos = (target.pos[0] + 5, target.pos[1])  # ...and the target steams away
    while battle.salvos:
        battle.apply(EndTurn())
    d = debrief(battle)
    assert d.of(0, "torpedo").lost.get("range") == 16 and not any(isinstance(e, SalvoHit) for e in battle.events)
    lesson = next(lesson for lesson in d.lessons if "ran out of range" in lesson)
    assert lesson.startswith("16 of your torpedoes ran out") and "missiles" not in lesson
    assert "Longer-Range Torpedoes" not in lesson  # a quick battle has no upgrades to buy
    assert "Longer-Range Torpedoes" in " ".join(debrief(battle, campaign=True).lessons)


def test_a_campaign_battle_saves_its_lessons_for_the_next_briefing(tmp_path, monkeypatch):
    monkeypatch.setenv("SEABATTLE_SAVE_DIR", str(tmp_path))
    c = cm.Campaign(slot=1)
    c.lessons = ["Red's guns did 90 of the 100 damage your fleet took."]
    cm.save(c)
    assert cm.load(1).lessons == c.lessons


# --------------------------------------------------------------------------- Act II: future tech

FUTURE = {"lasers": 3, "ion": 1, "graviton": 2, "railguns": 1, "plasma_torps": 2, "fields": 2, "point_defense": 2,
          "decoys": 1, "nanite": 1, "damage_control": 3, "warheads": 3}


@pytest.mark.parametrize("seed", [1, 2, 3, 4])
def test_damage_adds_up_with_every_future_tech(seed):
    from seabattle.designs import AEGIS_CRUISER, HYDROFOIL_RAIDER, LIGHT_CRUISER
    from seabattle.economy import refit

    blue = [(refit(d, FUTURE), n) for d, n in [(DESTROYER, 4), (AEGIS_CRUISER, 2), (HYDROFOIL_RAIDER, 6)]]
    red = [(refit(d, FUTURE), n) for d, n in [(LIGHT_CRUISER, 3), (TORPEDO_BOAT, 10), (PICKET, 8)]]
    battle = Battle([blue, red], seed=seed)
    before = start_hp(battle)
    run_battle(battle)
    d = debrief(battle)
    for side in (0, 1):
        lost = sum(before[s.id] - s.total_hp for s in battle.stacks.values() if s.side == side)
        assert lost + d.repaired[side] == sum(d.of(1 - side, k).damage for k in KINDS)
    assert d.of(0, "laser").shots + d.of(1, "laser").shots
    assert any(line.startswith("Lasers:") for line, _ in d.odds())
    assert sum(d.of(s, k).absorbed for s in (0, 1) for k in KINDS) > 0


def test_force_fields_soaking_up_damage_is_a_lesson():
    from seabattle.economy import refit

    shielded = refit(BATTLESHIP, {"fields": 4})
    battle = Battle([[(DESTROYER, 12)], [(shielded, 1)]], seed=5)
    battle.start()
    boats, target = battle.stacks[1], battle.stacks[2]
    boats.pos = (target.pos[0] - 2, target.pos[1])
    battle.active_id = boats.id
    battle.apply(Fire(0, target.id))
    d = debrief(battle, campaign=True)
    assert d.of(0, "gun").absorbed > 0
    lesson = next(line for line in d.lessons if "force fields soaked up" in line)
    assert "Ion Beams" in lesson and "Ion Beams" not in " ".join(debrief(battle).lessons)


def test_shots_at_holograms_are_a_lesson():
    from seabattle.economy import refit

    ghost = refit(BATTLESHIP, {"decoys": 3})
    battle = Battle([[(DESTROYER, 6)], [(ghost, 1)]], seed=6)
    battle.start()
    boats, target = battle.stacks[1], battle.stacks[2]
    boats.pos = (target.pos[0] - 2, target.pos[1])
    battle.active_id = boats.id
    battle.apply(Fire(0, target.id))
    d = debrief(battle)
    assert d.of(0, "gun").decoyed >= 6
    assert any("holograms" in line for line in d.lessons)
