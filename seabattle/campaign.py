"""Campaign mode: your Blue fleet against progressively stronger Red fleets.

Between missions you are in the workshop: solve math problems to earn
currency, then spend it on fleet upgrades, new ships and repairs. Ships sunk
in battle are not gone for good. They are towed home as wrecks that can be
repaired. A lost or abandoned mission can simply be tried again, so progress
is never lost, and the dockyards repair half the ships it sank for free: the
repair bill grows, but one defeat doesn't leave the fleet too weak to retry.
Missions already won can be replayed as skirmishes: practice battles with a
small prize and no repair bill.

The campaign has three acts of ten missions. Winning mission 10 ends Act I
and opens Plasma: a fifth currency with two math topics of its own, spent in
Act II on Future Tech and on retrofitting Act I's ship classes with it.
Winning the Kraken (mission 20) opens Act III, ten missions in which Red fields
the same future tech, and the Plasma ship classes; then come endless patrols.

Missions 10, 20 and 30 are super missions, one at the end of each act: Red's
biggest fleets yet, harder than the missions after them, longer battles with up
to 25 Math Boosts, and twice the prize money. A player can expect to need more
than one try.

A kind of problem the player gets wrong comes back for review a couple of
problems later, with new numbers, until they get one right. The campaign also
remembers the last few answers to each kind of problem for the Logbook.

Missions can be fought with Math Boost on (see ``boost.py``): the setting is
chosen on the mission briefing and kept with the campaign.

Everything here is plain data and rules (no pygame) and is saved as JSON.
"""

from __future__ import annotations

import json
import math
import os
import random
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from .battle import MAX_STACKS_PER_SIDE, Battle
from .boost import MAX_PER_BATTLE, MAX_PER_SUPER_MISSION
from .design import ShipDesign
from .designs import RED_SHIPS
from .economy import (
    CURRENCIES, NANITE_REPAIR_SHARE, PLASMA_MISSION, REPAIR_SHARE, RETROFITS, SHIP_CLASSES, STARTING_CLASSES, TRACKS, Cost,
    ShipClass, class_of, refit, retrofit, ship_design,
)
from .problems import LEVELS, SCHOOLS, TOPICS, Context, ShipRef, generator_named, penalty, reward
from .scenarios import HEIGHT, ISLANDS, WIDTH, generate_islands

SAVE_VERSION = 2  # 2: Act III; missions 21 and up are no longer patrols
SLOTS = (1, 2, 3)
MAX_SHIPS_PER_CLASS = 20
STARTING_FLEET = {"picket": 3, "torpedo_boat": 2}
STARTING_CURRENCY = {"steel": 30, "powder": 30, "fuel": 30, "blueprints": 20}
SHIP_NAMES = [
    "Kestrel", "Harrier", "Tempest", "Marlin", "Osprey", "Sabre", "Cormorant", "Aurora", "Valiant", "Intrepid",
    "Resolute", "Dauntless", "Stingray", "Barracuda", "Thunderhead", "Vigilant", "Sentinel", "Talon", "Endeavour",
    "Meridian",
]
RED_NAMES = ["Kraken", "Basilisk", "Vulture", "Scorpion", "Harpy", "Wraith", "Gorgon", "Viper", "Hydra", "Manticore"]
REVIEW_GAP = 2  # a kind of problem you got wrong comes back after this many other problems
REVIEW_MAX = 12  # most kinds of problem waiting for review at once
SKILL_MEMORY = 10  # answers remembered for each kind of problem


# --------------------------------------------------------------------------- missions


SKIRMISH_PAY = 0.1  # replaying a mission already won pays this share of its prize money
# The super missions, one at the end of each act: much harder, longer battles, more Math Boosts.
# What winning each one opens: (said on its briefing, said when it is won).
SUPER_REWARDS = {
    10: ("Win it to open Act II and Plasma: future tech, retrofits and two new math topics.",
         "Act II begins, and Plasma is open: future tech, retrofits and two new math topics."),
    20: ("Win it to open Act III and the Plasma ship classes.",
         "Act III begins, and the Plasma ship classes are open in the Shipyard."),
    30: ("Win it and the sea is yours.", "The sea is yours. Endless patrols follow."),
}
SUPER_MISSIONS = tuple(SUPER_REWARDS)
SUPER_PRIZE = 2  # a super mission pays this many times the prize money
# Share of the ships sunk (rounded down) that the dockyards repair for free: after a super mission, win or lose,
# and after any lost or abandoned mission, so one defeat doesn't leave the fleet too weak to win the retry.
DOCKYARD_REPAIRED = 0.5
# Red's dockyards are no faster: of the Red escorts a lost battle sinks, this share (rounded down) stays sunk for
# the next try at that mission. A squadron never drops below this share of its full strength (rounded up), so
# withdrawing early again and again can't grind a mission down to nothing, and super ships are always repaired.
RED_STAY_SUNK = 0.5
RED_WEAR_COST = 0.25  # ...and only after a real fight: one that cost the player this share of its fleet's hull


@dataclass(frozen=True)
class Mission:
    number: int
    name: str
    briefing: str
    enemy: tuple[tuple[str, int], ...]  # (ship class id, count) per Red stack
    tech: dict[str, int] = field(default_factory=dict, hash=False)  # Red upgrade levels

    @property
    def is_super(self) -> bool:
        """A super mission: Red's biggest fleet of its act, a longer battle with more math in it."""
        return self.number in SUPER_MISSIONS

    @property
    def opens(self) -> str:
        """What winning this super mission opens, for its briefing ("" for other missions)."""
        return SUPER_REWARDS.get(self.number, ("", ""))[0]

    @property
    def boosts(self) -> int:
        """The most Math Boosts this mission's battle offers."""
        return MAX_PER_SUPER_MISSION if self.is_super else MAX_PER_BATTLE

    @property
    def title(self) -> str:
        """"Mission 12" or "Super Mission 10"."""
        return f"{'Super Mission' if self.is_super else 'Mission'} {self.number}"

    @property
    def bounty(self) -> Cost:
        """Prize money for winning, on top of what the workshop earns. Plasma too, once it has opened.
        A super mission pays twice as much."""
        n = self.number
        prize = {"steel": 10 + 5 * n, "powder": 10 + 5 * n, "fuel": 10 + 5 * n, "blueprints": 5 + 3 * n}
        if n >= PLASMA_MISSION - 1:  # from the win that opens Plasma: the first plasma to spend
            prize["plasma"] = 3 * n - 20
        return {c: v * SUPER_PRIZE for c, v in prize.items()} if self.is_super else prize

    @property
    def skirmish_prize(self) -> Cost:
        """Prize money for winning this mission again as a skirmish (rounded up)."""
        return {c: math.ceil(v * SKIRMISH_PAY) for c, v in self.bounty.items()}


