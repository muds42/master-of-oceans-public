import collections
import json
import math
import random
from collections import deque
from pathlib import Path

import pytest

from seabattle import campaign as cm
from seabattle.battle import Withdraw
from seabattle.designs import BATTLESHIP, DESTROYER, PICKET, RED_SHIPS
from seabattle.economy import PLASMA_MISSION, PLASMA_SHIPS_MISSION, RETROFITS, SHIP_CLASSES, TRACKS, light_guns, refit, retrofit
from seabattle.headless import run_battle
from seabattle.problems import LEVELS, TIER_PAY, TOPICS, base_pay, choose, level_pay, penalty, reward, streak_bonus


@pytest.fixture(autouse=True)
def save_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("SEABATTLE_SAVE_DIR", str(tmp_path))
    return tmp_path


def rich(**overrides) -> cm.Campaign:
    c = cm.Campaign(slot=1)
    c.currency = {"steel": 5000, "powder": 5000, "fuel": 5000, "blueprints": 5000}
    for k, v in overrides.items():
        setattr(c, k, v)
    return c


def test_new_campaign_starts_small():
    c = cm.Campaign(slot=2)
    assert c.fleet == cm.STARTING_FLEET and not c.wrecks and not c.upgrades
    assert c.mission_number == 1 and c.mission.name == "Harbor Patrol"
    assert set(c.topics) == set(TOPICS)


def test_correct_answers_pay_the_topic_currency_with_a_streak_bonus():
    c = cm.Campaign(slot=1)
    before = dict(c.currency)
    pays = [c.answer("quad", 2, True) for _ in range(3)]
    assert pays == [reward("quad", 2, n) for n in (1, 2, 3)]
    assert pays[1] > pays[0]  # streak bonus
    assert c.currency["powder"] == before["powder"] + sum(pays)
    assert c.stats["solved"]["quad"] == 3


def test_wrong_answers_cost_35_percent_of_the_pay():
    c = cm.Campaign(slot=1)
    c.currency["powder"] = 100
    c.answer("quad", 2, True)
    lost = c.answer("quad", 2, False)
    assert lost == -penalty("quad", 2) == -math.ceil(0.35 * base_pay("quad", 2))
    assert c.currency["powder"] == 100 + reward("quad", 2, 1) - penalty("quad", 2)
    assert c.streak == 0 and c.stats["attempted"]["quad"] == 2 and c.stats["lost"]["powder"] == penalty("quad", 2)


def test_wrong_answers_never_push_a_balance_below_zero():
    c = cm.Campaign(slot=1)
    c.currency["steel"] = 2
    assert c.answer("lin", 3, False) == -2 and c.currency["steel"] == 0
    assert c.answer("lin", 3, False) == 0 and c.currency["steel"] == 0


def test_pay_is_tied_to_difficulty():
    for topic in TOPICS:
        assert base_pay(topic, 1) < base_pay(topic, 2) < base_pay(topic, 3)
    assert [level_pay(n) for n in sorted(LEVELS)] == sorted(level_pay(n) for n in LEVELS)
    assert level_pay(1) == TIER_PAY[1] and level_pay(5) == TIER_PAY[3]


def test_every_currency_pays_the_same_at_the_hardest_level():
    """Every topic serves only multi-step problems at the hardest level, and every topic
    pays alike, so a streak there earns as much steel or blueprints as powder or fuel."""
    c = cm.Campaign(slot=1)
    rng = random.Random(1)
    for topic in TOPICS:
        tiers = {choose(rng, [topic], max(LEVELS), c.problem_context(rng)).tier for _ in range(40)}
        assert tiers == {3}, (topic, tiers)
    pays = {TOPICS[t].currency: reward(t, 3, 6) for t in TOPICS}
    assert len(set(pays.values())) == 1, pays


def test_guessing_does_not_pay():
    """A blind guesser (right 1 time in 4) must not come out ahead on any problem."""
    # chance that a correct guess is the k-th in a row: 0.75 * 0.25^(k-1)
    for topic in TOPICS:
        for tier in TIER_PAY:
            paid = sum(0.75 * 0.25 ** (k - 1) * reward(topic, tier, k) for k in range(1, 40))
            ev = 0.25 * paid - 0.75 * penalty(topic, tier)
            assert -0.1 * base_pay(topic, tier) < ev <= 0, (topic, tier, ev)


def test_harder_levels_pay_more_even_with_more_mistakes():
    """A student who moves up a level and gets more wrong there still earns more per problem."""
    def expected(level: int, right: float) -> float:
        weights = LEVELS[level]
        per_tier = {t: right * reward("lin", t, 3) - (1 - right) * penalty("lin", t) for t in weights}
        return sum(w * per_tier[t] for t, w in weights.items()) / sum(weights.values())

    accuracy = {1: 0.95, 2: 0.9, 3: 0.85, 4: 0.8, 5: 0.75}
    pay = [expected(level, accuracy[level]) for level in sorted(LEVELS)]
    assert pay == sorted(pay) and pay[-1] > 2.5 * pay[0], pay
    assert streak_bonus(1) == 0 and streak_bonus(6) == streak_bonus(60) == 0.75


def test_topics_can_be_switched_but_not_all_off():
    c = cm.Campaign(slot=1)
    for t in ["lin", "sys", "quad"]:
        assert c.toggle_topic(t) is None
    assert c.toggle_topic("exp") is not None  # the last algebra topic stays on
    assert c.school_topics("algebra") == ["exp"]


def test_upgrades_cost_currency_and_stop_at_max_level():
    c = cm.Campaign(slot=1)
    assert "Not enough" in c.buy_upgrade("caliber")
    c = rich()
    track = TRACKS["belt"]
    for level in range(1, track.max_level + 1):
        cost = c.upgrade_cost("belt")
        steel = c.currency["steel"]
        assert c.buy_upgrade("belt") is None
        assert c.level("belt") == level and c.currency["steel"] == steel - cost["steel"]
    assert c.upgrade_cost("belt") is None and c.buy_upgrade("belt") is not None


def test_each_upgrade_level_costs_twice_the_last():
    for track in TRACKS.values():
        for level in range(2, track.max_level + 1):
            prev, cost = track.cost(level - 1), track.cost(level)
            assert cost == {c: 2 * v for c, v in prev.items()}, track.id


