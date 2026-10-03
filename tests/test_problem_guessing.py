"""Answer choices can't be picked without doing the math, and every wrong one says what mistake it is:
in the workshop's two schools, and in Math Boost's problems in battle.

A player who never reads a problem can still look at the four choices. These
tests play that player with a battery of blind tricks (the middle value, the
second smallest, the odd format out, the choice that shares the most parts with
the others, ...) and check that none of them works much better than chance
(25%). A wrong answer costs 35% of a problem's pay, so a trick has to be right
more than about 26% of the time to pay at all.
"""

from __future__ import annotations

import collections
import functools
import math
import random
import re
import statistics
from collections import deque
from typing import Callable, NamedTuple, Optional

import pytest

from seabattle import campaign as cm
from seabattle.problems import LEVELS, SCHOOLS, TOPICS, choose
from seabattle.problems import dinomath as dm

SAMPLES = 150  # problems per generator and fleet
SUPERSCRIPTS = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁻", "0123456789-")
GENERATORS = {g.key: g for school in SCHOOLS.values() for g in school.generators}
SCHOOL_OF = {g.key: school.id for school in SCHOOLS.values() for g in school.generators}
# Choices that are the same number written two ways, on purpose ("50 × 10⁴" is not in scientific notation).
SAME_VALUE_OK = {"exp.scientific_notation", "exp.scientific_product", "exp.scientific_quotient"}


def _fleets() -> list[cm.Campaign]:
    """A new campaign, one a few missions in, and a late one: the word problems use the player's ships."""
    start = cm.Campaign(slot=1)
    mid = cm.Campaign(slot=1, fleet={"picket": 4, "destroyer": 3, "light_cruiser": 2}, mission_number=6)
    late = cm.Campaign(slot=1, fleet={"destroyer": 6, "battleship": 2, "missile_cruiser": 3}, mission_number=15)
    return [start, mid, late]


@functools.lru_cache(maxsize=None)
def samples(name: str):
    out = []
    for i, c in enumerate(_fleets()):
        rng = random.Random(f"{name}/{i}")
        out += [GENERATORS[name].fn(c.problem_context(rng)) for _ in range(SAMPLES)]
    return tuple(out)


# --------------------------------------------------------------------------- reading a choice


def value(choice: str) -> Optional[float]:
    """The number a choice stands for, or None if it isn't a single number."""
    t = choice.strip().translate(SUPERSCRIPTS).replace("−", "-").replace(",", "")
    t = re.sub(r"\s*(sq nm|sq ft|sq m|cubic ft|cubic m|[a-zA-Z/]+(\s[a-zA-Z/]+)?)$", "", t).rstrip("°").strip()
    m = re.fullmatch(r"(-?\d+(?:\.\d+)?)", t)
    if m:
        return float(m[1])
    m = re.fullmatch(r"(-?\d+(?:\.\d+)?)?\s*π", t)
    if m:
        return float(m[1] or 1) * math.pi
    m = re.fullmatch(r"(-?\d+)?\s*√(\d+)", t)
    if m:
        return float(m[1] or 1) * math.sqrt(int(m[2]))
    m = re.fullmatch(r"(-?\d+(?:\.\d+)?) × 10(-?\d+)", t)
    if m:
        return float(m[1]) * 10 ** int(m[2])
    m = re.fullmatch(r"(-?\d+)\s*[⁄/]\s*(\d+)", t)
    if m and int(m[2]):
        return int(m[1]) / int(m[2])
    return None


def values(choices) -> Optional[list[float]]:
    vals = [value(c) for c in choices]
    return vals if all(v is not None for v in vals) else None


def shape(choice: str) -> str:
    """What a choice looks like with the digits taken out: "12.5 nm" -> "#.# nm"."""
    return re.sub(r"\d+", "#", choice)


def tokens(choice: str) -> collections.Counter:
    return collections.Counter(re.findall(r"\d+(?:\.\d+)?|[^\W\d_]+|[^\s\w]", choice.translate(SUPERSCRIPTS)))


# --------------------------------------------------------------------------- the tricks

Trick = Callable[[tuple], Optional[list[float]]]


def _best(scores: list[float], lowest: bool = False) -> list[float]:
    """Pick the best-scoring choice(s), splitting ties evenly."""
    target = min(scores) if lowest else max(scores)
    best = [i for i, s in enumerate(scores) if math.isclose(s, target, rel_tol=1e-9, abs_tol=1e-9)]
    return [1 / len(best) if i in best else 0.0 for i in range(len(scores))]


def middle_of_two(ch):
    """The choice that sits exactly halfway between two others (answer ± k)."""
    v = values(ch)
    if v is None:
        return None
    counts = [
        sum(1 for j in range(4) for k in range(j + 1, 4)
            if i not in (j, k) and math.isclose((v[j] + v[k]) / 2, v[i], rel_tol=1e-9, abs_tol=1e-9))
        for i in range(4)
    ]
    return _best(counts) if max(counts) else None