# (name, briefing, Red fleet as (ship id, count) per stack, upgrades Red gains at this mission).
# Red keeps every upgrade it has gained, so its technology depends only on how far
# the campaign has got, never on the player's fleet. Red's Act I upgrades stop at level 2.
# Balanced so that about 15 problems between missions (difficulty 2, most answers right)
# keeps a fleet in the fight: check changes with ``python -m seabattle.balance``.
_MISSIONS = [
    # Act I
    ("Harbor Patrol", "Two Red picket boats are snooping around the harbor mouth. Chase them off.",
     [("picket", 2)], {}),
    ("Smugglers' Run", "A Red smuggling convoy is slipping past the islands with an armed escort.",
     [("picket", 3), ("torpedo_boat", 3)], {}),
    ("Torpedo Alley", "A swarm of Red torpedo boats lurks in the straits. Don't let them get close.",
     [("torpedo_boat", 9), ("picket", 4)], {}),
    ("The Destroyer Screen",
     "Red has sent its first real warships: destroyers, with a screen of picket boats. "
     "Their torpedoes run under armor belts.",
     [("destroyer", 3), ("picket", 8)], {}),
    ("Night Raiders", "Fast destroyers with improved torpedoes are raiding the coast at night.",
     [("destroyer", 5), ("torpedo_boat", 8)], {"torp_speed": 1}),
    ("Cruiser Sighted", "Red light cruisers lead this squadron. Their 6-inch guns outrange yours.",
     [("light_cruiser", 2), ("destroyer", 4), ("picket", 7)], {}),
    ("The Iron Wall", "Red's ships now carry thicker armor. Light guns will bounce off.",
     [("light_cruiser", 2), ("destroyer", 5)], {"belt": 1, "armor": 1}),
    ("Wolf Pack", "Two packs of torpedo boats with bigger warheads. Keep your distance, or shoot them down.",
     [("torpedo_boat", 6), ("torpedo_boat", 6), ("destroyer", 2)], {"warheads": 1, "tubes": 1}),
    ("Battleship!", "A Red battleship has left port. Its 12-inch guns can sink anything you own.",
     [("battleship", 1), ("destroyer", 3)], {"fire_control": 1}),
    ("Cruiser Squadron", "Red's whole cruiser squadron is hunting your fleet: three light cruisers, with destroyers "
     "and picket boats screening them.",
     [("light_cruiser", 3), ("destroyer", 6), ("picket", 6)], {"caliber": 1}),
    # Act II: Plasma and the player's Future Tech.
    ("The Missile Age", "Red has built missile cruisers. Their missiles strike from across the map.",
     [("missile_cruiser", 2), ("destroyer", 3), ("torpedo_boat", 2)], {"interdiction": 1}),
    ("The Flagship", "Red's flagship puts to sea with its destroyer escort. Sink it, and Red will open its "
     "secret shipyards.",
     [("battleship", 1), ("destroyer", 2)], {}),
    # Red's super ships arrive.
    ("The Dreadnought", "Red's first dreadnought: 16-inch guns and armor thicker than anything you can build.",
     [("dreadnought", 1)], {"damage_control": 1}),
    ("Hunter-Killers", "Missile cruisers and torpedo boats hunt in packs, striking from long range.",
     [("missile_cruiser", 2), ("torpedo_boat", 6), ("destroyer", 4)], {}),
    ("Leviathan Rising", "The Leviathan, a missile battlecruiser as fast as your cruisers, leads the attack.",
     [("leviathan", 1), ("light_cruiser", 2), ("destroyer", 4)], {}),
    ("Twin Dreadnoughts", "Two dreadnoughts steam side by side, with a screen of destroyers to keep your torpedo "
     "boats off them.",
     [("dreadnought", 2), ("destroyer", 5)], {}),
    ("The Swarm", "Red floods the sea with small boats around a Leviathan. Every torpedo counts.",
     [("leviathan", 1), ("torpedo_boat", 9), ("torpedo_boat", 9), ("destroyer", 4), ("picket", 8)],
     {"warheads": 2, "armor": 2}),
    ("Battle of the Straits", "A dreadnought and a Leviathan force the straits together.",
     [("dreadnought", 1), ("leviathan", 1), ("destroyer", 4)], {"caliber": 2, "turrets": 1}),
    ("Siege of Red Harbor", "You have reached Red's home harbor. A Leviathan and two battleships guard the entrance, "
     "with every cruiser and destroyer in port.",
     [("leviathan", 1), ("battleship", 2), ("light_cruiser", 2), ("destroyer", 4)], {}),
    ("The Kraken", "The Kraken, Red's floating fortress, sails out with its last dreadnought and its last "
     "Leviathan. Sink it, and its wreck may hold Red's last secrets.",
     [("kraken", 1), ("dreadnought", 1), ("leviathan", 1)], {"belt": 2, "fire_control": 2, "interdiction": 2}),
    # Act III: Red fields future tech, one new technology a mission.
    ("Salvage Rights", "The Kraken's escorts are back to claim its wreck, and whatever Red was building inside it.",
     [("battleship", 3), ("missile_cruiser", 5), ("light_cruiser", 4), ("destroyer", 11)], {}),
    ("Strange Lights", "Red destroyers now carry laser cannons. Lasers burn straight through armor belts.",
     [("destroyer", 24), ("light_cruiser", 6)], {"lasers": 1}),
    ("The Shimmer", "Red cruisers shimmer behind force fields that refill every turn. Hit one ship with "
     "everything at once, or send torpedoes under the fields.",
     [("light_cruiser", 10), ("destroyer", 14)], {"fields": 1}),
    ("Ghost Fleet", "Red's missile cruisers hide among holograms: some of your shots will hit nothing at all.",
     [("missile_cruiser", 5), ("destroyer", 13), ("torpedo_boat", 19)], {"decoys": 1, "lasers": 2}),
    ("Plasma Run", "Swarms of torpedo boats armed with plasma torpedoes. Plasma fades as it runs: keep your distance.",
     [("torpedo_boat", 19), ("torpedo_boat", 19), ("destroyer", 10)], {"plasma_torps": 1}),
    ("The Tempest", "The Tempest, a laser super ship, leads the attack. Ion beams drain force fields fast.",
     [("tempest", 1), ("battleship", 1), ("light_cruiser", 4), ("destroyer", 8)], {"fields": 2, "ion": 1}),
    ("Rail Line", "Red battleships with railguns: their shells go through half of any armor belt.",
     [("battleship", 2), ("missile_cruiser", 3), ("destroyer", 6)], {"railguns": 1, "point_defense": 1}),
    ("Graviton Storm", "Graviton beams carry their overkill from ship to ship. Big stacks of small boats suffer most.",
     [("leviathan_mk2", 1), ("destroyer", 8), ("torpedo_boat", 12), ("light_cruiser", 1)], {"graviton": 1, "lasers": 3}),
    ("The Gauntlet", "The Tempest and a Leviathan Mk II together, with every trick Red has learned.",
     [("tempest", 1), ("leviathan_mk2", 1), ("destroyer", 2)], {"fields": 3, "decoys": 2}),
    ("The Maelstrom", "The Maelstrom, a sea fortress armed with everything Red knows, comes for you with two "
     "Leviathan Mk IIs and a screen of destroyers. Win this and the sea is yours.",
     [("maelstrom", 1), ("leviathan_mk2", 2), ("destroyer", 6)],
     {"fields": 4, "ion": 2, "plasma_torps": 2, "decoys": 3, "railguns": 2, "point_defense": 2, "graviton": 2}),
]
ACTS = (1, 11, 21)  # the first missions of Act I, Act II and Act III
# After the last scripted mission, each patrol's escort is 6% bigger than the one before. They grow from the
# Maelstrom and an escort a little stronger than Act III's, not from the whole fleet of super mission 30, so
# Patrol 1 is a little harder than mission 28, the last regular mission before the Maelstrom.
ENDLESS_GROWTH = 1.06
PATROL_FLEET = (("maelstrom", 1), ("destroyer", 15), ("light_cruiser", 6))


