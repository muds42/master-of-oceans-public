"""Math Boost: previewing actions, boosting hits, and which hits count as big."""

import random

import pytest

from seabattle import campaign as cm
from seabattle.ai import SimpleAI
from seabattle.battle import Battle, GunsFired, RoundStarted, SalvoHit, StackActivated
from seabattle.boost import (
    BOOST, FLOOR, LEVEL_ODDS, MAX_PER_BATTLE, MAX_PER_SUPER_MISSION, PENALTY, SUPER_FLOOR, WARMUP, MathBoost, play,
)
from seabattle.designs import DESTROYER, LIGHT_CRUISER
from seabattle.scenarios import SCENARIOS


def hits_of(events):
    return [e for e in events if isinstance(e, (GunsFired, SalvoHit))]


def test_a_preview_changes_nothing_and_foretells_the_action():
    for seed in range(6):
        battle = SCENARIOS["battle_line"].build(seed)
        battle.start()
        ai = (SimpleAI(), SimpleAI())
        while not battle.over:
            action = ai[battle.active.side].choose_action(battle, battle.active)
            state = (battle.round, battle.active_id, [(s.count, s.top_hp, s.status) for s in battle.stacks.values()],
                     len(battle.events), battle.rng.getstate())
            preview = battle.preview(action)
            assert state == (battle.round, battle.active_id, [(s.count, s.top_hp, s.status) for s in battle.stacks.values()],
                             len(battle.events), battle.rng.getstate())
            assert battle.apply(action) == preview


def test_boosts_scale_one_hit_and_roll_the_same_dice():
    totals = {1 + BOOST: [0, 0], 1 - BOOST: [0, 0]}
    for seed in range(10):
        battle = SCENARIOS["battle_line"].build(seed)
        battle.start()
        ai = (SimpleAI(), SimpleAI())
        while not battle.over:
            action = ai[battle.active.side].choose_action(battle, battle.active)
            hits = [e for e in hits_of(battle.preview(action)) if e.damage]
            if not hits:
                battle.apply(action)
                continue
            scale = 1 + BOOST if seed % 2 else 1 - BOOST
            real = battle.apply(action, {hits[0].key: scale})
            boosted = next(e for e in hits_of(real) if e.key == hits[0].key)
            assert boosted.boost == scale
            assert all(e.boost == 1.0 for e in hits_of(real) if e.key != hits[0].key)
            totals[scale][0] += hits[0].damage
            totals[scale][1] += boosted.damage
    # a boosted volley can sink its target sooner and stop there, so the hull damage moves by a little less than 30%
    assert totals[1 + BOOST][1] / totals[1 + BOOST][0] > 1.12
    assert totals[1 - BOOST][1] / totals[1 - BOOST][0] < 0.8


def build(scenario, seed):
    if scenario.startswith("mission"):
        fleet = {"destroyer": 6, "light_cruiser": 3, "torpedo_boat": 4}
        return cm.Campaign(slot=seed + 1, mission_number=int(scenario[7:]), fleet=fleet).build_battle()  # a map for each slot
    return SCENARIOS[scenario].build(seed)


@pytest.mark.parametrize("scenario", ["skirmish", "battle_line", "mosquito", "random", "mission9", "mission28"])
def test_a_boost_changes_nothing_before_its_hit(scenario):
    """The battle screen plays the preview up to a big hit, freezes it, and only then applies the
    action with the answer's boost: everything before the hit must come out the same."""
    for seed in range(3):
        battle = build(scenario, seed)
        boost = MathBoost.for_battle(battle, rng=random.Random(seed))
        battle.start()
        ai = (SimpleAI(), SimpleAI())
        checked = 0
        while not battle.over:
            action = ai[battle.active.side].choose_action(battle, battle.active)
            preview = battle.preview(action)
            hit = boost.big_hit(battle, preview) if boost.active else None
            if hit is None:
                battle.apply(action)
                continue
            k = next(i for i, e in enumerate(preview) if e is hit.event)
            scale = hit.scale if checked % 2 else hit.miss_scale
            real = battle.apply(action, {hit.key: scale})
            assert real[:k] == preview[:k]
            assert type(real[k]) is type(hit.event) and real[k].key == hit.key and real[k].boost == scale
            checked += 1
        assert checked


