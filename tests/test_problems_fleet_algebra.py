"""Tests for the Fleet Algebra (Algebra I) problem generators.

Every generator is run a few hundred times, with and without a player fleet.
The problems must be well formed (four distinct choices, plain Unicode text)
and the first choice must be the right answer, which is re-derived here from
the numbers printed in the problem.
"""

import collections
import functools
import itertools
import math
import os
import random
import re
from decimal import Decimal
from fractions import Fraction

import pytest

from seabattle.problems import fleet_algebra as fa
from seabattle.problems.common import Briefing, Context, Problem, ShipRef, sup

N = 300  # problems per generator per fleet setting
FLEET = [ShipRef("USS Ajax", "aircraft carrier", 30, 5000), ShipRef("USS Bonefish", "submarine", 25, 130)]
GENERATORS = {g.name: g for g in fa.GENERATORS}
FONT = os.path.join(os.path.dirname(__file__), "..", "seabattle", "assets", "fonts", "DejaVuSans.ttf")

TIER_1 = {
    "distance_rate_time", "function_notation", "linear_model", "decay_growth", "exponent_rules",
    "pythagorean_hypotenuse", "zero_negative_exponents", "scientific_notation", "square_root_perfect_square",
    "growth_factor", "factor_from_readings", "read_exponential", "half_life",
    "check_solution", "count_solutions", "substitute_known_value", "zero_product", "evaluate_quadratic", "axis_of_symmetry",
}
TIER_3 = {
    "inequality_load_limit", "overtake", "supply_mix", "substitution", "tickets_and_passes", "boat_and_current",
    "trajectory", "quadratic_roots", "deck_area", "projectile_from_height", "consecutive_product",
    "add_radicals", "scientific_product", "solve_for_exponent",
    "model_from_two_points", "rate_from_two_readings", "exponential_passes_linear", "decay_to_threshold",
    "distribute_both_sides", "predict_from_readings", "round_trip_speed", "cheaper_after",
    "power_of_a_product", "scientific_quotient",
}
REACTOR = [g.name for g in fa.GENERATORS if g.topic == "rx"]


@functools.lru_cache(maxsize=None)
def corpus(name: str) -> tuple[Problem, ...]:
    fn = GENERATORS[name].fn
    probs = [fn(Context(random.Random(seed))) for seed in range(N)]
    probs += [fn(Context(random.Random(seed), fleet=list(FLEET))) for seed in range(N)]
    return tuple(probs)


def texts(p: Problem) -> list[str]:
    return [p.story, p.expr, p.ask, p.hint, p.note, *p.solution, *p.choices, *p.why]


# ---------------------------------------------------------------------------
# Parsing helpers for re-deriving answers
# ---------------------------------------------------------------------------

_DESUP = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁻", "0123456789-")
SUP = "[⁰¹²³⁴⁵⁶⁷⁸⁹⁻]+"
INT = r"−?[\d,]+"


def val(s: str) -> Fraction:
    """A printed number ("−3", "1,250", "12.5") as an exact fraction."""
    return Fraction(s.replace("−", "-").replace(",", ""))


def ints(m: re.Match) -> list[int]:
    return [int(val(g)) if g is not None else None for g in m.groups()]


def desup(s: str) -> int:
    return int(s.translate(_DESUP))


def match(pattern: str, s: str) -> re.Match:
    m = re.fullmatch(pattern, s)
    assert m, f"{s!r} does not match {pattern!r}"
    return m


def ans(p: Problem) -> Fraction:
    return val(p.choices[0])


def exact_sqrt(n) -> int:
    r = math.isqrt(int(n))
    assert r * r == n, n
    return r


def squarefree(n: int) -> bool:
    return all(n % (k * k) for k in range(2, math.isqrt(n) + 1))


def parse_trinomial(s: str) -> tuple[int, int]:
    """'x² − 5x + 6' -> (-5, 6); 'x² + x − 2' -> (1, -2); 'x² − 9' -> (0, -9)."""
    m = match(r"x² (?:([+−]) (\d*)x )?([+−]) (\d+)", s)
    b = 0 if m[1] is None else (int(m[2]) if m[2] else 1) * (-1 if m[1] == "−" else 1)
    c = int(m[4]) * (-1 if m[3] == "−" else 1)
    return b, c


def parse_factors(s: str) -> tuple[int, int]:
    """'(x − 2)(x + 5)' -> (-2, 5)."""
    m = match(r"\(x ([+−]) (\d+)\)\(x ([+−]) (\d+)\)", s)
    return tuple(int(m[i + 1]) * (-1 if m[i] == "−" else 1) for i in (1, 3))


def formula_holds(eq: str, choice: str, want: str) -> bool:
    """Put random values into the letters, compute ``want`` from ``choice``; does ``eq`` still hold?"""

    def py(expr: str) -> str:
        out, prev = [], ""
        for ch in expr.replace(" ", ""):
            if prev and (prev.isalnum() or prev == ")") and (ch.isalpha() or ch == "(") and not (prev.isdigit() and ch.isdigit()):
                out.append("*")  # implicit multiplication: 2L, rt, 2πr, m(y − b)
            out.append({"÷": "/", "−": "-", "×": "*", "π": "pi"}.get(ch, ch))
            prev = ch
        return "".join(out)

    lhs, rhs = eq.split(" = ")
    target, formula = choice.split(" = ")
    assert target == want
    rng = random.Random(7)
    for _ in range(3):
        env = {ch: rng.uniform(1.5, 9.5) for ch in eq if ch.isalpha() and ch != "π"}
        env["pi"] = math.pi
        env[want] = eval(py(formula), {}, env)
        if not math.isclose(eval(py(lhs), {}, env), eval(py(rhs), {}, env), rel_tol=1e-9):
            return False
    return True


# ---------------------------------------------------------------------------
# One verifier per generator: re-derive the answer from the problem text
# ---------------------------------------------------------------------------