def red_tech(number: int) -> dict[str, int]:
    """Red's upgrade levels at mission ``number``: everything gained so far.
    Red's technology tops out with the last scripted mission."""
    tech: dict[str, int] = {}
    for _, _, _, gained in _MISSIONS[:number]:
        for track, level in gained.items():
            tech[track] = max(tech.get(track, 0), level)
    return tech


def red_design(ship_id: str, tech: dict[str, int]) -> ShipDesign:
    """A Red ship with Red's upgrades. Damage control can't keep up with a super
    ship's size, so those never repair themselves in battle (``refit`` sees to that)."""
    return refit(ship_design(ship_id), tech)


def grow_escorts(enemy: list[tuple[str, int]], factor: float) -> tuple[tuple[str, int], ...]:
    """``enemy`` with ``factor`` times as many escorts in each stack (rounded); super ships stay as they are.

    The escorts carry most of a fleet's firepower, so they are what grows. Growing the hull
    instead, with the super ship fixed, would pile all of it on the escorts: a fleet 20% bigger
    by hull had eight times the escort, and the patrols hit a wall at the third."""
    return tuple((cid, n if cid in RED_SHIPS else max(n, round(n * factor))) for cid, n in enemy)


def mission(number: int) -> Mission:
    """Mission ``number`` (1-based). After the scripted missions, Red keeps getting stronger."""
    if number <= len(_MISSIONS):
        name, text, enemy, _ = _MISSIONS[number - 1]
        return Mission(number, name, text, tuple(enemy), red_tech(number))
    extra = number - len(_MISSIONS)
    tech = red_tech(number)
    return Mission(
        number, f"Patrol {extra}", "Red keeps rebuilding. Each patrol brings 6% more escorts than the last.",
        grow_escorts(list(PATROL_FLEET), ENDLESS_GROWTH ** extra), tech,
    )


MISSION_COUNT = len(_MISSIONS)


# --------------------------------------------------------------------------- battle reports


@dataclass
class Report:
    outcome: str  # "victory" | "defeat" | "withdrew" | "draw"
    mission: Mission
    sunk: dict[str, int]  # Blue ships sunk: wrecks after a mission (but see ``repaired``), repaired for free after a skirmish
    bounty: Cost
    next_mission: Optional[Mission]
    skirmish: bool = False
    repaired: dict[str, int] = field(default_factory=dict)  # of ``sunk``, the ones the dockyards repair for free
    red_gone: int = 0  # Red ships this lost battle sank that stay sunk for the next try

    @property
    def won(self) -> bool:
        return self.outcome == "victory"

    def lines(self) -> list[str]:
        lines = []

        def listed(counts: dict[str, int]) -> str:
            return ", ".join(f"{n} {SHIP_CLASSES[c].name}{'s' if n > 1 else ''}" for c, n in counts.items() if n)

        ships = listed(self.sunk)
        prize = "Prize money: " + ", ".join(f"+{v} {c.title()}" for c, v in self.bounty.items())
        if self.skirmish:
            result = {"victory": "won", "defeat": "lost", "withdrew": "abandoned", "draw": "drawn"}[self.outcome]
            lines.append(f"Skirmish {result}: {self.mission.title}, {self.mission.name}.")
            if self.won:
                lines.append(prize)
            if self.sunk:
                lines.append(f"Back in port and repaired for free: {ships}.")
            if self.next_mission:
                lines.append(f"Next: {self.next_mission.title}, {self.next_mission.name}.")
            return lines
        if self.won:
            lines.append(f"{self.mission.title} complete: {self.mission.name}.")
            if self.mission.is_super:
                lines.append(SUPER_REWARDS[self.mission.number][1])
            lines.append(prize)
        else:
            lines.append(f"{self.mission.title} failed. Your fleet returns to port to regroup.")
        wrecked = {c: n - self.repaired.get(c, 0) for c, n in self.sunk.items()}
        if any(self.repaired.values()):
            which = "a super mission" if self.mission.is_super else "a lost mission"
            lines.append(f"The dockyards repair half the ships {which} sinks, for free: {listed(self.repaired)}.")
        if self.red_gone:
            lines.append(f"Red's dockyards are no faster than yours: {self.red_gone} of the Red ships you sank "
                         f"{'stays' if self.red_gone == 1 else 'stay'} sunk for your next try.")
        if any(wrecked.values()):
            lines.append(f"Towed home for repairs: {listed(wrecked)}.")
        elif not self.sunk and self.outcome != "draw":
            lines.append("No ships were lost.")
        if self.next_mission and self.won:
            lines.append(f"Next: {self.next_mission.title}, {self.next_mission.name}.")
        else:
            lines.append("Repair and upgrade in the workshop, then try again.")
        return lines