def test_refit_applies_fleet_upgrades():
    levels = {"caliber": 2, "turrets": 1, "rangefinders": 1, "armor": 2, "engines": 1, "belt": 1,
              "tubes": 1, "torp_speed": 1, "damage_control": 1, "interdiction": 2}
    d = refit(DESTROYER, levels)
    gun, torp = d.mounts[0], d.mounts[1]
    assert gun.weapon.damage == (DESTROYER.mounts[0].weapon.damage[0] + 2, DESTROYER.mounts[0].weapon.damage[1] + 2)
    assert gun.count == DESTROYER.mounts[0].count + 1 and gun.weapon.range == DESTROYER.mounts[0].weapon.range + 1
    assert torp.count == DESTROYER.mounts[1].count + 1 and torp.weapon.speed == DESTROYER.mounts[1].weapon.speed + 1
    assert d.max_hp == round(DESTROYER.max_hp * 1.5)
    assert d.speed == DESTROYER.speed + 1 and d.belt == DESTROYER.belt + 1
    assert d.repair_per_round > 0 and d.intercept_chance == pytest.approx(0.3)
    assert refit(PICKET, {}) == PICKET


def test_act_one_classes_unlock_with_blueprints_from_the_start():
    c = rich()
    assert c.mission_number == 1 and c.class_state("destroyer") == "unlockable"
    assert "Unlock" in c.buy_ship("destroyer")
    assert c.unlock_class("destroyer") is None and c.class_state("destroyer") == "available"
    assert c.buy_ship("destroyer") is None and c.fleet["destroyer"] == 1
    for cid in ["light_cruiser", "battleship", "missile_cruiser"]:
        assert c.unlock_class(cid) is None and c.buy_ship(cid) is None
    broke = cm.Campaign(slot=1)
    assert "Not enough" in broke.unlock_class("battleship") and broke.class_state("battleship") == "unlockable"


def test_plasma_classes_wait_for_the_kraken_to_be_won():
    c = rich(mission_number=20)
    c.currency["plasma"] = 5000
    for cid in ("hydrofoil", "aegis_cruiser", "stormbreaker"):
        assert c.class_state(cid) == "mission" and c.unlock_class(cid) == f"Win mission 20 to unlock the {SHIP_CLASSES[cid].name}."
    c.mission_number = cm.ACTS[2]  # all three open together when mission 20 is won, with Act III
    assert all(c.class_state(cid) == "unlockable" for cid in ("hydrofoil", "aegis_cruiser", "stormbreaker"))
    assert all(cls.requires_mission == 1 for cls in SHIP_CLASSES.values() if not cls.future)


def test_every_ship_class_fits_its_hull():
    for cls in SHIP_CLASSES.values():
        assert cls.design.validate() == [], cls.id


def test_repairs_cost_an_eighth_of_a_new_ship():
    for cls in SHIP_CLASSES.values():
        assert cls.repair_cost.keys() == cls.price.keys()
        for cur, amount in cls.repair_cost.items():
            assert amount == math.ceil(cls.price[cur] / 8)


def test_repairs_bring_wrecks_back():
    c = rich(wrecks={"destroyer": 2})
    before = dict(c.currency)
    assert c.repair("destroyer") is None
    assert c.wrecks == {"destroyer": 1} and c.fleet["destroyer"] == 1
    cost = SHIP_CLASSES["destroyer"].repair_cost
    assert cost == {"steel": 10, "powder": 5, "fuel": 4}
    assert all(c.currency[cur] == before[cur] - cost.get(cur, 0) for cur in before)
    assert c.repair("picket") is not None  # nothing to repair

    broke = cm.Campaign(slot=1, wrecks={"destroyer": 1}, currency={"steel": 100})
    assert "Not enough" in broke.repair("destroyer") and broke.wrecks == {"destroyer": 1}


def test_victory_advances_the_campaign_and_wrecks_the_sunk():
    c = rich(fleet={"picket": 6, "torpedo_boat": 6})
    battle = c.build_battle()
    run_battle(battle)
    assert battle.winner == 0
    lost = sum(s.start_count - s.count for s in battle.stacks.values() if s.side == 0)
    steel = c.currency["steel"]
    report = c.apply_result(battle)
    assert report.won and c.mission_number == 2 and c.attempts == 0
    assert sum(c.wrecks.values()) == lost and sum(c.fleet.values()) == 12 - lost
    assert c.currency["steel"] == steel + report.bounty["steel"]
    assert any("complete" in line for line in report.lines())


def _withdraw_at_once(battle):
    from seabattle.ai import SimpleAI

    battle.start()
    ai = SimpleAI()
    while battle.active.side == 1:  # let Red act until it's our turn
        battle.apply(ai.choose_action(battle, battle.active))
    battle.apply(Withdraw())


def test_withdrawing_fails_the_mission_but_keeps_the_ships():
    c = cm.Campaign(slot=1)
    battle = c.build_battle()
    _withdraw_at_once(battle)
    assert battle.over and battle.winner == 1
    report = c.apply_result(battle)
    assert report.outcome == "withdrew" and c.mission_number == 1 and c.attempts == 1
    assert c.fleet == cm.STARTING_FLEET and not c.wrecks


def test_only_missions_already_won_can_be_replayed_as_skirmishes():
    c = rich(mission_number=4)
    assert [n for n in range(6) if c.can_skirmish(n)] == [1, 2, 3]
    with pytest.raises(ValueError):
        c.build_battle(skirmish=4)


def test_a_skirmish_pays_a_tenth_of_the_prize_money():
    for n in (1, 4, cm.MISSION_COUNT):
        m = cm.mission(n)
        assert m.skirmish_prize == {cur: math.ceil(v / 10) for cur, v in m.bounty.items()}


def test_a_skirmish_win_pays_the_small_prize_and_changes_nothing_else():
    c = rich(mission_number=5, attempts=2, fleet={"destroyer": 10, "picket": 8}, wrecks={"picket": 1})
    battle = c.build_battle(skirmish=2)
    m = cm.mission(2)
    assert [(s.design, s.count) for s in battle.stacks.values() if s.side == 1] == [
        (cm.red_design(cid, m.tech), n) for cid, n in m.enemy
    ]
    run_battle(battle)
    assert battle.winner == 0
    sunk = sum(s.start_count - s.count for s in battle.stacks.values() if s.side == 0)
    before = dict(c.currency)
    report = c.apply_result(battle, skirmish=2)
    assert report.won and report.skirmish and report.bounty == m.skirmish_prize
    assert all(c.currency[cur] == before[cur] + report.bounty[cur] for cur in before)
    assert sum(report.sunk.values()) == sunk
    assert c.fleet == {"destroyer": 10, "picket": 8} and c.wrecks == {"picket": 1}  # sunk ships come back free
    assert c.mission_number == 5 and c.attempts == 2 and c.stats["skirmishes"] == {"won": 1}
    assert report.lines()[0] == "Skirmish won: Mission 2, Smugglers' Run."


