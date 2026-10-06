"""Balance the campaign with a modeled player: ``python -m seabattle.balance``.

The modeled player stands in for a student. Between missions it solves a set
number of problems at difficulty 2, getting 80% right (twice as many before a
super mission and each of its retries, which are expected to take longer), and
repairs every wreck it can. Then it spends on whatever most improves its fleet against the coming
mission and the three after it, per unit of currency (a Lanchester-style
estimate: expected damage per round times hull). It earns in the currency its
next purchase is short of. It fights each mission the way the game's own AI
plays your fleet (the Z key), against Red's campaign AI, and plays the
campaign in order: a lost mission is tried again after another round of
problems.

For each mission it reports how often the player wins at the first try and how
many tries it takes on average. The campaign is tuned so that with 15
problems between missions the player wins most missions at the first try
about 85% of the time or better, and the set pieces (the Dreadnought, Twin
Dreadnoughts, the Tempest, the Gauntlet) about 75%. The super missions (10, 20
and 30) aim much lower: with 30 problems before them, about 40% at the first
try and two or three tries in all, the Maelstrom a little harder. A player
strong enough to win a super mission comes out of it strong, so the missions
just after one come in easier than their targets, Act III's most of all.

With ``--boost`` the player fights with Math Boost on (see ``boost.py``) and
answers that share of its problems right; a column then shows how many
boosts came up in each mission's first-try battles.

The model is a guide, not a real player: it plays some fights worse than a
person would, and with 16 players a mission's numbers can move by 10-20% from
one seed to another, more near the end of the campaign, where a player that
loses badly can take several workshops to repair its fleet. The whole campaign
takes about three minutes on four cores.

    python -m seabattle.balance                    # the whole campaign, 15 problems between missions (30 before a super mission)
    python -m seabattle.balance --problems 30      # what 30 problems between missions would be like
    python -m seabattle.balance --last 12          # stop after mission 12
    python -m seabattle.balance --mission 13 --fleet dreadnought:1 --fleet dreadnought:1,destroyer:2
                                                   # play up to mission 13, then try each Red fleet there
    python -m seabattle.balance --boost 0.8        # Math Boost on, 80% of its problems right
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import os
import random
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from multiprocessing import Pool
from typing import Iterator, Optional

from . import campaign as cm
from .ai import SimpleAI, expected_damage
from .battle import Battle
from .boost import MathBoost, play
from .economy import RETROFITS, SHIP_CLASSES, TRACKS, Cost, ship_design
from .headless import run_battle
from .problems import LEVELS, TOPICS

PROBLEMS = 15  # problems between missions the campaign is balanced for
SUPER_WORK = 2  # a super mission is expected to take longer: twice the problems before it and before each retry
MAX_TRIES = 8  # a player still losing after this many tries moves on, counted as MAX_TRIES + 1 tries
LOOKAHEAD = (1.0, 0.6, 0.6, 0.6)  # how much the coming mission and the next three count when spending
PROJECTILE_WEIGHT = 0.5  # torpedoes and missiles only fire a couple of salvos a battle
# What the strength estimate can't see (speed, reach, repairs during battle), as a small bonus per level.
EXTRA_VALUE = {
    "engines": 0.06, "rangefinders": 0.06, "torp_speed": 0.03, "torp_range": 0.03,
    "damage_control": 0.08, "nanite": 0.08, "railguns": 0.05,
}
SAMPLE_ATTEMPTS = 50  # extra first-try battles use the maps of attempts 50 and up
TOPIC_FOR = {c: next(t.id for t in TOPICS.values() if t.currency == c) for c in {t.currency for t in TOPICS.values()}}

Fleet = list[tuple[str, int]]


@dataclass(frozen=True)
class Player:
    problems: int = PROBLEMS  # between missions, and again before each retry
    accuracy: float = 0.8
    difficulty: int = 2
    boost: Optional[float] = None  # Math Boost on, with this share of its problems right (None: off)

    def problems_before(self, m: cm.Mission) -> int:
        """Problems solved before mission ``m`` (and before each retry): more before a super mission."""
        return self.problems * SUPER_WORK if m.is_super else self.problems


# --------------------------------------------------------------------------- judging a fleet


def _strength(battle: Battle, side: int) -> float:
    """Each stack's expected damage per round to its best target, times its hull, summed over the side."""
    total = 0.0
    for s in battle.alive_stacks(side):
        best = max(
            (
                sum(
                    expected_damage(battle, s, i, target) * (PROJECTILE_WEIGHT if m.weapon.is_projectile else 1)
                    for i, m in enumerate(s.design.mounts)
                )
                for target in battle.alive_stacks(1 - side)
            ),
            default=0.0,
        )
        total += best * s.total_hp
    return total