# --------------------------------------------------------------------------- campaign state


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


@dataclass
class Campaign:
    slot: int
    created: str = field(default_factory=_now)
    updated: str = field(default_factory=_now)
    currency: dict[str, int] = field(default_factory=lambda: dict(STARTING_CURRENCY))
    fleet: dict[str, int] = field(default_factory=lambda: dict(STARTING_FLEET))
    wrecks: dict[str, int] = field(default_factory=dict)
    upgrades: dict[str, int] = field(default_factory=dict)
    unlocked: list[str] = field(default_factory=lambda: list(STARTING_CLASSES))
    mission_number: int = 1  # the next mission to fight
    attempts: int = 0  # tries at the current mission (varies the map)
    difficulty: dict[str, int] = field(default_factory=lambda: {s: 2 for s in SCHOOLS})  # per school, 1-5
    topics: list[str] = field(default_factory=lambda: list(TOPICS))  # topics switched on in the workshop
    streak: int = 0  # correct answers in a row (not saved, like the original games)
    stats: dict[str, dict[str, int]] = field(default_factory=dict)
    review: dict[str, int] = field(default_factory=dict)  # missed kind of problem -> problems to wait before it returns
    skills: dict[str, str] = field(default_factory=dict)  # kind of problem -> its latest results, oldest first ("1" right)
    notice: str = ""  # message for the workshop, e.g. after a failed mission
    in_port: list[str] = field(default_factory=list)  # classes the player keeps out of battle
    lessons: list[str] = field(default_factory=list)  # the last battle's debrief, shown at the next briefing
    boost: bool = False  # fight missions with Math Boost on
    retrofits: dict[str, list[str]] = field(default_factory=dict)  # Act I class -> the retrofits fitted to it
    red_worn: dict = field(default_factory=dict)  # {"mission": n, "ships": [per Red stack]}: Red ships still sunk from lost tries

    # ---- what has opened -----------------------------------------------------------

    @property
    def plasma_open(self) -> bool:
        """Plasma, its two math topics and Future Tech open at mission PLASMA_MISSION (when mission 10 is won)."""
        return self.mission_number >= PLASMA_MISSION

    @property
    def currencies(self) -> tuple[str, ...]:
        """The currencies in play so far."""
        return tuple(c for c in CURRENCIES if c != "plasma" or self.plasma_open)

    def topic_open(self, topic: str) -> bool:
        return TOPICS[topic].currency in self.currencies

    # ---- money ------------------------------------------------------------------

    def balance(self, currency: str) -> int:
        return self.currency.get(currency, 0)

    def can_afford(self, cost: Cost) -> bool:
        return all(self.balance(c) >= v for c, v in cost.items())

    def _pay(self, cost: Cost) -> None:
        for c, v in cost.items():
            self.currency[c] = self.balance(c) - v

    def _earn(self, cost: Cost) -> None:
        for c, v in cost.items():
            self.currency[c] = self.balance(c) + v
            self._count("earned", c, v)

    def _count(self, group: str, key: str, n: int = 1) -> None:
        self.stats.setdefault(group, {})
        self.stats[group][key] = self.stats[group].get(key, 0) + n

    # ---- workshop: math ---------------------------------------------------------

    def answer(self, topic: str, tier: int, correct: bool, generator: Optional[str] = None) -> int:
        """Record an answer to a problem. Returns the currency gained, or a negative
        number for what a wrong answer cost (balances never go below zero).

        ``generator`` names the kind of problem, for reviews and the Logbook."""
        self._count("attempted", topic)
        self._count("tier_attempted", f"{topic}:{tier}")
        if correct:
            self._count("tier_solved", f"{topic}:{tier}")
        if generator:
            self._remember(generator, correct)
        currency = TOPICS[topic].currency
        if not correct:
            self.streak = 0
            lost = min(penalty(topic, tier), self.balance(currency))
            self.currency[currency] = self.balance(currency) - lost
            self._count("lost", currency, lost)
            return -lost
        self._count("solved", topic)
        self.streak += 1
        amount = reward(topic, tier, self.streak)
        self.stats.setdefault("records", {})
        self.stats["records"]["best_streak"] = max(self.stats["records"].get("best_streak", 0), self.streak)
        self._earn({currency: amount})
        return amount

    def _remember(self, generator: str, correct: bool) -> None:
        """Keep the latest results for this kind of problem, and schedule a review after a miss."""
        self.skills[generator] = (self.skills.get(generator, "") + ("1" if correct else "0"))[-SKILL_MEMORY:]
        for g in self.review:  # every answer brings the waiting reviews one problem closer
            self.review[g] = max(0, self.review[g] - 1)
        if correct:
            self.review.pop(generator, None)
        elif generator in self.review or len(self.review) < REVIEW_MAX:
            self.review[generator] = REVIEW_GAP

    def due_review(self, topics: list[str]) -> Optional[str]:
        """A kind of problem the player missed that is due to come back, among ``topics``."""
        due = [g for g, wait in self.review.items() if wait <= 0 and (gen := generator_named(g)) and gen.topic in topics]
        return due[0] if due else None

    def record(self, group: str, key: str) -> tuple[int, int]:
        """(solved, attempted) for a topic (``group`` "topic") or a topic:tier (``group`` "tier")."""
        prefix = "" if group == "topic" else "tier_"
        return self.stats.get(prefix + "solved", {}).get(key, 0), self.stats.get(prefix + "attempted", {}).get(key, 0)

    def set_difficulty(self, school: str, level: int) -> None:
        self.difficulty[school] = min(max(LEVELS), max(min(LEVELS), level))

    def record_boost(self, correct: bool) -> None:
        """A Math Boost problem answered in battle, for the Logbook."""
        self._count("boost", "attempted")
        if correct:
            self._count("boost", "solved")

    def toggle_topic(self, topic: str) -> Optional[str]:
        """Switch a topic on or off; at least one topic of the school must stay on."""
        if not self.topic_open(topic):
            return f"{TOPICS[topic].name} opens with Plasma when you win mission {PLASMA_MISSION - 1}."
        if topic in self.topics:
            if len(self.school_topics(TOPICS[topic].school)) <= 1:
                return "Keep at least one topic on."
            self.topics.remove(topic)
        else:
            self.topics.append(topic)
        return None

    def school_topics(self, school: str) -> list[str]:
        """The school's topics that are switched on (and open)."""
        return [t for t in TOPICS if t in self.topics and TOPICS[t].school == school and self.topic_open(t)]

    def problem_context(self, rng: random.Random) -> Context:
        """Names and speeds of your own ships, for the word problems."""
        fleet: list[ShipRef] = []
        for cls, n in self.ready_fleet():
            for i in range(min(n, 3)):
                name = SHIP_NAMES[(list(SHIP_CLASSES).index(cls.id) * 3 + i) % len(SHIP_NAMES)]
                fleet.append(ShipRef(f"USS {name}", cls.name.lower(), cls.knots, cls.crew))
        flagship = fleet[-1].name if fleet else "USS Kestrel"
        enemy = f"RNS {RED_NAMES[(self.mission_number - 1) % len(RED_NAMES)]}"
        return Context(rng, fleet, flagship, enemy)

    # ---- workshop: upgrades, ships, repairs ------------------------------------

    def level(self, track: str) -> int:
        return self.upgrades.get(track, 0)

    def upgrade_cost(self, track: str) -> Optional[Cost]:
        """Price of the next level, or None when the track is maxed out."""
        t = TRACKS[track]
        n = self.level(track)
        return None if n >= t.max_level else t.cost(n + 1)

    def upgrade_needs(self, track: str) -> list[str]:
        """What a track still needs before its first level can be bought: campaign progress and other upgrades."""
        t = TRACKS[track]
        needs = [f"a win at mission {t.requires_mission - 1}"] if self.mission_number < t.requires_mission else []
        return needs + [f"{TRACKS[r].name} {lv}" for r, lv in t.requires.items() if self.level(r) < lv]

    def buy_upgrade(self, track: str) -> Optional[str]:
        """Returns an error message, or None on success."""
        cost = self.upgrade_cost(track)
        if cost is None:
            return f"{TRACKS[track].name} is already fully upgraded."
        needs = self.upgrade_needs(track)
        if needs:
            return f"{TRACKS[track].name} needs " + " and ".join(needs) + "."
        if not self.can_afford(cost):
            return "Not enough " + self._missing(cost) + "."
        self._pay(cost)
        self.upgrades[track] = self.level(track) + 1
        return None

    def class_state(self, class_id: str) -> str:
        """'available', 'unlockable' (can pay to unlock) or 'mission' (needs campaign progress)."""
        if class_id in self.unlocked:
            return "available"
        if self.mission_number < SHIP_CLASSES[class_id].requires_mission:
            return "mission"
        return "unlockable"

    def unlock_class(self, class_id: str) -> Optional[str]:
        state = self.class_state(class_id)
        cls = SHIP_CLASSES[class_id]
        if state == "available":
            return f"{cls.name} is already unlocked."
        if state == "mission":
            return f"Win mission {cls.requires_mission - 1} to unlock the {cls.name}."
        if not self.can_afford(cls.unlock):
            return "Not enough " + self._missing(cls.unlock) + "."
        self._pay(cls.unlock)
        self.unlocked.append(class_id)
        return None

    def ships(self, class_id: str) -> int:
        return self.fleet.get(class_id, 0) + self.wrecks.get(class_id, 0)

    def class_limit(self, class_id: str) -> int:
        return SHIP_CLASSES[class_id].limit or MAX_SHIPS_PER_CLASS

    def buy_ship(self, class_id: str) -> Optional[str]:
        cls = SHIP_CLASSES[class_id]
        state = self.class_state(class_id)
        if state == "mission":
            return f"Win mission {cls.requires_mission - 1} to unlock the {cls.name}."
        if state != "available":
            return f"Unlock the {cls.name} first."
        if self.ships(class_id) >= self.class_limit(class_id):
            if cls.limit:
                return f"Your fleet can hold at most {cls.limit} {cls.name}s."
            return f"Your fleet can hold at most {MAX_SHIPS_PER_CLASS} ships of each class."
        if not self.can_afford(cls.price):
            return "Not enough " + self._missing(cls.price) + "."
        self._pay(cls.price)
        self.fleet[class_id] = self.fleet.get(class_id, 0) + 1
        return None

    def repair_cost(self, class_id: str) -> Cost:
        """An eighth of a new ship's price, or less with Nanite Repair."""
        share = NANITE_REPAIR_SHARE.get(self.level("nanite"), REPAIR_SHARE)
        return SHIP_CLASSES[class_id].repair_cost_at(share)

    def repair(self, class_id: str) -> Optional[str]:
        cls = SHIP_CLASSES[class_id]
        if self.wrecks.get(class_id, 0) <= 0:
            return f"No {cls.name} needs repairs."
        cost = self.repair_cost(class_id)
        if not self.can_afford(cost):
            return "Not enough " + self._missing(cost) + "."
        self._pay(cost)
        self.wrecks[class_id] -= 1
        if not self.wrecks[class_id]:
            del self.wrecks[class_id]
        self.fleet[class_id] = self.fleet.get(class_id, 0) + 1
        return None

    # ---- retrofits ---------------------------------------------------------------

    def class_design(self, class_id: str) -> ShipDesign:
        """A class as it sails: its retrofits, then the fleet's upgrades."""
        return refit(retrofit(SHIP_CLASSES[class_id].design, self.retrofits.get(class_id, ())), self.upgrades)

    def has_retrofit(self, class_id: str, retrofit_id: str) -> bool:
        return retrofit_id in self.retrofits.get(class_id, ())

    def retrofit_cost(self, class_id: str, retrofit_id: str) -> Cost:
        """One price for the whole class: bigger hulls cost more."""
        return RETROFITS[retrofit_id].cost(SHIP_CLASSES[class_id].design.hull.id)

    def retrofit_needs(self, class_id: str, retrofit_id: str) -> list[str]:
        """What a retrofit still needs: its future tech, and the class unlocked."""
        r, cls = RETROFITS[retrofit_id], SHIP_CLASSES[class_id]
        needs = [f"{TRACKS[r.requires].name} 1"] if self.level(r.requires) < 1 else []
        return needs + ([f"the {cls.name} unlocked"] if self.class_state(class_id) != "available" else [])

    def buy_retrofit(self, class_id: str, retrofit_id: str) -> Optional[str]:
        """Fit a retrofit to every ship of an Act I class, now and later. Returns an error message, or None."""
        cls, r = SHIP_CLASSES[class_id], RETROFITS[retrofit_id]
        if not cls.retrofittable:
            return f"The {cls.name} is built with future tech: only Act I's classes are retrofitted."
        if self.has_retrofit(class_id, retrofit_id):
            return f"Your {cls.name}s already have a {r.name}."
        needs = self.retrofit_needs(class_id, retrofit_id)
        if needs:
            return f"A {r.name} needs " + " and ".join(needs) + "."
        cost = self.retrofit_cost(class_id, retrofit_id)
        if not self.can_afford(cost):
            return "Not enough " + self._missing(cost) + "."
        self._pay(cost)
        fitted = set(self.retrofits.get(class_id, ())) | {retrofit_id}
        self.retrofits[class_id] = [k for k in RETROFITS if k in fitted]
        return None

    def _missing(self, cost: Cost) -> str:
        return " and ".join(c.title() for c, v in cost.items() if self.balance(c) < v)

    # ---- missions ---------------------------------------------------------------

    @property
    def mission(self) -> Mission:
        return mission(self.mission_number)

    def ready_fleet(self) -> list[tuple[ShipClass, int]]:
        return [(cls, self.fleet[cls.id]) for cls in SHIP_CLASSES.values() if self.fleet.get(cls.id, 0) > 0]

    def sailing_fleet(self) -> list[tuple[ShipClass, int]]:
        """The ships that sail: one stack per class, at most six. Classes the player keeps in port stay
        behind; if there are still more than six, the six with the most hull go."""
        ready = [(cls, n) for cls, n in self.ready_fleet() if cls.id not in self.in_port] or self.ready_fleet()
        if len(ready) <= MAX_STACKS_PER_SIDE:
            return ready
        hull = {cls.id: self.class_design(cls.id).max_hp * n for cls, n in ready}
        keep = set(sorted(hull, key=lambda cid: -hull[cid])[:MAX_STACKS_PER_SIDE])
        return [(cls, n) for cls, n in ready if cls.id in keep]

    def toggle_port(self, class_id: str) -> Optional[str]:
        """Keep a class in port, or send it back to sea. At least one class has to sail."""
        if class_id in self.in_port:
            self.in_port.remove(class_id)
            return None
        if not any(cls.id != class_id and cls.id not in self.in_port for cls, _ in self.ready_fleet()):
            return "At least one squadron has to sail."
        self.in_port.append(class_id)
        return None

    def can_skirmish(self, number: int) -> bool:
        """Missions already won can be replayed as skirmishes."""
        return 1 <= number < self.mission_number

    def _worn(self) -> list[int]:
        """Red ships of each squadron of the coming mission still sunk from earlier lost tries."""
        ships = self.red_worn.get("ships") if self.red_worn.get("mission") == self.mission_number else None
        return list(ships) if ships and len(ships) == len(self.mission.enemy) else [0] * len(self.mission.enemy)

    def red_fleet(self) -> list[tuple[str, int]]:
        """The coming mission's Red fleet, less the escorts earlier lost tries sank for good: half of what each
        lost battle sank (rounded down) stays sunk, down to half the squadron's strength (rounded up)."""
        return [(cid, n - min(gone, self._most_worn(cid, n))) for (cid, n), gone in zip(self.mission.enemy, self._worn())]

    @staticmethod
    def _most_worn(cid: str, n: int) -> int:
        """How many ships a squadron of ``n`` can be short at most: none for super ships."""
        return 0 if cid in RED_SHIPS else n - math.ceil(n * (1 - RED_STAY_SUNK))

    def _wear_red(self, battle: Battle) -> int:
        """After a lost try that cost the player a quarter of its fleet's hull or more, keep half the Red
        escorts it sank (rounded down) out of the next try. Returns how many that is."""
        red = sorted((s for s in battle.stacks.values() if s.side == 1), key=lambda s: s.id)
        before = self.red_fleet()
        if [s.start_count for s in red] != [n for _, n in before]:
            return 0  # not this mission's fleet
        blue = [s for s in battle.stacks.values() if s.side == 0]
        lost = sum((s.start_count - max(0, s.count)) * s.design.max_hp for s in blue)
        if lost < RED_WEAR_COST * sum(s.start_count * s.design.max_hp for s in blue):
            return 0  # a withdrawal before the fight cost anything: Red's dockyards keep up
        stay = [math.floor((s.start_count - max(0, s.count)) * RED_STAY_SUNK) for s in red]
        most = [self._most_worn(cid, n) for cid, n in self.mission.enemy]
        self.red_worn = {"mission": self.mission_number,
                         "ships": [min(w + k, cap) for w, k, cap in zip(self._worn(), stay, most)]}
        return sum(n for _, n in before) - sum(n for _, n in self.red_fleet())

    def build_battle(self, skirmish: Optional[int] = None) -> Battle:
        """The battle for the next mission, or with ``skirmish`` a replay of that mission."""
        if skirmish is None:
            m, tries = self.mission, self.attempts
        elif self.can_skirmish(skirmish):
            # Skirmish maps come from their own run of seeds, and change every time.
            m, tries = mission(skirmish), 50 + sum(self.stats.get("skirmishes", {}).values()) % 50
        else:
            raise ValueError(f"mission {skirmish} hasn't been won yet")
        seed = self.slot * 100_000 + m.number * 100 + tries
        blue = [(self.class_design(cls.id), n) for cls, n in self.sailing_fleet()]
        red = [(red_design(cid, m.tech), n) for cid, n in (self.red_fleet() if skirmish is None else m.enemy)]
        rng = random.Random(seed)
        islands = generate_islands(rng, WIDTH, HEIGHT, rng.randint(*ISLANDS))
        return Battle([blue, red], width=WIDTH, height=HEIGHT, islands=islands, seed=seed)

    def apply_result(self, battle: Battle, skirmish: Optional[int] = None) -> Report:
        """Update the campaign after a mission battle has ended.

        After a skirmish (a replay of mission ``skirmish``) sunk ships come home
        repaired, progress doesn't change, and only a win's small prize is paid.
        """
        blue = [s for s in battle.stacks.values() if s.side == 0]
        sunk: dict[str, int] = {}
        for s in blue:
            lost = s.start_count - max(0, s.count)
            if lost:
                cid = class_of(s.design.name).id
                sunk[cid] = sunk.get(cid, 0) + lost
        if battle.winner == 0:
            outcome = "victory"
        elif battle.winner is None:
            outcome = "draw"
        elif any(s.status == "retreated" for s in blue):
            outcome = "withdrew"
        else:
            outcome = "defeat"
        if skirmish is not None:
            m = mission(skirmish)
            prize = m.skirmish_prize if outcome == "victory" else {}
            self._earn(prize)
            self._count("skirmishes", "won" if outcome == "victory" else "lost")
            report = Report(outcome, m, sunk, prize, self.mission, skirmish=True)
            self.notice = " ".join(report.lines())
            return report
        m = self.mission
        free = m.is_super or outcome != "victory"
        repaired = {cid: math.floor(lost * DOCKYARD_REPAIRED) for cid, lost in sunk.items()} if free else {}
        for cid, lost in sunk.items():
            wrecked = lost - repaired.get(cid, 0)
            self.fleet[cid] = self.fleet.get(cid, 0) - wrecked
            if self.fleet[cid] <= 0:
                del self.fleet[cid]
            if wrecked:
                self.wrecks[cid] = self.wrecks.get(cid, 0) + wrecked
        bounty: Cost = {}
        gone = 0
        if outcome == "victory":
            bounty = m.bounty
            self._earn(bounty)
            self.mission_number += 1
            self.attempts = 0
            self.red_worn = {}
            self._count("battles", "won")
        else:
            gone = self._wear_red(battle)
            self.attempts += 1
            self._count("battles", "lost")
        report = Report(outcome, m, sunk, bounty, self.mission if outcome == "victory" else None, repaired=repaired,
                        red_gone=gone)
        self.notice = " ".join(report.lines())
        return report

    # ---- saving -----------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "version": SAVE_VERSION,
            "slot": self.slot,
            "created": self.created,
            "updated": self.updated,
            "currency": self.currency,
            "fleet": self.fleet,
            "wrecks": self.wrecks,
            "upgrades": self.upgrades,
            "unlocked": self.unlocked,
            "mission": self.mission_number,
            "attempts": self.attempts,
            "difficulty": self.difficulty,
            "topics": self.topics,
            "stats": self.stats,
            "review": self.review,
            "skills": self.skills,
            "notice": self.notice,
            "lessons": self.lessons,
            "in_port": self.in_port,
            "boost": self.boost,
            "retrofits": self.retrofits,
            "red_worn": self.red_worn,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Campaign":
        """Build a campaign from saved data, ignoring anything unknown or invalid."""
        c = cls(slot=int(data.get("slot", 1)))
        version = int(data.get("version", 1))

        def counts(raw, valid) -> dict[str, int]:
            return {k: int(v) for k, v in (raw or {}).items() if k in valid and int(v) > 0}

        c.created = str(data.get("created", c.created))
        c.updated = str(data.get("updated", c.updated))
        c.currency = {k: max(0, int(v)) for k, v in (data.get("currency") or {}).items() if k in CURRENCIES}
        c.fleet = counts(data.get("fleet"), SHIP_CLASSES)
        c.wrecks = counts(data.get("wrecks"), SHIP_CLASSES)
        c.upgrades = {k: min(int(v), TRACKS[k].max_level) for k, v in counts(data.get("upgrades"), TRACKS).items()}
        c.unlocked = [k for k in data.get("unlocked", STARTING_CLASSES) if k in SHIP_CLASSES]
        c.mission_number = max(1, int(data.get("mission", 1)))
        c.attempts = max(0, int(data.get("attempts", 0)))
        for school, level in (data.get("difficulty") or {}).items():
            if school in SCHOOLS:
                c.set_difficulty(school, int(level))
        topics = [t for t in data.get("topics", list(TOPICS)) if t in TOPICS]
        if version < 2:
            topics += [t for t in TOPICS if TOPICS[t].currency == "plasma" and t not in topics]  # new: on to start with
            if c.mission_number >= ACTS[2]:  # patrols past the Kraken are now Act III
                c.mission_number, c.attempts = ACTS[2], 0
        for school in SCHOOLS:  # every school keeps at least one topic that is open
            if not any(TOPICS[t].school == school and c.topic_open(t) for t in topics):
                topics += [t for t in TOPICS if TOPICS[t].school == school and t not in topics]
        c.topics = topics
        c.stats = {
            str(group): {str(k): v for k, v in counts.items() if type(v) is int}
            for group, counts in (data.get("stats") or {}).items() if isinstance(counts, dict)
        }
        c.review = {  # keyed by generator, under its current key if it has been renamed since
            g.key: min(REVIEW_GAP, max(0, int(v))) for k, v in (data.get("review") or {}).items() if (g := generator_named(k))
        }
        c.skills = {
            g.key: "".join(ch for ch in str(v) if ch in "01")[-SKILL_MEMORY:]
            for k, v in (data.get("skills") or {}).items() if (g := generator_named(k))
        }
        c.notice = str(data.get("notice", ""))
        c.lessons = [str(x) for x in (data.get("lessons") or []) if isinstance(x, str)][:3]
        c.in_port = [k for k in (data.get("in_port") or []) if k in SHIP_CLASSES]
        c.boost = data.get("boost") is True  # saves from before may also carry a "boost_level": no longer used
        for k, fitted in (data.get("retrofits") or {}).items():
            fitted = [r for r in RETROFITS if isinstance(fitted, list) and r in fitted]
            if k in SHIP_CLASSES and SHIP_CLASSES[k].retrofittable and fitted:
                c.retrofits[k] = fitted
        worn = data.get("red_worn")
        if isinstance(worn, dict) and worn.get("mission") == c.mission_number and isinstance(worn.get("ships"), list):
            ships = worn["ships"]
            if len(ships) == len(c.mission.enemy) and all(type(k) is int and k >= 0 for k in ships):
                c.red_worn = {"mission": c.mission_number, "ships": ships}
        return c


