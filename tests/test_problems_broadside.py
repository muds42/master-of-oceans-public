"""Tests for the Broadside (Geometry & Trig) problem generators."""

from __future__ import annotations

import functools
import json
import math
import os
import random
import re
import zlib
from fractions import Fraction
from pathlib import Path
from typing import Callable

import pytest

from seabattle.problems import broadside
from seabattle.problems.broadside import GENERATORS, HELP, HELP_FIGURES
from seabattle.problems.common import Choices, Context, Problem

N = 300
ME, EN = "HMS Kestrel", "U-47"
FONT = Path(__file__).resolve().parents[1] / "seabattle" / "assets" / "fonts" / "DejaVuSans.ttf"

# The original game's trig tables, copied independently of the module under test.
TABLE = {
    10: (0.17, 0.98, 0.18), 20: (0.34, 0.94, 0.36), 30: (0.5, 0.87, 0.58), 37: (0.6, 0.8, 0.75),
    40: (0.64, 0.77, 0.84), 45: (0.71, 0.71, 1.0), 50: (0.77, 0.64, 1.19), 53: (0.8, 0.6, 1.33),
    60: (0.87, 0.5, 1.73), 70: (0.94, 0.34, 2.75), 80: (0.98, 0.17, 5.67),
}
COL = {"sin": 0, "cos": 1, "tan": 2}
SMALL = {1: 0.017, 2: 0.035, 3: 0.052, 4: 0.07, 5: 0.087}

GEN = {g.name: g for g in GENERATORS}
TIER2 = {
    "angle_between_bearings", "turn_between_courses", "parallel_lines", "distance_formula", "chart_scale",
    "similar_triangles", "triangle_30_60_90", "patrol_perimeter", "trig_find_angle", "stadimeter_range",
    "lead_angle", "trapezoid_area", "surface_area", "composite_area",
    "shield_equation", "torpedo_clearance", "tangent_length", "tangent_segments",
}
TOPIC_IDS = ("ang", "tri", "trig", "geo", "circ")
BAD_WORDS = ("undefined", "NaN", "None", "nan", "inf", "Infinity", "[object")


@functools.lru_cache(maxsize=None)
def samples(name: str, enemy: str = EN) -> tuple[Problem, ...]:
    ctx = Context(random.Random(zlib.crc32(name.encode())), my_name=ME, enemy_name=enemy)
    return tuple(GEN[name].fn(ctx) for _ in range(N))


def texts(p: Problem) -> list[str]:
    return [p.story, p.expr, p.note, p.ask, p.hint, *p.solution, *p.choices]


def fig_strings(obj) -> list[str]:
    if isinstance(obj, str):
        return [obj]
    if isinstance(obj, dict):
        return [s for v in obj.values() for s in fig_strings(v)]
    if isinstance(obj, (list, tuple)):
        return [s for v in obj for s in fig_strings(v)]
    return []


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


def test_registry():
    assert len(GENERATORS) == 71
    assert len(GEN) == 71, "generator names must be unique"
    standard = [g for g in GENERATORS if g.tier < 3]
    hard = [g for g in GENERATORS if g.tier == 3]
    assert len(standard) == 41 and len(hard) == 30
    count = lambda gs, t: sum(g.topic == t for g in gs)  # noqa: E731
    assert [count(standard, t) for t in TOPIC_IDS] == [9, 9, 6, 9, 8]
    assert [sum(g.topic == "trig" and g.tier == t for g in GENERATORS) for t in (1, 2, 3)] == [3, 3, 5]
    assert [count(hard, t) for t in TOPIC_IDS] == [4, 7, 5, 10, 4]
    assert [sum(g.topic == "circ" and g.tier == t for g in GENERATORS) for t in (1, 2, 3)] == [4, 4, 4]
    assert all(g.name.startswith("hard_") for g in hard)
    assert not any(g.name.startswith("hard_") for g in standard)
    assert {g.name for g in standard if g.tier == 2} == TIER2
    assert set(broadside.TOPICS) == set(TOPIC_IDS)
    assert broadside.TOPICS["circ"] == "Shields · Circles"


def test_trig_table_matches_original():
    assert broadside.TRIG == TABLE
    assert broadside.SMALL_TAN == SMALL
    assert broadside.TRIG_ANGLES == tuple(sorted(TABLE))


# ---------------------------------------------------------------------------
# Invariants for every generator
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", list(GEN))
def test_generator_invariants(name):
    for p in samples(name):
        assert isinstance(p, Problem)
        assert isinstance(p.choices, tuple) and len(p.choices) == 4, p.choices
        assert len(set(p.choices)) == 4, p.choices
        assert all(isinstance(c, str) and c.strip() for c in p.choices), p.choices
        for field in (p.story, p.expr, p.ask, p.hint):
            assert isinstance(field, str) and field.strip()
        assert isinstance(p.solution, tuple) and p.solution and all(s.strip() for s in p.solution)
        assert isinstance(p.note, str)
        assert p.help in HELP
        for t in texts(p):
            assert not re.search(r"</?[a-z]", t), t
            for bad in BAD_WORDS:
                assert bad not in t, (bad, t)
            assert not re.search(r"\d\.\d{5,}", t), f"float artifact in {t!r}"
        if p.fig is not None:
            assert isinstance(p.fig, dict) and isinstance(p.fig.get("kind"), str)
            json.dumps(p.fig)
            for s in fig_strings(p.fig):
                assert not re.search(r"</?[a-z]", s) and "undefined" not in s and "NaN" not in s, s
        # Numeric answers: every choice is a number shown with the same number of decimals.
        if re.fullmatch(r"[\d,]+(\.\d+)?", p.choices[0]):
            decimals = {len(c.split(".")[1]) if "." in c else 0 for c in p.choices}
            assert len(decimals) == 1, p.choices
            assert all(re.fullmatch(r"−?\d{1,3}(,\d{3})*(\.\d+)?", c) for c in p.choices), p.choices


def test_names_come_from_context():
    never_named = {"similar_triangles", "hard_similar_backwards"}  # these stories name no ship
    for name in GEN:
        ctx = Context(random.Random(7), my_name="SHIP-A", enemy_name="SHIP-B")
        joined = " ".join(t for _ in range(60) for t in texts(GEN[name].fn(ctx)))
        assert ("SHIP-A" in joined or "SHIP-B" in joined) != (name in never_named), name
        assert "USS Kestrel" not in joined and "Red destroyer" not in joined


def test_stadimeter_uses_the_enemys_mast():
    for name in ("stadimeter_range", "hard_stadimeter_angle"):
        for enemy, mast in (("Bismarck", 40), ("U-201", 12), ("Admiral Hipper", 35)):
            p = GEN[name].fn(Context(random.Random(3), my_name=ME, enemy_name=enemy))
            assert f"{mast} m" in p.story, p.story
    # An enemy the original game did not have gets one of the original enemies' masts.
    masts = {grab(r"^range = (\d+) ÷", GEN["stadimeter_range"].fn(Context(random.Random(s), enemy_name="Nobody")).expr)[0]
             for s in range(300)}
    assert masts == {e["mast"] for e in broadside.ENEMIES} == {10, 12, 25, 30, 35, 40}