VERIFY = {}


def verifies(name):
    def wrap(fn):
        VERIFY[name] = fn
        return fn

    return wrap


@verifies("fuel_burn")
def _(p):
    r, R, F = ints(match(r"(\d+)t \+ (\d+) = (\d+)", p.expr))
    assert ans(p) == Fraction(F - R, r)
    assert str(F) in p.story and str(R) in p.story


@verifies("distance_rate_time")
def _(p):
    m = re.fullmatch(r"(\d+) = (\d+) × t", p.expr)
    if m:
        d, s = ints(m)
        assert ans(p) == Fraction(d, s)
    else:
        s, t = ints(match(r"d = (\d+) × (\d+)", p.expr))
        assert ans(p) == s * t
    assert f"{s} knots" in p.story


@verifies("two_step_equation")
def _(p):
    m = match(r"(\d+)x ([+−]) (\d+) = (−?\d+)", p.expr)
    a, b, c = int(m[1]), int(m[3]) * (-1 if m[2] == "−" else 1), int(val(m[4]))
    x = ans(p)
    assert x.denominator == 1 and a * x + b == c


@verifies("slope_from_two_points")
def _(p):
    t1, f1, t2, f2 = ints(match(r"\((\d+), (\d+)\) and \((\d+), (\d+)\)", p.expr))
    assert ans(p) == Fraction(f2 - f1, t2 - t1)
    assert str(f1) in p.story and str(f2) in p.story


@verifies("function_notation")
def _(p):
    D, s = ints(match(r"r\(t\) = (\d+) − (\d+)t", p.expr))
    t = int(re.match(r"Find r\((\d+)\)", p.ask)[1])
    assert ans(p) == D - s * t


@verifies("inequality_load_limit")
def _(p):
    C, m, W = ints(match(r"([\d,]+) \+ (\d+)m ≤ ([\d,]+)", p.expr))
    n = ans(p)
    assert n.denominator == 1 and C + m * n <= W < C + m * (n + 1)


@verifies("overtake")
def _(p):
    s1, h, s2 = ints(match(r"(\d+)\(t \+ (\d+)\) = (\d+)t", p.expr))
    t = ans(p)
    assert s1 * (t + h) == s2 * t


@verifies("supply_mix")
def _(p):
    a, b, W1, c, d, W2 = ints(match(r"(\d+)s \+ (\d+)r = ([\d,]+)\n(\d+)s \+ (\d+)r = ([\d,]+)", p.expr))
    assert ans(p) == Fraction(W1 * d - b * W2, a * d - b * c)


@verifies("sum_and_difference")
def _(p):
    S, d = ints(match(r"x \+ y = (\d+)\nx − y = (\d+)", p.expr))
    assert ans(p) == Fraction(S + d, 2)


@verifies("substitution")
def _(p):
    m = match(r"y = (\d+)x ([+−]) (\d+)\n(\d+)x \+ (\d*)y = (−?\d+)", p.expr)
    mm, k, pp, C = int(m[1]), int(m[3]) * (-1 if m[2] == "−" else 1), int(m[4]), int(val(m[6]))
    q = int(m[5]) if m[5] else 1
    x = ans(p)
    y = mm * x + k
    assert pp * x + q * y == C


@verifies("trajectory")
def _(p):
    (v,) = ints(match(r"h = −16t² \+ (\d+)t", p.expr))
    if "seconds" in p.ask:
        t = ans(p)
        assert t > 0 and -16 * t * t + v * t == 0
    else:
        assert ans(p) == Fraction(v * v, 64)  # vertex of −16t² + vt


@verifies("factor_trinomial")
def _(p):
    b, c = parse_trinomial(p.expr)
    for i, choice in enumerate(p.choices):
        f, g = parse_factors(choice)
        assert (f + g == b and f * g == c) == (i == 0), choice


@verifies("quadratic_roots")
def _(p):
    assert p.expr.endswith(" = 0")
    b, c = parse_trinomial(p.expr[: -len(" = 0")])
    disc = exact_sqrt(b * b - 4 * c)
    roots = sorted([Fraction(-b - disc, 2), Fraction(-b + disc, 2)])
    for i, choice in enumerate(p.choices):
        m = match(r"x = (−?\d+) or x = (−?\d+)", choice)
        assert (sorted([val(m[1]), val(m[2])]) == roots) == (i == 0), choice


@verifies("deck_area")
def _(p):
    k, A = ints(match(r"w\(w \+ (\d+)\) = ([\d,]+)", p.expr))
    w = Fraction(-k + exact_sqrt(k * k + 4 * A), 2)
    assert ans(p) == w and w * (w + k) == A


@verifies("expand_binomials")
def _(p):
    a, b = parse_factors(p.expr)
    for i, choice in enumerate(p.choices):
        assert (parse_trinomial(choice) == (a + b, a * b)) == (i == 0), choice


@verifies("pythagorean_hypotenuse")
def _(p):
    a, b = ints(match(r"(\d+)² \+ (\d+)² = c²", p.expr))
    assert ans(p) == exact_sqrt(a * a + b * b)


@verifies("decay_growth")
def _(p):
    if p.help == "decay":
        S0, dist, step = ints(match(r"([\d,]+) × \(½\)ⁿ,\s+n = ([\d,]+) ÷ ([\d,]+)", p.expr))
        n = Fraction(dist, step)
        assert n.denominator == 1
        assert ans(p) == Fraction(S0, 2 ** int(n))
    else:
        assert p.help == "power"
        m = match(rf"(\d+)({SUP})", p.expr)
        assert ans(p) == int(m[1]) ** desup(m[2])


@verifies("exponent_rules")
def _(p):
    if m := re.fullmatch(rf"x({SUP}) · x({SUP})", p.expr):
        e = desup(m[1]) + desup(m[2])
    elif m := re.fullmatch(rf"x({SUP}) ÷ x({SUP})", p.expr):
        e = desup(m[1]) - desup(m[2])
    else:
        m = match(rf"\(x({SUP})\)({SUP})", p.expr)
        e = desup(m[1]) * desup(m[2])
    assert p.choices[0] == "x" + sup(e)