# --------------------------------------------------------------------------- save files


class SaveError(Exception):
    """A save slot that can't be played. The message says why, for the player.

    ``free`` is True when a new campaign can be started in the slot (a damaged
    file was set aside), False when the file is still there and must be kept:
    one another program has open, or one saved by a newer version of the game.
    """

    def __init__(self, message: str, free: bool = False) -> None:
        super().__init__(message)
        self.free = free


# What reading a damaged file can raise: bad JSON, wrong types, numbers too big for int().
_DAMAGED = (ValueError, TypeError, AttributeError, KeyError, OverflowError, RecursionError)


def user_dir() -> Path:
    """The game's folder for this user's data: where each system keeps app data, outside the game folder."""
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming") / "Master of Oceans"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Master of Oceans"
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "master-of-oceans"


def save_dir() -> Path:
    """Where save files live: ``saves`` in :func:`user_dir`, or SEABATTLE_SAVE_DIR if set."""
    env = os.environ.get("SEABATTLE_SAVE_DIR")
    if env:
        return Path(env)
    return user_dir() / "saves"


def old_save_dirs() -> list[Path]:
    """Where earlier versions kept saves: ``saves/`` in the game folder, or in the home folder."""
    return [Path(__file__).resolve().parent.parent / "saves", Path.home() / ".master_of_oceans" / "saves"]