# ---------------------------------------------------------------------------
# Help briefings
# ---------------------------------------------------------------------------


def test_help():
    assert len(HELP) == 41
    used = {p.help for name in GEN for p in samples(name)}
    assert used == set(HELP), set(HELP) ^ used
    for key, b in HELP.items():
        assert b.title and b.concept and b.steps and b.example, key
        assert isinstance(b.steps, tuple)
        for t in (b.title, b.concept, *b.steps, b.example):
            assert not re.search(r"</?[a-z]|&nbsp;|&[a-z]+;", t), (key, t)
        assert "\n" in b.example, key  # the worked example is several paragraphs
    assert set(HELP_FIGURES) == set(HELP)
    for figs in HELP_FIGURES.values():
        for f in figs:
            assert isinstance(f.get("kind"), str)
            json.dumps(f)


def test_figure_kinds():
    kinds = {p.fig["kind"] for name in GEN for p in samples(name) if p.fig}
    kinds |= {f["kind"] for figs in HELP_FIGURES.values() for f in figs}
    assert kinds == {
        "right_tri", "compass", "triangle", "angle_split", "polygon", "parallel", "scale_line", "similar", "grid",
        "rect", "tri_area", "circle", "arc", "box", "cyl", "trap", "composite",
        "shield", "tangents", "chord", "chords", "inscribed",
    }
    doc = broadside.__doc__
    for k in kinds:
        assert f'"{k}"' in doc, f"figure kind {k} is not documented"


SHIELD_FIGURES = {"shield", "tangents", "chord", "chords", "inscribed"}


def test_shield_figures_are_sketches():
    """The Shields figures are drawn the same shape whatever the numbers (no lengths, angles or
    centres to measure off them): the only numbers in them are the labels' text and a direction."""
    def numbers(o, key=None):
        if isinstance(o, dict):
            return [n for k, v in o.items() if k != "dir" for n in numbers(v, k)]
        if isinstance(o, (list, tuple)):
            return [n for v in o for n in numbers(v, key)]
        return [(key, o)] if isinstance(o, (int, float)) and not isinstance(o, bool) else []

    for name, g in GEN.items():
        for p in samples(name):
            if p.fig and p.fig["kind"] in SHIELD_FIGURES:
                assert g.topic == "circ" and not numbers(p.fig), (name, p.fig)
    for name, g in GEN.items():
        if g.topic == "circ":
            assert all(p.fig and p.fig["kind"] in SHIELD_FIGURES for p in samples(name)), name


# ---------------------------------------------------------------------------
# JS number helpers
# ---------------------------------------------------------------------------


def test_js_number_helpers():
    assert broadside._js(3.0) == "3" and broadside._js(0.125) == "0.125" and broadside._js(12) == "12"
    assert broadside._fmt_n(1234.5, 0) == "1,235"  # Intl rounds halves up
    assert broadside._fmt_n(1200, 1) == "1,200.0"
    assert broadside._fixed_num(22.5, 0) == 23.0  # toFixed: exact halves round up
    assert broadside._fixed_num(1.005, 2) == 1.0  # ...on the exact binary value
    assert broadside._jround(2.5) == 3 and broadside._jround(-2.5) == -2
    assert broadside._round1(2.25) == 2.3 and broadside._round1(12) == 12
    assert broadside._pad3(-30) == "330°" and broadside._pad3(45) == "045°" and broadside._pad3(360) == "000°"
    assert broadside._signed(-85) == "−85" and broadside._signed(12) == "12"
    assert broadside._fraction(120, 360) == "⅓" and broadside._fraction(30, 360) == "1/12" and broadside._fraction(360, 360) == "1"


def test_choice_helpers():
    why = {v: f"mistake {v}." for v in (10, -3, 12, 12.4, 15, 20, 7)}
    for seed in range(40):
        ctx = Context(random.Random(seed))
        # skips the answer again, the negative, the NaN, None, and 12.4 (not a whole number, the answer is)
        ch = broadside._numeric_choices(ctx, 10, [(10, "a"), (-3, "b"), (float("nan"), "c"), None, (12, why[12]),
                                                  (12.4, "d"), (15, why[15]), (20, why[20]), (7, why[7])])
        assert isinstance(ch, Choices) and ch.texts[0] == "10" and ch.why[0] == ""
        assert set(ch.texts[1:]) <= {"12", "15", "20", "7"} and len(set(ch.texts)) == 4
        assert all(w == f"mistake {t}." for t, w in zip(ch.texts[1:], ch.why[1:]))
        # never the answer halfway between two others: 10 is halfway between 7 and 13, 5 and 15
        ch = broadside._numeric_choices(ctx, 10, [(5, "p."), (15, "q."), (7, "r."), (13, "s."), (30, "t.")])
        vals = [float(t) for t in ch.texts]
        assert not any(vals[i] + vals[j] == 20 for i in range(1, 4) for j in range(i + 1, 4)), ch.texts
        # dp 1 for a fractional answer; "auto" shows whole numbers when all four are whole
        assert broadside._numeric_choices(ctx, 2.5, [(5, "a."), (1.25, "b."), (7, "c.")]).texts[0] == "2.5"
        assert broadside._numeric_choices(ctx, 20, [(5, "a."), (10, "b."), (40, "c.")], dp="auto").texts[0] == "20"
        assert broadside._numeric_choices(ctx, 20, [(5.5, "a."), (10, "b."), (40, "c.")], dp="auto").texts[0] == "20.0"
        # the calculator's value is never offered
        ch = broadside._numeric_choices(ctx, 2.7, [(2.55, "a."), (1.8, "b."), (5.4, "c."), (8.1, "d.")], dp="auto", avoid=[2.64])
        assert "2.6" not in ch.texts and "2.7" == ch.texts[0]
        ch = broadside._string_choices(ctx, "a", [("a", "x."), ("b", "b."), None, ("b", "y."), ("c", "c."), ("d", "d.")])
        assert ch.texts[0] == "a" and sorted(ch.texts[1:]) == ["b", "c", "d"]
        assert dict(zip(ch.texts, ch.why)) == {"a": "", "b": "b.", "c": "c.", "d": "d."}
    # a choice that is the answer written another way is not a wrong choice
    ch = broadside._string_choices(Context(random.Random(0)), "4π ft", [("4π ft", "x."), ("8π ft", "a."), ("2π ft", "b."), ("16π ft", "c.")])
    assert sorted(ch.texts) == sorted(["4π ft", "8π ft", "2π ft", "16π ft"])
    with pytest.raises(ValueError):
        broadside._string_choices(Context(random.Random(0)), "a", [("b", "b."), ("c", "c.")])