def near_median(ch):
    v = values(ch)
    if v is None:
        return None
    med = statistics.median(v)
    return _best([abs(x - med) for x in v], lowest=True)


def geometric_centre(ch):
    """The choice closest to the others by ratio (catches x2, /2, x10 distractors)."""
    v = values(ch)
    if v is None or min(v) <= 0:
        return None
    return _best([sum(abs(math.log(x / y)) for y in v) for x in v], lowest=True)


def rank(k: int) -> Trick:
    def trick(ch):
        v = values(ch)
        if v is None:
            return None
        order = sorted(range(4), key=lambda i: v[i])
        return [1.0 if i == order[k] else 0.0 for i in range(4)]
    trick.__name__ = f"rank_{k}"
    return trick


def length_rank(k: int) -> Trick:
    def trick(ch):
        lengths = sorted(len(c) for c in ch)
        return _best([-abs(len(c) - lengths[k]) for c in ch])
    trick.__name__ = f"length_{k}"
    return trick


def odd_shape(ch):
    """The one choice that is written differently from the rest (the only decimal, the only negative...)."""
    counts = collections.Counter(shape(c) for c in ch)
    odd = [i for i, c in enumerate(ch) if counts[shape(c)] == 1]
    return [1.0 if i == odd[0] else 0.0 for i in range(4)] if len(odd) == 1 else None


def common_shape(ch):
    """A choice written the same way as most of the others."""
    counts = collections.Counter(shape(c) for c in ch)
    top = max(counts.values())
    if top in (1, 4):
        return None
    return _best([float(counts[shape(c)] == top) for c in ch])


def most_shared_parts(ch):
    """Wrong answers made by changing one part of the answer share the most parts with it."""
    toks = [tokens(c) for c in ch]
    return _best([sum(sum((toks[i] & toks[j]).values()) for j in range(4) if j != i) for i in range(4)])


def fewest_shared_parts(ch):
    toks = [tokens(c) for c in ch]
    return _best([sum(sum((toks[i] & toks[j]).values()) for j in range(4) if j != i) for i in range(4)], lowest=True)


def complementary_pair(ch):
    """Angle problems: if exactly two choices add up to 90° or 180°, the answer is one of them."""
    if not all(c.strip().endswith("°") for c in ch):
        return None
    v = values(ch)
    if v is None:
        return None
    pairs = [(i, j) for i in range(4) for j in range(i + 1, 4) if round(v[i] + v[j]) in (90, 180)]
    if len(pairs) != 1:
        return None
    return [0.5 if i in pairs[0] else 0.0 for i in range(4)]


TRICKS: list[Trick] = [
    middle_of_two, near_median, geometric_centre, *[rank(k) for k in range(4)], *[length_rank(k) for k in range(4)],
    odd_shape, common_shape, most_shared_parts, fewest_shared_parts, complementary_pair,
]
# How often a trick may be right on one kind of problem. Chance is 25%. Picking the
# middle value is the trick players actually find, so it gets the tightest limit.
LIMITS = {"middle_of_two": 0.30, "odd_shape": 0.45, "common_shape": 0.45, "most_shared_parts": 0.45,
          "fewest_shared_parts": 0.45, "complementary_pair": 0.45}
DEFAULT_LIMIT = 0.55  # ranks, lengths and the median: some kinds of mistake only ever go one way


def accuracy(problems, trick: Trick) -> float:
    """How often the trick picks the right answer (choice 0), guessing at random where it doesn't apply."""
    total = 0.0
    for p in problems:
        weights = trick(tuple(p.choices))
        total += 0.25 if weights is None else weights[0]
    return total / len(problems)


@functools.lru_cache(maxsize=None)
def trick_accuracy(name: str) -> dict[str, float]:
    return {t.__name__: accuracy(samples(name), t) for t in TRICKS}


# --------------------------------------------------------------------------- tests


def _ids():
    return [f"{SCHOOL_OF[k]}-{GENERATORS[k].name}" for k in GENERATORS]


@pytest.mark.parametrize("name", list(GENERATORS), ids=_ids())
def test_no_blind_trick_works(name):
    scores = trick_accuracy(name)
    too_good = {t: round(a, 2) for t, a in scores.items() if a > LIMITS.get(t, DEFAULT_LIMIT)}
    assert not too_good, f"{name}: these tricks find the answer without the math: {too_good}"


@pytest.mark.parametrize("name", list(GENERATORS), ids=_ids())
def test_every_wrong_choice_says_what_went_wrong(name):
    for p in samples(name):
        assert len(p.why) == len(p.choices) == 4, (name, p.choices, p.why)
        assert p.why[0] == "", (name, p.why)
        for choice, why in zip(p.choices[1:], p.why[1:]):
            assert why.strip(), f"{name}: wrong choice {choice!r} has no explanation ({p.choices})"
            assert why.strip()[-1] in ".!?)", f"{name}: explanations are full sentences: {why!r}"