def strength_ratio(c: cm.Campaign, number: int) -> float:
    """How the fleet that would sail compares with mission ``number``'s Red fleet (above 1: stronger)."""
    blue = [(c.class_design(cls.id), n) for cls, n in c.sailing_fleet()]
    if not blue:
        return 0.0
    m = cm.mission(number)
    red = [(cm.red_design(cid, m.tech), n) for cid, n in m.enemy]
    battle = Battle([blue, red], width=cm.WIDTH, height=cm.HEIGHT)
    return _strength(battle, 0) / max(_strength(battle, 1), 1e-9)


# --------------------------------------------------------------------------- the workshop


@dataclass(frozen=True)
class Purchase:
    kind: str  # "upgrade", "ship" or "retrofit"
    key: str  # upgrade track, ship class, or "class/retrofit"
    cost: Cost  # a locked class's unlock cost is included


def purchases(c: cm.Campaign) -> list[Purchase]:
    """Everything the player could buy next: an upgrade level, a ship (unlocking its class first), or a
    retrofit for a class it owns."""
    out = []
    for tid in TRACKS:
        cost = c.upgrade_cost(tid)
        if cost is not None and not c.upgrade_needs(tid):
            out.append(Purchase("upgrade", tid, cost))
    for cid, cls in SHIP_CLASSES.items():
        state = c.class_state(cid)
        if state == "mission" or c.ships(cid) >= c.class_limit(cid):
            continue
        cost = dict(cls.price)
        if state == "unlockable":
            for k, v in cls.unlock.items():
                cost[k] = cost.get(k, 0) + v
        out.append(Purchase("ship", cid, cost))
    for cid, cls in SHIP_CLASSES.items():
        if not cls.retrofittable or not c.ships(cid):
            continue
        for rid in RETROFITS:
            if not c.has_retrofit(cid, rid) and not c.retrofit_needs(cid, rid):
                out.append(Purchase("retrofit", f"{cid}/{rid}", c.retrofit_cost(cid, rid)))
    return out


def _with(c: cm.Campaign, p: Purchase) -> cm.Campaign:
    """A copy of the campaign with ``p`` bought, for judging it (nothing is paid)."""
    trial = copy.copy(c)
    trial.fleet, trial.upgrades = dict(c.fleet), dict(c.upgrades)
    trial.retrofits = {k: list(v) for k, v in c.retrofits.items()}
    if p.kind == "upgrade":
        trial.upgrades[p.key] = c.level(p.key) + 1
    elif p.kind == "retrofit":
        cid, rid = p.key.split("/")
        trial.retrofits[cid] = trial.retrofits.get(cid, []) + [rid]
    else:
        trial.fleet[p.key] = c.fleet.get(p.key, 0) + 1
    return trial


def ranked(c: cm.Campaign) -> list[tuple[float, Purchase]]:
    """Purchases that make the fleet stronger against the coming missions, best value per currency first."""
    missions = range(c.mission_number, c.mission_number + len(LOOKAHEAD))

    def outlook(camp: cm.Campaign) -> list[float]:
        return [math.log(max(strength_ratio(camp, n), 1e-9)) for n in missions]

    base = outlook(c)
    out = []
    for p in purchases(c):
        gain = sum(w * (a - b) for w, a, b in zip(LOOKAHEAD, outlook(_with(c, p)), base)) / sum(LOOKAHEAD)
        if p.kind == "upgrade":
            gain += EXTRA_VALUE.get(p.key, 0.0)
        if gain > 0:
            out.append((gain / sum(p.cost.values()), p))
    return sorted(out, key=lambda x: -x[0])


def _best(c: cm.Campaign) -> Optional[Purchase]:
    r = ranked(c)
    return r[0][1] if r else None


def _buy(c: cm.Campaign, p: Purchase) -> None:
    c._count("model_bought", p.key)
    if p.kind == "upgrade":
        error = c.buy_upgrade(p.key)
    elif p.kind == "retrofit":
        error = c.buy_retrofit(*p.key.split("/"))
    else:
        error = (c.unlock_class(p.key) if c.class_state(p.key) == "unlockable" else None) or c.buy_ship(p.key)
    assert error is None, error