# ---------------------------------------------------------------------------
# Independent answer checks: re-derive choices[0] from the problem text
# ---------------------------------------------------------------------------


def grab(pattern: str, text: str) -> list:
    m = re.search(pattern, text)
    assert m, f"{pattern!r} not in {text!r}"
    out = []
    for g in m.groups():
        if g is not None and re.fullmatch(r"-?\d{1,3}(,\d{3})+|-?\d+", g):
            out.append(int(g.replace(",", "")))
        elif g is not None and re.fullmatch(r"-?\d+\.\d+", g):
            out.append(float(g))
        else:
            out.append(g)
    return out


def num(choice: str) -> float:
    return float(choice.replace(",", ""))


def jsnum(x) -> str:
    x = Fraction(x)
    return str(x.numerator) if x.denominator == 1 else repr(float(x))


def half_up(x: float) -> int:
    return math.floor(x + 0.5)


def round1(x: float) -> float:
    return math.floor(x * 10 + 0.5) / 10


def assert_num(p: Problem, expected, tol: float = 1e-9) -> None:
    assert abs(num(p.choices[0]) - float(expected)) <= tol, (p.choices, expected, p.expr, p.story)


def nearest(values: dict[int, float], x: float) -> int:
    ranked = sorted(values, key=lambda k: abs(values[k] - x))
    return ranked[0]


V: dict[str, Callable[[Problem], None]] = {}


def verifies(fn: Callable[[Problem], None]) -> Callable[[Problem], None]:
    V[fn.__name__[2:]] = fn
    return fn


# ---- Lookout · Angles ----

@verifies
def v_relative_to_true_bearing(p):
    H, R = grab(r"^(\d{3})° \+ (\d+)° = \?$", p.expr)
    assert f"course {H:03d}" in p.story and f"bearing {R}° relative" in p.story
    assert p.choices[0] == f"{(H + R) % 360:03d}°"


@verifies
def v_angle_between_bearings(p):
    a, b = grab(r"^(\d{3})° and (\d{3})°$", p.expr)
    d = abs(a - b)
    assert_num(p, min(d, 360 - d))


@verifies
def v_triangle_angle_sum(p):
    A, B = grab(r"^(\d+)° \+ (\d+)° \+ x = 180°$", p.expr)
    assert f"The angle at {ME} is {A}°" in p.story and f"escort is {B}°" in p.story
    assert_num(p, 180 - A - B)


@verifies
def v_supplementary_complementary(p):
    t, total = grab(r"^(\d+)° \+ x = (180|90)°$", p.expr)
    assert total == (180 if "stern" in p.ask else 90)
    assert f"{t}°" in p.story
    assert_num(p, total - t)


@verifies
def v_course_change(p):
    H, op, d = grab(r"^(\d{3})° ([+−]) (\d+)°$", p.expr)
    side, d2 = grab(r"come (starboard|port) (\d+) degrees", p.story)
    assert d2 == d and (op == "+") == (side == "starboard")
    assert p.choices[0] == f"{(H + d if side == 'starboard' else H - d) % 360:03d}°"


@verifies
def v_turn_between_courses(p):
    new, old = grab(r"^(\d{3})° − (\d{3})°$", p.expr)
    assert f"on course {old:03d}" in p.story and f"new course of {new:03d}" in p.story
    assert_num(p, (new - old) % 360)


@verifies
def v_regular_polygon_angles(p):
    if "interior" in p.ask:
        (n,) = grab(r"with n = (\d+)$", p.expr)
        assert_num(p, Fraction((n - 2) * 180, n))
    else:
        (n,) = grab(r"^360° ÷ (\d+)$", p.expr)
        assert_num(p, Fraction(360, n))
    assert f"{n} equal" in p.story


@verifies
def v_isosceles_triangle(p):
    m = re.fullmatch(r"(\d+)° \+ x \+ x = 180°", p.expr)
    if m:
        apex = int(m.group(1))
        assert f"The angle at the tip is {apex}°" in p.story
        assert_num(p, Fraction(180 - apex, 2))
    else:
        (b,) = grab(r"^(\d+)° \+ \1° \+ x = 180°$", p.expr)
        assert_num(p, 180 - 2 * b)


@verifies
def v_parallel_lines(p):
    (t,) = grab(r"one crossing line, (\d+)°$", p.expr)
    assert f"first column at {t}°" in p.story
    assert_num(p, 180 - t if "co-interior" in p.ask else t)


# ---- Plot · Triangles ----

@verifies
def v_pythagorean_range(p):
    a, b = grab(r"^(\d+)² \+ (\d+)² = r²$", p.expr)
    assert f"{a} nm east and {b} nm north" in p.story
    c = math.hypot(a, b)
    assert c.is_integer()
    assert_num(p, c)


@verifies
def v_pythagorean_leg(p):
    a, c = grab(r"^(\d+)² \+ n² = (\d+)²$", p.expr)
    assert f"Range to {EN} is {c} nm" in p.story and f"{a} nm east" in p.story
    assert_num(p, math.isqrt(c * c - a * a))
    assert math.isqrt(c * c - a * a) ** 2 == c * c - a * a


@verifies
def v_distance_formula(p):
    (x1, y1), (x2, y2) = [tuple(map(int, t)) for t in re.findall(r"\((\d+), (\d+)\)", p.story)]
    d = math.hypot(x2 - x1, y2 - y1)
    assert d.is_integer()
    assert_num(p, d)


@verifies
def v_chart_scale(p):
    (k,) = grab(r"1 cm on paper is (\d+) nm", p.story)
    if "measures" in p.story:
        (m,) = grab(r"measures ([\d.]+) cm", p.story)
        assert_num(p, k * m)
    else:
        (d,) = grab(r"is ([\d.]+) nm away", p.story)
        assert_num(p, d / k)


@verifies
def v_similar_triangles(p):
    a, b, c, big = grab(r"sides (\d+), (\d+) and (\d+) nm\. The big one's shortest side is (\d+) nm", p.story)
    assert a * a + b * b == c * c and a < b
    assert_num(p, Fraction(c * big, a))


@verifies
def v_diagonal_45_45_90(p):
    (s,) = grab(r"(\d+) nm (?:each way|on each side)", p.story)
    assert p.choices[0] == f"{s}√2 nm"


@verifies
def v_midpoint(p):
    (x1, y1), (x2, y2) = [tuple(map(int, t)) for t in re.findall(r"\((\d+), (\d+)\)", p.story)]
    assert (x1 + x2) % 2 == 0 and (y1 + y2) % 2 == 0
    assert p.choices[0] == f"({(x1 + x2) // 2}, {(y1 + y2) // 2})"


