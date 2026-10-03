"""The modeled player that balances the campaign (seabattle/balance.py)."""

import argparse
import random

import pytest

import seabattle.campaign as cm
from seabattle import balance
from seabattle.balance import Player


def test_the_modeled_player_spends_what_it_earns():
    c = cm.Campaign(slot=1)
    balance.workshop(c, Player(), random.Random(1))
    assert c.fleet != cm.STARTING_FLEET or c.upgrades
    assert sum(c.stats["earned"].values()) > 0


def test_it_repairs_wrecks_before_buying_anything():
    c = cm.Campaign(slot=1, fleet={"picket": 1}, wrecks={"picket": 2}, currency={"steel": 30, "powder": 30})
    balance.workshop(c, Player(problems=0), random.Random(1))
    assert not c.wrecks and c.fleet["picket"] >= 3


def test_more_ships_make_the_fleet_stronger():
    c = cm.Campaign(slot=1)
    picket = next(p for p in balance.purchases(c) if p.key == "picket")
    assert balance.strength_ratio(balance._with(c, picket), 1) > balance.strength_ratio(c, 1)
    assert c.fleet == cm.STARTING_FLEET  # only judged, not bought
    assert balance.ranked(c) and all(value > 0 for value, _ in balance.ranked(c))


def test_the_modeled_player_weighs_retrofits_for_the_classes_it_owns():
    c = cm.Campaign(slot=1, mission_number=21, fleet={"destroyer": 6}, unlocked=["picket", "torpedo_boat", "destroyer"],
                    upgrades={"lasers": 1}, currency={"plasma": 500, "powder": 500})
    offered = [p for p in balance.purchases(c) if p.kind == "retrofit"]
    assert [p.key for p in offered] == ["destroyer/laser_battery"]  # Force Fields not researched; no other class owned
    trial = balance._with(c, offered[0])
    assert trial.retrofits == {"destroyer": ["laser_battery"]} and not c.retrofits  # only judged, not bought
    assert balance.strength_ratio(trial, 21) > balance.strength_ratio(c, 21)
    balance._buy(c, offered[0])
    assert c.has_retrofit("destroyer", "laser_battery")
    assert not [p for p in balance.purchases(c) if p.kind == "retrofit"]


def test_a_short_run_reports_every_mission():
    first, tries, boosts = balance.play_campaign(Player(), index=0, seed=1, last=3, samples=1)
    assert sorted(first) == sorted(tries) == [1, 2, 3]
    assert all(0 <= p <= 1 for p in first.values())
    assert all(1 <= t <= balance.MAX_TRIES + 1 for t in tries.values())
    assert boosts == {n: [0, 0] for n in (1, 2, 3)}  # Math Boost off: none come up


def test_the_modeled_player_can_fight_with_math_boost():
    first, tries, boosts = balance.play_campaign(Player(boost=0.8), index=0, seed=1, last=3, samples=1)
    assert sorted(boosts) == [1, 2, 3] and all(len(counts) == 2 for counts in boosts.values())
    assert sum(sum(counts) for counts in boosts.values()) > 0


def test_trying_red_fleets_leaves_the_missions_as_they_were():
    before = cm.mission(2).enemy
    small, big = [("picket", 1)], [("destroyer", 6), ("torpedo_boat", 12)]
    rates = balance.try_fleets(Player(), index=0, seed=1, number=2, fleets=[small, big], samples=2)
    assert len(rates) == 2 and all(0 <= r <= 1 for r in rates)
    assert rates[0] >= rates[1]
    assert cm.mission(2).enemy == before


def test_fleets_on_the_command_line():
    assert balance.parse_fleet("dreadnought:1,destroyer:2") == [("dreadnought", 1), ("destroyer", 2)]
    assert balance.parse_fleet("kraken") == [("kraken", 1)]
    for bad in ("frigate:2", "destroyer:two", ",".join(["picket:1"] * 7)):
        with pytest.raises(argparse.ArgumentTypeError):
            balance.parse_fleet(bad)