def _repair(c: cm.Campaign) -> Cost:
    """Repair every wreck the player can afford. Returns what it is still short of for the rest."""
    need: Cost = {}
    for cid in list(c.wrecks):
        while c.wrecks.get(cid) and c.repair(cid) is None:
            pass
        for k, v in c.repair_cost(cid).items():
            need[k] = need.get(k, 0) + v * c.wrecks.get(cid, 0)
    return {k: v - c.balance(k) for k, v in need.items() if v > c.balance(k)}


def _spend(c: cm.Campaign, goal: Optional[Purchase]) -> Optional[Purchase]:
    """Buy the goal once it is affordable, and spend currency it doesn't need on the best thing that fits.
    Nothing is bought while wrecks wait for repair. Returns the goal still being saved for."""
    while not c.wrecks:
        if goal is None or goal not in purchases(c):
            goal = _best(c)
            if goal is None:
                return None
        if c.can_afford(goal.cost):
            _buy(c, goal)
            goal = None
            continue
        spare = {k: c.balance(k) - goal.cost.get(k, 0) for k in c.currencies}
        extra = next((p for _, p in ranked(c) if all(spare.get(k, 0) >= v for k, v in p.cost.items())), None)
        if extra is None:
            return goal
        _buy(c, extra)
    return goal


def _solve(c: cm.Campaign, player: Player, currency: str, rng: random.Random) -> None:
    weights = LEVELS[player.difficulty]
    tier = rng.choices(list(weights), weights=list(weights.values()))[0]
    c.answer(TOPIC_FOR[currency], tier, rng.random() < player.accuracy)


def workshop(c: cm.Campaign, player: Player, rng: random.Random) -> None:
    """Solve the player's problems, earning what repairs or the next purchase need, and spend as it comes in."""
    goal = None
    for _ in range(player.problems_before(c.mission)):
        short = _repair(c)
        if not short:
            if goal is None or goal not in purchases(c):
                goal = _best(c)
            short = {k: v - c.balance(k) for k, v in (goal.cost if goal else {}).items() if v > c.balance(k)}
        short = {k: v for k, v in short.items() if k in c.currencies}
        _solve(c, player, max(short, key=short.get) if short else min(c.currencies, key=c.balance), rng)
        goal = _spend(c, goal)
    _repair(c)
    _spend(c, goal)


# --------------------------------------------------------------------------- playing the campaign


def fight(c: cm.Campaign, player: Optional[Player] = None) -> tuple[Battle, int]:
    """The coming mission's battle, with Blue played the way the Z key plays it and Red as in the campaign,
    and how many Math Boosts came up (0 with the boost off)."""
    battle = c.build_battle()
    controllers = (SimpleAI(), SimpleAI(retreat_ratio=0))
    if player is None or player.boost is None:
        return run_battle(battle, controllers), 0
    boost = MathBoost.for_battle(battle, rng=random.Random(battle.seed), super_mission=c.mission.is_super)
    play(battle, controllers, boost, player.boost, random.Random(battle.seed + 1))
    return battle, boost.posed


def fleet_lost(battle: Battle) -> float:
    """Share of Blue's hull at the start of the battle that was sunk: 0 for a walkover, 1 for a rout."""
    blue = [s for s in battle.stacks.values() if s.side == 0]
    start = sum(s.start_count * s.design.max_hp for s in blue)
    return sum((s.start_count - max(0, s.count)) * s.design.max_hp for s in blue) / max(start, 1)


def _first_try_wins(c: cm.Campaign, samples: int, player: Optional[Player] = None,
                    boosts: Optional[list[int]] = None, lost: Optional[list[float]] = None) -> int:
    """Wins in ``samples`` extra first-try battles on other maps, the campaign itself left as it is.
    Each battle's Math Boost count goes in ``boosts``, and the share of the fleet it lost in ``lost``."""
    wins = 0
    for k in range(samples):
        trial = copy.deepcopy(c)
        trial.attempts = SAMPLE_ATTEMPTS + k
        battle, n = fight(trial, player)
        wins += battle.winner == 0
        if boosts is not None:
            boosts.append(n)
        if lost is not None:
            lost.append(fleet_lost(battle))
    return wins