def test_boosted_damage_keeps_the_fractions():
    """30% more of a 1-damage hit is nothing on its own; over a volley it adds up."""
    dmg, carry, total = 0, 0.0, 0
    for _ in range(10):
        dmg, carry = Battle._scaled(1, 1.3, carry)
        total += dmg
    assert total == 13
    assert Battle._scaled(10, 0.7, 0.0) == (7, pytest.approx(0.0))
    assert Battle._scaled(0, 1.3, 0.5) == (0, 0.5)


def make_hit(damage, attacker=1, target=4, mount=0, kills=0):
    return GunsFired("", attacker, target, mount, 10, 5, damage, kills, 3, 10)


def small_battle():
    blue = [(DESTROYER, 3), (LIGHT_CRUISER, 1)]
    red = [(DESTROYER, 3), (LIGHT_CRUISER, 1)]
    battle = Battle([blue, red], seed=1)
    battle.start()
    return battle


def test_big_means_big_for_this_battle():
    battle = small_battle()
    boost = MathBoost.for_battle(battle, rng=random.Random(1))
    floor = FLOOR * boost.scale
    turn = [RoundStarted("", 1)]

    def act(stack_id, *hits):
        return boost.big_hit(battle, [StackActivated("", stack_id), *hits])

    assert act(1, make_hit(int(floor) - 1)) is None  # small change never counts
    for k in range(WARMUP - 1):  # the first hits only need the floor
        assert act(2 + k, make_hit(int(floor) + 1)) is not None
    for k in range(6):
        act(10 + k, make_hit(int(floor) + 40))  # a run of big hits sets the bar
    assert act(20, make_hit(int(floor) + 1)) is None  # now "big" means bigger
    hit = act(21, make_hit(int(floor) + 40, attacker=3, target=2, kills=1))
    assert hit is not None and not hit.offense and hit.scale == pytest.approx(1 - BOOST)
    assert "damage, 1 sunk" in hit.story() and hit.headline() == "INCOMING!"
    assert boost.big_hit(battle, turn + [StackActivated("", 21), make_hit(10**6)]) is None  # one boost per ship's turn


def test_at_most_ten_and_off_means_off():
    battle = small_battle()
    boost = MathBoost.for_battle(battle, rng=random.Random(2))
    found = 0
    for k in range(40):
        if boost.big_hit(battle, [StackActivated("", 100 + k), make_hit(10**6)]):
            if k % 2:  # offers count whether or not the player takes them
                boost.pose()
            found += 1
    assert found == boost.offered == MAX_PER_BATTLE and not boost.active and boost.posed == MAX_PER_BATTLE // 2
    other = MathBoost.for_battle(battle)
    other.turn_off()
    assert other.big_hit(battle, [StackActivated("", 1), make_hit(10**6)]) is None


def test_a_super_mission_offers_more_boosts():
    battle = small_battle()
    plain = MathBoost.for_battle(battle, rng=random.Random(3))
    big = MathBoost.for_battle(battle, rng=random.Random(3), super_mission=True)
    assert (plain.limit, big.limit) == (MAX_PER_BATTLE, MAX_PER_SUPER_MISSION) == (10, 25)

    def act(boost, stack_id, size):
        return boost.big_hit(battle, [StackActivated("", stack_id), make_hit(size)])

    between = int(FLOOR * plain.scale) - 1  # under the usual floor, over a super mission's
    assert between >= SUPER_FLOOR * plain.scale
    assert act(plain, 1, between) is None and act(big, 1, between) is not None
    for k, size in enumerate([40, 50, 60, 70, 80, 90, 100]):  # a run of hits sets the bar
        act(plain, 10 + k, size)
        act(big, 10 + k, size)
    assert act(plain, 30, 55) is None and act(big, 30, 55) is not None  # under the middle hit, over the quarter-way one

    before = big.offered
    found = sum(act(big, 100 + k, 10**6) is not None for k in range(40))
    assert found == MAX_PER_SUPER_MISSION - before and big.offered == MAX_PER_SUPER_MISSION and not big.active