def test_losing_a_skirmish_costs_nothing_and_the_next_one_gets_a_new_map():
    c = rich(mission_number=5)
    battle = c.build_battle(skirmish=4)
    _withdraw_at_once(battle)
    before = (dict(c.currency), dict(c.fleet), dict(c.wrecks), c.mission_number, c.attempts)
    report = c.apply_result(battle, skirmish=4)
    assert report.outcome == "withdrew" and not report.bounty
    assert (c.currency, c.fleet, c.wrecks, c.mission_number, c.attempts) == before
    assert c.stats["skirmishes"] == {"lost": 1}
    assert c.build_battle(skirmish=4).seed != battle.seed


def test_every_mission_builds_a_valid_battle():
    c = rich()
    for n in range(1, cm.MISSION_COUNT + 4):
        c.mission_number = n
        battle = c.build_battle()
        for side in (0, 1):
            assert 1 <= len([s for s in battle.stacks.values() if s.side == side]) <= 6
    assert sum(n for _, n in cm.mission(cm.MISSION_COUNT + 3).enemy) > sum(n for _, n in cm.mission(cm.MISSION_COUNT).enemy)


def test_fleets_start_out_of_torpedo_reach():
    """Without upgraded engines nobody can move and launch torpedoes or fire lasers on the first turn;
    Red never gets engines, and one level of them gets your destroyers there. The Hydrofoil Raider is
    the one ship built fast enough to launch on the first turn, and Red never has one."""
    gap = cm.WIDTH - 3  # between the two deployment columns
    tech = cm.red_tech(cm.MISSION_COUNT)
    assert "engines" not in tech
    ours = [cls.design for cid, cls in SHIP_CLASSES.items() if cid != "hydrofoil"]
    designs = ours + [cm.red_design(cid, tech) for cid in [*SHIP_CLASSES, *RED_SHIPS] if cid != "hydrofoil"]
    for d in designs:
        for m in d.mounts:
            if m.weapon.kind in ("torpedo", "laser"):
                assert d.speed + m.weapon.range < gap, d.name
    fast = refit(DESTROYER, {"engines": 1})
    assert fast.speed + fast.mounts[1].weapon.range >= gap
    raider = SHIP_CLASSES["hydrofoil"].design
    assert raider.speed + raider.mounts[0].weapon.range >= gap
    assert not any(cid == "hydrofoil" for n in range(1, cm.MISSION_COUNT + 3) for cid, _ in cm.mission(n).enemy)


def test_thirty_missions_in_three_acts_then_endless_patrols():
    assert cm.ACTS == (1, 11, 21) and cm.MISSION_COUNT == 30
    assert cm.SUPER_MISSIONS == (10, 20, 30)  # a super mission ends each act
    assert (cm.ACTS[1], cm.ACTS[2]) == (PLASMA_MISSION, PLASMA_SHIPS_MISSION)  # Act II opens Plasma, Act III its ships
    assert cm.mission(20).name == "The Kraken" and cm.mission(30).name == "The Maelstrom"
    assert [cm.mission(n).name for n in (31, 32)] == ["Patrol 1", "Patrol 2"]


def test_red_upgrades_depend_only_on_the_mission():
    for n in range(2, cm.MISSION_COUNT + 5):
        before, now = cm.red_tech(n - 1), cm.red_tech(n)
        assert all(now.get(t, 0) >= lv for t, lv in before.items())  # Red never loses an upgrade
        assert all(lv <= TRACKS[t].max_level for t, lv in now.items())
        assert all(lv <= 2 for t, lv in now.items() if not TRACKS[t].future)  # the top Act I levels are yours alone
    assert cm.red_tech(1) == {} and cm.red_tech(cm.MISSION_COUNT + 4) == cm.red_tech(cm.MISSION_COUNT)
    # The player's own upgrades make no difference to what Red brings.
    weak, strong = cm.Campaign(slot=1, mission_number=12), rich(mission_number=12)
    strong.upgrades = {t.id: t.max_level for t in TRACKS.values()}
    reds = [[(s.design, s.count) for s in c.build_battle().stacks.values() if s.side == 1] for c in (weak, strong)]
    assert reds[0] == reds[1]


def test_red_super_ships_are_much_bigger_than_anything_in_the_shipyard():
    assert not set(RED_SHIPS) & set(SHIP_CLASSES)
    for design in RED_SHIPS.values():
        assert design.validate() == [], design.name
        assert design.max_hp >= 2 * BATTLESHIP.max_hp and design.firepower > 1.5 * BATTLESHIP.firepower
    early = {cid for n in range(1, 13) for cid, _ in cm.mission(n).enemy}
    late = {cid for n in range(13, cm.MISSION_COUNT + 1) for cid, _ in cm.mission(n).enemy}
    assert not early & set(RED_SHIPS) and set(RED_SHIPS) <= late
    # Your own super ship is an Act III ship: bigger than a battleship, but no match for Red's.
    storm = SHIP_CLASSES["stormbreaker"]
    assert storm.limit == 2 and storm.requires_mission == cm.ACTS[2] and storm.design.hull.super_ship
    assert refit(storm.design, {"damage_control": 3, "nanite": 2}).repair_per_round == 0
    # Force field generators can't keep up with a super ship either: it keeps the field it was built with.
    for design in [storm.design, *RED_SHIPS.values()]:
        assert refit(design, {"fields": 4}).field_bonus == design.field_bonus
    tech = cm.red_tech(cm.MISSION_COUNT)
    assert tech.get("damage_control") and cm.red_design("battleship", tech).repair_per_round > 0
    assert all(cm.red_design(cid, tech).repair_per_round == 0 for cid in RED_SHIPS)


def _hull(m: cm.Mission) -> int:
    return sum(cm.red_design(cid, m.tech).max_hp * n for cid, n in m.enemy)