def move_old_saves(sources: Optional[list[Path]] = None) -> list[Path]:
    """Move campaigns and settings from where earlier versions kept them into :func:`save_dir`.

    Earlier versions saved in the game folder, where downloading a new version
    or deleting the folder lost every campaign. A file the save folder already
    has is left where it was, and a note in the old folder says where the rest
    went. Returns the old folders that had files moved out of them.
    """
    if sources is None:
        if os.environ.get("SEABATTLE_SAVE_DIR"):
            return []  # saves are where they were asked to be
        sources = old_save_dirs()
    target = save_dir()
    emptied = []
    for old in sources:
        if not old.is_dir() or old.resolve() == target.resolve():
            continue
        moved = False
        for f in sorted(old.glob("campaign[0-9].json")) + sorted(old.glob("settings.json")):
            dest = target / f.name
            if dest.exists():
                continue
            try:
                target.mkdir(parents=True, exist_ok=True)
                shutil.move(str(f), str(dest))
            except OSError:
                continue
            moved = True
        if moved:
            emptied.append(old)
            note = f"Master of Oceans now keeps its saved campaigns in\n{target}\n"
            try:
                (old / "WHERE ARE MY SAVES.txt").write_text(note, encoding="utf-8")
            except OSError:
                pass
    return emptied