@verifies("simplify_radical")
def _(p):
    (N,) = ints(match(r"√(\d+)", p.expr))
    for i, choice in enumerate(p.choices):
        m = match(r"(\d*)√(\d+)", choice)  # "√6": the number in front was dropped
        k, rest = int(m[1] or 1), int(m[2])
        assert (k * k * rest == N and squarefree(rest)) == (i == 0), choice


@verifies("head_on_meeting")
def _(p):
    s1, s2, D = ints(match(r"(\d+)t \+ (\d+)t = (\d+)", p.expr))
    assert ans(p) == Fraction(D, s1 + s2)


@verifies("consecutive_integers")
def _(p):
    s1, s2, S = ints(match(r"x \+ \(x \+ (\d)\) \+ \(x \+ (\d)\) = (\d+)", p.expr))
    assert s2 == 2 * s1
    x = ans(p)
    assert x + (x + s1) + (x + s2) == S
    if s1 == 2:
        assert ("consecutive even" if x % 2 == 0 else "consecutive odd") in p.story
    else:
        assert "consecutive even" not in p.story and "consecutive odd" not in p.story


@verifies("perimeter")
def _(p):
    if m := re.fullmatch(r"2\(w \+ (\d+)\) \+ 2w = (\d+)", p.expr):
        k, P = ints(m)
        assert ans(p) == Fraction(P - 2 * k, 4)
        assert f"{k} feet longer" in p.story
    else:
        (P,) = ints(match(r"2\(2w\) \+ 2w = (\d+)", p.expr))
        assert ans(p) == Fraction(P, 6)
        assert "twice as long" in p.story


@verifies("literal_equation")
def _(p):
    want = match(r"Solve for (\w)\.", p.ask)[1]
    for i, choice in enumerate(p.choices):
        assert formula_holds(p.expr, choice, want) == (i == 0), choice


@verifies("proportion_chart_scale")
def _(p):
    if m := re.fullmatch(r"(\d+) ⁄ (\d+) = (\d+) ⁄ x", p.expr):
        a, b, c = ints(m)
        assert ans(p) == Fraction(b * c, a)
    else:
        a, b, c = ints(match(r"(\d+) ⁄ (\d+) = x ⁄ (\d+)", p.expr))
        assert ans(p) == Fraction(a * c, b)


@verifies("linear_model")
def _(p):
    F, r = [int(n) for n in re.findall(r"\d+", p.story)][:2]
    up = "IN" in p.story or "receives" in p.story
    assert p.expr.startswith("y = ?") and not re.search(r"[+−]", p.expr), p.expr  # doesn't give the sign away
    assert p.choices[0] == f"y = {F} {'+' if up else '−'} {r}t"


@verifies("tickets_and_passes")
def _(p):
    n, p1, p2, T = ints(match(r"x \+ y = (\d+)\n(\d+)x \+ (\d+)y = (\d+)", p.expr))
    y = ans(p)
    assert y.denominator == 1 and 0 < y < n and p1 * (n - y) + p2 * y == T
    assert f"${p2}" in p.ask


@verifies("boat_and_current")
def _(p):
    d1, t1, d2, t2 = ints(match(r"b \+ c = (\d+) ÷ (\d+)\nb − c = (\d+) ÷ (\d+)", p.expr))
    assert d1 == d2
    assert ans(p) == (Fraction(d1, t1) - Fraction(d2, t2)) / 2


@verifies("ratio_multiple")
def _(p):
    m, T = ints(match(r"x \+ (\d+)x = ([\d,]+)", p.expr))
    assert ans(p) == Fraction(T, m + 1)


@verifies("dropped_object")
def _(p):
    (H,) = ints(match(r"h = (\d+) − 16t²", p.expr))
    t = ans(p)
    assert t > 0 and H - 16 * t * t == 0


@verifies("projectile_from_height")
def _(p):
    v, h0 = ints(match(r"h = −16t² \+ (\d+)t \+ (\d+)", p.expr))
    t = Fraction(v + exact_sqrt(v * v + 64 * h0), 32)  # the positive root
    assert ans(p) == t and -16 * t * t + v * t + h0 == 0


@verifies("difference_of_squares")
def _(p):
    (K,) = ints(match(r"x² − (\d+)", p.expr))
    for i, choice in enumerate(p.choices):
        f, g = parse_factors(choice)
        assert (f + g == 0 and f * g == -K) == (i == 0), choice


@verifies("solve_by_square_roots")
def _(p):
    if m := re.fullmatch(r"x² = (\d+)", p.expr):
        a, c = 1, int(m[1])
    else:
        a, c = ints(match(r"(\d+)x² − (\d+) = 0", p.expr))
    assert p.choices[0] == f"x = ±{exact_sqrt(Fraction(c, a))}"


@verifies("consecutive_product")
def _(p):
    (P,) = ints(match(r"x\(x \+ 1\) = (\d+)", p.expr))
    x = ans(p)
    assert x > 0 and x * (x + 1) == P


@verifies("pythagorean_missing_leg")
def _(p):
    a, c = ints(match(r"(\d+)² \+ b² = (\d+)²", p.expr))
    assert ans(p) == exact_sqrt(c * c - a * a)


@verifies("distance_between_points")
def _(p):
    m = match(r"d = √\(\((−?\d+) − \(?(−?\d+)\)?\)² \+ \((−?\d+) − \(?(−?\d+)\)?\)²\)", p.expr)
    x2, x1, y2, y1 = (int(val(g)) for g in m.groups())
    assert ans(p) == exact_sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
    lead = lambda n: f"−{-n}" if n < 0 else str(n)  # noqa: E731
    assert f"({lead(x1)}, {lead(y1)})" in p.story and f"({lead(x2)}, {lead(y2)})" in p.story