@verifies
def v_triangle_30_60_90(p):
    if "range of" in p.story:
        (r,) = grab(r"range of (\d+) nm", p.story)
        assert "off your track" in p.ask
        assert_num(p, r / 2)
    else:
        (s,) = grab(r"and (\d+) nm off your track, the side across from the 30° angle", p.story)
        assert "range" in p.ask
        assert_num(p, 2 * s)


@verifies
def v_patrol_perimeter(p):
    a, b, c = grab(r"^(\d+) \+ (\d+) \+ (\d+)$", p.expr)
    assert f"{a} nm on the first leg, {b} nm on the second, then {c} nm" in p.story
    x, y, z = sorted((a, b, c))
    assert x * x + y * y == z * z
    assert_num(p, a + b + c)


# ---- Gunnery · Trig ----

@verifies
def v_trig_find_side(p):
    g, op, fn, th = grab(r"^x = (\d+) (×|÷) (sin|cos|tan) (\d+)°$", p.expr)
    val = TABLE[th][COL[fn]]
    assert p.note == f"{fn} {th}° ≈ {jsnum(val)}"
    assert f"{g}" in p.story and f"{th}°" in p.story
    # the ratio must fit the sides named in the story
    if "angle of depression" in p.story:
        assert (fn, op) == ("tan", "÷")
    elif "hypotenuse" in p.story:
        assert fn == ("sin" if "opposite" in p.story else "cos") and op == "×"
    else:
        assert (fn, op) == ("tan", "×")
    assert_num(p, round1(g * val if op == "×" else g / val))


@verifies
def v_trig_ratio(p):
    off, along, rng = grab(r"is (\d+) nm off your track and (\d+) nm ahead along it: (\d+) nm away", p.story)
    assert off * off + along * along == rng * rng
    (fn,) = grab(r"^(sin|cos|tan) θ = \? ÷ \?$", p.expr)
    at_target = "θ is the angle at U-47" in p.story
    opp, adj = (along, off) if at_target else (off, along)
    assert ("ang2" in p.fig) == at_target and ("ang" in p.fig) != at_target
    want = {"sin": (opp, rng), "cos": (adj, rng), "tan": (opp, adj)}[fn]
    for i, choice in enumerate(p.choices):
        top, bottom = grab(r"^(\d+)/(\d+)$", choice)
        assert ((top, bottom) == want) == (i == 0), choice


@verifies
def v_trig_which_ratio(p):
    th, known, g, want = grab(r"^θ = (\d+)°,  (opposite side|adjacent side|hypotenuse) = (\d+) nm,  "
                              r"(opposite side|adjacent side|hypotenuse) = x$", p.expr)
    assert th in TABLE and th != 45 and f"{th}°" in p.story
    k, w = known.split()[0][:3], want.split()[0][:3]
    for i, choice in enumerate(p.choices):
        g2, op, fn, th2 = grab(r"^x = (\d+) (×|÷) (sin|cos|tan) (\d+)°$", choice)
        assert (g2, th2) == (g, th)
        top, bottom = {"sin": ("opp", "hyp"), "cos": ("adj", "hyp"), "tan": ("opp", "adj")}[fn]
        right = {k, w} == {top, bottom} and op == ("×" if w == top else "÷")
        assert right == (i == 0), choice


@verifies
def v_trig_find_angle(p):
    fn, a, b, r = grab(r"^(sin|cos|tan) θ = \w+ ÷ \w+ = (\d+) ÷ (\d+) = ([\d.]+)$", p.expr)
    assert abs(float(r) - a / b) < 0.005
    th = nearest({k: v[COL[fn]] for k, v in TABLE.items()}, a / b)
    assert abs(TABLE[th][COL[fn]] - a / b) < 0.005
    assert p.choices[0] == f"{th}°"


@verifies
def v_stadimeter_range(p):
    H, th = grab(r"^range = (\d+) ÷ tan (\d)°$", p.expr)
    assert f"mast height as {H} m" in p.story and p.note == f"tan {th}° ≈ {SMALL[th]}"
    assert_num(p, half_up(H / SMALL[th]))


@verifies
def v_lead_angle(p):
    if p.expr.startswith("lead distance"):
        v, t = grab(r"^lead distance = (\d+) m/s × (\d+) s$", p.expr)
        assert_num(p, v * t)
    else:
        v, t, R = grab(r"^lead = (\d+) × (\d+);\s+tan\(lead angle\) = lead ÷ ([\d,]+)$", p.expr)
        th = nearest({k: v_[2] for k, v_ in TABLE.items()}, v * t / R)
        assert abs(TABLE[th][2] - v * t / R) < 0.005, "the lead ÷ range must be a value in the tan column"
        assert p.choices[0] == f"{th}°"


# ---- Engineering · Area & Volume ----

@verifies
def v_rectangle(p):
    if m := re.fullmatch(r"A = (\d+) × (\d+)", p.expr):
        assert_num(p, int(m[1]) * int(m[2]))
    elif m := re.fullmatch(r"P = 2 × (\d+) \+ 2 × (\d+)", p.expr):
        assert_num(p, 2 * int(m[1]) + 2 * int(m[2]))
    else:
        A, W = grab(r"^([\d,]+) = L × (\d+)$", p.expr)
        assert_num(p, A / W)


@verifies
def v_triangle_area(p):
    b, h = grab(r"^A = ½ × (\d+) × (\d+)$", p.expr)
    assert_num(p, Fraction(b * h, 2))


@verifies
def v_circle(p):
    if m := re.fullmatch(r"C = π × d, with d = (\d+)", p.expr):
        assert p.choices[0] == f"{m[1]}π ft"
    elif m := re.fullmatch(r"A = π × r², with r = (\d+)", p.expr):
        assert p.choices[0] == f"{int(m[1]) ** 2}π sq nm"
    elif m := re.fullmatch(r"C = 3\.14 × (\d+)", p.expr):
        assert_num(p, round1(3.14 * int(m[1])))
    else:
        (r,) = grab(r"^A = 3\.14 × (\d+)²$", p.expr)
        assert_num(p, round1(3.14 * r * r))


@verifies
def v_arc_length(p):
    th, r = grab(r"^arc = \((\d+) ÷ 360\) × 2π × (\d+)$", p.expr)
    assert f"radius of {r} yards" in p.story and f"through {th}°" in p.story
    assert p.choices[0] == f"{jsnum(Fraction(th, 360) * 2 * r)}π yd"


@verifies
def v_box_volume(p):
    L, W, H = grab(r"^V = (\d+) × (\d+) × (\d+)$", p.expr)
    assert_num(p, L * W * H)


@verifies
def v_cylinder_volume(p):
    r, h = grab(r"radius (\d+) ft, height (\d+) ft", p.story)
    assert p.choices[0] == f"{r * r * h}π cubic ft"