def slot_path(slot: int) -> Path:
    return save_dir() / f"campaign{slot}.json"


def _backup_path(path: Path) -> Path:
    return path.with_suffix(".bak")


def save(campaign: Campaign) -> Path:
    """Write the campaign to its slot.

    The data goes to a temp file that is flushed to disk and then swapped in,
    so a crash or power cut leaves the old save or the new one, never half of
    one. The save before it is kept as ``campaignN.bak`` for :func:`load` to
    fall back on if the file is ever damaged. Raises OSError if the file can't
    be written (a full disk, a folder that can't be written to).
    """
    campaign.updated = _now()
    path = slot_path(campaign.slot)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(campaign.to_dict(), f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    if path.exists():
        try:
            shutil.copyfile(path, _backup_path(path))
        except OSError:
            pass  # no backup this time; the save itself matters more
    os.replace(tmp, path)
    return path


def try_save(campaign: Campaign) -> Optional[str]:
    """:func:`save` for the game screens: None if it worked, else what went wrong, to show the player."""
    try:
        save(campaign)
    except OSError as exc:
        return f"Couldn't save the campaign ({exc.strerror or exc}). Your progress since the last save isn't kept."
    return None


def _read(path: Path) -> Campaign:
    """A campaign from a save file. Raises OSError, SaveError for a newer save, or one of _DAMAGED."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("not a campaign")
    if int(data.get("version", 1)) > SAVE_VERSION:
        raise SaveError("Saved by a newer version of Master of Oceans. Update the game to carry on with it.")
    return Campaign.from_dict(data)


def load(slot: int) -> Optional[Campaign]:
    """Load a slot; None if it is empty.

    Raises SaveError if the slot can't be played: the file can't be read (another
    program may have it open), or it was saved by a newer version of the game,
    which this one must not overwrite. A damaged file is set aside (renamed,
    never deleted) and the campaign comes back from its backup if that is good.
    """
    path = slot_path(slot)
    if not path.exists():
        return None
    try:
        campaign = _read(path)
    except OSError as exc:
        raise SaveError(f"Couldn't read the save file ({exc.strerror or exc}). "
                        "If another program has it open, close that and try again.") from exc
    except _DAMAGED:
        campaign = _restore(path)
    campaign.slot = slot
    return campaign


def _restore(path: Path) -> Campaign:
    """Set a damaged save aside and bring its campaign back from the backup, if that is good."""
    backup = _backup_path(path)
    try:
        campaign: Optional[Campaign] = _read(backup) if backup.exists() else None
    except (OSError, SaveError, *_DAMAGED):
        campaign = None
    aside = path.with_suffix(f".damaged-{datetime.now():%Y%m%d%H%M%S}.json")
    try:
        path.replace(aside)
        if campaign is not None:
            shutil.copyfile(backup, path)
    except OSError as exc:
        raise SaveError(f"The save file is damaged and couldn't be set aside ({exc.strerror or exc}).") from exc
    if campaign is None:
        raise SaveError(f"The save file was damaged, so it was set aside as {aside.name}.", free=True)
    campaign.notice = "The save file was damaged, so this campaign was brought back from the save before it."
    return campaign


def delete(slot: int) -> None:
    path = slot_path(slot)
    for p in (path, _backup_path(path)):
        if p.exists():
            p.unlink()