def _new_player(index: int, seed: int) -> tuple[cm.Campaign, random.Random]:
    # Each player gets its own slot, which gives it its own maps.
    return cm.Campaign(slot=1 + index + 1000 * seed), random.Random(seed * 1_000_003 + index)


def _play(c: cm.Campaign, player: Player, rng: random.Random, last: int, samples: int,
          first: dict[int, float], tries: dict[int, int], boosts: Optional[dict[int, list[int]]] = None,
          losses: Optional[dict[int, float]] = None) -> None:
    """Play from the campaign's next mission to mission ``last``, recording each one's first-try chance and tries,
    the Math Boosts in its first-try battles and the share of the fleet those battles lost."""
    while c.mission_number <= last:
        n = c.mission_number
        for attempt in range(1, MAX_TRIES + 1):
            workshop(c, player, rng)
            counts: list[int] = []
            lost: list[float] = []
            wins = _first_try_wins(c, samples, player, counts, lost) if attempt == 1 else 0
            battle, count = fight(c, player)
            if attempt == 1:
                first[n] = (wins + (battle.winner == 0)) / (samples + 1)
                if boosts is not None:
                    boosts[n] = counts + [count]
                if losses is not None:
                    losses[n] = (sum(lost) + fleet_lost(battle)) / (samples + 1)
            c.apply_result(battle)
            if battle.winner == 0:
                tries[n] = attempt
                break
        else:  # stuck: move on to the next mission anyway
            tries[n] = MAX_TRIES + 1
            c.mission_number, c.attempts = n + 1, 0


def play_campaign(player: Player, index: int, seed: int, last: int, samples: int) -> tuple[dict, dict, dict]:
    """One modeled player's campaign up to mission ``last``: ({mission: first-try chance}, {mission: tries},
    {mission: Math Boosts in each first-try battle})."""
    r = play_campaign_record(player, index, seed, last, samples)
    return r["first"], r["tries"], r["boosts"]


def play_campaign_record(player: Player, index: int, seed: int, last: int, samples: int) -> dict:
    """:func:`play_campaign`, plus each mission's share of the fleet lost in its first-try battles ("losses"),
    everything the player bought ("bought": upgrade track, ship class or class/retrofit -> how many) and the
    currency it was left holding ("bank")."""
    c, rng = _new_player(index, seed)
    first: dict[int, float] = {}
    tries: dict[int, int] = {}
    boosts: dict[int, list[int]] = {}
    losses: dict[int, float] = {}
    _play(c, player, rng, last, samples, first, tries, boosts, losses)
    return {"first": first, "tries": tries, "boosts": boosts, "losses": losses,
            "bought": dict(c.stats.get("model_bought", {})), "bank": dict(c.currency),
            "earned": dict(c.stats.get("earned", {}))}


@contextmanager
def red_fleet(number: int, fleet: Fleet) -> Iterator[None]:
    """Mission ``number`` with a different Red fleet, for trying one out."""
    name, text, enemy, gained = cm._MISSIONS[number - 1]
    cm._MISSIONS[number - 1] = (name, text, list(fleet), gained)
    try:
        yield
    finally:
        cm._MISSIONS[number - 1] = (name, text, enemy, gained)


def try_fleets(player: Player, index: int, seed: int, number: int, fleets: list[Fleet], samples: int) -> list[float]:
    """One modeled player plays up to mission ``number``, then each fleet is tried there from the same start:
    the same problems are answered, then ``samples`` first-try battles are fought. Returns each fleet's wins."""
    c, rng = _new_player(index, seed)
    _play(c, player, rng, number - 1, 0, {}, {})
    state = rng.getstate()
    out = []
    for fleet in fleets:
        with red_fleet(number, fleet):
            trial = copy.deepcopy(c)
            rng.setstate(state)
            workshop(trial, player, rng)
            out.append(_first_try_wins(trial, samples, player) / samples)
    return out


def _map(fn, args: list[tuple], jobs: int) -> list:
    if jobs <= 1:
        return [fn(*a) for a in args]
    with Pool(jobs) as pool:
        return pool.starmap(fn, args)


# --------------------------------------------------------------------------- command line