@verifies
def v_trapezoid_area(p):
    a, b, h = grab(r"^A = \((\d+) \+ (\d+)\) ÷ 2 × (\d+)$", p.expr)
    assert a < b
    assert_num(p, Fraction(a + b, 2) * h)


@verifies
def v_surface_area(p):
    l, w, h = grab(r"^SA = 2\((\d+)×(\d+) \+ \1×(\d+) \+ \2×\3\)$", p.expr)  # noqa: E741
    assert f"{l} ft long, {w} ft wide and {h} ft tall" in p.story
    assert_num(p, 2 * (l * w + l * h + w * h))


@verifies
def v_composite_area(p):
    L, W, b = grab(r"^A = (\d+) × (\d+) \+ ½ × \2 × (\d+)$", p.expr)
    assert_num(p, L * W + Fraction(W * b, 2))


# ---- Missiles: angles ----

@verifies
def v_hard_relative_bearing_after_turn(p):
    H, R = grab(r"on course (\d{3})° when the lookout reports .* bearing (\d+)° relative", p.story)
    side, d = grab(r"come (starboard|port) (\d+) degrees", p.story)
    true = (H + R) % 360
    new = (H + d if side == "starboard" else H - d) % 360
    assert p.choices[0] == f"{(true - new) % 360}°"


@verifies
def v_hard_related_triangle_angles(p):
    if m := re.fullmatch(r"2x \+ x \+ (\d+)° = 180°", p.expr):
        C = int(m[1])
        assert f"at {EN} is {C}°" in p.story and "twice" in p.story
        assert_num(p, 2 * Fraction(180 - C, 3))
    else:
        k, C = grab(r"^\(x \+ (\d+)°\) \+ x \+ (\d+)° = 180°$", p.expr)
        assert f"{k}° bigger" in p.story
        x = Fraction(180 - C - k, 2)
        assert_num(p, x if p.ask.endswith("at the escort?") else x + k)
        assert p.ask.endswith("at the escort?") or p.ask.endswith(f"at {ME}?")


@verifies
def v_hard_polygons(p):
    if m := re.fullmatch(r"exterior = 180° − (\d+)°", p.expr):
        interior = int(m[1])
        n = Fraction(360, 180 - interior)
        assert n.denominator == 1 and Fraction((n - 2) * 180, n) == interior
        assert_num(p, n)
    else:
        n, total = grab(r"^\((\d+) − 2\) × 180° = (\d+)°$", p.expr)
        assert total == (n - 2) * 180
        angles = [int(a) for a in re.fullmatch(r"([\d +]+) \+ x = \d+", p.note)[1].split(" + ")]
        assert len(angles) == n - 1 and ", ".join(f"{a}°" for a in angles) in p.story
        assert_num(p, total - sum(angles))


@verifies
def v_hard_zigzag_parallel(p):
    t1, t2 = grab(r"cuts across it at (\d+)°.* again at (\d+)°", p.story)
    assert_num(p, 180 - t1 - t2 if "angle between the two legs" in p.ask else t1 + t2)


# ---- Missiles: triangles ----

@verifies
def v_hard_pythagoras_after_move(p):
    e0, n0 = grab(r"(\d+) nm east and (\d+) nm north of", p.story)
    x, way = grab(r"steams (\d+) nm due (east|north)", p.story)
    r = math.hypot(e0 - x, n0) if way == "east" else math.hypot(e0, n0 - x)
    assert r.is_integer()
    assert_num(p, r)


@verifies
def v_hard_nearer_escort(p):
    pts = [tuple(int(v.replace("−", "-")) for v in t) for t in re.findall(r"\((−?\d+), (−?\d+)\)", p.story)]
    (x0, y0), (x1, y1), (x2, y2) = pts
    e1, e2 = grab(r"Escort (.+?) is at .* and escort (.+?) is at", p.story)
    d1, d2 = math.hypot(x1 - x0, y1 - y0), math.hypot(x2 - x0, y2 - y0)
    assert d1.is_integer() and d2.is_integer() and d1 != d2
    assert p.ask.startswith(f"{e1 if d1 < d2 else e2} is the nearer one")
    assert_num(p, abs(d1 - d2))


@verifies
def v_hard_scale_then_pythagoras(p):
    (k,) = grab(r"1 cm = (\d+) nm", p.story)
    a, b = grab(r"(\d+) cm east and (\d+) cm north", p.story)
    assert_num(p, math.hypot(a, b) * k)


@verifies
def v_hard_similar_backwards(p):
    A, B, C, c = grab(r"sides (\d+), (\d+) and (\d+) nm\. The small one's longest side is (\d+) nm", p.story)
    assert A * A + B * B == C * C and A < B
    (which,) = grab(r"small triangle's (shortest|middle) side\?$", p.ask)
    assert_num(p, Fraction((A if which == "shortest" else B) * c, C))


@verifies
def v_hard_special_right_backwards(p):
    if p.help == "sqdiag":
        (D,) = grab(r"corner to corner is (\d+) nm", p.story)
        assert p.choices[0] == f"{D // 2}√2 nm"  # D / √2 = (D / 2)√2
    else:
        (D,) = grab(r"range of (\d+) nm", p.story)
        assert p.choices[0] == f"{D // 2}√3 nm"


@verifies
def v_hard_midpoint_backwards(p):
    (mx, my), (x1, y1) = [tuple(map(int, t)) for t in re.findall(r"\((\d+), (\d+)\)", p.story)][:2]
    assert p.choices[0] == f"({2 * mx - x1}, {2 * my - y1})"


@verifies
def v_hard_right_patrol_perimeter(p):
    a, b = grab(r"(\d+) nm due east, a sharp turn, (\d+) nm due north", p.story)
    c = math.hypot(a, b)
    assert c.is_integer()
    assert_num(p, a + b + c)


# ---- Missiles: trig ----

@verifies
def v_hard_trig_find_hypotenuse(p):
    fn, th, g = grab(r"^(sin|cos) (\d+)° = (\d+) ÷ hyp$", p.expr)
    assert fn == ("cos" if "ahead" in p.story else "sin")
    assert_num(p, round1(g / TABLE[th][COL[fn]]))


@verifies
def v_hard_opposite_bows(p):
    R1, th1, R2, th2 = grab(r"^(\d+) × sin (\d+)° \+ (\d+) × sin (\d+)°$", p.expr)
    exact = R1 * TABLE[th1][0] + R2 * TABLE[th2][0]
    assert_num(p, round1(round1(R1 * TABLE[th1][0]) + round1(R2 * TABLE[th2][0])))
    assert abs(num(p.choices[0]) - exact) <= 0.1 + 1e-9


@verifies
def v_hard_which_ratio(p):
    fn, a, b = grab(r"^(sin|cos|tan) θ = \w+ ÷ \w+ = (\d+) ÷ (\d+)$", p.expr)
    if "straight line" in p.story:
        assert fn == ("cos" if "ahead" in p.story else "sin")
    else:
        assert fn == "tan"
    col = {k: v[COL[fn]] for k, v in TABLE.items()}
    th = nearest(col, a / b)
    assert abs(col[th] - a / b) < 0.02
    assert p.choices[0] == f"{th}°"