@pytest.mark.parametrize("name", list(GENERATORS), ids=_ids())
def test_wrong_choices_are_really_wrong(name):
    """No wrong choice is the right answer written another way."""
    if name in SAME_VALUE_OK:
        return
    for p in samples(name):
        v = values(p.choices)
        if v is None:
            continue
        for i in range(1, 4):
            assert not math.isclose(v[i], v[0], rel_tol=1e-9, abs_tol=1e-9), (name, p.choices)


@pytest.mark.parametrize("school", list(SCHOOLS))
@pytest.mark.parametrize("level", list(LEVELS))
def test_no_trick_works_across_a_whole_school(school, level):
    """What the workshop actually serves: no single trick beats chance by much at any difficulty,
    and neither does knowing the best trick for every kind of problem."""
    c = cm.Campaign(slot=1, fleet={"picket": 4, "destroyer": 3, "light_cruiser": 2}, mission_number=6)
    rng = random.Random(f"{school}/{level}")
    topics = [t for t in TOPICS if TOPICS[t].school == school]
    served = collections.Counter()
    recent: deque = deque(maxlen=8)
    for _ in range(1500):
        served[choose(rng, topics, level, c.problem_context(rng), recent).generator.key] += 1
    total = sum(served.values())
    for trick in TRICKS:
        blended = sum(trick_accuracy(n)[trick.__name__] * k for n, k in served.items()) / total
        assert blended <= 0.32, f"{school} level {level}: {trick.__name__} is right {blended:.0%} of the time"
    oracle = sum(max(trick_accuracy(n).values()) * k for n, k in served.items()) / total
    assert oracle <= 0.42, f"{school} level {level}: the best trick per problem type is right {oracle:.0%} of the time"


# --------------------------------------------------------------------------- Math Boost (Dino Math)

BOOST_SAMPLES = 120  # problems per topic and level


class Shown(NamedTuple):
    """A Math Boost problem as the tricks see it: the answer first."""

    choices: tuple[str, ...]
    why: tuple[str, ...]


@functools.lru_cache(maxsize=None)
def boost_samples(topic: str, level: int) -> tuple[Shown, ...]:
    rng = random.Random(f"boost/{topic}/{level}")
    out = []
    for _ in range(BOOST_SAMPLES):
        p = dm.make_problem(rng, level, topic)
        order = [p.answer] + [i for i in range(4) if i != p.answer]
        out.append(Shown(tuple(p.choices[i].text for i in order), tuple(p.choices[i].why for i in order)))
    return tuple(out)


@functools.lru_cache(maxsize=None)
def boost_accuracy(topic: str, level: int) -> dict[str, float]:
    return {t.__name__: accuracy(boost_samples(topic, level), t) for t in TRICKS}


BOOST_CASES = [(t.name, level) for t in dm.TOPICS for level in dm.LEVELS if level >= t.min]


@pytest.mark.parametrize("topic, level", BOOST_CASES, ids=[f"{t}-{lv + 1}" for t, lv in BOOST_CASES])
def test_no_blind_trick_works_on_a_math_boost_topic(topic, level):
    scores = boost_accuracy(topic, level)
    too_good = {t: round(a, 2) for t, a in scores.items() if a > LIMITS.get(t, DEFAULT_LIMIT)}
    assert not too_good, f"{topic} level {level + 1}: these tricks find the answer without the math: {too_good}"


@pytest.mark.parametrize("topic, level", BOOST_CASES, ids=[f"{t}-{lv + 1}" for t, lv in BOOST_CASES])
def test_every_math_boost_wrong_choice_says_what_went_wrong(topic, level):
    for p in boost_samples(topic, level):
        assert p.why[0] == "" and all(w.strip() for w in p.why[1:]), (topic, p.choices, p.why)


@pytest.mark.parametrize("level", list(dm.LEVELS))
def test_no_trick_works_across_math_boost(level):
    """What a battle actually serves at each level: topics drawn as Math Boost draws them,
    never the same one twice in a row. Same bars as the workshop's schools."""
    dice = dm.Dice(random.Random(f"boost/{level}"))
    served: collections.Counter = collections.Counter()
    last = None
    for _ in range(3000):
        last = dm.random_topic(dice, level, last).name
        served[last] += 1
    total = sum(served.values())
    for trick in TRICKS:
        blended = sum(boost_accuracy(t, level)[trick.__name__] * k for t, k in served.items()) / total
        assert blended <= 0.32, f"Math Boost level {level + 1}: {trick.__name__} is right {blended:.0%} of the time"
    oracle = sum(max(boost_accuracy(t, level).values()) * k for t, k in served.items()) / total
    assert oracle <= 0.42, f"Math Boost level {level + 1}: the best trick per topic is right {oracle:.0%} of the time"