def parse_fleet(text: str) -> Fleet:
    """``"dreadnought:1,destroyer:2"`` -> [("dreadnought", 1), ("destroyer", 2)]."""
    fleet = []
    for part in text.split(","):
        cid, _, count = part.strip().partition(":")
        try:
            ship_design(cid)
            fleet.append((cid, int(count or 1)))
        except (KeyError, ValueError):
            raise argparse.ArgumentTypeError(f"not a ship and count: {part!r}") from None
    if not 1 <= len(fleet) <= 6:
        raise argparse.ArgumentTypeError("a Red fleet has 1 to 6 stacks")
    return fleet


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m seabattle.balance", description="Campaign balance: a modeled player's win rates, mission by mission."
    )
    parser.add_argument("--problems", type=int, default=PROBLEMS, help="problems between missions (default: %(default)s)")
    parser.add_argument("--accuracy", type=float, default=0.8, help="share of problems answered right (default: %(default)s)")
    parser.add_argument("--difficulty", type=int, default=2, choices=sorted(LEVELS), help="difficulty level (default: 2)")
    parser.add_argument("--boost", type=float, metavar="ACCURACY",
                        help="fight with Math Boost on, answering this share of its problems right (e.g. 0.8)")
    parser.add_argument("--players", type=int, default=16, help="modeled players (default: %(default)s)")
    parser.add_argument("--samples", type=int, default=4,
                        help="extra first-try battles per player and mission (default: %(default)s)")
    parser.add_argument("--last", type=int, default=cm.MISSION_COUNT, help="last mission to play (default: %(default)s)")
    parser.add_argument("--seed", type=int, default=1, help="another seed gives other players and maps (default: 1)")
    parser.add_argument("--jobs", type=int, default=os.cpu_count() or 1, help="processes to use (default: all cores)")
    parser.add_argument("--mission", type=int, help="play up to this mission, then try each --fleet there")
    parser.add_argument("--fleet", type=parse_fleet, action="append", default=[],
                        help="a Red fleet to try at --mission, e.g. dreadnought:1,destroyer:2 (repeatable)")
    parser.add_argument("--json", metavar="PATH", help="also write every player's record to this JSON file")
    args = parser.parse_args(argv)
    player = Player(args.problems, args.accuracy, args.difficulty, args.boost)
    boost = f" Math Boost on, {player.boost:.0%} right." if player.boost is not None else ""
    print(f"Modeled player: {player.problems} problems between missions ({player.problems * SUPER_WORK} before a super "
          f"mission) at difficulty {player.difficulty}, {player.accuracy:.0%} right; {args.players} players, "
          f"seed {args.seed}.{boost}")

    if args.mission:
        if not args.fleet:
            parser.error("--mission needs at least one --fleet")
        n = args.mission
        rows = _map(try_fleets, [(player, i, args.seed, n, args.fleet, max(1, args.samples))
                                 for i in range(args.players)], args.jobs)
        print(f"Mission {n}, {cm.mission(n).name}: first-try wins for each Red fleet")
        for k, fleet in enumerate(args.fleet):
            rate = sum(r[k] for r in rows) / len(rows)
            print(f"  {rate:4.0%}  " + ", ".join(f"{cid} {count}" for cid, count in fleet))
        return 0

    records = _map(play_campaign_record, [(player, i, args.seed, args.last, args.samples)
                                          for i in range(args.players)], args.jobs)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump({"seed": args.seed, "players": records}, f)
    print(f"  #  {'Mission':24} first try  tries   lost" + ("  boosts" if boost else ""))
    total = 0.0
    for n in range(1, args.last + 1):
        m = cm.mission(n)
        first = [r["first"][n] for r in records if n in r["first"]]
        tries = [r["tries"][n] for r in records if n in r["tries"]]
        lost = [r["losses"][n] for r in records if n in r["losses"]]
        mean = sum(tries) / len(tries)
        total += mean * player.problems_before(m)
        counts = [k for r in records for k in r["boosts"].get(n, [])]
        extra = f"  {sum(counts) / len(counts):6.1f}" if boost and counts else ""
        name = m.name + (" (super)" if m.is_super else "")
        print(f"{n:3}  {name:24} {sum(first) / len(first):8.0%} {mean:6.2f} {sum(lost) / len(lost):6.0%}{extra}")
    print(f"About {total / args.last:.0f} problems per mission won, missions 1-{args.last}. "
          "Lost: the share of the fleet's hull sunk in a first-try battle.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