@verifies
def v_hard_stadimeter_angle(p):
    H, R = grab(r"^tan\(angle\) = (\d+) ÷ ([\d,]+)$", p.expr)
    assert p.choices[0] == f"{nearest(SMALL, H / R)}°"


@verifies
def v_hard_lead_backwards(p):
    R, th = grab(r"^lead = ([\d,]+) × tan (\d+)°$", p.expr)
    lead = R * TABLE[th][2]
    if m := re.fullmatch(r"time = lead ÷ (\d+)", p.note):
        assert f"at {m[1]} m/s" in p.story
        assert_num(p, lead / int(m[1]), 1e-6)
    else:
        (t,) = grab(r"^speed = lead ÷ (\d+)$", p.note)
        assert f"take {t} seconds" in p.story
        assert_num(p, lead / t, 1e-6)


# ---- Missiles: area & volume ----

@verifies
def v_hard_rectangle_missing_side(p):
    if m := re.fullmatch(r"(\d+) = 2L \+ 2 × (\d+)", p.expr):
        P, W = int(m[1]), int(m[2])
        assert_num(p, (Fraction(P, 2) - W) * W)
    else:
        A, W = grab(r"^([\d,]+) = L × (\d+)$", p.expr)
        assert_num(p, 2 * Fraction(A, W) + 2 * W)


@verifies
def v_hard_triangle_height(p):
    A, b = grab(r"^([\d,]+) = ½ × (\d+) × h$", p.expr)
    assert_num(p, Fraction(2 * A, b))


@verifies
def v_hard_circle_conversions(p):
    if m := re.fullmatch(r"C = π × d = (\d+)π, so d = \1", p.expr):
        assert p.choices[0] == f"{jsnum(Fraction(int(m[1]), 2) ** 2)}π sq ft"
    else:
        (A,) = grab(r"^A = π × r² = (\d+)π, so r = √\1$", p.expr)
        r = math.isqrt(A)
        assert r * r == A and p.choices[0] == f"{2 * r}π nm"


@verifies
def v_hard_sector_area(p):
    th, r = grab(r"^A = \((\d+) ÷ 360\) × π × (\d+)²$", p.expr)
    area = Fraction(th, 360) * r * r
    assert area.denominator == 1
    assert p.choices[0] == f"{area}π sq nm"


@verifies
def v_hard_box_depth(p):
    V, L, W = grab(r"^([\d,]+) = (\d+) × (\d+) × h$", p.expr)
    assert "in inches" in p.ask and "12 inches to a foot" in p.story
    assert_num(p, Fraction(V, L * W) * 12)


@verifies
def v_hard_cylinder_diameter(p):
    (d,) = grab(r"^r = (\d+) ÷ 2$", p.expr)
    (h,) = grab(r"^V = π × r² × (\d+)$", p.note)
    assert f"{d} ft across and {h} ft tall" in p.story
    assert p.choices[0] == f"{jsnum(Fraction(d, 2) ** 2 * h)}π cubic ft"


@verifies
def v_hard_trapezoid_height(p):
    A, a, b = grab(r"^(\d+) = \((\d+) \+ (\d+)\) ÷ 2 × h$", p.expr)
    assert_num(p, Fraction(A) / Fraction(a + b, 2))


@verifies
def v_hard_open_locker(p):
    l, w, h = grab(r"^SA = (\d+)×(\d+) \+ 2 × \1×(\d+) \+ 2 × \2×\3$", p.expr)  # noqa: E741
    assert f"{l} ft long, {w} ft wide and {h} ft tall" in p.story
    assert_num(p, l * w + 2 * l * h + 2 * w * h)


@verifies
def v_hard_deck_cutout(p):
    L, W, a, b = grab(r"^A = (\d+) × (\d+) − (\d+) × (\d+)$", p.expr)
    assert_num(p, L * W - a * b)


@verifies
def v_hard_triangular_prism(p):
    b, h, L = grab(r"^V = \(½ × (\d+) × (\d+)\) × (\d+)$", p.expr)
    assert_num(p, Fraction(b * h, 2) * L)


# ---- Shields · Circles ----

POINT = r"\((−?\d+), (−?\d+)\)"


def signed(v) -> int:
    """A number from the text, with its proper minus sign: "−3" -> -3."""
    return int(str(v).replace("−", "-"))


def fmt(n: int) -> str:
    return f"−{-n}" if n < 0 else str(n)


def circle_eq(h: int, k: int, rhs: int) -> str:
    """(x − h)² + (y − k)² = rhs as a player writes it: (x − 3)² + (y + 2)² = 49."""
    def bracket(v: str, c: int) -> str:
        return v if c == 0 else f"({v} − {c})" if c > 0 else f"({v} + {-c})"
    return f"{bracket('x', h)}² + {bracket('y', k)}² = {rhs}"


def whole_sqrt(n: int) -> int:
    r = math.isqrt(n)
    assert r * r == n, f"{n} is not a perfect square: not doable by hand"
    return r


@verifies
def v_shield_centre_radius(p):
    m = re.fullmatch(r"\(x ([−+]) (\d+)\)² \+ \(y ([−+]) (\d+)\)² = (\d+)", p.expr)
    assert m and p.expr in p.story, p.expr
    h = int(m[2]) if m[1] == "−" else -int(m[2])  # (x − 3) is centred on x = 3
    k = int(m[4]) if m[3] == "−" else -int(m[4])
    assert circle_eq(h, k, int(m[5])) == p.expr
    assert p.choices[0] == f"({fmt(h)}, {fmt(k)}), r = {whole_sqrt(int(m[5]))}"


@verifies
def v_inscribed_angle(p):
    if "diameter" in p.story:
        (x,) = grab(r"At A, the line to .+ makes (\d+)° with the diameter\.$", p.story)
        assert p.ask.startswith("At B")
        assert_num(p, 90 - x)  # the angle facing the diameter is 90°
    elif m := re.search(r"Seen from the shield's centre, they are (\d+)° apart", p.story):
        assert "far side" in p.story
        assert_num(p, Fraction(int(m[1]), 2))
    else:
        (rim,) = grab(r"on the edge, (\d+)° apart", p.story)
        assert "at the centre" in p.ask
        assert_num(p, 2 * rim)


@verifies
def v_tangent_radius_angle(p):
    (x,) = grab(r"(?:makes|make) (\d+)°", p.story)
    assert "meets the course at 90°" in p.story
    given_at_centre = "At the centre, the radius" in p.story
    assert p.ask.startswith(f"At {ME}," if given_at_centre else "At the centre,"), "asks for the other angle"
    assert_num(p, 90 - x)