@verifies("scientific_notation")
def _(p):
    def sci_value(s):
        m = match(rf"([\d.]+) × 10({SUP})", s)
        return Decimal(m[1]) * 10 ** desup(m[2]), Decimal(m[1])

    if "standard number" in p.ask:
        value, _mantissa = sci_value(p.expr)
        assert p.choices[0] == f"{int(value):,}"
    else:
        value = Decimal(p.expr.replace(",", ""))
        for i, choice in enumerate(p.choices):
            v, mantissa = sci_value(choice)
            assert (v == value and 1 <= mantissa < 10) == (i == 0), choice


@verifies("growth_from_start")
def _(p):
    start, base, n = match(rf"(\d+) × (\d)({SUP})", p.expr).groups()
    assert ans(p) == int(start) * int(base) ** desup(n)
    assert ("doubles" if base == "2" else "triples") in p.story
    assert f"after {desup(n)} " in p.ask


@verifies("zero_negative_exponents")
def _(p):
    b, e = match(rf"(\d+)({SUP})", p.expr).groups()
    n = desup(e)
    assert n <= 0
    assert p.choices[0] == ("1" if n == 0 else f"1⁄{int(b) ** -n}")


@verifies("square_root_perfect_square")
def _(p):
    (A,) = ints(match(r"s² = ([\d,]+)", p.expr))
    assert ans(p) == exact_sqrt(A)


@verifies("multiply_radicals")
def _(p):
    a, b = ints(match(r"√(\d+) · √(\d+)", p.expr))

    def correct(s):  # simplified form of √(ab)?
        if m := re.fullmatch(r"(\d+)", s):
            return int(m[1]) ** 2 == a * b
        m = re.fullmatch(r"(\d*)√(\d+)", s)
        k = int(m[1]) if m[1] else 1
        return k * k * int(m[2]) == a * b and squarefree(int(m[2])) and int(m[2]) > 1

    for i, choice in enumerate(p.choices):
        assert correct(choice) == (i == 0), choice


@verifies("add_radicals")
def _(p):
    a, b = ints(match(r"√(\d+) \+ √(\d+)", p.expr))
    total = math.sqrt(a) + math.sqrt(b)
    for i, choice in enumerate(p.choices):
        m = re.fullmatch(r"(\d*)√(\d+)", choice)
        k, rest = (int(m[1] or 1), int(m[2])) if m else (int(choice), 1)
        simplest = rest > 1 and squarefree(rest)
        assert (simplest and math.isclose(k * math.sqrt(rest), total)) == (i == 0), choice


@verifies("scientific_product")
def _(p):
    m = match(rf"\(([\d.]+) × 10({SUP})\) × \(([\d.]+) × 10({SUP})\)", p.expr)
    value = Decimal(m[1]) * 10 ** desup(m[2]) * Decimal(m[3]) * 10 ** desup(m[4])
    for i, choice in enumerate(p.choices):
        c = match(rf"([\d.]+) × 10({SUP})", choice)
        front = Decimal(c[1])
        assert (front * 10 ** desup(c[2]) == value and 1 <= front < 10) == (i == 0), choice


@verifies("solve_for_exponent")
def _(p):
    if m := re.fullmatch(r"([\d,]+) × \(½\)ⁿ = ([\d,]+)", p.expr):
        start, end = ints(m)
        base, ratio = 2, Fraction(start, end)
        (k,) = ints(re.search(r"every (\d+) meters", p.story))
    else:
        start, base, end = ints(match(r"(\d+) × (\d)ⁿ = ([\d,]+)", p.expr))
        ratio = Fraction(end, start)
        (k,) = ints(re.search(r"every (\d+) (?:hours|days|weeks)", p.story))
    n = round(math.log(ratio, base))
    assert base**n == ratio
    assert ans(p) == n * k


# Reactor · Exponentials

UNIT_SECONDS = {"second": 1, "minute": 60, "hour": 3600, "day": 86400}


def exp_model(s: str):
    """'y = 5 × 3ᵗ' -> (5, 3) as fractions; None for anything that isn't y = a × bᵗ ('y = 5 + 20t')."""
    m = re.fullmatch(r"y = ([\d.,]+) × ([\d.]+)ᵗ", s)
    return (val(m[1]), val(m[2])) if m else None


def pct(choice: str) -> Fraction:
    """'20%' -> 20."""
    assert choice.endswith("%"), choice
    return val(choice[:-1])


def story_factor(p: Problem) -> Fraction:
    """The factor a story's "grows 8%" or "loses 15%" stands for: 1.08 or 0.85."""
    word, r = re.search(r"\b(grows|loses) (\d+)%", p.story).groups()
    return 1 + Fraction(int(r), 100) * (1 if word == "grows" else -1)


def half_life_of(p: Problem) -> tuple[int, str]:
    """The half-life in a story: (3, "hour")."""
    h, unit = re.search(r"(?:half-life of|halves every) (\d+) (second|minute|hour|day)s?\b", p.story).groups()
    return int(h), unit


def half_lives(p: Problem) -> int:
    """How many half-lives pass by the time the question asks about."""
    h, unit = half_life_of(p)
    t, tunit = re.search(r"after (\d+) (second|minute|hour|day)s?\?", p.ask).groups()
    n = Fraction(int(t) * UNIT_SECONDS[tunit], h * UNIT_SECONDS[unit])
    assert n.denominator == 1, p.ask
    return int(n)


@verifies("growth_factor")
def _(p):
    sign, r = match(r"([+−])(\d+)% each (?:hour|minute|second|day|cycle)", p.expr).groups()
    rate = Fraction(int(r), 100)
    assert ans(p) == (1 + rate if sign == "+" else 1 - rate)
    assert f"{'grows' if sign == '+' else 'loses'} {r}%" in p.story


