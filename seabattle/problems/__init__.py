"""Math problems for the workshop, from the Fleet Algebra and Broadside games.

Each of the ten topics pays out in one currency. Topics are paired so each
currency can be earned with either algebra or geometry:

    Steel       Navigation · Linear        Engineering · Area & Volume
    Powder      Gunnery · Quadratics       Gunnery · Trig
    Fuel        Intercept · Systems        Plot · Triangles
    Blueprints  Radar · Powers & Roots     Lookout · Angles
    Plasma      Reactor · Exponentials     Shields · Circles

Plasma and its two topics open at mission 10 (see ``Campaign.topic_open``).

The difficulty slider (1-5) picks how often easy (tier 1), medium (tier 2)
and hard (tier 3) problems come up. Every topic has the same base pay, so no
currency is cheaper to earn than another. Pay is tied to difficulty: the
base pay is multiplied by the problem's tier (x1, x1.75, x4). A multi-step
problem takes several times as long as a one-step one, so it pays several
times as much, and a student working at a harder level earns more even
though they get more wrong. The streak bonus is a share of the problem's pay
(+15% for each right answer in a row, up to +75%), so it grows with
difficulty too. A wrong answer costs 35% of what the problem would have
paid; with four choices, guessing comes out slightly below zero.
"""

from __future__ import annotations

import functools
import math
import random
from collections import deque
from dataclasses import dataclass
from typing import Optional

from . import broadside, fleet_algebra
from .common import Briefing, Choices, Context, Generator, Problem, ShipRef

__all__ = [
    "Briefing", "Choices", "Context", "Generator", "Problem", "ShipRef", "SCHOOLS", "TOPICS", "LEVELS",
    "Posed", "choose", "reward", "penalty", "base_pay", "level_pay", "briefing", "generator_named", "skill_title",
]


@dataclass(frozen=True)
class School:
    id: str
    name: str
    subject: str
    help: dict[str, Briefing]
    generators: list[Generator]


@dataclass(frozen=True)
class Topic:
    id: str
    school: str
    name: str  # e.g. "Navigation · Linear"
    currency: str

    @property
    def short(self) -> str:
        return self.name.split(" · ")[-1]


SCHOOLS: dict[str, School] = {
    "algebra": School("algebra", "Fleet Algebra", "Algebra I", fleet_algebra.HELP, fleet_algebra.GENERATORS),
    "broadside": School("broadside", "Broadside", "Geometry & Trig", broadside.HELP, broadside.GENERATORS),
}

TOPICS: dict[str, Topic] = {
    t.id: t
    for t in [
        Topic("lin", "algebra", "Navigation · Linear", "steel"),
        Topic("sys", "algebra", "Intercept · Systems", "fuel"),
        Topic("quad", "algebra", "Gunnery · Quadratics", "powder"),
        Topic("exp", "algebra", "Radar · Powers & Roots", "blueprints"),
        Topic("rx", "algebra", "Reactor · Exponentials", "plasma"),
        Topic("ang", "broadside", "Lookout · Angles", "blueprints"),
        Topic("tri", "broadside", "Plot · Triangles", "fuel"),
        Topic("trig", "broadside", "Gunnery · Trig", "powder"),
        Topic("geo", "broadside", "Engineering · Area & Volume", "steel"),
        Topic("circ", "broadside", "Shields · Circles", "plasma"),
    ]
}

# Difficulty level -> relative weight of each tier.
LEVELS: dict[int, dict[int, int]] = {
    1: {1: 1},
    2: {1: 2, 2: 1},
    3: {1: 1, 2: 1, 3: 1},
    4: {2: 1, 3: 2},
    5: {3: 1},
}
LEVEL_NAMES = {1: "Easiest", 2: "Easy", 3: "Mixed", 4: "Hard", 5: "Hardest"}
TIER_NAMES = {1: "one step", 2: "a few steps", 3: "multi-step"}
BASE_PAY = 15  # every topic pays the same, whatever currency it earns
TIER_PAY = {1: 1.0, 2: 1.75, 3: 4.0}  # harder problems take longer, so they pay a lot more
WRONG_PENALTY = 0.35  # share of a problem's pay lost on a wrong answer
STREAK_STEP = 0.15  # each right answer in a row adds this share of the problem's pay...
STREAK_CAP = 5  # ...for up to this many answers (+75%)


def streak_bonus(streak: int) -> float:
    """The streak bonus as a share of a problem's pay; ``streak`` includes the answer just given."""
    return STREAK_STEP * min(max(streak - 1, 0), STREAK_CAP)


def base_pay(topic: str, tier: int) -> int:
    """What a problem is worth: the base pay scaled by how hard the problem is."""
    return int(BASE_PAY * TIER_PAY[tier] + 0.5)