@verifies
def v_cyclic_quadrilateral(p):
    g, x = grab(r"angle at ([ABCD]): (\d+)°\.$", p.story)
    a, g2 = grab(r"^What is the angle at ([ABCD]), the corner opposite ([ABCD])\?$", p.ask)
    assert g2 == g and {g, a} in ({"A", "C"}, {"B", "D"}), (g, a)
    assert_num(p, 180 - x)


@verifies
def v_shield_equation(p):
    h, k, r = grab(rf"sits at {POINT} on the grid, and the force field reaches (\d+) nm", p.story)
    assert p.choices[0] == circle_eq(signed(h), signed(k), r * r)


@verifies
def v_torpedo_clearance(p):
    r, h, k, x, y = map(signed, grab(rf"shield (\d+) nm in radius, centred on {POINT} .* running at {POINT}", p.story))
    d = whole_sqrt((x - h) ** 2 + (y - k) ** 2)
    assert d > r, "the torpedo must be outside the shield"
    assert_num(p, d - r)


@verifies
def v_tangent_length(p):
    d, r = grab(r"is (\d+) nm from the centre of .+ which reaches (\d+) nm out", p.story)
    assert_num(p, whole_sqrt(d * d - r * r))


@verifies
def v_tangent_segments(p):
    m = re.search(r"PA = (\d*)x \+ (\d+) nm and PB = (\d*)x − (\d+) nm", p.story)
    assert m, p.story
    a1, b1, a2, c = int(m[1] or 1), int(m[2]), int(m[3] or 1), int(m[4])
    x = Fraction(b1 + c, a2 - a1)
    assert x.denominator == 1 and x > 0
    assert a1 * x + b1 == a2 * x - c
    assert_num(p, a1 * x + b1)