@verifies("factor_from_readings")
def _(p):
    y0, y1 = ints(match(r"y\(0\) = (\d+),   y\(1\) = (\d+)", p.expr))
    assert ans(p) == Fraction(y1, y0)
    assert f"{y0} " in p.story and f"{y1} " in p.story
    assert ("growth factor" in p.ask) == (y1 > y0)


@verifies("read_exponential")
def _(p):
    b = val(match(r"y = \d+ × ([\d.]+)ᵗ", p.expr)[1])
    assert pct(p.choices[0]) == abs(b - 1) * 100
    assert ("grow each" in p.ask) == (b > 1) and ("drop each" in p.ask) == (b < 1)


@verifies("half_life")
def _(p):
    (S0,) = ints(match(r"([\d,]+) × \(½\)ⁿ", p.expr))
    n = half_lives(p)
    assert n in (1, 2) and ans(p) == Fraction(S0, 2**n)


@verifies("half_life_periods")
def _(p):
    (S0,) = ints(match(r"([\d,]+) × \(½\)ⁿ", p.expr))
    n = half_lives(p)
    assert 3 <= n <= 5 and ans(p) == Fraction(S0, 2**n)


@verifies("repeated_percent")
def _(p):
    (a,) = ints(match(r"y = ([\d,]+) × bᵗ", p.expr))
    (n,) = ints(re.search(r"after (\d+) ", p.ask))
    assert ans(p) == a * story_factor(p) ** n


@verifies("linear_or_exponential")
def _(p):
    ys = [val(v) for v in match(r"t = 0, 1, 2, 3, 4\ny = (\d+), (\d+), (\d+), (\d+), \?", p.expr).groups()]
    jumps = {v - u for u, v in zip(ys, ys[1:])}
    ratios = {v / u for u, v in zip(ys, ys[1:])}
    assert (len(jumps) == 1) != (len(ratios) == 1), ys  # one pattern or the other, never both
    assert ans(p) == (ys[3] + jumps.pop() if len(jumps) == 1 else ys[3] * ratios.pop())


@verifies("exponential_model")
def _(p):
    a = val(re.search(r"starts at ([\d,]+)", p.story)[1])
    for i, choice in enumerate(p.choices):
        assert (exp_model(choice) == (a, story_factor(p))) == (i == 0), choice


@verifies("model_from_two_points")
def _(p):
    t1, y1, t2, y2 = ints(match(r"y\((\d)\) = ([\d,]+),   y\((\d)\) = ([\d,]+)", p.expr))
    for i, choice in enumerate(p.choices):
        m = exp_model(choice)  # the straight line through both readings fits them too, but isn't y = a × bᵗ
        assert (m is not None and m[0] * m[1] ** t1 == y1 and m[0] * m[1] ** t2 == y2) == (i == 0), choice


@verifies("rate_from_two_readings")
def _(p):
    y0, k, yk = ints(match(r"y\(0\) = ([\d,]+),   y\((\d)\) = ([\d,]+)", p.expr))
    rate = pct(p.choices[0]) / 100
    assert (1 + rate if yk > y0 else 1 - rate) ** k == Fraction(yk, y0)
    assert ("grow each" in p.ask) == (yk > y0)


@verifies("exponential_passes_linear")
def _(p):
    a, b, c, m = ints(match(r"(\d+) × (\d)ᵗ > (\d+) \+ (\d+)t", p.expr))
    t = ans(p)
    assert t.denominator == 1 and a * b**t > c + m * t
    assert all(a * b**s < c + m * s for s in range(int(t)))  # behind until then, never level


@verifies("decay_to_threshold")
def _(p):
    S0, limit = ints(match(r"([\d,]+) × \(½\)ⁿ < (\d+)", p.expr))
    h, unit = half_life_of(p)
    assert p.ask == f"After how many {unit}s does it first drop below {limit}?"
    n = next(n for n in range(20) if Fraction(S0, 2**n) < limit)
    assert all(Fraction(S0, 2**k) != limit for k in range(n))  # it never lands exactly on the limit
    assert ans(p) == n * h


# ---- one-step and multi-step kinds added to fill out each tier


def coef(s: str) -> int:
    """The number in front of x: '' -> 1, '−' -> -1, '3' -> 3, '−2' -> -2."""
    return {"": 1, "−": -1}.get(s) or int(val(s))


def any_line(s: str) -> tuple[int, int]:
    """Slope and y-intercept of 'y = 2x − 3', 'y = −x', 'y = 3 + 2x' or 'y − 3 = 2x'."""
    if m := re.fullmatch(r"y ([+−]) (\d+) = (−?\d*)x", s):
        return coef(m[3]), int(m[2]) * (1 if m[1] == "−" else -1)
    if m := re.fullmatch(r"y = (−?\d+) ([+−]) (\d*)x", s):
        return coef(m[3]) * (-1 if m[2] == "−" else 1), int(val(m[1]))
    m = match(r"y = (−?\d*)x(?: ([+−]) (\d+))?", s)
    return coef(m[1]), 0 if m[2] is None else int(m[3]) * (-1 if m[2] == "−" else 1)


@verifies("distribute_both_sides")
def _(p):
    m = match(r"(\d+)\(x ([+−]) (\d+)\) = (\d*)x ([+−]) (\d+)", p.expr)
    a, c = int(m[1]), coef(m[4])
    q, r = int(m[3]) * (-1 if m[2] == "−" else 1), int(m[6]) * (-1 if m[5] == "−" else 1)
    x = ans(p)
    assert a != c and x.denominator == 1 and a * (x + q) == c * x + r


@verifies("predict_from_readings")
def _(p):
    t1, f1, t2, f2, L = ints(match(r"\((\d+), (\d+)\) and \((\d+), (\d+)\)\ny = (\d+) at t = \?", p.expr))
    rate = Fraction(f2 - f1, t2 - t1)
    T = ans(p)
    assert rate < 0 and T.denominator == 1 and T > t2 and f2 + rate * (T - t2) == L
    assert f"{f1} " in p.story and f"{L} " in p.story