def test_problems_come_from_every_level_mostly_the_middle():
    boost = MathBoost.for_battle(small_battle(), rng=random.Random(7))
    n = 4000
    levels = [boost.pose().level for _ in range(n)]
    for level, odds in enumerate(LEVEL_ODDS):
        assert abs(levels.count(level) / n - odds) < 0.025, (level, levels.count(level) / n)
    assert sum(LEVEL_ODDS) == pytest.approx(1) and LEVEL_ODDS == (0.1, 0.2, 0.4, 0.2, 0.1)


def test_problems_and_the_score():
    battle = small_battle()
    boost = MathBoost.for_battle(battle, rng=random.Random(4))
    topics = [boost.pose().topic for _ in range(8)]
    assert all(a != b for a, b in zip(topics, topics[1:]))  # never the same topic twice in a row
    hit = boost.big_hit(battle, [StackActivated("", 1), make_hit(10**4)])
    assert hit.offense
    assert boost.boosts(hit, True) == {hit.key: pytest.approx(1 + BOOST)}
    assert boost.boosts(hit, False) == {hit.key: pytest.approx(1 - PENALTY)}  # a wrong answer costs a little
    assert (boost.answered, boost.right) == (2, 1)
    boost.dealt, boost.saved, boost.cost = 12, 7, 3
    assert boost.summary() == "Math Boost: 1 of 2 right, +12 damage dealt, 7 damage stopped, 3 lost to wrong answers."
    defense = boost.big_hit(battle, [StackActivated("", 2), make_hit(10**4, attacker=3, target=2)])
    assert not defense.offense and defense.miss_scale == pytest.approx(1 + PENALTY)
    assert defense.outcome(False) == f"Not this time: you take {PENALTY:.0%} more damage."


def test_wrong_answers_cost_damage():
    """Every answer lands: right ones help, wrong ones hurt, and the score keeps both."""
    battle = SCENARIOS["battle_line"].build(2)
    boost = MathBoost.for_battle(battle, rng=random.Random(2))
    play(battle, (SimpleAI(), SimpleAI()), boost, 0.0, random.Random(2))  # every answer wrong
    assert boost.answered and boost.right == 0 and boost.dealt == boost.saved == 0 and boost.cost > 0
    assert all(e.boost in (pytest.approx(1 - PENALTY), pytest.approx(1 + PENALTY))
               for e in hits_of(battle.events) if e.boost != 1.0)


@pytest.mark.parametrize("seed", range(4))
def test_a_whole_battle_with_math_boost(seed):
    battle = SCENARIOS["battle_line"].build(seed)
    boost = MathBoost.for_battle(battle, rng=random.Random(seed))
    play(battle, (SimpleAI(), SimpleAI()), boost, 0.8, random.Random(seed))
    assert battle.over and 1 <= boost.posed <= MAX_PER_BATTLE and boost.answered == boost.posed
    boosted = [e.boost for e in hits_of(battle.events) if e.boost != 1.0]  # every answer changes its hit
    assert len(boosted) == boost.answered
    assert sum(b in (pytest.approx(1 + BOOST), pytest.approx(1 - BOOST)) for b in boosted) == boost.right
    assert boost.summary().startswith(f"Math Boost: {boost.right} of {boost.posed} right")


def test_the_summary_tells_offers_from_answers():
    boost = MathBoost.for_battle(small_battle())
    assert boost.summary() == "Math Boost: no big hits came up."
    boost.offered = 3
    assert boost.summary() == "Math Boost: no boosts taken."
    boost.turn_off()
    assert boost.summary() == "Math Boost: no boosts taken."
    assert MathBoost(on=False).summary() == ""


def test_the_campaign_keeps_the_setting():
    c = cm.Campaign(slot=1)
    assert not c.boost  # off to start with
    c.boost = True
    c.record_boost(True)
    c.record_boost(False)
    loaded = cm.Campaign.from_dict(c.to_dict())
    assert loaded.boost and "boost_level" not in c.to_dict()
    assert loaded.stats["boost"] == {"attempted": 2, "solved": 1}
    assert not cm.Campaign.from_dict({"boost": "yes"}).boost
    assert cm.Campaign.from_dict({"boost": True, "boost_level": 3}).boost  # a save from when it had levels