def test_missions_10_20_and_30_are_super_missions():
    from seabattle.boost import MAX_PER_BATTLE, MAX_PER_SUPER_MISSION

    assert [n for n in range(1, cm.MISSION_COUNT + 5) if cm.mission(n).is_super] == [10, 20, 30]
    for n in (10, 20, 30):
        m = cm.mission(n)
        assert m.title == f"Super Mission {n}" and m.boosts == MAX_PER_SUPER_MISSION and m.opens
        assert m.bounty["steel"] == 2 * (10 + 5 * n)  # twice the prize money
        assert _hull(m) > _hull(cm.mission(n - 1))  # Red's biggest fleet yet...
        if n < cm.MISSION_COUNT:
            assert _hull(m) > _hull(cm.mission(n + 1))  # ...and bigger than the next mission's
    plain = cm.mission(9)
    assert (plain.title, plain.boosts, plain.opens, plain.is_super) == ("Mission 9", MAX_PER_BATTLE, "", False)


def test_a_super_mission_repairs_half_its_losses_for_free():
    c = rich(mission_number=10, fleet={"picket": 8, "torpedo_boat": 8})
    battle = c.build_battle()
    run_battle(battle)  # small boats against Red's whole cruiser squadron
    assert battle.winner == 1
    lost = {cid: 8 - s.count for s in battle.stacks.values() if s.side == 0
            for cid in [{"Picket Boat": "picket", "Torpedo Boat": "torpedo_boat"}[s.design.name]]}
    report = c.apply_result(battle)
    assert report.sunk == {k: v for k, v in lost.items() if v}
    assert report.repaired == {k: v // 2 for k, v in report.sunk.items()} and any(report.repaired.values())
    for cid, n in report.sunk.items():  # half come home repaired (rounded down), the rest as wrecks
        assert c.wrecks.get(cid, 0) == n - n // 2 and c.fleet.get(cid, 0) == 8 - (n - n // 2)
    assert any("dockyards repair half" in line for line in report.lines())
    assert report.lines()[0] == "Super Mission 10 failed. Your fleet returns to port to regroup."


def test_a_lost_mission_repairs_half_its_losses_for_free_and_a_won_one_none():
    lost = rich(mission_number=7, fleet={"picket": 8, "torpedo_boat": 8})
    battle = lost.build_battle()
    run_battle(battle)  # small boats against the Iron Wall's cruisers
    assert battle.winner == 1 and not lost.mission.is_super
    report = lost.apply_result(battle)
    assert report.repaired == {k: v // 2 for k, v in report.sunk.items()} and any(report.repaired.values())
    assert sum(lost.wrecks.values()) == sum(report.sunk.values()) - sum(report.repaired.values())
    assert any("half the ships a lost mission sinks" in line for line in report.lines())
    won = rich(mission_number=2, fleet={"picket": 12, "torpedo_boat": 8})
    battle = won.build_battle()
    run_battle(battle)
    assert battle.winner == 0
    report = won.apply_result(battle)
    assert not report.repaired and won.wrecks == {k: v for k, v in report.sunk.items() if v}


def _lost(c: cm.Campaign, sunk: list[int]):
    """Mission ``c``'s battle, lost, with ``sunk`` Red ships gone from each Red squadron."""
    battle = c.build_battle()
    red = sorted((s for s in battle.stacks.values() if s.side == 1), key=lambda s: s.id)
    for s, k in zip(red, sunk):
        s.count -= k
    for s in battle.stacks.values():
        if s.side == 0:
            s.count, s.status = 0, "sunk"
    battle.over, battle.winner = True, 1
    return battle


def test_half_the_red_ships_a_lost_battle_sinks_stay_sunk_for_the_next_try(save_dir):
    c = rich(mission_number=8, fleet={"picket": 6})
    assert [n for _, n in c.mission.enemy] == [7, 7, 2] and c.red_fleet() == list(c.mission.enemy)
    report = c.apply_result(_lost(c, [5, 2, 1]))
    assert report.red_gone == 3 and any("3 of the Red ships you sank stay sunk" in line for line in report.lines())
    assert [n for _, n in c.red_fleet()] == [5, 6, 2]  # half of 5, 2 and 1, rounded down
    assert [start for _, start, _, _ in c.build_battle().summary()[1]] == [5, 6, 2]
    c.apply_result(_lost(c, [5, 6, 2]))  # no squadron drops below half its full strength
    assert [n for _, n in c.red_fleet()] == [4, 4, 1]
    cm.save(c)
    assert cm.load(1).red_fleet() == c.red_fleet()
    assert c.build_battle(skirmish=3).summary()[1] == [(d, n, n, "active") for d, n in
                                                     [("Torpedo Boat", 9), ("Picket Boat", 4)]]  # skirmishes don't change
    c.apply_result(_lost(c, [4, 4, 1]))  # however often the player withdraws early, half the fleet is still there
    assert [n for _, n in c.red_fleet()] == [4, 4, 1]
    other = cm.Campaign.from_dict(dict(c.to_dict(), mission=9))  # a record for another mission is ignored
    assert other.red_fleet() == list(other.mission.enemy)
    win = c.build_battle()
    for s in win.stacks.values():
        if s.side == 1:
            s.count, s.status = 0, "sunk"
    win.over, win.winner = True, 0
    c.apply_result(win)
    assert c.mission_number == 9 and c.red_fleet() == list(c.mission.enemy) and not c.red_worn


def test_withdrawing_before_the_fight_costs_anything_wears_nothing_down():
    c = rich(mission_number=8, fleet={"picket": 6})
    for _ in range(10):  # sink two of each squadron, then pull out with the whole fleet afloat
        battle = c.build_battle()
        for s in battle.stacks.values():
            if s.side == 1:
                s.count -= min(2, s.count - 1)
            else:
                s.status = "retreated"
        battle.over, battle.winner = True, 1
        assert c.apply_result(battle).outcome == "withdrew"
    assert c.red_fleet() == list(c.mission.enemy) and c.attempts == 10


def test_red_super_ships_are_always_repaired_for_the_next_try():
    c = rich(mission_number=16, fleet={"battleship": 4})
    assert list(c.mission.enemy) == [("dreadnought", 2), ("destroyer", 5)]
    report = c.apply_result(_lost(c, [2, 4]))
    assert c.red_fleet() == [("dreadnought", 2), ("destroyer", 3)] and report.red_gone == 2


def test_winning_a_super_mission_says_what_it_opens():
    c = rich(mission_number=20, fleet={"battleship": 20, "missile_cruiser": 20, "destroyer": 20},
             upgrades={"caliber": 4, "armor": 4, "belt": 3, "fire_control": 3, "turrets": 3, "rangefinders": 2})
    battle = c.build_battle()
    run_battle(battle)
    assert battle.winner == 0
    report = c.apply_result(battle)
    assert report.lines()[:2] == ["Super Mission 20 complete: The Kraken.", cm.SUPER_REWARDS[20][1]]
    assert c.mission_number == 21 and c.class_state("hydrofoil") == "unlockable"


def test_each_patrol_brings_twenty_percent_more_escorts():
    def hull(m):
        return sum(cm.red_design(cid, m.tech).max_hp * n for cid, n in m.enemy)

    # They grow from the Maelstrom and a small escort, not from super mission 30's whole fleet.
    last = cm.Mission(cm.MISSION_COUNT, "", "", cm.PATROL_FLEET, cm.red_tech(cm.MISSION_COUNT))
    assert hull(last) < hull(cm.mission(cm.MISSION_COUNT)) and cm.red_tech(cm.MISSION_COUNT + 1) == last.tech
    escorts = {cid: n for cid, n in cm.PATROL_FLEET if cid not in RED_SHIPS}
    assert escorts and dict(cm.PATROL_FLEET)["maelstrom"] == 1
    for extra in range(1, 12):
        m = cm.mission(cm.MISSION_COUNT + extra)
        prev = cm.mission(cm.MISSION_COUNT + extra - 1) if extra > 1 else last
        assert [cid for cid, _ in m.enemy] == [cid for cid, _ in last.enemy]
        assert all(n >= k for (_, n), (_, k) in zip(m.enemy, prev.enemy))  # no stack ever shrinks
        assert hull(m) > hull(prev)
        assert dict(m.enemy)["maelstrom"] == 1  # the super ship stays as it is; the escorts grow
        for cid, n in escorts.items():
            assert dict(m.enemy)[cid] == pytest.approx(n * cm.ENDLESS_GROWTH ** extra, abs=0.5)


def test_save_and_load_round_trip(save_dir):
    c = rich(upgrades={"caliber": 2}, wrecks={"picket": 1}, mission_number=4)
    c.answer("geo", 2, True)
    c.set_difficulty("broadside", 5)
    c.toggle_topic("trig")
    path = cm.save(c)
    assert path.parent == save_dir and path.exists()
    loaded = cm.load(1)
    assert loaded.to_dict() == c.to_dict()
    assert cm.load(2) is None


def test_bad_save_data_is_cleaned_up(save_dir):
    cm.slot_path(1).write_text(json.dumps({
        "slot": 1, "currency": {"steel": -5, "gold": 99}, "fleet": {"picket": 2, "zeppelin": 3},
        "upgrades": {"caliber": 99, "warp": 1}, "difficulty": {"algebra": 9}, "topics": ["nope"],
        "reward_multiplier": 1.2,  # from older saves; ignored now
    }))
    c = cm.load(1)
    assert c.currency == {"steel": 0} and c.fleet == {"picket": 2}
    assert c.upgrades == {"caliber": TRACKS["caliber"].max_level}
    assert c.difficulty["algebra"] == 5 and not hasattr(c, "reward_multiplier")
    assert set(c.topics) == set(TOPICS)


def test_damaged_save_file_is_set_aside(save_dir):
    cm.slot_path(3).write_text("{not json")
    with pytest.raises(cm.SaveError) as caught:
        cm.load(3)
    assert caught.value.free and "set aside" in str(caught.value)
    assert not cm.slot_path(3).exists()
    assert list(save_dir.glob("campaign3.damaged-*.json"))
    assert cm.load(3) is None  # the slot is free for a new campaign


@pytest.mark.parametrize("damage", ["", "[1, 2]", '{"mission": Infinity}', '{"fleet": {"picket": 1e999}}', "[" * 100_000])
def test_any_kind_of_damage_is_caught(save_dir, damage):
    cm.slot_path(1).write_text(damage)
    with pytest.raises(cm.SaveError):
        cm.load(1)
    assert list(save_dir.glob("campaign1.damaged-*.json"))


def test_a_damaged_save_comes_back_from_its_backup(save_dir):
    c = rich(mission_number=5)
    cm.save(c)
    assert not cm.slot_path(1).with_suffix(".bak").exists()  # nothing to back up yet
    c.mission_number = 6
    cm.save(c)
    assert json.loads(cm.slot_path(1).with_suffix(".bak").read_text())["mission"] == 5
    cm.slot_path(1).write_text('{"mission": 6, "fleet": ')  # cut off
    restored = cm.load(1)
    assert restored.mission_number == 5 and "brought back" in restored.notice
    assert cm.load(1).mission_number == 5  # put back in place, not only in memory
    assert list(save_dir.glob("campaign1.damaged-*.json"))
    cm.delete(1)
    assert not list(save_dir.glob("campaign1.json*")) and not cm.slot_path(1).with_suffix(".bak").exists()


def test_a_save_from_a_newer_version_is_left_alone(save_dir):
    data = rich().to_dict()
    data["version"] = cm.SAVE_VERSION + 1
    data["warp_drive"] = {"level": 3}
    text = json.dumps(data)
    cm.slot_path(2).write_text(text)
    with pytest.raises(cm.SaveError) as caught:
        cm.load(2)
    assert not caught.value.free and "newer version" in str(caught.value)
    assert cm.slot_path(2).read_text() == text  # not set aside, not rewritten
    assert not list(save_dir.glob("campaign2.damaged-*"))


def test_a_save_that_cant_be_read_is_left_alone(save_dir):
    cm.slot_path(1).mkdir()  # reading it fails the way a file another program has locked does
    with pytest.raises(cm.SaveError) as caught:
        cm.load(1)
    assert not caught.value.free and "close that and try again" in str(caught.value)
    assert cm.slot_path(1).is_dir()


def test_bad_stats_are_dropped_not_kept(save_dir):
    data = rich().to_dict()
    data["stats"] = {"solved": {"lin": 3, "sys": "x", "quad": [1]}, "attempted": 7, "records": {"best_streak": 4}}
    cm.slot_path(1).write_text(json.dumps(data))
    c = cm.load(1)
    assert c.stats == {"solved": {"lin": 3}, "records": {"best_streak": 4}}
    c.answer("lin", 1, True)  # counting carries on from there
    assert c.record("topic", "lin") == (4, 1)


def test_a_failed_save_is_reported_not_raised(save_dir, monkeypatch):
    blocked = save_dir / "file"
    blocked.write_text("")
    monkeypatch.setenv("SEABATTLE_SAVE_DIR", str(blocked / "saves"))  # a folder can't be made inside a file
    problem = cm.try_save(cm.Campaign(slot=1))
    assert problem and problem.startswith("Couldn't save the campaign")
    monkeypatch.setenv("SEABATTLE_SAVE_DIR", str(save_dir))
    assert cm.try_save(cm.Campaign(slot=1)) is None and cm.load(1) is not None


def test_saves_live_outside_the_game_folder(monkeypatch, tmp_path):
    monkeypatch.delenv("SEABATTLE_SAVE_DIR")
    game_folder = Path(cm.__file__).resolve().parent.parent
    assert game_folder not in cm.save_dir().parents
    assert cm.old_save_dirs()[0] == game_folder / "saves"
    for platform, env, expected in [
        ("win32", {"APPDATA": str(tmp_path / "Roaming")}, tmp_path / "Roaming" / "Master of Oceans" / "saves"),
        ("linux", {"XDG_DATA_HOME": str(tmp_path / "share")}, tmp_path / "share" / "master-of-oceans" / "saves"),
    ]:
        monkeypatch.setattr(cm.sys, "platform", platform)
        for k, v in env.items():
            monkeypatch.setenv(k, v)
        assert cm.save_dir() == expected


def test_old_saves_are_moved_once_and_never_over_newer_ones(save_dir, tmp_path):
    old = tmp_path / "game" / "saves"
    old.mkdir(parents=True)
    (old / "campaign1.json").write_text('{"mission": 4}')
    (old / "campaign2.json").write_text('{"mission": 9}')
    (old / "settings.json").write_text('{"muted": true}')
    (old / "crash.log").write_text("old crash")
    cm.slot_path(2).write_text('{"mission": 2}')  # already in the save folder: keep it

    assert cm.move_old_saves([old]) == [old]
    assert json.loads(cm.slot_path(1).read_text()) == {"mission": 4}
    assert json.loads(cm.slot_path(2).read_text()) == {"mission": 2}
    assert (save_dir / "settings.json").exists()
    assert not (old / "campaign1.json").exists() and (old / "campaign2.json").exists() and (old / "crash.log").exists()
    assert str(save_dir) in (old / "WHERE ARE MY SAVES.txt").read_text()
    assert cm.move_old_saves([old]) == []  # nothing new to move
    assert cm.move_old_saves() == []  # with SEABATTLE_SAVE_DIR set, saves stay where they were asked to be


def test_a_missed_kind_of_problem_comes_back_for_review():
    c = cm.Campaign(slot=1)
    c.answer("lin", 1, False, generator="lin.function_notation")
    assert c.due_review(["lin"]) is None  # not straight away...
    c.answer("lin", 1, True, generator="lin.distance_rate_time")
    assert c.due_review(["lin"]) is None
    c.answer("sys", 2, True, generator="sys.sum_and_difference")
    assert c.due_review(["lin"]) == "lin.function_notation"  # ...but after two other problems
    assert c.due_review(["sys", "quad"]) is None  # only for topics that are switched on

    posed = choose(random.Random(1), ["sys"], 1, c.problem_context(random.Random(1)), generator=c.due_review(["lin"]))
    assert posed.generator.key == "lin.function_notation" and posed.topic.id == "lin"

    c.answer("lin", 1, False, generator="lin.function_notation")  # wrong again: it waits and comes back again
    assert c.review["lin.function_notation"] == cm.REVIEW_GAP
    c.answer("lin", 1, True, generator="lin.function_notation")  # right: done with it
    assert "lin.function_notation" not in c.review


def test_review_queue_and_skill_memory_are_saved():
    c = cm.Campaign(slot=2)
    for correct in (True, False, True, True, False, True, True, True, True, True, False, True):
        c.answer("tri", 1, correct, generator="tri.pythagorean_leg")
    c.answer("exp", 2, False, generator="exp.pythagorean_missing_leg")
    assert c.skills["tri.pythagorean_leg"] == "101101111101"[-cm.SKILL_MEMORY:] == "1101111101"
    cm.save(c)
    loaded = cm.load(2)
    assert loaded.review == {"exp.pythagorean_missing_leg": cm.REVIEW_GAP}
    assert loaded.skills == c.skills
    assert loaded.record("topic", "tri") == (9, 12) and loaded.record("tier", "exp:2") == (0, 1)

    data = c.to_dict()
    data["review"] = {"no.such_problem": 1, "exp.pythagorean_missing_leg": 99}
    data["skills"] = {"exp.pythagorean_missing_leg": "10x1", "nope": "111"}
    again = cm.Campaign.from_dict(data)
    assert again.review == {"exp.pythagorean_missing_leg": cm.REVIEW_GAP} and again.skills == {"exp.pythagorean_missing_leg": "101"}


# --------------------------------------------------------------------------- Plasma, Act II and Act III


def test_plasma_opens_with_its_topics_when_mission_ten_is_won():
    assert PLASMA_MISSION == 11
    plasma_topics = [t for t in TOPICS if TOPICS[t].currency == "plasma"]
    c = cm.Campaign(slot=1, mission_number=10)
    assert "plasma" not in c.currencies and not any(c.topic_open(t) for t in plasma_topics)
    assert all(t not in c.school_topics(TOPICS[t].school) for t in plasma_topics)
    assert all("when you win mission 10" in c.toggle_topic(t) for t in plasma_topics)
    assert "plasma" not in cm.mission(9).bounty
    assert cm.mission(10).bounty["plasma"] == 20  # winning it opens Plasma, with some to spend (twice: a super mission)
    c.mission_number = PLASMA_MISSION
    assert "plasma" in c.currencies and all(t in c.school_topics(TOPICS[t].school) for t in plasma_topics)
    assert cm.mission(11).bounty["plasma"] == 13 and cm.mission(30).bounty["plasma"] == 140


def test_future_tech_needs_plasma_its_mission_and_act_one_upgrades():
    c = rich(mission_number=10)
    c.currency["plasma"] = 50_000
    assert "a win at mission 10" in c.buy_upgrade("lasers")
    c.mission_number = 11
    error = c.buy_upgrade("lasers")
    assert "Fire Control 3" in error and "Rangefinders 2" in error and c.level("lasers") == 0
    c.upgrades.update({"fire_control": 3, "rangefinders": 2})
    assert c.upgrade_needs("lasers") == [] and c.buy_upgrade("lasers") is None
    assert c.upgrade_needs("graviton") == ["Laser Cannons 2", "Force Fields 1"]
    for track in TRACKS.values():  # every future tech costs Plasma and needs something from Act I
        assert track.future == ("plasma" in track.base_cost), track.id
        if track.future:
            assert track.requires and track.requires_mission == 11, track.id
            assert all(req in TRACKS and lv <= TRACKS[req].max_level for req, lv in track.requires.items())


def test_refit_fits_lasers_in_the_free_mount_sized_to_the_hull():
    from seabattle.designs import KRAKEN, TEMPEST
    from seabattle.economy import LASERS_PER_HULL

    for cls in SHIP_CLASSES.values():
        d = refit(cls.design, {"lasers": 3, "ion": 2, "graviton": 1})
        laser = d.mounts[-1]
        assert len(d.mounts) == len(cls.design.mounts) + 1 <= 4, cls.id
        assert laser.count == LASERS_PER_HULL[cls.design.hull.id]
        assert laser.weapon.damage == (10, 10) and laser.weapon.field_factor == 3 and laser.weapon.carry == 0.5
    assert refit(KRAKEN, {"lasers": 1}).mounts == KRAKEN.mounts  # no free mount, no lasers
    assert refit(TEMPEST, {"lasers": 2}).mounts[0].weapon.damage == (8, 8)  # its own lasers improve


def test_retrofits_need_their_future_tech_and_the_class_unlocked():
    c = rich(mission_number=21)
    c.currency["plasma"] = 5000
    error = c.buy_retrofit("destroyer", "laser_battery")
    assert "Laser Cannons 1" in error and "Destroyer unlocked" in error and not c.retrofits
    c.upgrades["lasers"] = 1
    assert c.retrofit_needs("destroyer", "laser_battery") == ["the Destroyer unlocked"]
    assert c.unlock_class("destroyer") is None and c.retrofit_needs("destroyer", "laser_battery") == []
    before = dict(c.currency)
    cost = c.retrofit_cost("destroyer", "laser_battery")
    assert c.buy_retrofit("destroyer", "laser_battery") is None and c.has_retrofit("destroyer", "laser_battery")
    assert c.currency == {k: v - cost.get(k, 0) for k, v in before.items()}
    assert "already" in c.buy_retrofit("destroyer", "laser_battery")
    assert "Force Fields 1" in c.buy_retrofit("picket", "field_generator")
    c.upgrades["fields"] = 1
    assert c.buy_retrofit("picket", "field_generator") is None and c.buy_retrofit("picket", "laser_battery") is None
    assert c.retrofits == {"destroyer": ["laser_battery"], "picket": ["laser_battery", "field_generator"]}
    assert "only Act I's classes" in c.buy_retrofit("aegis_cruiser", "field_generator")  # built with future tech
    broke = cm.Campaign(slot=1, mission_number=21, upgrades={"lasers": 1})
    assert "Not enough" in broke.buy_retrofit("picket", "laser_battery") and not broke.retrofits


def test_a_retrofit_is_one_price_for_the_class_and_bigger_hulls_pay_more():
    c = rich()
    for r in RETROFITS.values():
        assert TRACKS[r.requires].future and "plasma" in r.base_cost
        assert c.retrofit_cost("picket", r.id) == c.retrofit_cost("torpedo_boat", r.id) == r.base_cost
        prices = [sum(c.retrofit_cost(cid, r.id).values()) for cid in ("picket", "destroyer", "light_cruiser", "battleship")]
        assert prices == sorted(prices) and prices[-1] == 8 * prices[0]
    assert all(not cls.future for cls in SHIP_CLASSES.values() if cls.retrofittable)


def test_a_laser_battery_trades_the_lightest_guns_for_twice_the_lasers():
    for cls in (c for c in SHIP_CLASSES.values() if c.retrofittable):
        light = light_guns(cls.design)
        plain = refit(cls.design, {"lasers": 2})
        fitted = refit(retrofit(cls.design, ["laser_battery"]), {"lasers": 2})
        lasers = [m for m in fitted.mounts if m.weapon.kind == "laser"]
        assert len(lasers) == 1 and lasers[0].count == 2 * plain.mounts[-1].count, cls.id
        assert lasers[0].weapon.damage == (8, 8)  # Laser Cannons improve them like any other laser
        assert light.weapon.id not in {m.weapon.id for m in fitted.mounts}, cls.id
        assert all(light.weapon.avg_damage <= m.weapon.avg_damage for m in cls.design.mounts if m.weapon.kind == "gun")
        kept = [m for m in retrofit(cls.design, ["laser_battery"]).mounts if m.weapon.kind != "laser"]
        assert kept == [m for m in cls.design.mounts if m is not light], cls.id  # everything else stays aboard
        assert len(fitted.mounts) <= 4 and fitted.name == cls.design.name
    assert retrofit(PICKET, []) == PICKET


def test_a_field_generator_adds_its_own_field_to_force_fields():
    plain = refit(BATTLESHIP, {"fields": 2})
    fitted = refit(retrofit(BATTLESHIP, ["field_generator"]), {"fields": 2})
    assert fitted.field_bonus == pytest.approx(plain.field_bonus + 0.2) and fitted.max_field > plain.max_field
    assert refit(retrofit(BATTLESHIP, ["field_generator"]), {}).max_field == math.ceil(0.2 * BATTLESHIP.max_hp)
    both = retrofit(DESTROYER, ["field_generator", "laser_battery"])
    assert both.field_bonus == pytest.approx(0.2) and both.has_lasers


def test_retrofits_sail_with_their_class_and_are_saved(save_dir):
    c = rich(mission_number=21, fleet={"destroyer": 3, "battleship": 1}, unlocked=list(SHIP_CLASSES),
             upgrades={"lasers": 1, "fields": 1})
    c.currency["plasma"] = 5000
    assert c.buy_retrofit("destroyer", "laser_battery") is None and c.buy_retrofit("battleship", "field_generator") is None
    battle = c.build_battle()
    blue = {s.design.name: s.design for s in battle.stacks.values() if s.side == 0}
    assert blue["Destroyer"] == c.class_design("destroyer") and blue["Battleship"] == c.class_design("battleship")
    assert blue["Destroyer"].mounts[-1].count == 4 and blue["Battleship"].max_field > refit(BATTLESHIP, c.upgrades).max_field
    report = c.apply_result(run_battle(battle))  # stacks still map back to their classes
    assert set(report.sunk) <= {"destroyer", "battleship"}
    cm.save(c)
    assert cm.load(1).retrofits == {"destroyer": ["laser_battery"], "battleship": ["field_generator"]}
    junk = dict(c.to_dict(), retrofits={"destroyer": ["field_generator", "x", "field_generator"],
                                        "aegis_cruiser": ["field_generator"], "frigate": ["laser_battery"],
                                        "picket": "laser_battery"})
    assert cm.Campaign.from_dict(junk).retrofits == {"destroyer": ["field_generator"]}
    assert cm.Campaign.from_dict({k: v for k, v in c.to_dict().items() if k != "retrofits"}).retrofits == {}


def test_the_stormbreaker_is_limited_to_two():
    c = rich(mission_number=27)
    c.currency["plasma"] = 50_000
    c.currency = {k: 50_000 for k in c.currency}
    assert c.unlock_class("stormbreaker") is None
    assert c.buy_ship("stormbreaker") is None and c.buy_ship("stormbreaker") is None
    assert "at most 2" in c.buy_ship("stormbreaker") and c.fleet["stormbreaker"] == 2


def test_nanite_repair_makes_wrecks_cheaper_to_repair():
    c = rich(wrecks={"battleship": 1})
    price = SHIP_CLASSES["battleship"].price
    assert c.repair_cost("battleship") == {k: math.ceil(v / 8) for k, v in price.items()}
    c.upgrades["nanite"] = 1
    assert c.repair_cost("battleship") == {k: math.ceil(v / 12) for k, v in price.items()}
    c.upgrades["nanite"] = 2
    assert c.repair_cost("battleship") == {k: math.ceil(v / 16) for k, v in price.items()}
    steel = c.currency["steel"]
    assert c.repair("battleship") is None and c.currency["steel"] == steel - math.ceil(price["steel"] / 16)


def test_act_three_gives_red_future_tech_a_mission_at_a_time():
    """Missions 22-28 each bring out a technology Red didn't have; after that, every mission raises a level."""
    for n in range(cm.ACTS[2] + 1, cm.MISSION_COUNT + 1):
        before, now = cm.red_tech(n - 1), cm.red_tech(n)
        raised = {t for t, lv in now.items() if lv > before.get(t, 0)}
        assert raised and all(TRACKS[t].future for t in raised), n
        assert n > 28 or raised - set(before), n
    assert all(TRACKS[t].future is False for t in cm.red_tech(cm.ACTS[2] - 1))  # no future tech for Red before Act III
    battle = rich(mission_number=30).build_battle()
    maelstrom = next(s for s in battle.stacks.values() if s.design.name == "Maelstrom")
    assert maelstrom.design.max_field > 0 and maelstrom.design.has_lasers and maelstrom.design.repair_per_round == 0


def test_old_saves_start_act_three_and_get_the_plasma_topics(save_dir):
    old = rich(mission_number=24).to_dict()
    old["version"] = 1
    old["topics"] = ["lin", "geo"]
    cm.slot_path(1).write_text(json.dumps(old))
    c = cm.load(1)
    assert c.mission_number == cm.ACTS[2] and c.mission.name == "Salvage Rights"
    assert {t for t in TOPICS if TOPICS[t].currency == "plasma"} <= set(c.topics) and {"lin", "geo"} <= set(c.topics)
    cm.save(c)
    assert cm.load(1).mission_number == cm.ACTS[2]  # a new save is left alone
    early = dict(old, mission=7)
    cm.slot_path(2).write_text(json.dumps(early))
    assert cm.load(2).mission_number == 7
    # A save whose only topics haven't opened yet still has something to practise.
    locked = dict(old, version=2, mission=3, topics=[t for t in TOPICS if TOPICS[t].currency == "plasma"])
    cm.slot_path(3).write_text(json.dumps(locked))
    c = cm.load(3)
    assert all(c.school_topics(school) for school in ("algebra", "broadside"))


def test_at_most_six_squadrons_sail_and_the_player_can_keep_some_in_port():
    fleet = {cid: 2 for cid in SHIP_CLASSES}  # nine classes
    c = rich(fleet=dict(fleet), mission_number=27)
    sailing = [cls.id for cls, _ in c.sailing_fleet()]
    assert len(sailing) == 6 and "stormbreaker" in sailing and "picket" not in sailing
    assert c.toggle_port("stormbreaker") is None and "stormbreaker" not in [cls.id for cls, _ in c.sailing_fleet()]
    battle = c.build_battle()
    assert len([s for s in battle.stacks.values() if s.side == 0]) == 6
    assert c.toggle_port("stormbreaker") is None and not c.in_port
    alone = rich(fleet={"picket": 3}, mission_number=2)
    assert alone.toggle_port("picket") is not None
    c.toggle_port("picket")
    cm.save(c)
    assert cm.load(1).in_port == ["picket"]


@pytest.mark.parametrize("school", ["algebra", "broadside"])
@pytest.mark.parametrize("plasma", [False, True])
def test_with_every_topic_on_each_currency_comes_up_as_often(school, plasma):
    """No currency (fuel, say) is drawn more or less often than the others. (A missed kind of problem
    coming back for review adds to its topic for a while, but evens out over many problems.)"""
    c = cm.Campaign(slot=1, mission_number=PLASMA_MISSION if plasma else 1)
    rng = random.Random(f"{school}/{plasma}")
    recent: deque = deque(maxlen=8)
    drawn = collections.Counter()
    n = 5000  # enough to see a skew of 2.5 points, four times the spread of a fair draw
    for _ in range(n):
        topics = c.school_topics(school)
        posed = choose(rng, topics, 3, c.problem_context(rng), recent, generator=c.due_review(topics))
        drawn[posed.topic.currency] += 1
        c.answer(posed.topic.id, posed.tier, True, posed.generator.key)
    share = 1 / len(c.currencies)
    assert set(drawn) == set(c.currencies)
    assert all(abs(k / n - share) < 0.025 for k in drawn.values()), {cur: f"{k / n:.1%}" for cur, k in drawn.items()}