@verifies("round_trip_speed")
def _(p):
    D, sa, D2, sb = ints(match(r"out: (\d+) nm at (\d+) knots\nback: (\d+) nm at (\d+) knots", p.expr))
    assert D == D2 and f"{D} nautical miles" in p.story
    assert ans(p) == 2 * D / (Fraction(D, sa) + Fraction(D, sb)) != Fraction(sa + sb, 2)


@verifies("cheaper_after")
def _(p):
    B0, b, A0, a = ints(match(r"(\d+) \+ (\d+)h < (\d+) \+ (\d+)h", p.expr))
    h = ans(p)
    assert h.denominator == 1 and B0 + b * h < A0 + a * h and not B0 + b * (h - 1) < A0 + a * (h - 1)
    assert f"${A0} " in p.story and f"${B0} " in p.story


@verifies("check_solution")
def _(p):
    first, second = p.expr.split("\n")
    S = val(match(r"x \+ y = (−?\d+)", first)[1])

    def on_second(x, y):
        if m := re.fullmatch(r"x − y = (−?\d+)", second):
            return x - y == val(m[1])
        if m := re.fullmatch(r"(\d)x \+ y = (−?\d+)", second):
            return int(m[1]) * x + y == val(m[2])
        slope, b = any_line(second)
        return y == slope * x + b

    for i, choice in enumerate(p.choices):
        x, y = (val(v) for v in match(r"\((−?\d+), (−?\d+)\)", choice).groups())
        assert (x + y == S and on_second(x, y)) == (i == 0), choice


@verifies("count_solutions")
def _(p):
    (m1, b1), (m2, b2) = (any_line(s) for s in p.expr.split("\n"))
    want = "Exactly one solution" if m1 != m2 else "Infinitely many solutions" if b1 == b2 else "No solution"
    assert p.choices[0] == want and set(p.choices) == set(fa._SOLUTION_COUNTS.values())


@verifies("substitute_known_value")
def _(p):
    m = match(r"([xy]) = (\d+)\n(?:(\d+)x \+ y|x \+ (\d+)y) = (−?\d+)", p.expr)
    known, k, a, c = m[1], int(m[2]), int(m[3] or m[4]), int(val(m[5]))
    assert (known == "x") == (m[3] is not None)
    assert p.ask == f"What is {'y' if known == 'x' else 'x'}?" and ans(p) == c - a * k


@verifies("elimination_add")
def _(p):
    m = match(r"(\d*)x \+ (\d*)y = (−?\d+)\n(\d*)x − (\d*)y = (−?\d+)", p.expr)
    a1, b1, c1, a2, b2, c2 = (coef(g) for g in m.groups())
    assert b1 == b2 and ans(p) == Fraction(c1 + c2, a1 + a2)


@verifies("set_equal")
def _(p):
    (m1, b1), (m2, b2) = (any_line(s) for s in p.expr.split("\n"))
    x = ans(p)
    assert m1 != m2 and x.denominator == 1 and m1 * x + b1 == m2 * x + b2


@verifies("zero_product")
def _(p):
    if m := re.fullmatch(r"x\(x ([+−]) (\d+)\) = 0", p.expr):
        roots = {0, int(m[2]) * (1 if m[1] == "−" else -1)}
    else:
        assert p.expr.endswith(" = 0")
        roots = {-v for v in parse_factors(p.expr[: -len(" = 0")])}
    for i, choice in enumerate(p.choices):
        got = {val(v) for v in re.findall(r"x = (−?\d+)", choice)}
        assert (got == roots) == (i == 0), choice


@verifies("evaluate_quadratic")
def _(p):
    v, h0 = ints(match(r"h = −16t² \+ (\d+)t \+ (\d+)", p.expr))
    (s,) = ints(re.match(r"How high is it after (\d+) seconds", p.ask))
    assert ans(p) == -16 * s * s + v * s + h0 > 0


@verifies("axis_of_symmetry")
def _(p):
    m = match(r"y = (−?\d*)x² ([+−]) (\d*)x ([+−]) (\d+)", p.expr)
    a, b = coef(m[1]), coef(m[3]) * (-1 if m[2] == "−" else 1)
    assert ans(p) == Fraction(-b, 2 * a)


@verifies("power_of_a_product")
def _(p):
    m = match(rf"\((\d)x({SUP})\)({SUP}) ([·÷]) x({SUP})?", p.expr)
    k, e, n, q = int(m[1]), desup(m[2]), desup(m[3]), desup(m[5]) if m[5] else 1
    want = (k**n, e * n + (q if m[4] == "·" else -q))
    for i, choice in enumerate(p.choices):
        c = match(rf"(\d+)x({SUP})?", choice)
        assert ((int(c[1]), desup(c[2]) if c[2] else 1) == want) == (i == 0), choice


@verifies("scientific_quotient")
def _(p):
    m = match(rf"\(([\d.]+) × 10({SUP})\) ÷ \(([\d.]+) × 10({SUP})\)", p.expr)
    value = Decimal(m[1]) * Decimal(10) ** desup(m[2]) / (Decimal(m[3]) * Decimal(10) ** desup(m[4]))
    for i, choice in enumerate(p.choices):
        c = match(rf"([\d.]+) × 10({SUP})", choice)
        front = Decimal(c[1])
        assert (front * Decimal(10) ** desup(c[2]) == value and 1 <= front < 10) == (i == 0), choice


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_registry():
    assert len(fa.GENERATORS) == 69
    assert len(GENERATORS) == 69, "generator names must be unique"
    counts = {}
    for g in fa.GENERATORS:
        counts[g.topic] = counts.get(g.topic, 0) + 1
        expected_tier = 1 if g.name in TIER_1 else 3 if g.name in TIER_3 else 2
        assert g.tier == expected_tier, g.name
    assert counts == {"lin": 16, "sys": 12, "quad": 13, "exp": 16, "rx": 12}
    assert TIER_1 | TIER_3 <= set(GENERATORS)
    assert set(VERIFY) == set(GENERATORS), "every generator has an answer check"