@verifies
def v_hard_chord_length(p):
    if m := re.search(r"radius is (\d+) nm, and at the closest point her course passes (\d+) nm from its centre", p.story):
        r, d = int(m[1]), int(m[2])
        assert "inside the shield" in p.ask
        assert_num(p, 2 * whole_sqrt(r * r - d * d))
    else:
        r, run = grab(r"radius of (\d+) nm\. .+ spent (\d+) nm inside the field", p.story)
        assert run % 2 == 0 and "centre" in p.ask
        assert_num(p, whole_sqrt(r * r - (run // 2) ** 2))


@verifies
def v_hard_tangent_arc(p):
    if m := re.search(r"is an arc of (\d+)°", p.story):
        assert p.ask.startswith("At what angle")
        assert_num(p, 180 - int(m[1]))  # two right angles, the arc's angle at the centre, and this make 360°
    else:
        (x,) = grab(r"meet at .+ at an angle of (\d+)°", p.story)
        assert ("short arc" in p.ask) != ("long arc" in p.ask)
        assert_num(p, 180 - x if "short arc" in p.ask else 180 + x)


@verifies
def v_hard_intersecting_chords(p):
    a, b, c = grab(r"first run into (\d+) nm and (\d+) nm\. On the second run, (\d+) nm", p.story)
    x = Fraction(a * b, c)
    assert x.denominator == 1
    assert_num(p, c + x if "from edge to edge?" in p.ask else x)


@verifies
def v_hard_equation_from_point(p):
    h, k, x, y = map(signed, grab(rf"generator sits at {POINT} .* she is at {POINT}", p.story))
    assert p.choices[0] == circle_eq(h, k, (x - h) ** 2 + (y - k) ** 2)


def test_every_generator_is_verified():
    assert set(V) == set(GEN)


@pytest.mark.parametrize("name", sorted(V))
def test_answer_is_correct(name):
    for p in samples(name):
        V[name](p)


# ---------------------------------------------------------------------------
# Wrong choices: each one is a mistake, and says which
# ---------------------------------------------------------------------------


@functools.lru_cache(maxsize=None)
def many(name: str, n: int = 1000) -> tuple[Problem, ...]:
    """More problems than ``samples``, for things that go wrong once in a few hundred."""
    ctx = Context(random.Random(f"many/{name}"), my_name="USS Thunderhead", enemy_name="RNS Leviathan")
    return tuple(GEN[name].fn(ctx) for _ in range(n))


@pytest.mark.parametrize("name", list(GEN))
def test_every_wrong_choice_says_why(name):
    for p in samples(name):
        assert len(p.why) == 4 and p.why[0] == "", p.why
        for choice, why in zip(p.choices[1:], p.why[1:]):
            assert why.strip() and why.strip()[-1] in ".!?)", (choice, why)
            assert len(why) <= 190, f"{why!r} is more than two short lines"
            assert "  " not in why and not re.search(r"\d\.\d{5,}", why), why


@pytest.mark.parametrize("name", list(GEN))
def test_filler_choices_are_rare(name):
    """A generic "that doesn't come out of the working" choice only when a problem runs out of mistakes."""
    filled = sum(broadside._FILLER_WHY in p.why for p in many(name))
    assert filled / len(many(name)) < 0.01, f"{name}: {filled} of {len(many(name))} problems needed a filler choice"


@pytest.mark.parametrize("name", list(GEN))
def test_working_shows_the_answer_as_the_choice_does(name):
    """The working ends on the answer written exactly as the choice is ("20.0" in both, or "20" in both)."""
    for p in samples(name):
        assert p.choices[0] in " ".join(p.solution), (p.choices[0], p.solution)
        for t in texts(p):
            assert not re.search(r"(?<![\w.])-\d", t), f"ASCII minus in {t!r}"


# ---------------------------------------------------------------------------
# Trig: the table, not a calculator
# ---------------------------------------------------------------------------


def _exact(fn: str, deg: float) -> float:
    return {"sin": math.sin, "cos": math.cos, "tan": math.tan}[fn](math.radians(deg))


def calculator_answer(name: str, p: Problem) -> float:
    """What the problem's numbers give with exact sin/cos/tan instead of the trig table."""
    if name == "trig_find_side":
        g, op, fn, th = grab(r"^x = (\d+) (×|÷) (sin|cos|tan) (\d+)°$", p.expr)
        return g * _exact(fn, th) if op == "×" else g / _exact(fn, th)
    if name == "hard_trig_find_hypotenuse":
        fn, th, g = grab(r"^(sin|cos) (\d+)° = (\d+) ÷ hyp$", p.expr)
        return g / _exact(fn, th)
    if name == "hard_opposite_bows":
        R1, th1, R2, th2 = grab(r"^(\d+) × sin (\d+)° \+ (\d+) × sin (\d+)°$", p.expr)
        return R1 * _exact("sin", th1) + R2 * _exact("sin", th2)
    if name == "stadimeter_range":
        H, th = grab(r"^range = (\d+) ÷ tan (\d)°$", p.expr)
        return H / _exact("tan", th)
    if name == "hard_lead_backwards":
        R, th = grab(r"^lead = ([\d,]+) × tan (\d+)°$", p.expr)
        (by,) = grab(r"^(?:time|speed) = lead ÷ (\d+)$", p.note)
        return R * _exact("tan", th) / by
    raise KeyError(name)


# Every generator whose answer is a number worked out by multiplying or dividing by a trig value.
TRIG_ARITHMETIC = ("trig_find_side", "hard_trig_find_hypotenuse", "hard_opposite_bows", "stadimeter_range", "hard_lead_backwards")


def test_trig_arithmetic_list_is_complete():
    for name, g in GEN.items():
        if g.topic != "trig":
            continue
        numeric_trig = any(re.fullmatch(r"[\d,.]+", p.choices[0]) and re.search(r"\b(sin|cos|tan)\b", p.expr) for p in samples(name))
        assert numeric_trig == (name in TRIG_ARITHMETIC), name


@pytest.mark.parametrize("name", TRIG_ARITHMETIC)
def test_no_wrong_choice_is_the_calculator_answer(name):
    """The problems use the trig table's 2-decimal values. A player who uses a calculator
    instead must not find their number among the wrong choices."""
    disagree = 0
    for p in many(name) + samples(name):
        exact = calculator_answer(name, p)
        decimals = len(p.choices[0].split(".")[1]) if "." in p.choices[0] else 0
        shown = round(Fraction(exact), decimals)  # exact is irrational: no ties to break
        values = [Fraction(c.replace(",", "").replace("−", "-")) for c in p.choices]
        assert shown not in values[1:], f"{name}: a calculator gives {float(shown)}, offered as wrong in {p.choices}"
        disagree += shown != values[0]
    if name in ("trig_find_side", "hard_lead_backwards"):
        assert disagree, "the table and a calculator never disagreed, so this test tested nothing"


TRIG_MENTION = re.compile(r"\b(sin|cos|tan) (\d+)°")
TRIG_VALUE = re.compile(r"\b(sin|cos|tan) (\d+)° (?:≈ |is |\()(\d*\.\d+|\d+)")


@pytest.mark.parametrize("name", [n for n, g in GEN.items() if g.topic == "trig"])
def test_trig_problems_only_need_the_trig_table(name):
    """Every angle a trig problem needs is in the table the workshop shows, every value
    quoted is the table's, and the player is told to use the table where it's needed."""
    for p in samples(name):
        words = texts(p) + list(p.why)
        for t in words:
            for fn, deg in TRIG_MENTION.findall(t):
                deg = int(deg)
                assert deg in TABLE or (fn == "tan" and deg in SMALL), f"{fn} {deg}° is not in the trig table: {t!r}"
            for fn, deg, val in TRIG_VALUE.findall(t):
                table = SMALL[int(deg)] if fn == "tan" and int(deg) in SMALL else TABLE[int(deg)][COL[fn]]
                assert float(val) == table, f"{fn} {deg}° is {table} in the table, not {val}: {t!r}"
        needs = re.search(r"\b(sin|cos|tan)\b", p.expr + p.note) or "θ" in p.expr
        given = re.search(r"(sin|cos|tan) \d+° ≈", p.note) or "Small-angle tangents" in p.story
        if needs and not given:
            assert "trig table" in p.ask + p.hint, (name, p.ask, p.hint)


# ---------------------------------------------------------------------------
# Figures don't give the answer away
# ---------------------------------------------------------------------------


def fig_labels(fig) -> list[tuple[str, object]]:
    """(text, colour) for each label a figure shows. Numbers the renderer prints from the
    figure's own numeric fields (sides, radii, grid points) are all given quantities."""
    out: list[tuple[str, object]] = []

    def walk(o, key=None):
        if isinstance(o, dict):
            if isinstance(o.get("t"), str):
                out.append((o["t"], o.get("c")))
            if isinstance(o.get("label"), str):
                out.append((o["label"], o.get("c")))
            for k, v in o.items():
                if k not in ("t", "label", "c"):
                    walk(v, k)
        elif isinstance(o, (list, tuple)):
            for v in o:
                walk(v, key)
        elif isinstance(o, str) and key in ("note", "rayLabel", "names"):
            out.append((o, None))

    walk(fig)
    return out


def numbers_in(text: str) -> set[Fraction]:
    return {Fraction(x.replace(",", "")) for x in re.findall(r"\d[\d,]*(?:\.\d+)?", text)}


@pytest.mark.parametrize("name", [n for n in GEN if any(p.fig for p in samples(n))])
def test_figure_labels_do_not_show_the_answer(name):
    """No label carries the answer's number, unless that label is a known value (drawn in the
    "given" colour, or a number the problem states) that happens to equal the answer."""
    for p in samples(name) + many(name, 600):
        if not p.fig:
            continue
        answer = numbers_in(p.choices[0])
        stated = numbers_in(" ".join((p.story, p.expr, p.note)))
        for text, colour in fig_labels(p.fig):
            leak = numbers_in(text) & answer
            if leak and colour != "given":
                assert leak <= stated, f"{name}: the figure label {text!r} shows the answer {p.choices[0]!r}"


def test_figures_that_used_to_give_the_answer_away():
    for p in samples("hard_lead_backwards"):
        if "How long" in p.ask:
            assert "in ? s" in [m.get("label") for m in p.fig["marks"].values()]
    for p in samples("chart_scale"):
        if p.fig["ask"] == "cm":  # the ruler would be drawn the answer's length, with a tick every cm
            assert "m" not in p.fig and p.fig["d"] == grab(r"is ([\d.]+) nm away", p.story)[0]
    for name in ("trig_find_angle", "hard_which_ratio", "lead_angle"):
        for p in samples(name):
            if p.choices[0].endswith("°"):  # the angle is asked: the triangle isn't drawn with it
                assert p.fig.get("ratio") == 1 and "deg" not in p.fig and "not to scale" in p.fig["note"]


# ---------------------------------------------------------------------------
# Font coverage
# ---------------------------------------------------------------------------


def test_font_renders_every_character():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    freetype = pytest.importorskip("pygame.freetype")
    chars: set[str] = set()
    for name in GEN:
        for p in samples(name):
            for t in texts(p):
                chars.update(t)
            if p.fig:
                for s in fig_strings(p.fig):
                    chars.update(s)
    for b in HELP.values():
        for t in (b.title, b.concept, *b.steps, b.example):
            chars.update(t)
    for figs in HELP_FIGURES.values():
        for s in fig_strings(list(figs)):
            chars.update(s)
    chars.discard("\n")
    freetype.init()  # idempotent; not quit afterwards, other tests may share the module
    font = freetype.Font(str(FONT), 20)
    text = "".join(sorted(chars))
    metrics = font.get_metrics(text)
    missing = [ch for ch, m in zip(text, metrics) if m is None]
    assert not missing, f"glyphs missing from DejaVuSans: {missing}"
