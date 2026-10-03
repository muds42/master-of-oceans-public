import pytest

from seabattle.ai import SimpleAI
from seabattle.battle import Battle, Fire, Retreat
from seabattle.designs import BATTLESHIP, PICKET
from seabattle.headless import run_battle
from seabattle.scenarios import SCENARIOS


@pytest.mark.parametrize("scenario", sorted(SCENARIOS))
def test_ai_plays_every_scenario_to_the_end(scenario):
    for seed in range(3):
        battle = run_battle(SCENARIOS[scenario].build(seed))  # raises on any illegal action
        assert battle.over


def test_symmetric_battles_are_decided_and_roughly_fair():
    wins = [0, 0]
    for seed in range(30):
        battle = run_battle(SCENARIOS["skirmish"].build(seed))
        assert battle.winner is not None
        wins[battle.winner] += 1
    assert min(wins) >= 8, wins


def _focus_setup():
    battle = Battle([[(PICKET, 3)], [(PICKET, 3), (PICKET, 3)]], seed=1)
    battle.start()
    me = battle.stacks[1]
    healthy, damaged = battle.stacks[2], battle.stacks[3]
    battle.active_id = me.id
    healthy.pos = (me.pos[0] + 1, me.pos[1] - 1)
    damaged.pos = (me.pos[0] + 1, me.pos[1] + 1)
    damaged.count, damaged.top_hp = 1, 5
    return battle, me, damaged


def test_ai_focuses_fire_on_the_damaged_stack():
    battle, me, damaged = _focus_setup()
    fire = SimpleAI().best_fire(battle, me)
    assert isinstance(fire, Fire) and fire.target == damaged.id


def test_ai_uses_every_weapon_it_can_in_one_activation():
    battle, me, damaged = _focus_setup()
    ai = SimpleAI()
    fired = []
    while battle.active is me:
        action = ai.choose_action(battle, me)
        if isinstance(action, Fire):
            fired.append(action.mount)
        battle.apply(action)
    assert sorted(fired) == [0, 1]


def test_ai_retreats_when_hopeless():
    battle = Battle([[(PICKET, 1)], [(BATTLESHIP, 3)]], seed=1)
    battle.start()
    battle.round = 3
    picket = battle.stacks[1]
    battle.active_id = picket.id
    assert isinstance(SimpleAI().choose_action(battle, picket), Retreat)


def test_ai_that_may_not_retreat_fights_on():
    battle = Battle([[(PICKET, 1)], [(BATTLESHIP, 3)]], seed=1)
    battle.start()
    battle.round = 3
    picket = battle.stacks[1]
    battle.active_id = picket.id
    assert not isinstance(SimpleAI(retreat_ratio=0).choose_action(battle, picket), Retreat)