def test_reactor_topic():
    """Reactor · Exponentials is a workshop topic of its own, paid in plasma, with four kinds of problem per tier."""
    from seabattle.problems import TOPICS, generators_for

    assert {g.topic for g in fa.GENERATORS} == {t for t, topic in TOPICS.items() if topic.school == "algebra"}
    rx = TOPICS["rx"]
    assert (rx.school, rx.name, rx.short, rx.currency) == ("algebra", "Reactor · Exponentials", "Exponentials", "plasma")
    assert sorted(g.tier for g in generators_for("rx")) == [1] * 4 + [2] * 4 + [3] * 4
    assert sup("t") == "ᵗ" and sup("n") == "ⁿ"
    assert fa._exact(Fraction(1331, 1000)) == "1.331" and fa._exact(1331) == "1,331" and fa._exact(Fraction(5, 2)) == "2.5"
    assert fa._root(Fraction(144, 100), 2) == Fraction(6, 5) and fa._root(Fraction(512, 1000), 3) == Fraction(4, 5)
    for a, b, c, m, t in fa._RACES:  # the exponential starts behind, passes the line at t and never ties it
        assert a < c and a * b ** (t - 1) < c + m * (t - 1) and a * b**t > c + m * t


@pytest.mark.parametrize("name", REACTOR)
def test_reactor_numbers_work_out_by_hand(name):
    """Every reading, answer and worked step is a whole number or has at most three decimals (1.331), and
    no step needs a calculator: the numbers in the solution are exact, never rounded."""
    for p in corpus(name):
        for t in (p.story, p.expr, *p.solution):
            for n in re.findall(r"\d[\d,]*(?:\.\d+)?", t):
                assert len(n.partition(".")[2]) <= 3, (n, t)
        assert "≈" not in " ".join(p.solution) and "about" not in " ".join(p.solution)


def test_help_briefings():
    assert len(fa.HELP) == 69
    for key, b in fa.HELP.items():
        assert isinstance(b, Briefing)
        assert b.title and b.concept and b.example and b.steps and all(b.steps), key
        for t in (b.title, b.concept, b.example, *b.steps):
            assert not re.search(r"</?[a-zA-Z]|&\w+;", t), (key, t)
    assert fa.HELP["exprule"].example == "x⁴ · x³ = x⁷  ·  x⁸ ÷ x² = x⁶  ·  (x²)⁵ = x¹⁰"
    assert fa.HELP["fuel"].example.split("\n") == [
        "A cutter has 200 tons, burns 8 tons/hr, must keep a 40-ton reserve.",
        "Usable = 200 − 40 = 160. Then 8t = 160, so t = 160 ÷ 8 = 20 hours.",
    ]
    used = {p.help for name in GENERATORS for p in corpus(name)}
    assert used == set(fa.HELP), "every briefing is used, and only briefings that exist"


BAD_WORDS = re.compile(r"\b(undefined|NaN|None|nan|inf|Infinity)\b|\[object")


@pytest.mark.parametrize("name", list(GENERATORS))
def test_problems_are_well_formed(name):
    for p in corpus(name):
        assert isinstance(p, Problem)
        assert len(p.choices) == 4 and len(set(p.choices)) == 4, p.choices
        assert all(isinstance(c, str) and c.strip() for c in p.choices), p.choices
        assert p.story and p.expr and p.ask and p.hint, p
        assert p.solution and all(isinstance(s, str) and s for s in p.solution), p.solution
        assert p.help in fa.HELP
        assert fa._FALLBACK_WHY not in p.why, p.choices  # every wrong choice is a real mistake, not a filler
        for t in texts(p):
            assert not re.search(r"</?[a-z]", t), t
            assert not BAD_WORDS.search(t), t
            assert "+ -" not in t and "+ −" not in t and "− −" not in t, t
            assert not re.search(r"(?<!\w)-\d", t), t  # negatives are printed with "−"
            assert "\t" not in t and not t.startswith(" ") and not t.endswith(" "), repr(t)


@pytest.mark.parametrize("name", list(GENERATORS))
def test_first_choice_is_correct(name):
    for p in corpus(name):
        VERIFY[name](p)


@pytest.mark.parametrize("name", list(GENERATORS))
def test_uses_only_ctx_randomness(name):
    fn = GENERATORS[name].fn
    for seed in range(15):
        random.seed(1)
        a = fn(Context(random.Random(seed), fleet=list(FLEET)))
        random.seed(2)
        b = fn(Context(random.Random(seed), fleet=list(FLEET)))
        assert a == b


def test_fleet_ships_appear_in_stories():
    lone = ShipRef("USS Wasp", "amphibious assault ship", 22, 1100)
    stories = [fa.distance_rate_time(Context(random.Random(s), fleet=[lone])).story for s in range(60)]
    assert all("USS Wasp" in s for s in stories)
    assert any("USS Wasp, an amphibious assault ship," in s for s in stories)

    # Without a fleet, the stand-in fleet is used.
    default_names = {s.name for s in fa.DEFAULT_FLEET}
    for seed in range(40):
        story = fa.fuel_burn(Context(random.Random(seed))).story
        assert any(n in story for n in default_names)

    # A pair always names two different ships; one ship is not enough for a pair.
    for seed in range(60):
        a, b = fa._fleet_pair(Context(random.Random(seed), fleet=list(FLEET)))
        assert {a.name, b.name} == {"USS Ajax", "USS Bonefish"}
        a, b = fa._fleet_pair(Context(random.Random(seed), fleet=[lone]))
        assert a != b and a in fa.DEFAULT_FLEET and b in fa.DEFAULT_FLEET
        story = fa.head_on_meeting(Context(random.Random(seed), fleet=list(FLEET))).story
        assert "USS Ajax" in story and "USS Bonefish" in story

    # The ratio problem names the ship with the bigger crew as the bigger one.
    crews = [fa.ratio_multiple(Context(random.Random(s), fleet=list(FLEET))).story for s in range(60)]
    assert any("USS Ajax carries" in s for s in crews)
    assert not any("USS Bonefish carries" in s for s in crews)