def reward(topic: str, tier: int, streak: int = 1) -> int:
    """Currency paid for a correct answer (``streak`` includes this answer)."""
    base = base_pay(topic, tier)
    return base + int(base * streak_bonus(streak) + 0.5)


def penalty(topic: str, tier: int) -> int:
    """Currency lost for a wrong answer: 35% of the problem's pay, rounded up.

    With four choices a blind guess is right one time in four, so on average
    0.25 x pay (plus a little streak bonus) is won and 0.75 x 0.35 x pay lost:
    guessing comes out slightly below zero.
    """
    return math.ceil(WRONG_PENALTY * base_pay(topic, tier))


def level_pay(level: int) -> float:
    """Average pay multiplier at a difficulty level (for topics that have every tier)."""
    weights = LEVELS[level]
    return sum(w * TIER_PAY[t] for t, w in weights.items()) / sum(weights.values())


@dataclass(frozen=True)
class Posed:
    """A problem ready to show: choices shuffled, the right one remembered."""

    topic: Topic
    generator: Generator
    problem: Problem
    choices: tuple[str, ...]
    answer: int  # index into choices
    why: tuple[str, ...] = ()  # why[i] explains the mistake behind choices[i] ("" for the answer)

    @property
    def tier(self) -> int:
        return self.generator.tier

    def reason(self, i: int) -> str:
        """What went wrong if the player picked choice ``i`` ("" for the right answer or if unknown)."""
        return self.why[i] if 0 <= i < len(self.why) and i != self.answer else ""


def generators_for(topic: str) -> list[Generator]:
    return [g for g in SCHOOLS[TOPICS[topic].school].generators if g.topic == topic]


# Saves keep the player's reviews and Logbook results under each generator's key,
# which comes from its function's name. A generator that is renamed (or moved to
# another topic) must be listed here, old key -> new key, or its results are lost
# when an older save is loaded. tests/test_problem_keys.py checks this.
RENAMED: dict[str, str] = {}


def generator_named(key: str) -> Optional[Generator]:
    """The generator with this :attr:`Generator.key` (e.g. "tri.pythagorean_leg"), in either school,
    following :data:`RENAMED` for keys from older saves."""
    key = RENAMED.get(key, key)
    return next((g for s in SCHOOLS.values() for g in s.generators if g.key == key), None)


def _pick_tier(rng: random.Random, available: set[int], level: int) -> int:
    weights = {t: w for t, w in LEVELS[level].items() if t in available}
    if not weights:  # nothing at this level for this topic: take the closest tier there is
        target = {1: 1, 2: 1, 3: 2, 4: 3, 5: 3}[level]
        return min(available, key=lambda t: (abs(t - target), t))
    tiers = sorted(weights)
    return rng.choices(tiers, weights=[weights[t] for t in tiers])[0]


def choose(
    rng: random.Random, topics: list[str], level: int, ctx: Context, recent: Optional[deque] = None,
    generator: Optional[str] = None,
) -> Posed:
    """Pick a topic from ``topics``, a tier for ``level``, and a problem, avoiding recent repeats.

    With ``generator`` (a generator's key), pose that kind of problem instead, with
    fresh numbers: this is how a problem type the player got wrong comes back for review.
    """
    forced = generator_named(generator) if generator else None
    if forced is not None:
        topic, fresh = TOPICS[forced.topic], [forced]
    else:
        topic = TOPICS[rng.choice(sorted(topics))]
        gens = generators_for(topic.id)
        tier = _pick_tier(rng, {g.tier for g in gens}, level)
        pool = [g for g in gens if g.tier == tier]
        fresh = [g for g in pool if recent is None or g.name not in recent] or pool
    for _ in range(20):
        g = rng.choice(fresh)
        p = g.fn(ctx)
        if len(p.choices) == 4 and len(set(p.choices)) == 4:
            break
    if recent is not None:
        recent.append(g.name)
    order = rng.sample(range(4), 4)
    return Posed(
        topic, g, p, tuple(p.choices[i] for i in order), order.index(0), tuple(p.why[i] for i in order),
    )


def briefing(posed: Posed) -> Optional[Briefing]:
    return SCHOOLS[posed.topic.school].help.get(posed.problem.help)


@functools.lru_cache(maxsize=None)
def skill_title(generator: str) -> str:
    """What a kind of problem practises, in a few words: the title of its briefing."""
    g = generator_named(generator)
    if g is None:
        return generator.replace("_", " ")
    b = SCHOOLS[TOPICS[g.topic].school].help.get(g.fn(Context(random.Random(0))).help)
    return b.title if b else generator.replace("_", " ")