def test_helpers_match_javascript():
    assert fa._fmt(3) == "3" and fa._fmt(3.0) == "3" and fa._fmt(-4) == "−4"
    assert fa._fmt(12.5) == "12.5" and fa._fmt(2 / 3) == "0.67" and fa._fmt(-0.2) == "−0.2" and fa._fmt(2.999) == "3"
    assert fa._js_round(2.5) == 3 and fa._js_round(-2.5) == -2 and fa._js_round(-2.6) == -3
    assert fa._to_fixed(15.384615, 2) == "15.38" and fa._to_fixed(15, 2) == "15.00"
    assert fa._locale(3200000) == "3,200,000" and fa._locale(1.2 * 3) == "3.6" and fa._locale(42.5) == "42.5"
    assert fa._sgn(3) == "+ 3" and fa._sgn(-3) == "− 3"
    assert fa._lead(-3) == "−3" and fa._par(-3) == "(−3)" and fa._par(3) == "3"
    assert fa._factor_form(-2, 5) == "(x − 2)(x + 5)"
    assert fa._trinomial(-5, 6) == "x² − 5x + 6"
    assert fa._trinomial(1, -2) == "x² + x − 2" and fa._trinomial(-1, 0) == "x² − x + 0"
    assert fa._trinomial(0, -9) == "x² − 9"


def test_numeric_choices():
    ctx = Context(random.Random(3))

    def wrong(c):
        return sorted(zip(c.texts[1:], c.why[1:]))

    # Each wrong choice keeps its reason. Mistakes that aren't finite, are negative (unless allowed),
    # or print the same as the answer or as an earlier mistake are left out.
    c = fa._numeric_choices(ctx, 5, [(5, "same"), (-1, "neg"), (math.nan, "nan"), (6, "a"), (6.001, "dup"), (7, "b"), (8, "c")])
    assert c.texts[0] == "5" and c.why[0] == ""
    assert wrong(c) == [("6", "a"), ("7", "b"), ("8", "c")]
    c = fa._numeric_choices(ctx, 5, [(-1, "neg"), (6, "a"), (7, "b")], allow_neg=True)
    assert wrong(c) == [("6", "a"), ("7", "b"), ("−1", "neg")]
    c = fa._numeric_choices(ctx, 5, [(1 / 3, "third"), (4.5, "half"), (9, "nine")])  # printed like the answer
    assert wrong(c) == [("0.33", "third"), ("4.5", "half"), ("9", "nine")]

    # From a bigger pool, three are drawn: as often none, one, two or all three below the answer,
    # and never two that leave the answer exactly in the middle.
    below = collections.Counter()
    for seed in range(400):
        c = fa._numeric_choices(Context(random.Random(seed)), 10, [(v, str(v)) for v in (1, 4, 7, 13, 16, 19)])
        vals = [float(t) for t in c.texts[1:]]
        assert c.why[1:] == tuple(t for t in c.texts[1:])
        assert not any(math.isclose((a + b) / 2, 10) for a, b in itertools.combinations(vals, 2)), c.texts
        below[sum(v < 10 for v in vals)] += 1
    assert all(60 < below[n] < 140 for n in range(4)), below

    # Out of real mistakes: the last resort goes beyond every other value, never mirroring one around the answer.
    for seed in range(100):
        c = fa._numeric_choices(Context(random.Random(seed)), 10, [(4, "a")])
        assert c.texts[0] == "10" and len(set(c.texts)) == 4 and c.why.count(fa._FALLBACK_WHY) == 2
        extra = [float(t) for t, w in zip(c.texts, c.why) if w == fa._FALLBACK_WHY]
        assert min(extra) > 10 and 16 not in extra

    c = fa._string_choices(ctx, "a", [("b", "why b"), ("a", "same"), ("c", "why c"), ("b", "again"), ("d", "why d")])
    assert c.texts[0] == "a" and wrong(c) == [("b", "why b"), ("c", "why c"), ("d", "why d")]
    with pytest.raises(ValueError):  # too few left: say so, rather than show fewer than four choices
        fa._string_choices(ctx, "a", [("b", "why b"), ("a", "same"), ("c", "why c"), ("b", "again")])

    # The same number written another way is left out, unless that is the point of the problem.
    pool = [("3√2", "same", 18 ** 0.5), ("2√3", "x", 12 ** 0.5), ("6", "y", 6.0), ("9", "z", 9.0), ("√20", "w", 20 ** 0.5)]
    c = fa._string_choices(ctx, "√18", pool, 18 ** 0.5)
    assert "3√2" not in c.texts and len(c.texts) == 4
    for seed in range(40):
        c = fa._string_choices(Context(random.Random(seed)), "√18", pool, 18 ** 0.5, same_value_ok=True)
        if "3√2" in c.texts:
            break
    else:
        raise AssertionError("a same-value choice is never picked when it's allowed")


def test_font_renders_every_character():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    freetype = pytest.importorskip("pygame.freetype")
    chars = set()
    for name in GENERATORS:
        for p in corpus(name):
            for t in texts(p):
                chars.update(t)
    for b in fa.HELP.values():
        for t in (b.title, b.concept, b.example, *b.steps):
            chars.update(t)
    chars -= {"\n"}
    assert all(ord(c) < 0x10000 for c in chars)  # freetype metrics are only reliable in the BMP
    freetype.init()
    font = freetype.Font(FONT, 20)
    text = "".join(sorted(chars))
    missing = [c for c, m in zip(text, font.get_metrics(text)) if m is None]
    assert not missing, missing
