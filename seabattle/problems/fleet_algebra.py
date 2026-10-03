"""Fleet Algebra (Algebra I) problems, ported from the browser game.

Topics: ``lin`` (Navigation · Linear), ``sys`` (Intercept · Systems),
``quad`` (Gunnery · Quadratics), ``exp`` (Radar · Powers & Roots) and ``rx``
(Reactor · Exponentials).

The generators are ports of the game's JavaScript: same number ranges, story
variants, worked solutions and hints. Numbers are printed the way the game
prints them (``−`` for negatives, thousands separators where the game used
``toLocaleString``). The ``rx`` problems are not in the game: they cover
exponential functions and models (percent growth and decay, half-life, linear
or exponential, y = a × bᵗ) and were written for this one in the same style,
with numbers picked so every step works out by hand.

The wrong answers were reworked: each one is a named mistake (forgetting the
reserve, dividing the wrong way round, reading the roots off the factors...)
with a short reason the game shows to a player who picks it. Each generator
offers a pool of such mistakes and three are drawn at random, balanced around
the answer, so the right choice can't be spotted without doing the math.
"""

from __future__ import annotations

import math
import re
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction
from typing import Optional, Sequence, Union

from .common import Briefing, Choices, Context, Generator, Problem, ShipRef, is_int, js_fixed, js_round, js_str, pick_three, registry, sup

Number = Union[int, float]

# ---------------------------------------------------------------------------
# Number formatting (JavaScript semantics)
# ---------------------------------------------------------------------------


_is_int, _num, _js_round, _to_fixed = is_int, js_str, js_round, js_fixed


def _locale(n: Number) -> str:
    """JS ``n.toLocaleString()`` (en-US): thousands separators, at most 3 decimals."""
    if _is_int(n):
        return f"{int(n):,}"
    d = Decimal(abs(n)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
    s = f"{d:,f}".rstrip("0").rstrip(".")
    return ("-" if n < 0 else "") + s


def _sgn(n: Number) -> str:
    """For "x − 3" style: 3 -> "+ 3", -3 -> "− 3"."""
    return f"− {_num(abs(n))}" if n < 0 else f"+ {_num(n)}"


def _lead(n: Number) -> str:
    """Leading negative: -3 -> "−3"."""
    return f"−{_num(abs(n))}" if n < 0 else _num(n)


def _par(n: Number) -> str:
    """Negative numbers in parentheses: -3 -> "(−3)"."""
    return f"({_lead(n)})" if n < 0 else _num(n)


def _fmt(n: Number) -> str:
    """Integers as is; anything else rounded to 2 decimals with trailing zeros dropped."""
    return _lead(n) if _is_int(n) else _lead(float(_to_fixed(n, 2)))


def _factor_form(p: int, q: int) -> str:
    """(x + p)(x + q)"""
    return f"(x {_sgn(p)})(x {_sgn(q)})"


def _trinomial(b: int, c: int) -> str:
    """x² + bx + c, dropping a zero middle term and writing ±1x as ±x."""
    mid = "" if b == 0 else (_sgn(b).replace("1", "x", 1) if abs(b) == 1 else _sgn(b) + "x") + " "
    return "x" + sup(2) + " " + mid + _sgn(c)


def _coef(k: int, var: str = "x") -> str:
    """kx, writing 1x as x and −1x as −x: (3, "x") -> "3x", (-1, "y") -> "−y"."""
    return {1: var, -1: f"−{var}"}.get(k, f"{_lead(k)}{var}")


def _line(m: int, b: int) -> str:
    """y = mx + b: (2, -3) -> "y = 2x − 3", (-1, 0) -> "y = −x"."""
    return f"y = {_coef(m)}" + (f" {_sgn(b)}" if b else "")


def _pair_roots(a: int, b: int) -> str:
    """Two solutions, smaller first: "x = −3 or x = 5"."""
    return f"x = {_lead(min(a, b))} or x = {_lead(max(a, b))}"


def _an(word: str) -> str:
    return ("an " if re.match(r"[aeiou]", word, re.I) else "a ") + word


def _cap(s: str) -> str:
    return s[:1].upper() + s[1:]


# ---------------------------------------------------------------------------
# Answer choices
# ---------------------------------------------------------------------------

# A wrong answer and the mistake that leads to it: ``(value, why)`` for numeric
# choices, ``(text, why)`` for the others (``(text, why, value)`` when the text
# stands for a number, like "3√2" or "1⁄8", so it can be balanced around the answer).
Mistake = tuple

# Only used if a generator runs out of real mistakes, which the pools are built to avoid.
_FALLBACK_WHY = "Not quite. Go back over each step and check the arithmetic."


def _whole(x: float) -> Number:
    """A wrong result as a player would give it when the answers are whole numbers.

    Rounded to a whole number (35.83 hours -> 36), except below 1, where rounding
    would change what it is (dividing the wrong way round gives 0.05, not 0).
    Mistakes whose reason is about the exact value (halving instead of taking a
    square root) pass the value as it is instead."""
    return _js_round(x) if abs(x) >= 1 else x


def _shown(text: str) -> float:
    """The number a choice made by ``_fmt`` shows."""
    return float(text.replace("−", "-"))


def _middle(ans: float, vals: Sequence[float]) -> bool:
    """Is the answer exactly halfway between two of the values?"""
    return any(math.isclose((u + v) / 2, ans, abs_tol=1e-9) for i, u in enumerate(vals) for v in vals[i + 1:])


def _choices(ans: str, picked: Sequence[tuple]) -> Choices:
    return Choices((ans, *(p[0] for p in picked)), ("", *(p[1] for p in picked)))


def _numeric_choices(ctx: Context, ans: Number, mistakes: Sequence[Mistake], allow_neg: bool = False) -> Choices:
    """The answer and three of the ``(value, why)`` mistakes, printed like the answer.

    A mistake is left out if it is not a finite number, is negative (unless
    ``allow_neg``), or prints the same as the answer or as a mistake listed
    before it (so a value keeps the first reason given for it).
    """
    ans_text = _fmt(ans)
    ans_val = _shown(ans_text)
    seen = {ans_text}
    usable = []
    for v, why in mistakes:
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
            continue
        text = _fmt(v)
        val = _shown(text)
        if text in seen or (val < 0 and not allow_neg) or math.isclose(val, ans_val, abs_tol=1e-9):
            continue
        seen.add(text)
        usable.append((text, why, val))
    picked = pick_three(ctx, ans_text, ans_val, usable)
    if len(picked) < 3:  # last resort: beyond every other value, never mirroring one around the answer
        vals = [ans_val] + [p[2] for p in picked]
        step = max(1, _js_round(abs(ans_val) / 2)) if _is_int(ans_val) else max(abs(ans_val) / 2, 0.5)
        v = max(vals) + step
        while len(picked) < 3:
            if _fmt(v) not in seen and not _middle(ans_val, vals[1:] + [v]):
                seen.add(_fmt(v))
                vals.append(v)
                picked.append((_fmt(v), _FALLBACK_WHY, v))
            v += step
    return _choices(ans_text, picked)


def _string_choices(ctx: Context, ans: str, mistakes: Sequence[Mistake], ans_value: Optional[float] = None,
                    same_value_ok: bool = False) -> Choices:
    """The answer and three of the ``(text, why)`` mistakes.

    Mistakes that read the same as the answer or as an earlier mistake are left
    out, and so are those that stand for the same number as the answer (unless
    ``same_value_ok``: in scientific notation "50 × 10⁴" is a real mistake for
    5 × 10⁵). If every mistake also gives the number it stands for (and
    ``ans_value`` is given), the three are balanced around the answer like
    numeric choices. Every generator's list is long enough to always leave three;
    a ValueError says so if one doesn't.
    """
    seen = {ans}
    usable = []
    for m in mistakes:
        text, why = m[0], m[1]
        value = m[2] if len(m) > 2 else None
        if text in seen:
            continue
        if not same_value_ok and None not in (value, ans_value) and math.isclose(value, ans_value, abs_tol=1e-9):
            continue
        seen.add(text)
        usable.append((text, why, value))
    if len(usable) < 3:
        raise ValueError(f"only {len(usable)} wrong choices for {ans!r}")
    return _choices(ans, pick_three(ctx, ans, ans_value, usable))


# ---------------------------------------------------------------------------
# The fleet (ships named in word problems)
# ---------------------------------------------------------------------------

# id -> (name, speed in knots, crew) for the classes the stand-in fleet uses.
_CLASSES = {
    "patrol": ("Patrol boat", 25, 12),
    "corvette": ("Corvette", 28, 60),
    "minesweeper": ("Minesweeper", 14, 80),
    "frigate": ("Frigate", 30, 200),
    "destroyer": ("Destroyer", 32, 300),
    "cruiser": ("Cruiser", 32, 400),
    "carrier": ("Aircraft carrier", 30, 5000),
}


def _ship(name: str, class_id: str) -> ShipRef:
    cls_name, speed, crew = _CLASSES[class_id]
    return ShipRef(name=name, cls=cls_name.lower(), speed=speed, crew=crew)


# Used in missions before the player owns any ships.
DEFAULT_FLEET: tuple[ShipRef, ...] = (
    _ship("USS Kestrel", "destroyer"),
    _ship("USS Harrier", "frigate"),
    _ship("USS Tempest", "cruiser"),
    _ship("USS Marlin", "patrol"),
    _ship("USS Osprey", "corvette"),
    _ship("USS Sabre", "destroyer"),
    _ship("USS Cormorant", "minesweeper"),
    _ship("USS Aurora", "carrier"),
)


def _fleet_ship(ctx: Context) -> ShipRef:
    """One ship from the player's fleet (or the stand-in fleet if they have none)."""
    return ctx.pick(ctx.fleet if len(ctx.fleet) >= 1 else DEFAULT_FLEET)


def _fleet_pair(ctx: Context) -> tuple[ShipRef, ShipRef]:
    """Two different ships from the player's fleet (or the stand-in fleet if they have fewer than two)."""
    src = ctx.fleet if len(ctx.fleet) >= 2 else DEFAULT_FLEET
    i = ctx.pick(range(len(src)))
    other = ctx.pick([s for j, s in enumerate(src) if j != i])
    return src[i], other


# ---------------------------------------------------------------------------
# Help briefings, one per problem type
# ---------------------------------------------------------------------------

HELP: dict[str, Briefing] = {
    "fuel": Briefing(
        title="Rates: fuel burn",
        concept='A rate tells you how much changes each hour. If the ship burns 12 tons every hour, then after t hours it has burned 12t tons. "How long until…" questions are asking you to solve for t.',
        steps=(
            "Figure out how much fuel can actually be used: start minus the reserve you must keep.",
            "Set up: rate × time = usable fuel, or r·t = usable.",
            "Divide both sides by the rate to get t alone.",
        ),
        example="A cutter has 200 tons, burns 8 tons/hr, must keep a 40-ton reserve.\nUsable = 200 − 40 = 160. Then 8t = 160, so t = 160 ÷ 8 = 20 hours.",
    ),
    "drt": Briefing(
        title="Distance = rate × time",
        concept="Ships measure speed in knots: 1 knot = 1 nautical mile per hour. Distance, rate and time are tied together by d = r·t. Cover the one you want with your thumb and the other two tell you what to do.",
        steps=(
            "Write d = r × t.",
            "Put in the two numbers you know.",
            "Solve for the third: divide if the unknown is being multiplied, multiply if it is alone.",
        ),
        example="A frigate is 90 nm from port at 18 knots. How long to arrive?\n90 = 18 × t → t = 90 ÷ 18 = 5 hours.",
    ),
    "solve": Briefing(
        title="Solving a two-step equation",
        concept="The goal is to get x by itself. Whatever you do to one side, do to the other, and undo operations in reverse order: first undo the adding/subtracting, then undo the multiplying.",
        steps=(
            "Move the plain number to the other side by adding or subtracting it from both sides.",
            "Now you have (number)·x = (number). Divide both sides by the number in front of x.",
            "Check by plugging your answer back in.",
        ),
        example="Solve 4x − 7 = 21.\nAdd 7 to both sides: 4x = 28. Divide by 4: x = 7. Check: 4(7) − 7 = 21 ✓",
    ),
    "slope": Briefing(
        title="Slope: rate of change from two points",
        concept="Slope is \"rise over run\": how much the up-and-down value changes for each step of the across value. For a ship's fuel graph, slope is tons per hour. A negative slope means it is going down.",
        steps=(
            "Label the points (x₁, y₁) and (x₂, y₂).",
            "Subtract the y's: y₂ − y₁ (the change in fuel).",
            "Subtract the x's in the same order: x₂ − x₁ (the change in time).",
            "Divide: slope = (y₂ − y₁) ÷ (x₂ − x₁).",
        ),
        example="Fuel readings: (2 hrs, 150 tons) and (5 hrs, 90 tons).\nChange in fuel: 90 − 150 = −60. Change in time: 5 − 2 = 3. Slope = −60 ÷ 3 = −20 tons/hr.",
    ),
    "func": Briefing(
        title="Function notation: r(t)",
        concept='r(t) is not "r times t". It means "the range when the time is t" — a rule that takes in a time and gives back a distance. r(3) means: put 3 wherever you see t, then work it out.',
        steps=(
            "Write the rule down.",
            "Replace every t with the number in the parentheses (use your own parentheses to be safe).",
            "Do the multiplication first, then the adding or subtracting.",
        ),
        example="Range r(t) = 60 − 20t. Find r(2).\nr(2) = 60 − 20(2) = 60 − 40 = 20 nm.",
    ),
    "ineq": Briefing(
        title="Inequalities: the load limit",
        concept="A limit like \"at most 8,000 pounds\" is an inequality: total weight ≤ 8,000. You solve it just like an equation, but the answer is a whole range — and since you can't load part of a Marine, you round DOWN to the biggest whole number that fits.",
        steps=(
            "Write the total: (already loaded) + (weight each) × (how many) ≤ limit.",
            "Subtract what is already loaded from both sides.",
            "Divide by the weight of each one.",
            "Round down to a whole number.",
        ),
        example="Limit 5,000 lb, 1,400 lb already aboard, each Marine 240 lb.\n240m ≤ 3,600 → m ≤ 15 → 15 Marines.",
    ),
    "overtake": Briefing(
        title="Systems: the intercept problem",
        concept="Two ships on the same track each have a distance equation. When the faster one catches up, both distances are equal. Setting the two equations equal to each other turns two unknowns into one.",
        steps=(
            "Write distance = speed × time for each ship. The one that left earlier has extra time: (t + head start).",
            "Set the two distances equal.",
            "Expand, collect the t terms on one side, and divide.",
        ),
        example="Sub leaves at 12 knots; 2 hours later a destroyer leaves at 20 knots.\nSub: 12(t + 2). Destroyer: 20t. Set equal: 12t + 24 = 20t → 24 = 8t → t = 3 hours after the destroyer sails.",
    ),
    "mix": Briefing(
        title="Systems: two unknowns, two equations",
        concept="When there are two things you don't know (weight of a shell crate, weight of a ration crate) you need two facts about them. Each fact becomes an equation. The trick is to combine the equations so one unknown disappears.",
        steps=(
            "Let s = one unknown, r = the other. Write one equation per fact.",
            "Multiply one equation so a matching term lines up with the other (elimination).",
            "Subtract the equations — one unknown cancels. Solve for the one left.",
            "Plug back in to get the other if needed.",
        ),
        example="2s + 3r = 1,300 and 2s + 1r = 900.\nSubtract: 2r = 400 → r = 200. Then 2s + 200 = 900 → s = 350.",
    ),
    "sumdiff": Briefing(
        title="Systems: a total and a difference",
        concept="If you know two things add up to a total AND you know how much bigger one is, that's a system of two equations. Adding the equations makes the difference cancel out.",
        steps=(
            "Let x = the bigger group, y = the smaller. Write x + y = total and x − y = difference.",
            "Add the two equations: the y's cancel, leaving 2x = total + difference.",
            "Divide by 2 to get x.",
        ),
        example="Two convoys total 46 ships; one has 8 more than the other.\nx + y = 46, x − y = 8. Add: 2x = 54 → x = 27.",
    ),
    "subst": Briefing(
        title="Systems: substitution",
        concept="If one equation already tells you what y equals, you can swap that expression in for y in the other equation. Then there is only x left to solve.",
        steps=(
            "Take the equation that says y = (something with x).",
            "In the other equation, replace y with that expression, in parentheses.",
            "Simplify and solve the one-variable equation for x.",
        ),
        example="y = 2x + 1 and 3x + y = 16.\n3x + (2x + 1) = 16 → 5x + 1 = 16 → 5x = 15 → x = 3.",
    ),
    "traj": Briefing(
        title="Quadratics: shell in flight",
        concept="Height of a shell follows h = −16t² + vt (feet and seconds). It is a parabola: up, then down. The shell is in the air while h > 0 and splashes when h = 0. Highest point is exactly halfway through the flight.",
        steps=(
            "Set h = 0 and factor out t: t(−16t + v) = 0.",
            "One root is t = 0 (launch). The other is when −16t + v = 0, so t = v ÷ 16. That's the flight time.",
            "Peak time is half the flight time: t = v ÷ 32. Plug it back into h for the max height.",
        ),
        example="h = −16t² + 128t.\nFlight time: 128 ÷ 16 = 8 s. Peak at t = 4: h = −16(16) + 128(4) = −256 + 512 = 256 ft.",
    ),
    "factor": Briefing(
        title="Factoring a trinomial",
        concept="x² + bx + c factors into (x + p)(x + q) where the two numbers p and q MULTIPLY to c and ADD to b. It's a search: list pairs that multiply to c, then find the pair that adds to b. Watch the signs.",
        steps=(
            "Identify b (the number with x) and c (the plain number).",
            "List factor pairs of c, including negative pairs if c is positive and b is negative.",
            "Pick the pair that adds to b.",
            "Write (x + p)(x + q). Multiply back out to check.",
        ),
        example="Factor x² − 5x + 6.\nNeed product 6, sum −5: (−2)(−3) = 6 and −2 + −3 = −5. So (x − 2)(x − 3).",
    ),
    "roots": Briefing(
        title="Solving a quadratic by factoring",
        concept="If (x − p)(x − q) = 0, then one of the factors must be 0, so x = p or x = q. Factor first, then set each factor equal to zero. A quadratic usually has TWO solutions.",
        steps=(
            "Get everything on one side so it equals 0.",
            "Factor the trinomial (find two numbers that multiply to c and add to b).",
            "Set each factor equal to 0 and solve each little equation.",
        ),
        example="Solve x² − 7x + 12 = 0.\nFactors: (x − 3)(x − 4) = 0 → x = 3 or x = 4. Solutions {3, 4}.",
    ),
    "area": Briefing(
        title="Quadratic word problem: deck area",
        concept="Area of a rectangle is length × width. If the length is described in terms of the width (\"30 feet longer than it is wide\"), you get an equation with w² in it. Factor to find w. Throw out a negative answer — a width can't be negative.",
        steps=(
            "Let w = width. Write length in terms of w.",
            "Area: w(w + k) = A. Expand: w² + kw − A = 0.",
            "Factor (two numbers that multiply to −A and add to k), or just test the answer choices.",
            "Keep the positive solution.",
        ),
        example="Deck is 5 ft longer than wide, area 84 sq ft.\nw(w + 5) = 84 → w² + 5w − 84 = 0 → (w + 12)(w − 7) = 0 → w = 7 ft.",
    ),
    "expand": Briefing(
        title="Multiplying two binomials (FOIL)",
        concept="To multiply (x + a)(x + b), every term in the first parentheses gets multiplied by every term in the second. FOIL = First, Outer, Inner, Last. Then combine the two middle terms.",
        steps=(
            "First: x · x = x².",
            "Outer + Inner: x·b + a·x = (a + b)x.",
            "Last: a · b.",
            "Put it together: x² + (a + b)x + ab.",
        ),
        example="(x + 3)(x − 5)\nx² + (3 + −5)x + (3)(−5) = x² − 2x − 15.",
    ),
    "pyth": Briefing(
        title="Pythagorean theorem: radar range",
        concept="A contact that is east AND north of you makes a right triangle with the straight-line range as the longest side (hypotenuse). a² + b² = c², where c is the range.",
        steps=(
            "Square the east distance and the north distance.",
            "Add them.",
            "Take the square root of the total.",
        ),
        example="Contact 6 nm east and 8 nm north.\n6² + 8² = 36 + 64 = 100. √100 = 10 nm.",
    ),
    "decay": Briefing(
        title="Exponential change: halving and doubling",
        concept="When something halves (or doubles) over and over, you multiply by ½ (or 2) once for EACH step. n steps means multiplying n times, which is the same as raising to the nth power. Count the steps first.",
        steps=(
            "Find how many steps happen (total distance ÷ distance per step, or number of rounds).",
            "Each step multiplies by the same factor (½ for halving, 2 or 3 for doubling/tripling).",
            "Apply the factor n times: start × factorⁿ.",
        ),
        example="A ping starts at 800 units and halves every 500 m. Strength at 2,000 m?\n2,000 ÷ 500 = 4 halvings. 800 × (½)⁴ = 800 ÷ 16 = 50.",
    ),
    "exprule": Briefing(
        title="Exponent rules",
        concept="An exponent counts how many copies are multiplied. x³·x² is 5 x's multiplied together, so the exponents ADD. Dividing removes copies, so exponents SUBTRACT. A power of a power multiplies the exponents.",
        steps=(
            "Same base multiplied: add the exponents. xᵃ · xᵇ = xᵃ⁺ᵇ",
            "Same base divided: subtract. xᵃ ÷ xᵇ = xᵃ⁻ᵇ",
            "Power of a power: multiply. (xᵃ)ᵇ = xᵃᵇ",
        ),
        example="x⁴ · x³ = x⁷  ·  x⁸ ÷ x² = x⁶  ·  (x²)⁵ = x¹⁰",
    ),
    "radical": Briefing(
        title="Simplifying a square root",
        concept="A square root can be split apart: √(a·b) = √a · √b. If one of the factors is a perfect square (4, 9, 16, 25, 36…), its root comes out front as a whole number and the rest stays under the sign.",
        steps=(
            "Find the biggest perfect square that divides the number.",
            "Split: √(perfect square × leftover).",
            "Take the square root of the perfect square and write it in front.",
        ),
        example="Simplify √72.\n72 = 36 × 2, so √72 = √36 · √2 = 6√2.",
    ),
    "power": Briefing(
        title="Evaluating a power",
        concept='bⁿ means multiply b by itself n times. 3⁴ is 3·3·3·3 = 81, NOT 3 × 4. Relay chains, doublings and "each one tells three more" all grow like this.',
        steps=(
            "Identify the base (what gets multiplied) and the exponent (how many times).",
            "Multiply step by step: write each product as you go.",
            "Don't multiply base × exponent — that's the classic trap.",
        ),
        example="Each ship relays a signal to 3 more ships, 4 rounds in a row.\n3⁴ = 3·3·3·3 = 81 ships hear it in round 4.",
    ),
    "meet": Briefing(
        title="Two ships closing on each other",
        concept="When two ships steam TOWARD each other, the gap shrinks by both speeds combined. Their closing speed is s₁ + s₂, so the time to meet is the distance divided by that combined speed.",
        steps=(
            "Add the two speeds to get the closing speed.",
            "Time = distance ÷ closing speed.",
            "Check: each ship's distance should add up to the original gap.",
        ),
        example="Ships 120 nm apart steam toward each other at 15 and 25 knots.\nClosing speed 40 knots. 120 ÷ 40 = 3 hours.",
    ),
    "consec": Briefing(
        title="Consecutive numbers",
        concept="Consecutive numbers go up by 1 each time. If the first is x, the next ones are x + 1 and x + 2. Add them up and you get a simple equation with one x.",
        steps=(
            "Call the smallest number x. Write the others as x + 1, x + 2 (or x + 2, x + 4 for consecutive evens/odds).",
            "Add them: 3x + 3 = total.",
            "Subtract, then divide by 3.",
        ),
        example="Three consecutive hull numbers add to 219.\nx + (x + 1) + (x + 2) = 219 → 3x + 3 = 219 → 3x = 216 → x = 72. (72, 73, 74)",
    ),
    "perim": Briefing(
        title="Perimeter word problem",
        concept="Perimeter is the distance all the way around: 2 × length + 2 × width. If the length is described using the width, everything is in terms of w and you can solve.",
        steps=(
            "Let w = width. Write the length in terms of w.",
            "Perimeter: 2(length) + 2w = P.",
            "Distribute, combine the w terms, solve.",
        ),
        example="A helipad is 10 ft longer than it is wide; perimeter 100 ft.\n2(w + 10) + 2w = 100 → 4w + 20 = 100 → 4w = 80 → w = 20 ft.",
    ),
    "literal": Briefing(
        title="Rearranging a formula (literal equations)",
        concept='A formula like d = rt is an equation with several letters. "Solve for t" means get t alone on one side, treating the other letters like numbers. Same moves as always: undo multiplication by dividing, undo addition by subtracting.',
        steps=(
            "Find the letter you want alone.",
            "Undo whatever is done to it, doing the same to the other side.",
            "Write the result with your letter on the left.",
        ),
        example="Solve d = rt for t.\nt is multiplied by r, so divide both sides by r: t = d ÷ r.",
    ),
    "prop": Briefing(
        title="Proportions and chart scale",
        concept="A chart scale is a ratio: 3 cm on paper = 12 nm at sea. Ratios that are equal make a proportion. Cross-multiply to solve for the missing piece.",
        steps=(
            "Write two equal fractions: paper ÷ real = paper ÷ real.",
            "Cross-multiply: top-left × bottom-right = top-right × bottom-left.",
            "Divide to find the unknown.",
        ),
        example="3 cm = 12 nm. How many nm is 7 cm?\n3/12 = 7/x → 3x = 84 → x = 28 nm.",
    ),
    "model": Briefing(
        title="Writing a linear model",
        concept="A situation with a starting amount and a steady change each hour is a line: y = (start) + (rate)·t. If the amount is going DOWN, the rate is negative. Reading the story carefully tells you which number is which.",
        steps=(
            "Find the starting amount (when t = 0). That is the constant term.",
            "Find the change per hour. Going down? Make it negative.",
            "Write y = start + rate·t (or start − rate·t).",
        ),
        example="Tank starts with 500 gallons and loses 20 per hour.\ny = 500 − 20t",
    ),
    "tickets": Briefing(
        title="Systems: two kinds of items, a count and a total",
        concept="If you know how MANY items there are and how much they cost in TOTAL, that is two facts about two unknowns. Solve the count equation for one variable and substitute into the cost equation.",
        steps=(
            "Let x = number of the first kind, y = the second. Write x + y = count.",
            "Write price₁·x + price₂·y = total.",
            "From the first, y = count − x. Substitute into the second and solve for x.",
        ),
        example="30 liberty passes sold: $8 day passes and $15 weekend passes, total $310.\nx + y = 30 and 8x + 15y = 310. Substitute x = 30 − y: 8(30 − y) + 15y = 310 → 240 + 7y = 310 → 7y = 70 → y = 10 weekend passes.",
    ),
    "current": Briefing(
        title="Systems: boat speed and current",
        concept="Going WITH the current, the boat's speed over the ground is (boat + current). Going AGAINST it, (boat − current). Each leg gives you a speed from distance ÷ time. Then it is a sum-and-difference system.",
        steps=(
            "Downstream speed = distance ÷ time. Upstream speed = distance ÷ time.",
            "b + c = downstream speed, b − c = upstream speed.",
            "Subtract the equations: 2c = (down − up). Divide by 2 for the current.",
        ),
        example="36 nm downstream in 3 hr; back in 4 hr.\nDown 12 kn, up 9 kn. 2c = 12 − 9 = 3 → c = 1.5 knots.",
    ),
    "ratio": Briefing(
        title="One amount is a multiple of another",
        concept='"Three times as many" means one unknown is 3 × the other. Call the smaller one x; the bigger is 3x. Their total is x + 3x = 4x, which is easy to solve.',
        steps=(
            "Let x = the smaller group. Write the larger as (multiple)·x.",
            "Add them and set equal to the total.",
            "Divide by the combined coefficient.",
        ),
        example="Carrier A has 3 times the crew of destroyer B; together 480.\nx + 3x = 480 → 4x = 480 → x = 120 (B), A = 360.",
    ),
    "drop": Briefing(
        title="Falling object: h = H − 16t²",
        concept="Something DROPPED (not thrown) from height H falls according to h = H − 16t². It hits the deck when h = 0. Solve by getting t² alone and taking the square root.",
        steps=(
            "Set h = 0: H − 16t² = 0.",
            "Move: 16t² = H, then t² = H ÷ 16.",
            "Take the square root (only the positive one — time can't be negative).",
        ),
        example="A tool drops from a 144-ft mast.\n16t² = 144 → t² = 9 → t = 3 seconds.",
    ),
    "traj2": Briefing(
        title="Projectile launched from a height",
        concept="A shell fired from a deck above the water has h = −16t² + vt + h₀, where h₀ is the deck height. It splashes when h = 0. Divide everything by −16 to make factoring easy, then factor.",
        steps=(
            "Set h = 0.",
            "Divide every term by −16 so the t² coefficient is 1.",
            "Factor the trinomial and set each factor to zero.",
            "Throw out the negative time.",
        ),
        example="h = −16t² + 32t + 48.\n÷(−16): t² − 2t − 3 = 0 → (t − 3)(t + 1) = 0 → t = 3 s (ignore −1).",
    ),
    "diffsq": Briefing(
        title="Difference of squares",
        concept="x² − k² has a special factoring: (x − k)(x + k). No middle term is the giveaway. Only works with a MINUS; x² + k² does not factor.",
        steps=(
            "Confirm it is (something)² minus (something)².",
            "Take the square root of each piece.",
            "Write (first − second)(first + second).",
        ),
        example="x² − 49\n√x² = x, √49 = 7 → (x − 7)(x + 7)",
    ),
    "sqroot": Briefing(
        title="Solving x² = k by square roots",
        concept="If x² equals a number, x could be the positive OR the negative square root, because a negative squared is positive. Get x² alone first, then write ±.",
        steps=(
            "Isolate x²: undo any adding/subtracting, then divide by the coefficient.",
            "Take the square root of both sides.",
            "Write both answers: x = ±√k.",
        ),
        example="3x² − 48 = 0\n3x² = 48 → x² = 16 → x = ±4",
    ),
    "consecprod": Briefing(
        title="Product of consecutive numbers",
        concept="Two consecutive numbers are x and x + 1. Their product is x(x + 1) = x² + x. Setting that equal to the total gives a quadratic you can factor — or just find two neighboring numbers that multiply to the total.",
        steps=(
            "Let the smaller be x, the next x + 1.",
            "x(x + 1) = product → x² + x − product = 0.",
            "Factor, or estimate with a square root: √product is between the two numbers.",
        ),
        example="Two consecutive hull numbers multiply to 210.\n√210 ≈ 14.5, so try 14 × 15 = 210 ✓. Smaller is 14.",
    ),
    "pythleg": Briefing(
        title="Pythagorean theorem: finding a leg",
        concept="If you know the longest side (hypotenuse) and one leg, rearrange a² + b² = c² into b² = c² − a². Subtract, then square-root.",
        steps=(
            "Square the hypotenuse and the known leg.",
            "Subtract: hypotenuse² − leg².",
            "Take the square root.",
        ),
        example="Range 13 nm, contact is 5 nm east. How far north?\n13² − 5² = 169 − 25 = 144 → √144 = 12 nm.",
    ),
    "dist": Briefing(
        title="Distance between two points",
        concept="On a plotting grid, the distance between two points is the hypotenuse of a right triangle. The legs are the difference in x and the difference in y. So distance = √((Δx)² + (Δy)²).",
        steps=(
            "Subtract the x-coordinates; subtract the y-coordinates.",
            "Square each difference and add.",
            "Take the square root.",
        ),
        example="Contacts at (2, 3) and (8, 11).\nΔx = 6, Δy = 8. √(36 + 64) = √100 = 10.",
    ),
    "sci": Briefing(
        title="Scientific notation",
        concept="Big numbers are written as (a number between 1 and 10) × 10ⁿ. The exponent n tells you how many places to move the decimal point. Positive n → move right (bigger).",
        steps=(
            "Look at the exponent on the 10.",
            "Move the decimal point that many places to the right, adding zeros as needed.",
            "Going the other way: count how many places the decimal moves to land after the first digit.",
        ),
        example="3.2 × 10⁶ gallons\nMove the point 6 places: 3,200,000",
    ),
    "growth": Briefing(
        title="Exponential growth: start × baseⁿ",
        concept="If something multiplies by the same factor every period, after n periods it is start × factorⁿ. Tripling for 3 years is × 3 × 3 × 3, not × 9.",
        steps=(
            "Find the starting amount and the growth factor.",
            "Count the periods, n.",
            "Compute factorⁿ first, then multiply by the start.",
        ),
        example="12 patrol boats, fleet triples each year, 3 years.\n12 × 3³ = 12 × 27 = 324",
    ),
    "negexp": Briefing(
        title="Zero and negative exponents",
        concept='Anything to the power 0 is 1. A NEGATIVE exponent means "one over": b⁻ⁿ = 1 ÷ bⁿ. It does not make the answer negative — it makes it a fraction.',
        steps=(
            "If the exponent is 0, the answer is 1 (as long as the base isn't 0).",
            "If the exponent is negative, flip: write 1 over the base with a positive exponent.",
            "Evaluate the positive power.",
        ),
        example="2⁻³ = 1 ÷ 2³ = 1/8  ·  7⁰ = 1",
    ),
    "sqrtnum": Briefing(
        title="Square roots of perfect squares",
        concept="The square root of a number is what you multiply by itself to get it. For a square-shaped area, the side length is the square root of the area. Knowing squares up to 15² = 225 (and 20² = 400, 25² = 625) makes these fast.",
        steps=(
            "Ask: what number times itself gives this?",
            "Estimate: 10² = 100, 20² = 400 — is it between?",
            "Check by multiplying.",
        ),
        example="A square helipad covers 225 sq ft.\n15 × 15 = 225, so each side is 15 ft.",
    ),
    "mulrad": Briefing(
        title="Multiplying square roots",
        concept="Square roots multiply under one sign: √a · √b = √(a·b). Multiply the insides, then simplify — often the product is a perfect square and the root disappears completely.",
        steps=(
            "Multiply the numbers under the roots.",
            "Look for the biggest perfect square factor.",
            "Simplify.",
        ),
        example="√3 · √12 = √36 = 6  ·  √2 · √10 = √20 = 2√5",
    ),
    "addrad": Briefing(
        title="Adding square roots",
        concept="Square roots add like like terms: 2√3 + 5√3 = 7√3, just as 2x + 5x = 7x. √a + √b is NOT √(a + b). Roots that look different often turn into like roots once each one is simplified.",
        steps=(
            "Simplify each square root: take the biggest perfect square out in front.",
            "Check that the numbers left under the roots match.",
            "Add the numbers in front. The root stays as it is.",
        ),
        example="√12 + √27\n√12 = 2√3 and √27 = 3√3, so the total is 2√3 + 3√3 = 5√3.",
    ),
    "sciprod": Briefing(
        title="Multiplying in scientific notation",
        concept="To multiply numbers in scientific notation, multiply the numbers in front and add the exponents on the 10s. If the number in front comes out 10 or more, move its decimal point one place left and add 1 to the exponent, so it is back between 1 and 10.",
        steps=(
            "Multiply the numbers in front.",
            "Add the exponents on the 10s.",
            "If the number in front is 10 or more, move its point one place left and add 1 to the exponent.",
        ),
        example="(4 × 10⁵) × (3 × 10²)\n4 × 3 = 12 and 10⁵ × 10² = 10⁷, so 12 × 10⁷ = 1.2 × 10⁸.",
    ),
    "solvexp": Briefing(
        title="How many doublings? Finding the exponent",
        concept="When something doubles (or triples, or halves) every so often, the exponent n counts how many times that happens. Find n by dividing the start and end amounts and counting the doublings in the result. Then multiply n by how long each one takes.",
        steps=(
            "Divide the bigger amount by the smaller one: how many times bigger (or smaller) did it get?",
            "Count how many times you multiply by the factor to reach that number. That count is n.",
            "Multiply n by the time (or distance) each doubling takes.",
        ),
        example="5 colonies double every 3 weeks. When will there be 80?\n80 ÷ 5 = 16 = 2⁴, so there are 4 doublings: 4 × 3 = 12 weeks.",
    ),
    # Navigation · Linear, multi-step
    "distrib": Briefing(
        title="Brackets, and x on both sides",
        concept="A number in front of brackets multiplies EVERYTHING inside them: 3(x − 4) is 3x − 12, not 3x − 4. Once the brackets are gone, gather the x terms on one side and the plain numbers on the other, then divide.",
        steps=(
            "Distribute: multiply the number in front by each term in the brackets.",
            "Take the x term away from one side, so x is only on the other.",
            "Undo the plain number on the x side, doing the same to the other side.",
            "Divide by the number in front of x.",
        ),
        example="3(x − 4) = x + 6\n3x − 12 = x + 6 → 2x − 12 = 6 → 2x = 18 → x = 9.",
    ),
    "predict": Briefing(
        title="Predicting with a rate of change",
        concept="Two readings give the rate: how much the amount changes each hour. If it keeps changing at that rate, you can work out when it reaches any level. Count the hours from the latest reading, then turn that into the hour on the log.",
        steps=(
            "Rate = (change in the amount) ÷ (change in time).",
            "How much still has to go: latest reading − the level you want.",
            "Hours needed = that amount ÷ the rate (without its minus sign).",
            "Add those hours to the time of the latest reading.",
        ),
        example="(2, 410) and (6, 330). When is it down to 250?\nRate: −80 ÷ 4 = −20 an hour. 330 − 250 = 80 to go: 80 ÷ 20 = 4 hours. 6 + 4 = hour 10.",
    ),
    "avgspeed": Briefing(
        title="Average speed for a round trip",
        concept="Average speed is total distance ÷ total time. It is NOT halfway between two speeds: on a round trip you spend longer at the slower speed, so the average is pulled down toward it.",
        steps=(
            "Time for each leg: distance ÷ speed.",
            "Total distance: both legs together.",
            "Total time: add the two times.",
            "Average speed = total distance ÷ total time.",
        ),
        example="60 nm out at 20 knots, 60 nm back at 30 knots.\n3 hours out, 2 back: 120 nm in 5 hours = 24 knots (not 25).",
    ),
    "breakeven": Briefing(
        title="When is one deal cheaper?",
        concept="A bigger fee with a lower hourly rate starts out dearer but catches up a little every hour. Write the cost of each, put a < between them, and solve like an equation. At the break-even point they cost exactly the same, which isn't cheaper yet.",
        steps=(
            "Cost of each: fee + rate × h.",
            "Write (the one you want) < (the other one).",
            "Gather the h terms on one side and the fees on the other, then divide.",
            "The answer is the first whole number of hours past that point.",
        ),
        example="$90 + $5h < $30 + $10h\n60 < 5h → h > 12. At 12 hours both cost $150, so it's cheaper from 13 hours.",
    ),
    # Intercept · Systems
    "checksol": Briefing(
        title="Checking a solution of a system",
        concept="A solution of a system of two equations is a point (x, y) that makes BOTH equations true. Lots of points work in one equation; only the point where the two lines cross works in both.",
        steps=(
            "Take a point (x, y). The first number is x, the second is y.",
            "Put them into the first equation. Is it true?",
            "Put them into the second equation. Is that true too?",
            "Only a point that passes both checks is the solution.",
        ),
        example="x + y = 10 and x − y = 4.\n(7, 3): 7 + 3 = 10 ✓ and 7 − 3 = 4 ✓. (6, 4): 6 + 4 = 10 ✓ but 6 − 4 = 2 ✗.",
    ),
    "howmany": Briefing(
        title="How many solutions?",
        concept="Two straight lines can cross once, never (they're parallel), or lie on top of each other (they're the same line). Write each one as y = mx + b and compare: the slope m says which way it points, b where it crosses the y-axis.",
        steps=(
            "Rewrite each equation as y = mx + b if it isn't already.",
            "Different slopes: they cross once. One solution.",
            "Same slope, different b: parallel. No solution.",
            "Same slope and same b: the same line. Infinitely many solutions.",
        ),
        example="y = 2x + 3 and y = 2x − 1: same slope, different b. Parallel: no solution.\ny = 2x + 3 and y = 3 + 2x: the same line. Infinitely many.",
    ),
    "knownvar": Briefing(
        title="Systems: one value already known",
        concept="Sometimes one equation hands you a value straight away, like x = 4. Put that number in wherever the letter appears in the other equation, and only one unknown is left.",
        steps=(
            "Write the known value in place of its letter in the other equation, in brackets.",
            "Multiply it out.",
            "Solve for the letter that is left.",
        ),
        example="x = 4 and 3x + y = 19.\n3(4) + y = 19 → 12 + y = 19 → y = 7.",
    ),
    "elim": Briefing(
        title="Systems: adding to eliminate",
        concept="If one equation has +2y and the other −2y, adding the two equations makes the y's cancel, leaving one equation with only x in it. Add the left sides together and the right sides together.",
        steps=(
            "Check that the y terms are opposites, like +2y and −2y.",
            "Add the equations: left side + left side = right side + right side.",
            "The y's cancel. Divide to find x.",
        ),
        example="3x + 2y = 16 and 5x − 2y = 0.\nAdd: 8x = 16, so x = 2. (Then 6 + 2y = 16, y = 5.)",
    ),
    "setequal": Briefing(
        title="Systems: two expressions for y",
        concept="If both equations start y = ..., then where the lines cross the two right-hand sides are equal. Set them equal to each other and you have one equation with only x in it.",
        steps=(
            "Write: (right side of the first) = (right side of the second).",
            "Gather the x terms on one side.",
            "Gather the plain numbers on the other side, then divide.",
        ),
        example="y = 3x + 1 and y = x + 7.\n3x + 1 = x + 7 → 2x + 1 = 7 → 2x = 6 → x = 3 (and y = 10).",
    ),
    # Gunnery · Quadratics
    "zeroprod": Briefing(
        title="The zero product property",
        concept="If two numbers multiply to 0, one of them must be 0. So when a quadratic is already factored and set equal to 0, each factor gives one solution. Setting x − 3 = 0 gives x = 3: the sign flips.",
        steps=(
            "Set the first factor equal to 0 and solve it.",
            "Set the second factor equal to 0 and solve it.",
            "Both answers are solutions.",
        ),
        example="(x − 3)(x + 5) = 0\nx − 3 = 0 → x = 3, and x + 5 = 0 → x = −5. Solutions: x = −5 or x = 3.",
    ),
    "evalquad": Briefing(
        title="Evaluating a quadratic",
        concept="To find the height at a given time, put the time in for t everywhere it appears. Powers come before multiplying: in −16t², square t first, then multiply by −16.",
        steps=(
            "Write the equation with the time in brackets in place of each t.",
            "Square the time first, then multiply by −16.",
            "Multiply the time by the number with t.",
            "Add everything up.",
        ),
        example="h = −16t² + 64t + 20 at t = 3.\n−16(9) + 64(3) + 20 = −144 + 192 + 20 = 68 feet.",
    ),
    "axis": Briefing(
        title="The axis of symmetry",
        concept="Every parabola y = ax² + bx + c is the same on both sides of a vertical line, its axis of symmetry. The line is x = −b ÷ (2a), and the vertex (the highest or lowest point) sits on it.",
        steps=(
            "Read off a (the number with x²) and b (the number with x), with their signs.",
            "Work out 2a.",
            "x = −b ÷ (2a). The minus sign flips the sign of b.",
        ),
        example="y = 2x² − 12x + 5: a = 2, b = −12.\nx = −(−12) ÷ (2 × 2) = 12 ÷ 4 = 3.",
    ),
    # Radar · Powers & Roots, multi-step
    "powprod": Briefing(
        title="Powers of products",
        concept="A power outside brackets applies to everything inside them: (3x²)⁴ = 3⁴ · (x²)⁴. A power of a power multiplies the exponents. After that, multiplying powers of x adds their exponents and dividing subtracts them.",
        steps=(
            "Raise the number in the brackets to the power: 3² = 9, 2³ = 8.",
            "Multiply x's exponent by the power: (x⁴)³ = x¹².",
            "Multiplying by another power of x? Add the exponents. Dividing? Subtract them.",
        ),
        example="(2x³)² · x⁴ = 4x⁶ · x⁴ = 4x¹⁰  ·  (3x²)³ ÷ x⁴ = 27x⁶ ÷ x⁴ = 27x²",
    ),
    "sciquot": Briefing(
        title="Dividing in scientific notation",
        concept="Divide the numbers in front and subtract the exponents on the 10s. If the number in front comes out less than 1, move its point one place right to get it between 1 and 10, and take 1 off the exponent to make up for it.",
        steps=(
            "Divide the numbers in front.",
            "Subtract the exponents: 10ᵐ ÷ 10ⁿ = 10ᵐ⁻ⁿ.",
            "Less than 1 in front? Move the point one place right and take 1 off the exponent.",
        ),
        example="(1.2 × 10⁸) ÷ (4 × 10³)\n1.2 ÷ 4 = 0.3 and 10⁸ ÷ 10³ = 10⁵: 0.3 × 10⁵ = 3 × 10⁴.",
    ),
    # Reactor · Exponentials
    "pctfactor": Briefing(
        title="Growth and decay factors",
        concept="A percent change is really a multiplication. Growing 15% means you keep ALL of it (100%) and gain 15% more: 115%, so you multiply by 1.15. Losing 20% leaves 80%, so you multiply by 0.8. That number is the growth (or decay) factor, b.",
        steps=(
            "Write the percent as a decimal: move the point two places left (15% → 0.15, 5% → 0.05).",
            "Growing? Add it to 1: b = 1 + 0.15 = 1.15.",
            "Shrinking? Take it away from 1: b = 1 − 0.2 = 0.8.",
        ),
        example="Output grows 6% an hour → b = 1 + 0.06 = 1.06.\nCoolant loses 25% a cycle → b = 1 − 0.25 = 0.75.",
    ),
    "newold": Briefing(
        title="The factor from two readings",
        concept="If a reading is multiplied by the same number every hour, you can find that number by dividing: new ÷ old. A factor bigger than 1 means it grew; less than 1 means it shrank. The amount it went up by is NOT the percent unless it started at 100.",
        steps=(
            "Divide the later reading by the earlier one.",
            "Check: old × factor should give new.",
            "The percent change is the distance from 1: 1.15 is 15% up, 0.85 is 15% down.",
        ),
        example="200 MW at 0900, 230 MW at 1000.\n230 ÷ 200 = 1.15. Check: 200 × 1.15 = 230 ✓ (it grew 15%, not 30%).",
    ),
    "readexp": Briefing(
        title="Reading y = a × bᵗ",
        concept="In y = a × bᵗ, a is the starting amount (at t = 0, because b⁰ = 1) and b is the factor it is multiplied by every step. If b is more than 1 it grows by b − 1 each step; if b is less than 1 it shrinks by 1 − b.",
        steps=(
            "a, the number in front, is where it starts.",
            "b, the number with the power t, is the factor.",
            "Growing: the rate is b − 1 (1.08 → 0.08). Shrinking: the rate is 1 − b (0.9 → 0.1).",
            "Turn the rate into a percent: move the point two places right.",
        ),
        example="y = 400 × 0.85ᵗ\nIt starts at 400. Each hour 85% is left, so it drops 1 − 0.85 = 0.15 = 15% an hour.",
    ),
    "halflife": Briefing(
        title="Half-life",
        concept="The half-life is how long it takes for half of something to decay. After one half-life half is left, after two a quarter, after three an eighth. Count the half-lives first, then halve that many times.",
        steps=(
            "Put the time in the same units as the half-life (1 hour = 60 minutes).",
            "Number of half-lives: n = time ÷ half-life.",
            "Halve the starting amount n times: start × (½)ⁿ.",
        ),
        example="800 units with a half-life of 3 hours. How much after 9 hours?\nn = 9 ÷ 3 = 3 half-lives: 800 → 400 → 200 → 100 units.",
    ),
    "compound": Briefing(
        title="Repeated percent change",
        concept="A percent change works on whatever is there NOW, not on what you started with. So 10% growth for two hours is × 1.1 × 1.1, not +10% +10%. Each step adds more than the last (or takes away less).",
        steps=(
            "Find the factor: 1 + rate for growth, 1 − rate for decay.",
            "Multiply by the factor once for each step: start × bⁿ.",
            "Work step by step if it helps, writing down each new amount.",
        ),
        example="200 MW, growing 10% an hour, after 2 hours:\n200 × 1.1 = 220, then 220 × 1.1 = 242 MW (not 240).",
    ),
    "linexp": Briefing(
        title="Linear or exponential?",
        concept="Look at how a table changes from one step to the next. If it goes up (or down) by the same AMOUNT every time, it is linear. If it is multiplied by the same NUMBER every time, it is exponential.",
        steps=(
            "Differences: take each value from the next. All the same? Linear: add it once more.",
            "If not, ratios: divide each value by the one before. All the same? Exponential: multiply by it once more.",
            "Only go one step past the table.",
        ),
        example="3, 6, 12, 24: jumps 3, 6, 12 (not equal); ratios 2, 2, 2. Exponential: 24 × 2 = 48.\n3, 7, 11, 15: jumps 4, 4, 4. Linear: 15 + 4 = 19.",
    ),
    "expmodel": Briefing(
        title="Writing an exponential model",
        concept="A starting amount that changes by the same PERCENT every step is exponential: y = a × bᵗ. a is the start and b is the factor, 1 + rate or 1 − rate. The rate never goes in on its own or as a whole number.",
        steps=(
            "a = the amount at t = 0.",
            "b = 1 + rate (growing) or 1 − rate (shrinking), as a decimal.",
            "Write y = a × bᵗ. The power t goes on b only.",
        ),
        example="A store starts at 600 units and loses 15% a day.\na = 600, b = 1 − 0.15 = 0.85, so y = 600 × 0.85ᵗ.",
    ),
    "twopoints": Briefing(
        title="An exponential model from two points",
        concept="Between two readings the amount is multiplied by b once for every step. So divide the later reading by the earlier one, then find the number that multiplies by itself that many times to make it. That is b. Then work back to t = 0 for a.",
        steps=(
            "Divide: later reading ÷ earlier reading.",
            "Count the steps between them. Two steps: b × b = the ratio, so b is its square root. Three steps: b × b × b.",
            "a is the reading at t = 0. If you don't have it, divide back: a = y(1) ÷ b.",
        ),
        example="y(0) = 5 and y(2) = 45.\n45 ÷ 5 = 9 over 2 steps. b × b = 9, so b = 3, and y = 5 × 3ᵗ.",
    ),
    "splitrate": Briefing(
        title="The rate per step from a longer change",
        concept="Something that grows 44% over two hours did NOT grow 22% each hour: each hour's growth builds on the last. Find the factor for the whole time, then the factor for one step, the number that multiplies by itself to make it.",
        steps=(
            "Factor for the whole time: later reading ÷ earlier reading.",
            "Two steps: b × b = that factor, so b is its square root (three steps: b × b × b).",
            "The rate per step is b − 1 (growing) or 1 − b (shrinking), as a percent.",
        ),
        example="400 → 576 in 2 hours: 576 ÷ 400 = 1.44.\nb × b = 1.44, so b = 1.2: 20% an hour (not 22%).",
    ),
    "versus": Briefing(
        title="When exponential passes linear",
        concept="Linear growth adds the same amount every step; exponential growth multiplies. An exponential can start far behind, but its steps keep getting bigger, so it always catches up in the end. To find when, make a table of both and compare the totals.",
        steps=(
            "Work out both for t = 1, 2, 3... (doubling is quick: just keep doubling).",
            "Compare the totals each hour, not how much each one grew.",
            "The answer is the first t where the exponential one is bigger.",
        ),
        example="10 × 2ᵗ against 100 + 50t:\nt = 5: 320 against 350 (behind). t = 6: 640 against 400 (ahead). First ahead at t = 6.",
    ),
    "threshold": Briefing(
        title="Decay down to a limit",
        concept="To find when something that keeps halving drops below a limit, halve step by step and count. It usually won't land exactly on the limit, so look for the first amount that is under it. Then turn the number of halvings into time.",
        steps=(
            "Halve step by step, writing down each amount.",
            "Stop at the first amount below the limit. Count the halvings, n.",
            "Time = n × the half-life.",
        ),
        example="1,000 units halve every 2 minutes. When is it first below 150?\n1,000 → 500 → 250 → 125: 3 halvings, so 3 × 2 = 6 minutes.",
    ),
}


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------

GENERATORS: list[Generator] = []
gen = registry(GENERATORS)

_TRIPLES = [[3, 4, 5], [5, 12, 13], [8, 15, 17], [7, 24, 25], [6, 8, 10], [9, 12, 15], [12, 16, 20], [15, 20, 25], [10, 24, 26], [20, 21, 29]]


def _undo(n: int) -> tuple[str, str]:
    """How to undo "+ n" (the right move) and the opposite (the mistake): 7 -> ("subtract 7", "added 7")."""
    return (f"add {abs(n)}", f"subtracted {abs(n)}") if n < 0 else (f"subtract {n}", f"added {n}")


def _check_root(x: int, got: int) -> str:
    """A reason that shows the check: "Check x = 3: it makes the left side 4, not 0."."""
    return f"Check x = {_lead(x)}: it makes the left side {_lead(got)}, not 0."


# ---------------- Linear ----------------


@gen("lin", 2)
def fuel_burn(ctx: Context) -> Problem:
    """Fuel burn down to a reserve: rt + R = F."""
    r = ctx.pick([6, 8, 10, 12, 15, 20])
    t = ctx.rand(4, 18)
    R = ctx.pick([30, 40, 50, 60, 80])
    F = r * t + R
    ship = _fleet_ship(ctx).name
    sc = ctx.pick([
        dict(story=f"{ship} has {F} tons of fuel aboard and burns {r} tons every hour. Standing orders say she must never drop below a {R}-ton reserve.", ask="How many hours can she steam before hitting the reserve? Solve for t.", unit="hours", per="hour", amt="tons", one="ton"),
        dict(story=f"The galley on {ship} has {F} pounds of flour and uses {r} pounds a day. The cook wants to keep {R} pounds in reserve for emergencies.", ask="How many days until the flour hits the reserve? Solve for t.", unit="days", per="day", amt="pounds", one="pound"),
        dict(story=f"{ship}'s freshwater tank holds {F} gallons and the crew uses {r} gallons an hour. The chief wants {R} gallons left for the boilers.", ask="How many hours until the water reaches the reserve? Solve for t.", unit="hours", per="hour", amt="gallons", one="gallon"),
        dict(story=f"A helicopter aboard {ship} carries {F} gallons of fuel and burns {r} per hour. Regulations require landing with {R} gallons still in the tank.", ask="How many hours can it fly? Solve for t.", unit="hours", per="hour", amt="gallons", one="gallon"),
    ])
    per, amt, one = sc["per"], sc["amt"], sc["one"]
    mistakes = [
        (_whole(F / r), f"You divided {F} by {r} but forgot to take away the {R}-{one} reserve first."),
        (_whole((F + R) / r), f"You added the {R}-{one} reserve to {F}. The reserve can't be used, so take it away."),
        (F - R, f"{F} − {R} = {F - R} {amt} can be used, but you stopped there. Divide by the {r} used each {per}."),
        (_whole(R / r), f"{R} ÷ {r} is how long the reserve alone would last. Take {R} away from {F} first, then divide by {r}."),
        (_whole((F - R) / R), f"You divided by {R}, the reserve, instead of by {r}, the amount used each {per}."),
        ((F - R) * r, f"You multiplied by {r}. To undo {r} times t, divide by {r}."),
        (F - R - r, f"You subtracted {r} instead of dividing by it: {r}t means {r} times t."),
    ]
    return Problem(
        help="fuel",
        story=sc["story"],
        expr=f"{r}t + {R} = {F}",
        ask=sc["ask"],
        choices=_numeric_choices(ctx, t, mistakes),
        solution=(f"Usable fuel is {F} − {R} = {F - R} tons.", f"So {r}t = {F - R}.", f"Divide both sides by {r}: t = {t} {sc['unit']}."),
        hint=f"First subtract the {R} reserve from {F} — that's the fuel she can actually burn. Then divide by {r}.",
    )


@gen("lin", 1)
def distance_rate_time(ctx: Context) -> Problem:
    """d = r·t: find the time or the distance."""
    sh = _fleet_ship(ctx)
    s = sh.speed
    t = ctx.rand(2, 9)
    d = s * t
    ship = sh.cls
    mode = ctx.rand(0, 1)
    if mode == 0:
        story = ctx.pick([
            f"{sh.name}, {_an(ship)}, is {d} nautical miles from port and making {s} knots ({s} nautical miles per hour) straight toward it.",
            f"{sh.name} must cover {d} nautical miles to reach a drifting life raft. At full speed the {ship} makes {s} knots ({s} nautical miles per hour).",
            f"{sh.name} has {d} nautical miles left to Guam and holds {s} knots ({s} nautical miles per hour).",
            f"Escorting a convoy, {sh.name} races ahead {d} nautical miles to scout the strait at {s} knots ({s} nautical miles per hour).",
        ])
        mistakes = [
            (d - s, f"You subtracted {s} from {d}. Time = distance ÷ speed, so divide {d} by {s}."),
            (d + s, f"You added {s} to {d}. Time = distance ÷ speed, so divide {d} by {s}."),
            (d * s, f"You multiplied {d} by {s}. Time = distance ÷ speed, so divide instead."),
            (s / d, f"You divided the wrong way round: {s} ÷ {d}. Time = distance ÷ speed."),
            (s, f"{s} knots is the speed, not the time. Divide the {d} nautical miles by it."),
            (t - 1, f"Check by multiplying: {s} × {t - 1} = {s * (t - 1)}, which falls short of {d}."),
            (t + 1, f"Check by multiplying: {s} × {t + 1} = {s * (t + 1)}, which is more than {d}."),
        ]
        return Problem(
            help="drt",
            story=story,
            expr=f"{d} = {s} × t",
            ask="How many hours does the trip take?",
            choices=_numeric_choices(ctx, t, mistakes),
            solution=(f"Distance = rate × time, so {d} = {s}t.", f"Divide both sides by {s}: t = {t} hours."),
            hint=f"d = r × t. You know d ({d}) and r ({s}). Divide to get t.",
        )
    story = ctx.pick([
        f"{sh.name} holds {s} knots for {t} hours on a steady heading.",
        f"{sh.name} sweeps a search sector at her top speed of {s} knots for {t} hours before turning back.",
        f"The {ship} {sh.name} tows a barge at {s} knots for {t} hours through the strait.",
        f"{sh.name} steams at {s} knots for {t} hours to rejoin the fleet.",
    ])
    mistakes = [
        (s + t, f"You added {s} and {t}. Distance = speed × time, so multiply."),
        (s, f"{s} nautical miles is how far she goes in one hour. Multiply by the {t} hours."),
        (s / t, f"You divided {s} by {t}. Distance = speed × time, so multiply."),
        (s * (t - 1), f"That's {s} × {t - 1}: one hour short. She steams for {t} hours."),
        (s * (t + 1), f"That's {s} × {t + 1}: one hour too many. She steams for {t} hours."),
        (s * t * 60, f"You also multiplied by 60, but knots are already nautical miles per hour, so {s} × {t} is enough."),
    ]
    return Problem(
        help="drt",
        story=story,
        expr=f"d = {s} × {t}",
        ask="How far has she traveled, in nautical miles?",
        choices=_numeric_choices(ctx, d, mistakes),
        solution=(f"Distance = rate × time = {s} × {t}.", f"d = {d} nautical miles."),
        hint=f"Multiply speed by time: {s} × {t}.",
    )


@gen("lin", 2)
def two_step_equation(ctx: Context) -> Problem:
    """Solve ax + b = c."""
    a = ctx.rand(2, 9)
    x = ctx.rand(-6, 12) or 3
    b = ctx.rand(-15, 15) or 4
    c = a * x + b
    story = ctx.pick([
        "Signals decodes a coded bearing. The cipher gives an equation; the true bearing offset is x.",
        "A dock worker earns a flat bonus plus an hourly rate. The equation below models the shift; x is the hours worked.",
        "The armory ledger is smudged. The only readable line is this equation, where x is the number of crates.",
        "The sonar tech balances an equation to calibrate the array. Find x.",
    ])
    undo, wrong = _undo(b)
    sb = _sgn(b)
    mistakes = [
        (c - b, f"{_lead(c - b)} is {a}x, not x. You still need to divide by {a}."),
        (_whole((c + b) / a), f"To undo the {sb}, {undo} on both sides. You {wrong} instead."),
        (-x, f"The sign flipped: {a}x = {_lead(c - b)}, and dividing by {a} keeps that sign."),
        (_whole(c / a - b), f"You divided {_lead(c)} by {a} before undoing the {sb}. Undo the {sb} first, then divide."),
        (_whole(c / a), f"You divided {_lead(c)} by {a} but forgot about the {sb}."),
        (c - b - a, f"You subtracted {a} instead of dividing by it: {a}x means {a} times x."),
        ((c - b) * a, f"You multiplied by {a}. To undo {a} times x, divide by {a}."),
    ]
    return Problem(
        help="solve",
        story=story,
        expr=f"{a}x {_sgn(b)} = {_lead(c)}",
        ask="Solve for x.",
        choices=_numeric_choices(ctx, x, mistakes, allow_neg=True),
        solution=(
            f"{f'Add {abs(b)}' if b < 0 else f'Subtract {b}'} on both sides: {a}x = {_lead(c - b)}.",
            f"Divide both sides by {a}: x = {_lead(x)}.",
            f"Check: {a}({_lead(x)}) {_sgn(b)} = {_lead(c)} ✓",
        ),
        hint=f"Undo the {_sgn(b).replace(' ', '', 1)} first ({f'add {abs(b)}' if b < 0 else f'subtract {b}'} from both sides), then divide by {a}.",
    )


@gen("lin", 2)
def slope_from_two_points(ctx: Context) -> Problem:
    """Slope (rate of change) from two log readings."""
    t1 = ctx.rand(1, 4)
    t2 = t1 + ctx.rand(2, 5)
    m = -ctx.pick([5, 8, 10, 12, 15, 20, 25])
    f1 = ctx.rand(300, 500)
    f2 = f1 + m * (t2 - t1)
    sc = ctx.pick([
        dict(story=f"The engineering log plots fuel remaining against time: at {t1} hours the ship had {f1} tons, and at {t2} hours she had {f2} tons.", unit="tons", what="fuel"),
        dict(story=f"A submarine's battery gauge reads {f1} amp-hours at {t1} hours into the dive and {f2} amp-hours at {t2} hours.", unit="amp-hours", what="charge"),
        dict(story=f"The ship's freshwater log shows {f1} gallons at hour {t1} and {f2} gallons at hour {t2}.", unit="gallons", what="water"),
        dict(story=f"Ammunition count during a gunnery exercise: {f1} rounds at {t1} hours, {f2} rounds at {t2} hours.", unit="rounds", what="ammunition"),
    ])
    unit, what = sc["unit"], sc["what"]
    dt, df = t2 - t1, f2 - f1
    mistakes = [
        (-m, f"The sign is wrong: the {what} went down, so the slope is negative."),
        ((t2 - t1) / (f2 - f1), f"You divided the change in time by the change in {what}. Slope is change in {what} ÷ change in time."),
        (df, f"{_lead(df)} is the change in {what}. Divide it by the change in time, {t2} − {t1} = {dt}."),
        (_whole(df / t2), f"You divided by {t2}, but the time changed by {t2} − {t1} = {dt} hours."),
        (_whole(df / (t1 + t2)), f"You added the times. The change in time is {t2} − {t1} = {dt}."),
        (_whole(f2 / t2), "You divided one reading by its time. Slope compares how both numbers change between the two readings."),
        (df - dt, "You subtracted the change in time instead of dividing by it."),
        (df * dt, f"You multiplied the change in {what} by the change in time. Slope divides them."),
    ]
    return Problem(
        help="slope",
        story=sc["story"],
        expr=f"({t1}, {f1}) and ({t2}, {f2})",
        ask=f"What is the slope of the line through these points, in {unit} per hour?",
        choices=_numeric_choices(ctx, m, mistakes, allow_neg=True),
        solution=(
            f"Change in {what}: {f2} − {f1} = {_lead(f2 - f1)}.",
            f"Change in time: {t2} − {t1} = {t2 - t1}.",
            f"Slope = {_lead(f2 - f1)} ÷ {t2 - t1} = {_lead(m)} {unit}/hour (negative because it is going down).",
        ),
        hint=f"Slope = (change in {what}) ÷ (change in time). It went from {f1} to {f2}; time went from {t1} to {t2}.",
    )


@gen("lin", 1)
def function_notation(ctx: Context) -> Problem:
    """Evaluate r(t) = D − st."""
    D = ctx.pick([40, 50, 60, 72, 80, 90, 100, 120])
    s = ctx.pick([10, 12, 15, 18, 20, 25])
    t = ctx.rand(1, 4)
    if D - s * t < 0:
        t = 1
    r = D - s * t
    story = ctx.pick([
        f"The officer of the watch writes the range to a contact as a function of time: the contact starts {D} nm away and closes at {s} knots.",
        f"A tanker is {D} nm from the rendezvous point and steams toward it at {s} knots. The navigator writes the remaining distance as a function r(t).",
        f"An incoming aircraft is {D} nm out and closing at {s} knots. Combat writes its range as a function of time.",
    ])
    st = s * t
    mistakes = [
        (D - s, f"You took away {s} only once. r({t}) means {s} × {t} comes off {D}."),
        (D + st, f"You added {st}. The rule says {D} minus {s}t, so subtract."),
        (st, f"{s} × {t} = {st} is how much the range has closed. Take it away from {D}."),
        ((D - s) * t, f"You subtracted before multiplying. Work out {s} × {t} first, then subtract."),
        (D - s - t, f"{s}t means {s} times {t}, not {s} and then {t}."),
        (st - D, f"You subtracted the wrong way round. The rule is {D} minus {s}t."),
        (_whole(D / s), f"{D} ÷ {s} is how many hours until the range reaches 0, not the range after {t} hour{'s' if t > 1 else ''}."),
        (t, f"{t} is what goes in, the time. r({t}) is the range that comes out when you put {t} in for t."),
        (D, f"{D} is r(0), the range at the start. Put {t} in for t first."),
    ]
    return Problem(
        help="func",
        story=story,
        expr=f"r(t) = {D} − {s}t",
        ask=f"Find r({t}), the range after {t} hour{'s' if t > 1 else ''}.",
        choices=_numeric_choices(ctx, r, mistakes, allow_neg=True),
        solution=(f"Replace t with {t}: r({t}) = {D} − {s}({t}).", f"Multiply first: {s} × {t} = {s * t}.", f"Subtract: {D} − {s * t} = {r} nm."),
        hint=f'r({t}) means "plug in {t} for t". Multiply {s} × {t} before you subtract.',
    )


@gen("lin", 3)
def inequality_load_limit(ctx: Context) -> Problem:
    """Load limit: C + mw ≤ W, largest whole m."""
    m = ctx.pick([220, 240, 250, 260, 280])
    n = ctx.rand(6, 18)
    W = ctx.pick([6000, 7000, 8000, 9000])
    slack = ctx.rand(20, m - 20)
    c = W - m * n - slack
    cr = _js_round(c / 100) * 100
    cargo = max(400, cr)
    n_ans = (W - cargo) // m
    room = W - cargo
    mistakes = [
        (n_ans + 1, f"You rounded up. {n_ans + 1} Marines would weigh more than the {room:,} pounds left, so round down."),
        (n_ans - 1, f"One more Marine still fits: {cargo:,} + {m} × {n_ans} = {cargo + m * n_ans:,}, which is under {W:,}."),
        (W // m, f"You forgot the {cargo:,} pounds of cargo already aboard. Take it away from {W:,} before dividing."),
        ((W + cargo) // m, f"You added the {cargo:,} pounds of cargo. It takes up room, so take it away from {W:,}."),
        (room, f"{room:,} pounds is the room left. Divide it by the {m} pounds each Marine weighs."),
        (cargo // m, f"{cargo:,} ÷ {m} turns the cargo into Marines. Take the cargo away from {W:,} first, then divide."),
        (_whole(W / (cargo + m)), f"{cargo:,} + {m}m isn't ({cargo:,} + {m}) × m. Take the {cargo:,} away first, then divide by {m}."),
        (_whole(W / cargo), f"You divided the limit by the cargo. Take the {cargo:,} pounds of cargo away from {W:,}, then divide by {m}."),
    ]
    return Problem(
        help="ineq",
        story=f"A landing craft is rated for at most {W:,} pounds. {cargo:,} pounds of cargo are already lashed down. Each Marine with full gear weighs {m} pounds.",
        expr=f"{cargo:,} + {m}m ≤ {W:,}",
        ask="What is the greatest number of Marines that can board?",
        choices=_numeric_choices(ctx, n_ans, mistakes),
        solution=(
            f"Subtract the cargo: {m}m ≤ {W:,} − {cargo:,} = {W - cargo:,}.",
            f"Divide by {m}: m ≤ {_to_fixed((W - cargo) / m, 2)}.",
            f"You can't load part of a Marine, so round down: {n_ans} Marines.",
        ),
        hint=f"Subtract the {cargo:,} lb already aboard, divide by {m}, and round DOWN.",
    )


# ---------------- Systems ----------------


@gen("sys", 3)
def overtake(ctx: Context) -> Problem:
    """A faster ship leaves later and catches up: s1(t + h) = s2·t."""
    s1 = ctx.pick([10, 12, 15])
    h = ctx.rand(1, 3)
    diff = ctx.pick([d for d in [3, 5, 6, 10, 15] if (s1 * h) % d == 0])
    s2 = s1 + diff
    t = (s1 * h) // diff
    F = _fleet_ship(ctx)
    later = "One hour" if h == 1 else f"{h} hours"
    sc = ctx.pick([
        dict(story=f"A submarine leaves port at {s1} knots. {later} later {F.name} leaves the same port on the same heading at {s2} knots.", slow="submarine", fast=F.name, fast_ref=F.name),
        dict(story=f"A slow tanker departs at {s1} knots. {later} later her escort, {F.name}, leaves the same pier at {s2} knots to catch up.", slow="tanker", fast=F.name, fast_ref=F.name),
        dict(story=f"A smuggler's boat flees the harbor at {s1} knots. The coast guard cutter gets underway {'an hour' if h == 1 else f'{h} hours'} later at {s2} knots.", slow="smuggler", fast="cutter", fast_ref="the cutter"),
    ])
    slow = sc["slow"]
    gap = s1 * h
    hrs = "hour" if h == 1 else "hours"
    mistakes = [
        (t + h, f"That counts from when the {slow} left. The question counts from when {sc['fast_ref']} sails."),
        (gap, f"{s1} × {h} = {gap} nautical miles is the {slow}'s head start, not a time. Divide it by how fast the gap closes."),
        (_whole(gap / s2), f"You divided the head start by {s2}, the full speed. The gap only closes by {s2} − {s1} = {diff} knots an hour."),
        (_whole(gap / (s1 + s2)), f"You added the speeds, but both head the same way: the gap closes by {s2} − {s1} = {diff} knots an hour."),
        (h / diff, f"You multiplied only the t by {s1}. {s1}(t + {h}) is {s1}t + {gap}."),
        (h, f"{h} {hrs} is the {slow}'s head start, not the time to catch up."),
        (diff, f"{diff} knots is how fast the gap closes. Divide the {gap} nautical-mile head start by it."),
    ]
    return Problem(
        help="overtake",
        story=sc["story"],
        expr=f"{s1}(t + {h}) = {s2}t",
        ask=f"How many hours after {sc['fast_ref']} sails does it catch the {slow}?",
        choices=_numeric_choices(ctx, t, mistakes),
        solution=(
            f"{_cap(slow)} distance: {s1}(t + {h}) = {s1}t + {s1 * h}. {_cap(sc['fast'])} distance: {s2}t.",
            f"Set equal: {s1}t + {s1 * h} = {s2}t.",
            f"Subtract {s1}t: {s1 * h} = {diff}t.",
            f"Divide: t = {t} hours.",
        ),
        hint=f"The {slow} has been sailing {h} hour{'s' if h > 1 else ''} longer, so its distance is {s1}(t + {h}). Set that equal to {s2}t.",
    )


@gen("sys", 3)
def supply_mix(ctx: Context) -> Problem:
    """Two weighings of two kinds of crate, solved by elimination."""
    s = ctx.pick([120, 150, 180, 200, 250, 300])
    r = ctx.pick([v for v in [60, 80, 90, 100, 110, 140] if v != s])
    a = ctx.rand(2, 5)
    b = ctx.rand(1, 4)
    c = a
    d = b + ctx.rand(1, 3)
    W1 = a * s + b * r
    W2 = c * s + d * r
    pl = "s" if b > 1 else ""
    sc = ctx.pick([
        dict(story=f"The quartermaster weighs two loads. {a} shell crates and {b} ration crate{pl} weigh {W1:,} lb. {c} shell crates and {d} ration crates weigh {W2:,} lb.", item="shell", other="ration"),
        dict(story=f"The crane log shows two lifts: {a} torpedo crates (s) plus {b} spare-part crate{pl} (r) came to {W1:,} lb; {c} torpedo crates plus {d} spare-part crates came to {W2:,} lb.", item="torpedo", other="spare-part"),
        dict(story=f"Two pallets are weighed: {a} medical crates (s) with {b} blanket crate{pl} (r) total {W1:,} lb; {c} medical crates with {d} blanket crates total {W2:,} lb.", item="medical", other="blanket"),
    ])
    item, other = sc["item"], sc["other"]
    them, weigh = ("them", "weigh") if b > 1 else ("it", "weighs")
    mistakes = [
        (r, f"{r} lb is r, one {other} crate. The question asks for s: put r = {r} back into the first equation."),
        (_whole(W1 / (a + b)), f"You shared {W1:,} lb evenly over all {a + b} crates, but the two kinds of crate weigh different amounts."),
        (_whole(W2 / (c + d)), f"You shared {W2:,} lb evenly over all {c + d} crates, but the two kinds of crate weigh different amounts."),
        (_whole(W1 / a), f"You divided {W1:,} by {a}, but the {b} {other} crate{pl} {weigh} part of that. Take {them} away first."),
        (_whole((W1 - r) / a), f"There are {b} {other} crates in the first load, so take away {b} × {r}, not just {r}."),
        (W1 - b * r, f"{W1 - b * r:,} lb is all {a} {item} crates together. Divide by {a} to get one."),
        (_whole((W1 + b * r) / a), f"You added the {other} crates' weight. Take it away from {W1:,} instead."),
    ]
    if b == 1:
        del mistakes[4]
    return Problem(
        help="mix",
        story=sc["story"],
        expr=f"{a}s + {b}r = {W1:,}\n{c}s + {d}r = {W2:,}",
        ask=f"How much does one {item} crate (s) weigh, in pounds?",
        choices=_numeric_choices(ctx, s, mistakes),
        solution=(
            f"Both equations have {a}s, so subtract the first from the second.",
            f"({d} − {b})r = {W2:,} − {W1:,} → {d - b}r = {W2 - W1:,} → r = {r}.",
            f"Plug into the first: {a}s + {b}({r}) = {W1:,} → {a}s = {W1 - b * r:,} → s = {s} lb.",
        ),
        hint=f"The s terms match ({a}s in both). Subtract one equation from the other so s disappears, find r, then go back for s.",
    )


@gen("sys", 2)
def sum_and_difference(ctx: Context) -> Problem:
    """x + y = S, x − y = d."""
    y = ctx.rand(8, 30)
    dfrn = ctx.pick([2, 4, 6, 8, 10, 12])
    x = y + dfrn
    S = x + y
    sc = ctx.pick([
        dict(story=f"Two convoys are heading for Pearl Harbor with {S} ships between them. The northern convoy (x) has {dfrn} more ships than the southern one (y).", ask="How many ships are in the northern convoy, x?", unit="ships", small="southern convoy"),
        dict(story=f"Two watch sections total {S} sailors. The port section (x) has {dfrn} more sailors than the starboard section (y).", ask="How many sailors are in the port section, x?", unit="sailors", small="starboard section"),
        dict(story=f"{S} aircraft are split between two carriers. The flagship (x) carries {dfrn} more than the other carrier (y).", ask="How many aircraft does the flagship, x carry?", unit="aircraft", small="other carrier"),
    ])
    mistakes = [
        (y, f"{y} is y, the {sc['small']}. The question asks for x, the bigger one."),
        (S // 2, f"{S} ÷ 2 splits them evenly, but x has {dfrn} more than y."),
        (S - dfrn, f"{S} − {dfrn} = {S - dfrn} is 2y. Add the equations instead: 2x = {S} + {dfrn}."),
        (S + dfrn, f"{S} + {dfrn} = {S + dfrn} is 2x. Divide by 2 to get x."),
        (S // 2 + dfrn, f"You split {S} evenly and then added all {dfrn}. Add the equations instead: 2x = {S} + {dfrn}."),
    ]
    return Problem(
        help="sumdiff",
        story=sc["story"],
        expr=f"x + y = {S}\nx − y = {dfrn}",
        ask=sc["ask"],
        choices=_numeric_choices(ctx, x, mistakes),
        solution=(
            f"Add the two equations so y cancels: 2x = {S} + {dfrn} = {S + dfrn}.",
            f"Divide by 2: x = {x} {sc['unit']}.",
            f"Check: the {sc['small']} has {y}, and {x} + {y} = {S} ✓",
        ),
        hint="Add the two equations together — the y's cancel and you get 2x = something.",
    )


@gen("sys", 3)
def substitution(ctx: Context) -> Problem:
    """y = mx + k and px + qy = C, solved by substitution."""
    x = ctx.rand(1, 8)
    m = ctx.rand(2, 4)
    k = ctx.rand(-5, 6) or 1
    y = m * x + k
    p = ctx.rand(2, 5)
    q = ctx.pick([1, 2])
    C = p * x + q * y
    qs = "" if q == 1 else str(q)
    qk = q * k
    story = ctx.pick([
        "Signals intercepts a two-line cipher. The first line already tells you y in terms of x.",
        "The supply officer's notes give two equations. The first already has y by itself — use substitution.",
        "A damage-control drill is scored with two equations. Substitute the first into the second to find x.",
    ])
    sub = f"({m}x {_sgn(k)})"
    coef = p + q * m
    undo, wrong = _undo(qk)
    mistakes = [
        (y, f"{_lead(y)} is y. The question asks for x."),
        (_whole((C + qk) / coef), f"To undo the {_sgn(qk)}, {undo} on both sides. You {wrong} instead."),
        (_whole(C / coef), f"You left out the {_lead(k)} when you put {sub} in for y."),
        (_whole(C / (p + q)), f"You treated y like x and added {p} + {q}. Put {sub} in for y instead."),
        (C - qk, f"{_lead(C - qk)} is {coef}x, not x. Divide by {coef}."),
        (_whole(C / p), f"You dropped the y. Put {sub} in for y instead of leaving it out."),
        (-x, f"The sign flipped: {coef}x = {_lead(C - qk)}, and dividing by {coef} keeps that sign."),
    ]
    for v in (x - 1, x + 1):
        mistakes.append((v, f"Check x = {_lead(v)}: then y = {_lead(m * v + k)}, and {p}x + {qs}y = {_lead(p * v + q * (m * v + k))}, not {_lead(C)}."))
    if p != q * m:
        mistakes.append((_whole((C - qk) / (p - q * m)), f"You subtracted the x terms. {p}x + {q * m}x is {coef}x."))
    if q == 2:
        mistakes += [
            (_whole((C - k) / coef), f"You multiplied only the {m}x by 2. The {_lead(k)} gets multiplied by 2 too."),
            (_whole((C - qk) / (p + m)), f"You multiplied only the {_lead(k)} by 2. The {m}x gets multiplied by 2 too."),
        ]
    return Problem(
        help="subst",
        story=story,
        expr=f"y = {m}x {_sgn(k)}\n{p}x + {qs}y = {_lead(C)}",
        ask="Solve for x.",
        choices=_numeric_choices(ctx, x, mistakes, allow_neg=True),
        solution=(
            f"Substitute the first line into the second: {p}x + {qs}({m}x {_sgn(k)}) = {_lead(C)}.",
            f"Distribute and combine: {p + q * m}x {_sgn(qk)} = {_lead(C)}.",
            f"{f'Add {abs(qk)}' if qk < 0 else f'Subtract {qk}'}: {p + q * m}x = {_lead(C - qk)} → x = {x}.",
        ),
        hint=f"Wherever you see y in the second line, write ({m}x {_sgn(k)}) instead. Then it's a one-variable equation.",
    )


# ---------------- Quadratics ----------------


@gen("quad", 3)
def trajectory(ctx: Context) -> Problem:
    """h = −16t² + vt: flight time or maximum height."""
    v = ctx.pick([96, 128, 160, 192, 224, 256, 320])
    T = v // 16
    peak_t = v // 32
    H = v * v // 64
    mode = ctx.rand(0, 1)
    story = ctx.pick([
        "A 5-inch gun fires and the shell's height in feet after t seconds is given by the equation.",
        "A signal flare is launched from the deck. Its height in feet after t seconds follows the equation.",
        "A line-throwing gun fires a weighted rope to another ship. The rope's height in feet after t seconds is given by the equation.",
    ])
    expr = f"h = −16t{sup(2)} + {v}t"
    if mode == 0:
        mistakes = [
            (peak_t, f"{peak_t} seconds is when it reaches the top. It takes just as long again to come back down."),
            (0, f"t = 0 is the moment it's fired. The other solution, from −16t + {v} = 0, is when it comes down."),
            (16 / v, f"You divided 16 by {v}, the wrong way round. −16t + {v} = 0 gives t = {v} ÷ 16."),
            (v, f"{v} is the launch speed in feet per second, not a time. Solve −16t + {v} = 0."),
            (v - 16, f"You subtracted 16 from {v}. Solve −16t + {v} = 0 by dividing {v} by 16."),
            (H, f"{H} feet is its highest point, not the time it spends in the air."),
        ]
        return Problem(
            help="traj",
            story=story,
            expr=expr,
            ask="How many seconds is it in the air before it comes down (h = 0)?",
            choices=_numeric_choices(ctx, T, mistakes),
            solution=(
                f"Set h = 0: −16t{sup(2)} + {v}t = 0.",
                f"Factor out t: t(−16t + {v}) = 0.",
                f"t = 0 is launch. The other root: −16t + {v} = 0 → t = {v} ÷ 16 = {T} seconds.",
            ),
            hint=f"Set h = 0, factor out t, and solve −16t + {v} = 0.",
        )
    p = peak_t
    mistakes = [
        (v * p, f"You forgot the −16t{sup(2)} part: {v} × {p} = {v * p}, then take away 16 × {p}{sup(2)}."),
        (0, f"That's the height when it lands, at t = {T}. The top is halfway there, at t = {p}."),
        (p, f"{p} seconds is when it's highest. Put t = {p} into the equation to get the height."),
        (T, f"{T} seconds is how long it's in the air, not how high it goes."),
        (16 * p * p + v * p, f"You added 16 × {p}{sup(2)} instead of taking it away: the equation has −16t{sup(2)}."),
        (v * p - 32 * p, f"You doubled {p} instead of squaring it: t{sup(2)} is {p} × {p} = {p * p}."),
    ]
    return Problem(
        help="traj",
        story=story,
        expr=expr,
        ask="What is its maximum height in feet?",
        choices=_numeric_choices(ctx, H, mistakes),
        solution=(
            f"Flight time is {v} ÷ 16 = {T} s, so the peak is at half that: t = {peak_t}.",
            f"h({peak_t}) = −16({peak_t}){sup(2)} + {v}({peak_t}) = −{16 * peak_t * peak_t} + {v * peak_t}.",
            f"Max height = {H} feet.",
        ),
        hint=f"The peak happens halfway through the flight, at t = {v} ÷ 32. Plug that t into the equation.",
    )


def _factor_pairs(n: int) -> list[tuple[int, int]]:
    """Every (u, v) with u ≤ v and u·v = n (n ≠ 0), negative pairs included."""
    out = []
    for u in range(-abs(n), abs(n) + 1):
        if u and n % u == 0 and u <= n // u:
            out.append((u, n // u))
    return out


@gen("quad", 2)
def factor_trinomial(ctx: Context) -> Problem:
    """Factor x² + bx + c."""
    while True:
        p = ctx.rand(-9, 9)
        q = ctx.rand(-9, 9)
        if not (p == 0 or q == 0 or p == q or p + q == 0):
            break
    b, c = p + q, p * q
    ans = _factor_form(min(p, q), max(p, q))

    def form(u: int, v: int) -> str:
        return _factor_form(min(u, v), max(u, v))

    wrong = [
        (form(-p, -q), f"The signs are backwards: those numbers multiply to {_lead(c)} but add to {_lead(-b)}, not {_lead(b)}."),
        (form(p, -q), f"Those numbers multiply to {_lead(-c)}, not {_lead(c)}. Check the signs."),
        (form(-p, q), f"Those numbers multiply to {_lead(-c)}, not {_lead(c)}. Check the signs."),
    ]
    others = [(u, v) for u, v in _factor_pairs(c) if u + v not in (b, -b)]
    for u, v in ctx.shuffle(others)[:2]:
        wrong.append((form(u, v), f"{_lead(u)} and {_lead(v)} multiply to {_lead(c)} but add to {_lead(u + v)}, not {_lead(b)}."))
    sums = [u for u in range(-9, 10) if u and u not in (p, q) and b - u and abs(b - u) <= 12 and u <= b - u]
    for u in ctx.shuffle(sums)[:1]:
        wrong.append((form(u, b - u), f"{_lead(u)} and {_lead(b - u)} add to {_lead(b)} but multiply to {_lead(u * (b - u))}, not {_lead(c)}."))
    story = ctx.pick([
        "The gunnery computer spits out a trinomial. Factor it to unlock the firing solution.",
        "The engine-room manual gives the shape of a fuel curve. Factor the expression.",
        "A sonar waveform is modeled by the trinomial below. Factor it.",
    ])
    return Problem(
        help="factor",
        story=story,
        expr=_trinomial(b, c),
        ask="Which is the factored form?",
        choices=_string_choices(ctx, ans, wrong),
        solution=(
            f"Need two numbers that multiply to {_lead(c)} and add to {_lead(b)}.",
            f"{_lead(p)} × {_lead(q)} = {_lead(c)} and {_lead(p)} + {_par(q)} = {_lead(b)} ✓",
            f"So the factors are {ans}.",
        ),
        hint=f"Look for two numbers whose product is {_lead(c)} and whose sum is {_lead(b)}. Check the signs carefully.",
    )


@gen("quad", 3)
def quadratic_roots(ctx: Context) -> Problem:
    """Solve x² + bx + c = 0 by factoring."""
    while True:
        p = ctx.rand(-8, 9)
        q = ctx.rand(-8, 9)
        if not (p == 0 or q == 0 or p == q):
            break
    b, c = -(p + q), p * q

    def pair(a: int, bb: int) -> str:
        return f"x = {_lead(min(a, bb))} or x = {_lead(max(a, bb))}"

    def f(x: int) -> int:
        return x * x + b * x + c

    ans = pair(p, q)
    wrong = [(pair(-p, -q), "Those are the numbers inside the factors. Setting each factor equal to 0 flips its sign.")]
    for keep, flip in ((p, q), (q, p)):
        if keep != -flip:
            wrong.append((pair(keep, -flip), f"Only one of those works. {_check_root(-flip, f(-flip))}"))
    others = [(u, v) for u, v in _factor_pairs(c) if u != v and {u, v} != {p, q} and {u, v} != {-p, -q}]
    for u, v in ctx.shuffle(others)[:2]:
        bad = u if f(u) else v
        wrong.append((pair(u, v), f"Those multiply to {_lead(c)}, but they don't both work. {_check_root(bad, f(bad))}"))
    sums = [u for u in range(-9, 10) if u not in (p, q) and u < p + q - u and u * (p + q - u) != c]
    distinct = len({w[0] for w in wrong} - {ans})
    for u in ctx.shuffle(sums)[: max(1, 4 - distinct)]:
        bad = u if f(u) else p + q - u
        wrong.append((pair(u, p + q - u), f"Those multiply to {_lead(u * (p + q - u))}, but the two answers must multiply to {_lead(c)}. {_check_root(bad, f(bad))}"))
    story = ctx.pick([
        "Fire control needs both times the shell's path crosses a target altitude. That means solving a quadratic.",
        "A periscope depth calculation reduces to the quadratic below. Find both solutions.",
        "The navigator's bearing check gives this equation. Solve it.",
    ])
    return Problem(
        help="roots",
        story=story,
        expr=_trinomial(b, c) + " = 0",
        ask="What are the solutions?",
        choices=_string_choices(ctx, ans, wrong),
        solution=(
            f"Factor: two numbers multiplying to {_lead(c)} and adding to {_lead(b)}: {_lead(-p)} and {_lead(-q)}.",
            f"(x {_sgn(-p)})(x {_sgn(-q)}) = 0.",
            f"Set each factor to zero: {ans}.",
        ),
        hint="Factor the left side first. Then remember: if (x − p)(x − q) = 0, then x = p or x = q — the signs flip.",
    )


@gen("quad", 3)
def deck_area(ctx: Context) -> Problem:
    """w(w + k) = A: find the width."""
    w = ctx.rand(6, 20)
    k = ctx.pick([2, 3, 4, 5, 6, 8, 10, 12])
    A = w * (w + k)
    story = ctx.pick([
        f"The flight deck of a carrier section is {k} feet longer than it is wide and covers {A:,} square feet.",
        f"A rectangular cargo hold is {k} feet longer than it is wide and has a floor area of {A:,} square feet.",
        f"The helipad's safety net is {k} feet longer than it is wide and covers {A:,} square feet.",
    ])
    mistakes = [
        (w + k, f"{w + k} feet is the length, the longer side. The question asks for the width."),
        (-(w + k), "That's the negative solution. A width can't be negative."),
        (_whole(A / k), f"You divided {A:,} by {k}. The {k} is how much longer the length is, not a side."),
        (_whole(math.sqrt(A)), f"√{A:,} would be the side of a square, but this one is {k} feet longer than it is wide."),
        (_whole(A / (k + 1)), f"You treated w × w as w. w(w + {k}) is w{sup(2)} + {k}w, not {k + 1}w."),
        (k, f"{k} feet is how much longer the length is, not the width."),
    ]
    pairs = [(u, A // u) for u in range(2, math.isqrt(A) + 1) if A % u == 0 and A // u - u != k]
    for u, v in ctx.shuffle(pairs)[:2]:
        mistakes.append((u, f"{u} × {v} = {A:,}, but those sides are {v - u} feet apart, not {k}."))
    return Problem(
        help="area",
        story=story,
        expr=f"w(w + {k}) = {A:,}",
        ask="What is the width w, in feet?",
        choices=_numeric_choices(ctx, w, mistakes, allow_neg=True),
        solution=(
            f"Expand: w{sup(2)} + {k}w − {A:,} = 0.",
            f"Factor: (w + {w + k})(w − {w}) = 0, since {w + k} × {w} = {A:,} and {w + k} − {w} = {k}.",
            f"A width can't be −{w + k}, so w = {w} feet. (Length is {w + k}.)",
        ),
        hint=f"You need two numbers {k} apart that multiply to {A:,}. The smaller one is the width. Testing the answer choices works too.",
    )


@gen("quad", 2)
def expand_binomials(ctx: Context) -> Problem:
    """Multiply (x + a)(x + b) (FOIL)."""
    while True:
        a = ctx.rand(-9, 9)
        b = ctx.rand(-9, 9)
        if not (a == 0 or b == 0 or a + b == 0 or a == b):
            break
    ans = _trinomial(a + b, a * b)
    wrong = [
        (_trinomial(a + b, a + b), f"You added for the last term too. The last term is {_lead(a)} × {_par(b)}."),
        (_trinomial(a * b, a + b), "You swapped them: the sum goes with x, and the product is the last term."),
        (_trinomial(a * b, a * b), "You multiplied for the middle term too. The Outer and Inner terms add up to the middle term."),
        (_trinomial(a + b, -a * b), f"Check the sign of the last term: multiply {_lead(a)} by {_par(b)}."),
        (_trinomial(-(a + b), a * b), f"Check the sign of the middle term: add {_lead(a)} and {_par(b)}."),
        (_trinomial(a - b, a * b), f"You subtracted for the middle term. The Outer and Inner terms add: ({_lead(b)})x + ({_lead(a)})x."),
        (_trinomial(b - a, a * b), f"You subtracted for the middle term. The Outer and Inner terms add: ({_lead(b)})x + ({_lead(a)})x."),
        (_trinomial(0, a * b), "You left out the Outer and Inner terms. They make the middle x term."),
    ]
    story = ctx.pick([
        "The chart room needs the product expanded to plot a curve on the plotting board.",
        "The deck's dimensions are written as two binomials. Multiply them out to get the area expression.",
        "Expand the product to feed it into the fire-control table.",
    ])
    return Problem(
        help="expand",
        story=story,
        expr=_factor_form(a, b),
        ask="Which is the expanded form?",
        choices=_string_choices(ctx, ans, wrong),
        solution=(
            f"First: x · x = x{sup(2)}.",
            f"Outer + Inner: ({_lead(b)})x + ({_lead(a)})x = {_lead(a + b)}x.",
            f"Last: ({_lead(a)})({_lead(b)}) = {_lead(a * b)}.",
            f"Result: {ans}.",
        ),
        hint=f"FOIL: the middle term is ({_lead(a)} + {_par(b)})x and the last term is {_lead(a)} × {_lead(b)}.",
    )


# ---------------- Powers & roots ----------------


@gen("exp", 1)
def pythagorean_hypotenuse(ctx: Context) -> Problem:
    """a² + b² = c²: find the hypotenuse."""
    trip = ctx.pick(_TRIPLES)
    a, b, c = trip if ctx.rand(0, 1) else [trip[1], trip[0], trip[2]]
    sc = ctx.pick([
        dict(story=f"Radar shows a contact {a} nautical miles east and {b} nautical miles north of your position.", ask="What is the straight-line range to the contact, in nautical miles?", unit="nm"),
        dict(story=f"A rescue helicopter flies {a} nautical miles east, then {b} nautical miles north to reach a life raft.", ask="How far is the raft from the ship in a straight line, in nautical miles?", unit="nm"),
        dict(story=f"A guy wire runs from a point {a} feet up the mast to a deck cleat {b} feet from the base of the mast.", ask="How long is the wire, in feet?", unit="ft"),
        dict(story=f"A gangway rests against the pier: its foot is {a} feet from the pier wall and its top is {b} feet up the wall.", ask="How long is the gangway, in feet?", unit="ft"),
    ])
    lo, hi = min(a, b), max(a, b)
    mistakes = [
        (a + b, f"You added {a} and {b}. Square them first, add the squares, then take the square root."),
        (c * c, f"{c * c} is c{sup(2)}. Take its square root to get c."),
        (c * c / 2, f"A square root isn't half. Find the number that times itself makes {c * c}."),
        (hi - lo, f"You subtracted {lo} from {hi}. For the longest side, square both and add them."),
        (_whole(math.sqrt(hi * hi - lo * lo)), "You subtracted the squares, which finds a shorter side. For the longest side, add them."),
        (_whole(math.sqrt(a + b)), f"You took the square root of {a} + {b}. Square each side first, then add."),
    ]
    return Problem(
        help="pyth",
        story=sc["story"],
        expr=f"{a}{sup(2)} + {b}{sup(2)} = c{sup(2)}",
        ask=sc["ask"],
        choices=_numeric_choices(ctx, c, mistakes),
        solution=(f"{a}{sup(2)} + {b}{sup(2)} = {a * a} + {b * b} = {c * c}.", f"c = √{c * c} = {c} {sc['unit']}."),
        hint=f"Square both legs ({a}² and {b}²), add them, then take the square root.",
    )


@gen("exp", 1)
def decay_growth(ctx: Context) -> Problem:
    """A sonar ping halving with distance, or a relay chain growing as a power."""
    if ctx.rand(0, 1):
        step = ctx.pick([200, 250, 500, 1000])
        n = ctx.rand(2, 5)
        S0 = ctx.pick([320, 640, 800, 960, 1600, 3200])
        if S0 % 2**n:  # not a whole number: try again
            return decay_growth(ctx)
        S = S0 // 2**n
        dist = step * n
        mistakes = [
            (_whole(S0 / (2 * n)), f"Halving {n} times isn't dividing by 2 × {n}. Halve, then halve again: {n} halvings in all."),
            (S * 2, f"That's one halving too few: {dist:,} ÷ {step:,} = {n} halvings."),
            (S0 // 2, f"That's after only one halving. There are {dist:,} ÷ {step:,} = {n} of them."),
            (_whole(S0 / n), f"You divided by {n}. Each step halves it, so divide by 2, {n} times."),
            (S0 * 2**n, "It gets weaker, so halve it each time instead of doubling."),
            (n, f"{n} is how many halvings there are. Now halve {S0:,} that many times."),
        ]
        if S % 2 == 0:
            mistakes.append((S // 2, f"That's one halving too many: {dist:,} ÷ {step:,} = {n} halvings."))
        return Problem(
            help="decay",
            story=f"A sonar ping leaves the ship at {S0:,} units of strength and loses half its strength every {step:,} meters.",
            expr=f"{S0:,} × (½){sup('n')},   n = {step * n:,} ÷ {step:,}",
            ask=f"How strong is the ping at {step * n:,} meters?",
            choices=_numeric_choices(ctx, S, mistakes),
            solution=(
                f"Number of halvings: {step * n:,} ÷ {step:,} = {n}.",
                f"Halve {n} times: {S0:,} ÷ 2{sup(n)} = {S0:,} ÷ {2**n}.",
                f"Strength = {S}.",
            ),
            hint=f"Count the halvings first: {step * n:,} ÷ {step:,}. Then divide by 2 that many times.",
        )
    base = ctx.pick([2, 3])
    n = ctx.rand(3, 6)
    N = base**n
    everyone = sum(base**i for i in range(1, n + 1))
    mistakes = [
        (base * n, f"{base}{sup(n)} isn't {base} × {n}. Multiply {n} {base}s together."),
        (base ** (n - 1), f"That's {base}{sup(n - 1)}: one {base} too few. Each of the {n} rounds multiplies by {base}."),
        (base ** (n + 1), f"That's {base}{sup(n + 1)}: one {base} too many. Each of the {n} rounds multiplies by {base}."),
        (n**base, f"You swapped the base and the exponent: that's {n}{sup(base)}."),
        (everyone, f"That's everyone who heard it in all {n} rounds. The question asks only about the last round."),
        (base + n, f"You added {base} and {n}. The exponent says multiply {n} {base}s together."),
    ]
    return Problem(
        help="power",
        story=f"A distress call is relayed: every ship that hears it passes it to {base} new ships. After {n} relay rounds, how many ships hear it in that final round?",
        expr=f"{base}{sup(n)}",
        ask="Evaluate the power.",
        choices=_numeric_choices(ctx, N, mistakes),
        solution=(
            f"{base}{sup(n)} means {' × '.join([str(base)] * n)}.",
            f"Multiply step by step: {' → '.join(str(base ** (i + 1)) for i in range(n))}.",
            f"{N} ships. (Not {base} × {n} = {base * n}!)",
        ),
        hint=f"{base}{sup(n)} is {base} multiplied by itself {n} times — not {base} × {n}.",
    )


@gen("exp", 1)
def exponent_rules(ctx: Context) -> Problem:
    """Product, quotient and power-of-a-power rules."""
    mode = ctx.rand(0, 2)
    a = ctx.rand(2, 7)
    b = ctx.rand(2, 6)

    def x(n: int) -> str:
        return "x" + sup(n)

    if mode == 0:
        story = ctx.pick([
            "The plotting board uses shorthand for repeated multiplication. Simplify the expression.",
            "The radar power equation has two factors with the same base. Simplify.",
            "The code book multiplies two powers of x. Write it as a single power.",
        ])
        wrong = [
            (x(a * b), "You multiplied the exponents; that's the rule for a power of a power. Multiplying adds them."),
            (x(abs(a - b)), "You subtracted the exponents; that's the rule for dividing. Multiplying adds them."),
            (f"{a + b}x", f"You added the exponents but wrote {a + b} times x. The {a + b} goes up top, as the power."),
            ("2" + x(a + b), f"Multiplying x's doesn't make a 2 in front: x · x is x{sup(2)}, not 2x."),
        ]
        return Problem(
            help="exprule",
            story=story,
            expr=f"{x(a)} · {x(b)}",
            ask="Which is the simplified form?",
            choices=_string_choices(ctx, x(a + b), [w for w in wrong if w[0] != x(a + b)]),
            solution=(f"{x(a)} is {a} x's multiplied; {x(b)} is {b} more.", f"All together: {a} + {b} = {a + b} x's → {x(a + b)}."),
            hint="Same base, multiplied → add the exponents.",
        )
    if mode == 1:
        hi = a + b
        story = ctx.pick([
            "The plotting board uses shorthand for repeated multiplication. Simplify the expression.",
            "A signal-strength ratio divides two powers of x. Simplify.",
            "The engineer cancels matching factors in a fraction of powers. What is left?",
        ])
        wrong = [
            (x(hi + b), "You added the exponents; that's the rule for multiplying. Dividing subtracts them."),
            (x(hi * b), "You multiplied the exponents. Dividing same bases subtracts them."),
            (x(b - hi), f"You subtracted the wrong way round. Take {b} away from {hi}."),
            (f"{a}x", f"You subtracted the exponents but wrote {a} times x. The {a} goes up top, as the power."),
        ]
        if hi % b == 0:
            wrong.append((x(hi // b), "You divided the exponents. Dividing same bases subtracts them."))
        return Problem(
            help="exprule",
            story=story,
            expr=f"{x(hi)} ÷ {x(b)}",
            ask="Which is the simplified form?",
            choices=_string_choices(ctx, x(a), [w for w in wrong if w[0] != x(a)]),
            solution=(f"Dividing removes {b} of the {hi} x's.", f"{hi} − {b} = {a} → {x(a)}."),
            hint="Same base, divided → subtract the exponents.",
        )
    if a == b == 2:  # (x²)²: adding or powering the exponents gives the right answer by luck
        b = ctx.rand(3, 6)
    story = ctx.pick([
        "The plotting board uses shorthand for repeated multiplication. Simplify the expression.",
        "A power is raised to another power in the reactor formula. Simplify.",
        "The code book raises a power of x to another power. Write it as a single power.",
    ])
    wrong = [
        (x(a + b), "You added the exponents; that's the rule for multiplying. A power of a power multiplies them."),
        (f"{b}{x(a)}", f"You multiplied by {b}. Raising to the power {b} means {b} copies of {x(a)} multiplied together."),
        (f"{a * b}x", f"You multiplied the exponents but wrote {a * b} times x. The {a * b} goes up top, as the power."),
    ]
    if a**b < 1000:
        wrong.append((x(a**b), f"You worked out {a}{sup(b)}. For a power of a power, just multiply {a} × {b}."))
    return Problem(
        help="exprule",
        story=story,
        expr=f"({x(a)}){sup(b)}",
        ask="Which is the simplified form?",
        choices=_string_choices(ctx, x(a * b), [w for w in wrong if w[0] != x(a * b)]),
        solution=(f"({x(a)}){sup(b)} means {x(a)} multiplied {b} times.", f"Each copy has {a} x's, so {a} × {b} = {a * b} → {x(a * b)}."),
        hint="A power of a power → multiply the exponents.",
    )


def _root_value(k: int, m: int) -> float:
    return k * math.sqrt(m)


def _root_text(k: int, m: int) -> str:
    """k√m, leaving out a coefficient of 1."""
    return f"{k if k != 1 else ''}√{m}"


@gen("exp", 2)
def simplify_radical(ctx: Context) -> Problem:
    """√(k²m) = k√m."""
    k = ctx.pick([2, 3, 4, 5, 6])
    m = ctx.pick([2, 3, 5, 6, 7, 10])
    N = k * k * m
    ans = f"{k}√{m}"
    story = ctx.pick([
        "A bearing calculation leaves the navigator with a square root. Simplify it before plotting.",
        "The range formula produced a square root that isn't in simplest form. Simplify it.",
        "A diagonal brace measurement came out as a square root. Simplify it for the shipwright.",
    ])
    kk = k * k
    wrong = [
        (m, k, "You swapped the numbers. The square root of the perfect square goes in front."),
        (kk, m, f"√{kk} is {k}, not {kk}. Take the square root as it comes out."),
        (k, k * m, f"When {k} × {k} comes out from under the √, it comes out as one {k}. No {k} stays inside."),
        (2 * k, m, f"√{kk} is {k}, not {2 * k}. A square root undoes squaring, not doubling."),
        (1, m, f"The {k} that came out of the root is missing. Write it in front."),
    ]
    if k % 2 == 0 and kk // 2 != 2 * k:
        wrong.append((kk // 2, m, f"A square root isn't half: √{kk} is {k}, because {k} × {k} = {kk}."))
    if k != m:
        wrong.append((1, k * m, f"√{kk} is {k}, and it comes out in front of the √. It doesn't stay inside."))
    return Problem(
        help="radical",
        story=story,
        expr=f"√{N}",
        ask="Which is the simplified form?",
        choices=_string_choices(
            ctx, ans, [(_root_text(c, r), why, _root_value(c, r)) for c, r, why in wrong if (c, r) != (k, m)], _root_value(k, m)
        ),
        solution=(f"Find the biggest perfect square inside {N}: {N} = {k * k} × {m}.", f"√{N} = √{k * k} · √{m} = {ans}."),
        hint=f"Which perfect square (4, 9, 16, 25, 36…) divides {N}? Its root goes out front.",
    )


# ---------------- More linear ----------------


@gen("lin", 2)
def head_on_meeting(ctx: Context) -> Problem:
    """Two ships steaming toward each other: s1·t + s2·t = D."""
    A, B = _fleet_pair(ctx)
    s1, s2 = A.speed, B.speed
    t = ctx.rand(2, 6)
    D = (s1 + s2) * t
    if A.cls == B.cls:
        story = f"{A.name} and {B.name}, two {A.cls}s, are {D} nautical miles apart and steaming straight toward each other at {s1} knots each."
    else:
        story = ctx.pick([
            f"{A.name} and {B.name} are {D} nautical miles apart and steaming straight toward each other — the {A.cls} at {s1} knots, the {B.cls} at {s2} knots.",
            f"{A.name} ({s1} knots) and {B.name} ({s2} knots) start {D} nautical miles apart and head directly for each other to rendezvous.",
        ])
    close = s1 + s2
    mistakes = [
        (_whole(D / s1), f"You divided by one ship's speed. Heading toward each other, they close at {s1} + {s2} = {close} knots."),
        (_whole(D / s2), f"You divided by one ship's speed. Heading toward each other, they close at {s1} + {s2} = {close} knots."),
        (D - s1 - s2, f"You took the speeds away from {D}. Divide the {D} nautical miles by the closing speed instead."),
        (close, f"{close} knots is how fast the gap closes. Divide the {D} nautical miles by it."),
        (t / 2, f"You split the {D} nautical miles in half and also added the speeds. Adding the speeds already counts both ships."),
        (t - 1, f"Check: in {t - 1} hour{'s' if t > 2 else ''} they close {close} × {t - 1} = {close * (t - 1)} nautical miles, short of {D}."),
        (t + 1, f"Check: in {t + 1} hours they close {close} × {t + 1} = {close * (t + 1)} nautical miles, more than {D}."),
    ]
    if s1 != s2:
        mistakes += [
            (_whole(D / abs(s1 - s2)), "You subtracted the speeds. Heading toward each other, their speeds add."),
            (_whole(D / (2 * max(s1, s2))), f"You gave each ship half of the {D} nautical miles, but the faster one covers more."),
            (_whole(D / (2 * min(s1, s2))), f"You gave each ship half of the {D} nautical miles, but the faster one covers more."),
        ]
    return Problem(
        help="meet",
        story=story,
        expr=f"{s1}t + {s2}t = {D}",
        ask="How many hours until they meet?",
        choices=_numeric_choices(ctx, t, mistakes),
        solution=(
            f"Closing speed: {s1} + {s2} = {s1 + s2} knots.",
            f"{s1 + s2}t = {D} → t = {D} ÷ {s1 + s2} = {t} hours.",
            f"Check: {s1 * t} + {s2 * t} = {D} ✓",
        ),
        hint="They close the gap at their combined speed. Add the speeds, then divide the distance by that.",
    )


@gen("lin", 2)
def consecutive_integers(ctx: Context) -> Problem:
    """Three consecutive (or consecutive even/odd) numbers with a given sum."""
    x = ctx.rand(20, 120)
    kind = ctx.pick(["plain", "plain", "even"])
    step = 2 if kind == "even" else 1
    S = 3 * x + 3 * step
    label = ("even" if x % 2 == 0 else "odd") if kind == "even" else "consecutive"
    desc = "consecutive" if label == "consecutive" else f"consecutive {label}"
    xs = [x, x + step, x + 2 * step]
    story = ctx.pick([
        f"Three ships moored in a row have {desc} hull numbers that add up to {S}.",
        f"Three {desc} berth numbers on the pier add up to {S}.",
        f"A sailor's three locker numbers are {desc} integers with a sum of {S}.",
    ])
    s3 = 3 * step
    mistakes = [
        (x + step, f"{x + step} is the middle number. The question asks for the smallest."),
        (x + 2 * step, f"{x + 2 * step} is the largest of the three. The question asks for the smallest."),
        (3 * x, f"{S} − {s3} = {3 * x} is 3x, all three x's together. Divide by 3."),
        (_whole(3 * x / 2), "There are three x's, so divide by 3, not 2."),
        (x - 2 * step, f"You divided {S} by 3 first and then took away {s3}. Take away {s3} first, then divide."),
        (_whole((S - step) / 3), f"You took away only {step}. The plain numbers add up to {step} + {2 * step} = {s3}."),
    ]
    mistakes.append((x - step, f"Check: {x - step} + {x} + {x + step} = {3 * x}, not {S}."))
    if step == 1:
        mistakes.append((x - 1, "Consecutive numbers go up by 1, not 2: x, x + 1, x + 2."))
    else:
        mistakes.append((x + 1, f"Consecutive {label} numbers go up by 2, not 1: x, x + 2, x + 4."))
    return Problem(
        help="consec",
        story=story,
        expr=f"x + (x + {step}) + (x + {2 * step}) = {S}",
        ask="What is the smallest of the three numbers?",
        choices=_numeric_choices(ctx, x, mistakes),
        solution=(
            f"Combine: 3x + {3 * step} = {S}.",
            f"Subtract {3 * step}: 3x = {S - 3 * step}.",
            f"Divide by 3: x = {x}. The numbers are {', '.join(map(str, xs))}.",
        ),
        hint=f"Add the three x's together and the three plain numbers together first: 3x + {3 * step} = {S}.",
    )


@gen("lin", 2)
def perimeter(ctx: Context) -> Problem:
    """Rectangle perimeter with the length given in terms of the width."""
    w = ctx.rand(8, 40)
    mode = ctx.rand(0, 1)
    k = ctx.pick([4, 6, 8, 10, 12, 15, 20])
    L = w + k if mode else 2 * w
    P = 2 * L + 2 * w
    desc = f"{k} feet longer than it is wide" if mode else "twice as long as it is wide"
    story = ctx.pick([
        f"A rectangular helipad is {desc}. A safety rope around its edge is {P} feet long.",
        f"The hangar deck is {desc}, and the painted boundary line around it measures {P} feet.",
        f"A rectangular life-raft is {desc}; the grab line around its perimeter is {P} feet.",
    ])
    if mode:
        solution = (f"Distribute: 2w + {2 * k} + 2w = {P}.", f"Combine: 4w + {2 * k} = {P} → 4w = {P - 2 * k}.", f"w = {w} feet (length {L}).")
        mistakes = [
            (L, f"{L} feet is the length. The question asks for the width, w."),
            (_whole(P / 4), f"{P} ÷ 4 would be the side of a square. Take away the extra 2 × {k} = {2 * k} feet first."),
            (P // 2, f"{P} ÷ 2 = {P // 2} is one length and one width together."),
            (_whole((P - k) / 4), f"You multiplied only the w by 2. 2(w + {k}) is 2w + {2 * k}, not 2w + {k}."),
            (P // 2 - k, f"You counted only two w's. 2(w + {k}) + 2w has four w's, so divide by 4."),
            (P - 2 * k, f"{P - 2 * k} is 4w. Divide by 4 to get w."),
            (_whole(P / 4 - 2 * k), f"You divided {P} by 4 and then took away {2 * k}. Take away {2 * k} first, then divide."),
            (k, f"{k} feet is how much longer the length is, not the width."),
            (_whole(P / 6), f"The length is {k} feet more than the width, not twice the width."),
        ]
    else:
        solution = (f"Simplify: 4w + 2w = {P} → 6w = {P}.", f"w = {w} feet (length {L}).")
        mistakes = [
            (L, f"{L} feet is the length. The question asks for the width, w."),
            (_whole(P / 4), f"{P} ÷ 4 would be the side of a square, but the length is twice the width."),
            (P // 2, f"{P} ÷ 2 = {P // 2} is one length and one width together."),
            (_whole(P / 12), f"You halved it again. 6w = {P}, so dividing by 6 already gives the width."),
            (_whole((P - 2) / 4), "2(2w) means 2 × 2w = 4w, not 2 + 2w."),
            (P - 6, "You subtracted 6 instead of dividing by 6: 6w means 6 times w."),
            (_whole(P / 8), "You multiplied all the 2s together. 2(2w) + 2w is 4w + 2w = 6w."),
        ]
    return Problem(
        help="perim",
        story=story,
        expr=f"2(w + {k}) + 2w = {P}" if mode else f"2(2w) + 2w = {P}",
        ask="What is the width w, in feet?",
        choices=_numeric_choices(ctx, w, mistakes),
        solution=solution,
        hint="Perimeter = 2(length) + 2(width). Write the length using w, then combine the w terms.",
    )


def _undo_times(x: str, y: str, z: str) -> list[tuple[str, str]]:
    """Mistakes solving y = x·z (or y = z·x) for x: the answer is x = y ÷ z."""
    return [
        (f"{x} = {z} ÷ {y}", f"You divided the wrong way round. {x} is multiplied by {z}, so divide {y} by {z}."),
        (f"{x} = {y} × {z}", f"You multiplied by {z}. To undo times {z}, divide by {z}."),
        (f"{x} = {y} − {z}", f"{x} is multiplied by {z}, not added to it. To undo times {z}, divide by {z}."),
        (f"{x} = {y} + {z}", f"You added {z}. {x} is multiplied by {z}, so divide by {z}."),
        (f"{x} = {z} − {y}", f"{x} is multiplied by {z}. Divide {y} by {z}; subtracting doesn't undo it."),
    ]


_LITERAL = [
    dict(eq="d = rt", want="t", ans="t = d ÷ r", story="Distance equals rate times time. The navigator wants the formula rearranged to find time.",
         wrong=_undo_times("t", "d", "r")),
    dict(eq="d = rt", want="r", ans="r = d ÷ t", story="Distance equals rate times time. Rearrange it to find the rate.",
         wrong=_undo_times("r", "d", "t")),
    dict(eq="P = 2L + 2W", want="W", ans="W = (P − 2L) ÷ 2", story="The deck perimeter formula. The shipwright needs it solved for the width.", wrong=[
        ("W = P − 2L", "You took away 2L but stopped there. That leaves 2W, so divide by 2."),
        ("W = (P + 2L) ÷ 2", "You added 2L. To undo + 2L, take 2L away from both sides."),
        ("W = P ÷ 2 − 2L", "You divided only P by 2. Take away 2L first, then divide all of P − 2L by 2."),
        ("W = (P − L) ÷ 2", "The formula has 2L, not L. Take away 2L."),
        ("W = (P − 2L) × 2", "You multiplied by 2. To undo 2 times W, divide by 2."),
        ("W = (2L − P) ÷ 2", "You subtracted the wrong way round. It's P minus 2L."),
        ("W = P − 2L ÷ 2", "Only the 2L got divided by 2. Put brackets round P − 2L so all of it is divided."),
    ]),
    dict(eq="A = LW", want="L", ans="L = A ÷ W", story="Area of the cargo hold. Solve the formula for the length.",
         wrong=_undo_times("L", "A", "W")),
    dict(eq="F = ma", want="a", ans="a = F ÷ m", story="Newton's law aboard the catapult team. Solve for acceleration.",
         wrong=_undo_times("a", "F", "m")),
    dict(eq="v = d ÷ t", want="d", ans="d = v × t", story="Speed equals distance over time. Solve for distance.", wrong=[
        ("d = v ÷ t", "d is divided by t. To undo that, multiply by t; don't divide again."),
        ("d = t ÷ v", "To undo ÷ t, multiply both sides by t."),
        ("d = v + t", "d is divided by t, not added to. To undo ÷ t, multiply by t."),
        ("d = v − t", "Taking away t doesn't undo ÷ t. Multiply both sides by t."),
        ("d = t − v", "Taking away doesn't undo ÷ t. Multiply both sides by t."),
    ]),
    dict(eq="C = 2πr", want="r", ans="r = C ÷ (2π)", story="The circumference of a gun turret ring. Solve for the radius.", wrong=[
        ("r = C × (2π)", "You multiplied by 2π. To undo times 2π, divide by 2π."),
        ("r = C − 2π", "r is multiplied by 2π, not added to it. Divide by 2π."),
        ("r = (2π) ÷ C", "You divided the wrong way round. Divide C by 2π."),
        ("r = C ÷ π", "You divided by π but forgot the 2. r is multiplied by 2π."),
        ("r = C ÷ 2", "You divided by 2 but forgot the π. r is multiplied by 2π."),
        ("r = (C − 2) ÷ π", "You took away the 2 instead of dividing by it: 2πr means 2 times π times r."),
    ]),
    dict(eq="y = mx + b", want="x", ans="x = (y − b) ÷ m", story="The fuel-line equation. Solve it for x.", wrong=[
        ("x = (y + b) ÷ m", "You added b. To undo + b, take b away from both sides."),
        ("x = y ÷ m − b", "You divided first. Take away b first, then divide all of y − b by m."),
        ("x = (y − b) × m", "You multiplied by m. To undo times m, divide by m."),
        ("x = y − b", "You took away b but stopped there. That leaves mx, so divide by m."),
        ("x = y − b ÷ m", "Only b got divided by m. Put brackets round y − b so all of it is divided."),
        ("x = (b − y) ÷ m", "You subtracted the wrong way round. It's y minus b."),
        ("x = (y − m) ÷ b", "You mixed up m and b. b is added on; m is what x is multiplied by."),
    ]),
]


@gen("lin", 2)
def literal_equation(ctx: Context) -> Problem:
    """Rearrange a formula for one of its letters."""
    F = ctx.pick(_LITERAL)
    want = F["want"]
    return Problem(
        help="literal",
        story=F["story"],
        expr=F["eq"],
        ask=f"Solve for {want}.",
        choices=_string_choices(ctx, F["ans"], F["wrong"]),
        solution=(f"Look at what is done to {want} and undo it on both sides.", f"Result: {F['ans']}."),
        hint=f"Treat the other letters like numbers. Is {want} being multiplied? Divide. Is something added? Subtract it first.",
    )


@gen("lin", 2)
def proportion_chart_scale(ctx: Context) -> Problem:
    """Chart scale or a steady rate, solved as a proportion."""
    per = ctx.pick([2, 3, 4, 5])
    nm = per * ctx.pick([4, 5, 6, 8, 10])
    cm2 = ctx.rand(3, 12)
    ans = nm // per * cm2
    mode = ctx.rand(0, 1)
    if mode == 0:
        story = ctx.pick([
            f"On the chart, {per} cm represents {nm} nautical miles. The navigator measures {cm2} cm between two buoys.",
            f"The plotting scale is {per} cm = {nm} nm. Two contacts are {cm2} cm apart on the plot.",
        ])
        j = nm // per
        mistakes = [
            (nm * cm2, f"You cross-multiplied to {nm} × {cm2} = {nm * cm2} but forgot to divide by {per}."),
            (per * cm2 / nm, f"You set the proportion up upside down. Keep cm over nm on both sides: {per} ⁄ {nm} = {cm2} ⁄ x."),
            (j, f"{j} nautical miles is what 1 cm stands for. Multiply by the {cm2} cm."),
            (nm + cm2 - per, f"You added {cm2} − {per} to {nm}, but a scale multiplies: every cm is worth the same distance."),
            (_whole(nm * per / cm2), f"You cross-multiplied the wrong pair. Cross-multiply {per} × x = {nm} × {cm2}."),
            (per * cm2, f"You multiplied the {cm2} cm by {per}. Each cm stands for {nm} ÷ {per} nautical miles, so use that."),
        ]
        return Problem(
            help="prop",
            story=story,
            expr=f"{per} ⁄ {nm} = {cm2} ⁄ x",
            ask="What is the real distance x, in nautical miles?",
            choices=_numeric_choices(ctx, ans, mistakes),
            solution=(f"Cross-multiply: {per}x = {nm} × {cm2} = {nm * cm2}.", f"x = {nm * cm2} ÷ {per} = {ans} nm."),
            hint="Set up paper ÷ real = paper ÷ real, then cross-multiply.",
        )
    rate = ctx.pick([3, 4, 5, 6, 8])
    mins = ctx.pick([10, 15, 20, 30])
    hrs = ctx.rand(2, 5)
    blocks = hrs * 60 // mins
    total = rate * blocks
    story = ctx.pick([
        f"A dockside crane lifts {rate} crates every {mins} minutes.",
        f"The mess line serves {rate} sailors every {mins} minutes.",
        f"A pump moves {rate} barrels every {mins} minutes.",
    ])
    per_hour = rate * 60 // mins
    mistakes = [
        (rate * hrs, f"You multiplied by {hrs} hours, but {rate} is for every {mins} minutes, not every hour."),
        (rate * hrs * 60, f"You turned {hrs} hours into {hrs * 60} minutes but forgot that {rate} is for every {mins} minutes. Divide by {mins} too."),
        (per_hour, f"{per_hour} is how many in one hour. Multiply by the {hrs} hours."),
        (blocks, f"{blocks} is how many {mins}-minute blocks there are. Multiply by {rate}."),
        (_whole(mins * hrs * 60 / rate), f"You flipped the rate. It's {rate} every {mins} minutes, not {mins} every {rate}."),
        (rate + hrs * 60 - mins, f"You added the extra {hrs * 60 - mins} minutes to {rate}. A rate multiplies: {rate} for every {mins} minutes."),
    ]
    return Problem(
        help="prop",
        story=story,
        expr=f"{rate} ⁄ {mins} = x ⁄ {hrs * 60}",
        ask=f"How many in {hrs} hours ({hrs * 60} minutes)?",
        choices=_numeric_choices(ctx, total, mistakes),
        solution=(f"{hrs} hours = {hrs * 60} minutes, which is {blocks} blocks of {mins} minutes.", f"{rate} × {blocks} = {total}."),
        hint=f"Convert hours to minutes, then figure out how many {mins}-minute chunks that is.",
    )


@gen("lin", 1)
def linear_model(ctx: Context) -> Problem:
    """Write y = start ± rate·t from a story."""
    F = ctx.pick([300, 400, 500, 600, 800])
    r = ctx.pick([15, 20, 25, 30, 40])
    up = ctx.rand(0, 1)
    if up:
        ans = f"y = {F} + {r}t"
        story, unit = ctx.pick([
            (f"A drydock starts with {F} gallons of water and pumps IN {r} gallons per minute.", "minute"),
            (f"The ship's store starts the cruise with {F} candy bars and receives {r} more each day from resupply.", "day"),
        ])
        wrong = [
            (f"y = {F} − {r}t", f"The amount goes up, so add the {r} each {unit}."),
            (f"y = {r} + {F}t", f"You swapped the numbers. {F} is the start, and the {r} each {unit} goes with t."),
            (f"y = {F}t + {r}", f"You put the t on {F}. The start doesn't grow with time; the {r} each {unit} does."),
            (f"y = {r}t", f"You left out the start. At t = 0 there are already {F}."),
            (f"y = {F + r}t", f"You added {F} + {r} and put t on it. Only the {r} each {unit} goes with t; the {F} is there from the start."),
            (f"y = {F} + {r}", f"You left out the t. The {r} is added every {unit}, so it's {r}t."),
        ]
    else:
        ans = f"y = {F} − {r}t"
        story, unit = ctx.pick([
            (f"A fuel tank starts with {F} gallons and the engines burn {r} gallons per hour.", "hour"),
            (f"The magazine holds {F} rounds and the gun fires {r} rounds per minute during the exercise.", "minute"),
        ])
        wrong = [
            (f"y = {F} + {r}t", f"The amount goes down, so take away the {r} each {unit}."),
            (f"y = {r} − {F}t", f"You swapped the numbers. {F} is the start, and the {r} each {unit} goes with t."),
            (f"y = {F}t − {r}", f"You put the t on {F}. The start doesn't change with time; the {r} each {unit} does."),
            (f"y = {r}t − {F}", f"You subtracted the wrong way round. Start with {F} and take away {r}t."),
            (f"y = {F - r}t", f"You took {r} from {F} and put t on it. Only the {r} each {unit} goes with t; the {F} is there from the start."),
            (f"y = {F} − {r}", f"You left out the t. The {r} comes off every {unit}, so it's {r}t."),
        ]
    sign = "+" if up else "−"
    return Problem(
        help="model",
        story=story,
        expr=f"y = ?   (t in {unit}s)",
        ask="Which equation gives the amount y after t time units?",
        choices=_string_choices(ctx, ans, wrong),
        solution=(f"Starting amount (t = 0): {F} — that's the constant.", f"Change per unit of time: {sign}{r} — that multiplies t.", ans),
        hint="The number that's there at the start is the constant; the per-hour change goes with t. Is the amount going up or down?",
    )


# ---------------- Multi-step linear ----------------


@gen("lin", 3)
def distribute_both_sides(ctx: Context) -> Problem:
    """a(x + p) = cx + r: distribute, gather the x terms on one side, then solve."""
    while True:
        a, c = ctx.rand(2, 9), ctx.rand(1, 9)
        x, p = ctx.rand(-6, 12), ctx.rand(-9, 9)
        if c != a and x and p and a * (x + p) != c * x:
            break
    r = a * (x + p) - c * x
    k, ap = a - c, a * p  # x's coefficient once the x terms are together; the distributed number
    left = f"{a}(x {_sgn(p)})"
    undo, wrong = _undo(ap)
    story = ctx.pick([
        "A coded signal from the flagship comes down to one equation, with x on both sides. Find x.",
        "The fire-control computer balances the equation below to set the fuse. Find x.",
        "The navigator's correction formula leaves x on both sides of the equation. Solve it.",
    ])
    mistakes = [
        (_whole((r - p) / k), f"You multiplied only the x by {a}. {left} is {a}x {_sgn(ap)}: the {_lead(p)} gets multiplied too."),
        (_whole((r + ap) / k), f"To undo the {_sgn(ap)}, {undo} on both sides. You {wrong} instead."),
        (_whole((r - ap) / (a + c)), f"You added the x terms. Take {_coef(c)} away from both sides: {a}x − {_coef(c)} = {_coef(k)}."),
        (_whole((r - ap) / a), f"You divided by {a}, but the {_coef(c)} on the right has to come over first, which leaves {_coef(k)}."),
        (r - ap, f"{_lead(r - ap)} is {_coef(k)}, not x. Divide by {_par(k)}."),
        (-x, f"Check the sign: {_coef(k)} = {_lead(r - ap)}, and {_lead(r - ap)} ÷ {_par(k)} = {_lead(x)}."),
    ]
    for v in (x - 1, x + 1):
        mistakes.append((v, f"Check x = {_lead(v)}: the left side is {_lead(a * (v + p))} and the right side is {_lead(c * v + r)}. They must be equal."))
    return Problem(
        help="distrib",
        story=story,
        expr=f"{left} = {_coef(c)} {_sgn(r)}",
        ask="Solve for x.",
        choices=_numeric_choices(ctx, x, mistakes, allow_neg=True),
        solution=(
            f"Distribute the {a}: {a}x {_sgn(ap)} = {_coef(c)} {_sgn(r)}.",
            f"Take {_coef(c)} away from both sides: {_coef(k)} {_sgn(ap)} = {_lead(r)}.",
            f"{_cap(undo)} on both sides: {_coef(k)} = {_lead(r - ap)}.",
            f"Divide both sides by {_par(k)}: x = {_lead(x)}." if k != 1 else f"So x = {_lead(x)}.",
        ),
        hint=f"Multiply the {a} into both terms in the brackets first. Then gather the x terms on one side and the plain numbers on the other.",
    )


@gen("lin", 3)
def predict_from_readings(ctx: Context) -> Problem:
    """Two log readings give the rate; at what hour does it reach a given level?"""
    m = ctx.pick([5, 6, 8, 10, 12, 15, 20, 25])
    t1, dt, k = ctx.rand(1, 4), ctx.rand(2, 5), ctx.rand(3, 12)
    L = ctx.pick([40, 50, 60, 80, 100, 120, 150, 200])
    t2, T = t1 + dt, t1 + dt + k
    f2 = L + m * k
    f1 = f2 + m * dt
    sc = ctx.pick([
        dict(story=f"The engineering log shows {f1} tons of fuel at hour {t1} and {f2} tons at hour {t2}. She burns fuel at a steady rate, and the reserve line is {L} tons.",
             ask=f"At what hour will the fuel reach the {L}-ton reserve?", unit="tons", what="fuel"),
        dict(story=f"A submarine's battery reads {f1} amp-hours at hour {t1} of the dive and {f2} amp-hours at hour {t2}, draining at a steady rate. She must surface when it is down to {L} amp-hours.",
             ask="At what hour of the dive must she surface?", unit="amp-hours", what="charge"),
        dict(story=f"The freshwater log shows {f1} gallons at hour {t1} and {f2} gallons at hour {t2}, used at a steady rate. The chief starts the evaporators when it is down to {L} gallons.",
             ask=f"At what hour will the water be down to {L} gallons?", unit="gallons", what="water"),
    ])
    unit, what = sc["unit"], sc["what"]
    mistakes = [
        (k, f"{k} hours is how long it takes after hour {t2}. The question asks for the hour on the log: add {t2}."),
        (t1 + k, f"You counted the {k} hours from hour {t1}. They start at hour {t2}, when it read {f2}."),
        (dt + k, f"{dt + k} hours is how long it takes after hour {t1}. The question asks for the hour on the log: add {t1}."),
        (_whole(t2 + k / dt), f"{f1} − {f2} = {m * dt} {unit} is the drop over {dt} hours, not one. Divide by {dt} for the rate."),
        (_whole(t2 + f2 / m), f"That's when the {what} would run out completely. It only has to get down to {L} {unit}."),
        (_whole(t2 + L / m), f"You divided the {L} by the rate. Divide what still has to go: {f2} − {L} = {f2 - L} {unit}."),
        (T - 1, f"Check: at hour {T - 1} it still reads {L + m} {unit}."),
        (T + 1, f"Check: by hour {T + 1} it is already down to {L - m} {unit}."),
    ]
    return Problem(
        help="predict",
        story=sc["story"],
        expr=f"({t1}, {f1}) and ({t2}, {f2})\ny = {L} at t = ?",
        ask=sc["ask"],
        choices=_numeric_choices(ctx, T, mistakes),
        solution=(
            f"Rate: ({f2} − {f1}) ÷ ({t2} − {t1}) = −{m * dt} ÷ {dt} = −{m} {unit} an hour.",
            f"From hour {t2} it has {f2} − {L} = {f2 - L} {unit} still to go: {f2 - L} ÷ {m} = {k} hours.",
            f"Hour {t2} + {k} = hour {T}.",
        ),
        hint=f"Find the rate first: change in {what} ÷ change in time. Then work out how long the last {f2} − {L} {unit} take, starting from hour {t2}.",
    )


def _round_trips() -> list[tuple[int, int, int]]:
    """(slower speed, faster speed, average speed for a round trip) where the average is a whole number of knots."""
    out = []
    for s1 in range(6, 41):
        for s2 in range(s1 + 2, min(3 * s1, 60) + 1):
            if 2 * s1 * s2 % (s1 + s2) == 0 and math.lcm(s1, s2) <= 120:
                out.append((s1, s2, 2 * s1 * s2 // (s1 + s2)))
    return out


_ROUND_TRIPS = _round_trips()


@gen("lin", 3)
def round_trip_speed(ctx: Context) -> Problem:
    """Average speed out and back at two speeds: total distance ÷ total time, not the average of the speeds."""
    s1, s2, A = ctx.pick(_ROUND_TRIPS)
    D = math.lcm(s1, s2) * ctx.rand(1, max(1, 240 // math.lcm(s1, s2)))
    t1, t2 = D // s1, D // s2
    ship = _fleet_ship(ctx).name
    out_slow = bool(ctx.rand(0, 1))
    sa, sb = (s1, s2) if out_slow else (s2, s1)
    story = ctx.pick([
        f"{ship} steams {D} nautical miles out to the patrol line at {sa} knots, then {D} nautical miles back at {sb} knots.",
        f"{ship} runs {D} nautical miles to the rendezvous at {sa} knots and returns the same {D} nautical miles at {sb} knots.",
        (f"{ship} tows a damaged barge {D} nautical miles to the repair yard at {s1} knots, then comes back alone at {s2} knots."
         if out_slow else f"{ship} races {D} nautical miles to a rescue at {s2} knots, then escorts the lifeboats back at {s1} knots."),
    ])
    mean = (s1 + s2) / 2
    mistakes = [
        (mean, f"{_num(mean)} knots is halfway between the two speeds, but she spends longer at {s1} knots than at {s2}. Divide the total distance by the total time."),
        (s1 + s2, "You added the two speeds. Average speed is the total distance ÷ the total time."),
        (_whole(D / (t1 + t2)), f"{D} nautical miles is one way. The round trip is {2 * D}: divide that by the {t1 + t2} hours."),
        (t1 + t2, f"{t1 + t2} hours is the total time. Divide the {2 * D} nautical miles by it."),
        (s2 - s1, "You took the difference of the speeds. Average speed is the total distance ÷ the total time."),
        (A - 1, f"Check: {A - 1} knots for {t1 + t2} hours is {(A - 1) * (t1 + t2)} nautical miles, short of the {2 * D}-mile round trip."),
        (A + 1, f"Check: {A + 1} knots for {t1 + t2} hours is {(A + 1) * (t1 + t2)} nautical miles, more than the {2 * D}-mile round trip."),
    ]
    return Problem(
        help="avgspeed",
        story=story,
        expr=f"out: {D} nm at {sa} knots\nback: {D} nm at {sb} knots",
        ask="What is her average speed for the whole round trip, in knots?",
        choices=_numeric_choices(ctx, A, mistakes),
        solution=(
            f"Time out: {D} ÷ {sa} = {D // sa} hours. Time back: {D} ÷ {sb} = {D // sb} hours.",
            f"Round trip: {2 * D} nautical miles in {t1 + t2} hours.",
            f"Average speed: {2 * D} ÷ {t1 + t2} = {A} knots. It's less than {_num(mean)}, the halfway speed, because she spends more of the time at {s1} knots.",
        ),
        hint="Average speed is total distance ÷ total time. Work out each leg's time first; don't just average the two speeds.",
    )


@gen("lin", 3)
def cheaper_after(ctx: Context) -> Problem:
    """A bigger fee and a lower hourly rate: B + bh < A + ah. The fewest whole hours, and equal isn't cheaper."""
    d = ctx.pick([3, 4, 5, 6, 8, 10])  # what the cheaper rate saves each hour
    b = ctx.pick([5, 6, 8, 10, 12, 15])
    a = b + d
    q = ctx.rand(3, 12)
    G = d * q + (0 if ctx.rand(0, 2) == 0 else ctx.rand(1, d - 1))  # the difference in fees
    A0 = ctx.pick([20, 25, 30, 40, 50, 60])
    B0 = A0 + G
    h = q + 1  # the first whole number of hours past G ÷ d (at exactly G ÷ d they cost the same)
    exact = G % d == 0
    sc = ctx.pick([
        dict(story=f"The base motor pool rents out a launch for ${A0} plus ${a} an hour. A harbor company charges ${B0} plus ${b} an hour.", cheap="harbor company", dear="motor pool"),
        dict(story=f"A navy tug costs ${A0} to call out plus ${a} an hour. A civilian tug costs ${B0} to call out plus ${b} an hour.", cheap="civilian tug", dear="navy tug"),
        dict(story=f"The port crane costs ${A0} to book plus ${a} an hour. A floating crane costs ${B0} to book plus ${b} an hour.", cheap="floating crane", dear="port crane"),
    ])
    cheap, dear = sc["cheap"], sc["dear"]

    def costs(n: int) -> str:
        return f"${B0 + b * n} against ${A0 + a * n}"

    mistakes = [
        (q, f"At {q} hours they cost the same: ${B0 + b * q} each. The {cheap} has to cost less, so one more hour." if exact
         else f"You rounded down. At {q} hours the {cheap} still costs more: {costs(q)}."),
        (_whole(G / (a + b)), f"You added the hourly rates. The gap closes by ${a} − ${b} = ${d} each hour."),
        (_whole((A0 + B0) / d), f"You added the two fees. The {cheap} only starts ${B0} − ${A0} = ${G} dearer."),
        (G, f"${G} is how much more the {cheap} costs to start with. Divide it by the ${d} it saves each hour."),
        (_whole(G / b), f"You divided by ${b}, but each hour the {cheap} saves ${a} − ${b} = ${d}."),
        (_whole(G / a), f"You divided by ${a}, but each hour the {cheap} saves ${a} − ${b} = ${d}."),
        (h + 1, f"It already costs less at {h} hours: {costs(h)}."),
    ]
    return Problem(
        help="breakeven",
        story=sc["story"],
        expr=f"{B0} + {b}h < {A0} + {a}h",
        ask=f"What is the fewest whole hours for which the {cheap} costs less?",
        choices=_numeric_choices(ctx, h, mistakes),
        solution=(
            f"Take {b}h from both sides: {B0} < {A0} + {d}h.",
            f"Take {A0} from both sides: {G} < {d}h, so h > {G} ÷ {d}" + (f" = {q}." if exact else f", which is {_fmt(G / d)}."),
            f"At exactly {q} hours they cost the same, so the {cheap} costs less from {h} hours." if exact
            else f"The fewest whole hours more than {_fmt(G / d)} is {h}.",
            f"Check: at {h} hours the {cheap} costs ${B0 + b * h} and the {dear} ${A0 + a * h}.",
        ),
        hint="Get the h terms on one side and the fees on the other. Careful: where they cost the same, neither one is cheaper.",
    )


# ---------------- More systems ----------------


@gen("sys", 3)
def tickets_and_passes(ctx: Context) -> Problem:
    """A count and a money total for two kinds of item."""
    p1 = ctx.pick([5, 6, 8, 10])
    p2 = p1 + ctx.pick([4, 5, 7, 10])
    y = ctx.rand(4, 20)
    x = ctx.rand(5, 25)
    n = x + y
    T = p1 * x + p2 * y
    story = ctx.pick([
        f"The ship's store sold {n} liberty passes: day passes at ${p1} and weekend passes at ${p2}, for a total of ${T}.",
        f"The mess sold {n} tickets for the pier picnic — ${p1} for sailors and ${p2} for guests — collecting ${T}.",
        f"The dive locker rented {n} sets of gear, snorkels at ${p1} and full scuba at ${p2}, taking in ${T}.",
    ])
    gap = p2 - p1
    rest = T - p1 * n
    mistakes = [
        (x, f"{x} is x, the number of ${p1} ones. The question asks for y, the ${p2} kind."),
        (_whole(T / p2), f"You divided all ${T} by ${p2}, but some of that money came from the ${p1} ones."),
        (_whole(T / p1), f"You divided all ${T} by ${p1}, but some of the money came from the ${p2} ones."),
        (rest, f"${T} − ${p1 * n} = ${rest} is {gap}y. Divide by {gap} to get y."),
        (_whole(rest / p2), f"After taking away {p1} × {n} = {p1 * n}, divide by {p2} − {p1} = {gap}, not by {p2}."),
        (_whole(rest / (p1 + p2)), f"A sign slipped: {p1}({n} − y) is {p1 * n} − {p1}y, so the y's give {p2} − {p1} = {gap}y."),
        (_whole(rest / (p2 - 1)), f"You multiplied only the {n} by {p1}. {p1}({n} − y) is {p1 * n} − {p1}y."),
        (_whole(n / 2), f"You split the {n} evenly, but the money total only works with different numbers of each."),
        (_whole(T / (p1 + p2)), "You added the two prices, but each one sold was one price or the other."),
    ]
    return Problem(
        help="tickets",
        story=story,
        expr=f"x + y = {n}\n{p1}x + {p2}y = {T}",
        ask=f"How many of the ${p2} kind (y) were sold?",
        choices=_numeric_choices(ctx, y, mistakes),
        solution=(
            f"From the first equation, x = {n} − y.",
            f"Substitute: {p1}({n} − y) + {p2}y = {T} → {p1 * n} + {p2 - p1}y = {T}.",
            f"{p2 - p1}y = {T - p1 * n} → y = {y}. (And x = {x}.)",
        ),
        hint=f"Replace x with ({n} − y) in the money equation. Then only y is left.",
    )


@gen("sys", 3)
def boat_and_current(ctx: Context) -> Problem:
    """Downstream and upstream legs: find the current."""
    guard = 0
    while True:
        c = ctx.pick([1, 2, 3, 4])
        b = c + ctx.pick([5, 6, 7, 8, 9, 10, 11, 12])
        down, up = b + c, b - c
        d = down * up // math.gcd(down, up)
        t1, t2 = d // down, d // up
        if not (d > 200 or t1 < 2) or guard >= 30:
            break
        guard += 1
    story = ctx.pick([
        f"A patrol boat runs {d} nautical miles WITH the current in {t1} hours, then returns the same {d} miles AGAINST the current in {t2} hours.",
        f"A river gunboat goes {d} miles downstream in {t1} hours and back upstream in {t2} hours.",
        f"A supply launch covers {d} miles with the tide in {t1} hours and the same {d} miles against it in {t2} hours.",
    ])
    mistakes = [
        (b, f"{b} knots is b, the boat's own speed. The question asks for the current, c."),
        (down, f"{down} knots is the speed downstream: boat plus current. The question asks for the current alone."),
        (up, f"{up} knots is the speed upstream: boat minus current. The question asks for the current alone."),
        (2 * c, f"{down} − {up} = {2 * c} is 2c. Divide by 2 to get the current."),
        (t2 - t1, f"{t2} − {t1} is a difference in hours, not in speed. Work out each speed with distance ÷ time first."),
        (-c, "You subtracted the wrong way round, so the current came out negative. Take the upstream speed from the downstream one."),
    ]
    for v in (c - 1, c + 1):
        if v > 0:
            mistakes.append((v, f"Check c = {v}: then b = {down} − {v} = {down - v}, and b − c = {down - 2 * v}, not {up}."))
    return Problem(
        help="current",
        story=story,
        expr=f"b + c = {d} ÷ {t1}\nb − c = {d} ÷ {t2}",
        ask="What is the speed of the current, c, in knots?",
        choices=_numeric_choices(ctx, c, mistakes, allow_neg=True),
        solution=(
            f"Downstream speed: {d} ÷ {t1} = {b + c} knots. Upstream: {d} ÷ {t2} = {b - c} knots.",
            f"b + c = {b + c} and b − c = {b - c}. Subtract: 2c = {2 * c}.",
            f"c = {c} knots (boat speed {b}).",
        ),
        hint="Find each speed with distance ÷ time. Then subtract the two speed equations so b cancels.",
    )


@gen("sys", 2)
def ratio_multiple(ctx: Context) -> Problem:
    """One amount is m times another: x + mx = T."""
    m = ctx.pick([2, 3, 4, 5])
    x = ctx.rand(15, 90) * 2
    T = x + m * x
    big, small = sorted(_fleet_pair(ctx), key=lambda s: -s.crew)
    if big.cls == small.cls:
        crews = f"{big.name} carries {m} times as many sailors as the supply ship alongside her. Together the two ships have {T:,} sailors."
    else:
        crews = f"{big.name} carries {m} times as many sailors as {small.name}. Together the two ships have {T:,} sailors."
    story = ctx.pick([
        crews,
        f"The main magazine holds {m} times as many rounds as the ready locker. Together they hold {T:,} rounds.",
        f"The flight deck has {m} times as many aircraft as the hangar bay; the carrier has {T:,} aircraft in all.",
    ])
    mistakes = [
        (m * x, f"{m * x} is the larger one, {m}x. The question asks for the smaller one, x."),
        (_whole(T / m), f"You divided by {m}, but x + {m}x is {m + 1}x: the lone x counts too."),
        (T // 2, f"You split the {T:,} evenly, but one is {m} times the other."),
        (_whole((T - m) / 2), f"{m} times as many isn't {m} more. The larger one is {m}x, not x + {m}."),
        (T - m, f"You took away {m} instead of dividing. x + {m}x = {m + 1}x."),
        (_whole(math.sqrt(T / (m + 1))), f"x + {m}x is {m + 1}x, not {m + 1}x{sup(2)}. Adding x's doesn't square them."),
        (m, f"{m} is how many times bigger the larger one is, not how many are on the smaller one."),
    ]
    return Problem(
        help="ratio",
        story=story,
        expr=f"x + {m}x = {T:,}",
        ask="How many are on the smaller one (x)?",
        choices=_numeric_choices(ctx, x, mistakes),
        solution=(f"Smaller = x, larger = {m}x. Together: x + {m}x = {m + 1}x.", f"{m + 1}x = {T:,} → x = {x}. The larger is {m * x}."),
        hint=f"Call the smaller one x; the bigger is {m}x. Add them: that's {m + 1}x.",
    )


@gen("sys", 1)
def check_solution(ctx: Context) -> Problem:
    """Which point makes both equations true? Each wrong point works in one equation, or in neither."""
    while True:
        x, y = ctx.rand(-3, 9), ctx.rand(-3, 9)
        if x != y and (x or y):
            break
    S = x + y
    form = ctx.rand(0, 2)
    if form == 0:  # x − y = D
        D = x - y
        second, along = f"x − y = {_lead(D)}", (1, 1)

        def check2(u: int, v: int) -> str:
            return f"{_lead(u)} − {_par(v)} = {_lead(u - v)}" + ("" if u - v == D else f", not {_lead(D)}")
    elif form == 1:  # y = mx + k
        m = ctx.pick([2, 3, -2])
        k = y - m * x
        second, along = _line(m, k), (1, m)

        def check2(u: int, v: int) -> str:
            return f"{_lead(m)}({_lead(u)})" + (f" {_sgn(k)}" if k else "") + f" = {_lead(m * u + k)}" + ("" if m * u + k == v else f", not {_lead(v)}")
    else:  # ax + y = c
        a = ctx.pick([2, 3])
        c = a * x + y
        second, along = f"{a}x + y = {_lead(c)}", (1, -a)

        def check2(u: int, v: int) -> str:
            return f"{a}({_lead(u)}) + {_par(v)} = {_lead(a * u + v)}" + ("" if a * u + v == c else f", not {_lead(c)}")

    def point(u: int, v: int) -> str:
        return f"({_lead(u)}, {_lead(v)})"

    wrong = [(point(y, x), f"Check the order: the point is (x, y), so x = {_lead(y)} and y = {_lead(x)}. Then in the second equation {check2(y, x)}.")]
    for d in ctx.shuffle([-2, -1, 1, 2])[:2]:  # on the first line only
        wrong.append((point(x + d, y - d), f"It works in x + y = {_lead(S)}, but not in the second equation: {check2(x + d, y - d)}."))
    for d in ctx.shuffle([-1, 1])[:2]:  # on the second line only
        u, v = x + d * along[0], y + d * along[1]
        wrong.append((point(u, v), f"It works in the second equation, but not in the first: {_lead(u)} + {_par(v)} = {_lead(u + v)}, not {_lead(S)}."))
    story = ctx.pick([
        "Fire control plots two bearing lines. The target is at the point that lies on both of them.",
        "Two radar operators each report a line the contact is on. It has to be on both lines.",
        "Navigation and sonar each give an equation for the submarine's position. Only one point fits both.",
    ])
    return Problem(
        help="checksol",
        story=story,
        expr=f"x + y = {_lead(S)}\n{second}",
        ask="Which point is a solution of both equations?",
        choices=_string_choices(ctx, point(x, y), wrong),
        solution=(
            f"Try {point(x, y)} in the first equation: {_lead(x)} + {_par(y)} = {_lead(S)} ✓",
            f"And in the second: {check2(x, y)} ✓",
            "It makes both equations true, so it is the solution.",
        ),
        hint="Put each point's x and y into BOTH equations. The solution has to work in both, not just one.",
    )


_SOLUTION_COUNTS = {"none": "No solution", "one": "Exactly one solution", "many": "Infinitely many solutions", "two": "Exactly two solutions"}


@gen("sys", 1)
def count_solutions(ctx: Context) -> Problem:
    """Two lines: parallel (no solution), crossing (one) or the same line (infinitely many)."""
    m = ctx.pick([-3, -2, -1, 2, 3, 4])
    b = ctx.pick([v for v in range(-6, 8) if v])
    case = ctx.pick(["none", "one", "many"])
    if case == "none":
        m2, b2 = m, ctx.pick([v for v in range(-6, 8) if v != b])
    elif case == "one":
        m2 = ctx.pick([v for v in (-3, -2, -1, 1, 2, 3, 4) if v != m])
        b2 = b if ctx.rand(0, 1) else ctx.pick([v for v in range(-6, 8) if v])
    else:
        m2, b2 = m, b
    forms = [f"y = {_lead(b2)} {'−' if m2 < 0 else '+'} {_coef(abs(m2))}" if b2 else _line(m2, b2)]  # y = 3 + 2x
    if case == "many":
        forms.append(f"y {_sgn(-b2)} = {_coef(m2)}")  # y − 3 = 2x
    else:
        forms.append(_line(m2, b2))
    second = ctx.pick(forms)
    same = f"the same line, {_line(m, b)}"
    why = {
        "none": {
            "one": f"Both lines have slope {_lead(m)}: they're parallel, so they never cross.",
            "many": f"Same slope, but they cross the y-axis at {_lead(b)} and {_lead(b2)}: two different parallel lines, which never meet.",
            "two": "Two straight lines can't cross twice. These have the same slope, so they never cross at all.",
        },
        "one": {
            "none": f"The slopes are different ({_lead(m)} and {_lead(m2)}), so the lines aren't parallel: they cross once."
                    + (f" Both cross the y-axis at {_lead(b)}, and that point is the solution." if b == b2 else ""),
            "many": f"The slopes are different ({_lead(m)} and {_lead(m2)}), so these are two different lines, which cross only once."
                    + (f" Sharing the y-intercept {_lead(b)} isn't enough." if b == b2 else ""),
            "two": "Two straight lines can cross only once.",
        },
        "many": {
            "none": f"Write the second one as y = mx + b: it's {same}. Every point on it is a solution.",
            "one": f"Same slope and same y-intercept: it's {same}, so every point on it is a solution.",
            "two": f"It's {same}: if two lines share two points, they share every point.",
        },
    }[case]
    rewritten = "" if second == _line(m2, b2) else f", which is {_line(m2, b2)}"
    verdict = {
        "none": "Same slope, different y-intercepts: the lines are parallel and never meet. No solution.",
        "one": "Different slopes: the lines cross exactly once. One solution.",
        "many": "Same slope and same y-intercept: it's the same line. Every point on it is a solution.",
    }[case]
    story = ctx.pick([
        "Two ships' tracks are plotted as lines on the chart. Do they meet?",
        "Two plotting equations come in from different stations. How many points fit both?",
        "Fire control checks whether two bearing lines cross before working out where.",
    ])
    return Problem(
        help="howmany",
        story=story,
        expr=f"{_line(m, b)}\n{second}",
        ask="How many solutions does the system have?",
        choices=_string_choices(ctx, _SOLUTION_COUNTS[case], [(_SOLUTION_COUNTS[k], w) for k, w in why.items()]),
        solution=(
            f"First line: slope {_lead(m)}, crosses the y-axis at {_lead(b)}.",
            f"Second line{rewritten}: slope {_lead(m2)}, crosses the y-axis at {_lead(b2)}.",
            verdict,
        ),
        hint="Write both in y = mx + b form, then compare the slopes (m) and the y-intercepts (b).",
    )


@gen("sys", 1)
def substitute_known_value(ctx: Context) -> Problem:
    """One equation already gives x (or y): put it into the other and solve."""
    k, a = ctx.rand(2, 9), ctx.rand(2, 6)
    ans = ctx.rand(-4, 15) or 5
    known, unknown = ("x", "y") if ctx.rand(0, 1) else ("y", "x")
    c = a * k + ans
    ak = a * k
    second = f"{a}x + y = {_lead(c)}" if known == "x" else f"x + {a}y = {_lead(c)}"
    story = ctx.pick([
        f"Sonar fixes the contact's {known} straight away. The plot gives a second equation for its position.",
        f"The first equation already tells you {known}. The supply officer needs {unknown} from the second.",
        f"A cipher's first line gives {known} outright. Put it into the second line to find {unknown}.",
    ])
    mistakes = [
        (c - a, f"You took away {a}, but {a}{known} means {a} × {k} = {ak}."),
        (c - k, f"You put in {k} but left out the {a}: {a}{known} is {a} × {k} = {ak}."),
        (c + ak, f"The {ak} is added on the left, so take it away from {_lead(c)}."),
        (ak, f"{ak} is {a}{known}. Take it away from {_lead(c)} to find {unknown}."),
        (k, f"{k} is {known}, which you already knew. The question asks for {unknown}."),
        (-ans, f"You subtracted the wrong way round: {unknown} = {_lead(c)} − {ak}."),
        (_whole(ans / a), f"Only {known} is multiplied by {a}. {unknown} has no number in front, so there's nothing to divide by."),
    ]

    def put_in(rest: str) -> str:  # the second equation's left side with the known value put in
        return f"{a}({k}) + {rest}" if known == "x" else f"{rest} + {a}({k})"

    for v in (ans - 1, ans + 1):
        mistakes.append((v, f"Check {unknown} = {_lead(v)}: {put_in(_par(v))} = {_lead(ak + v)}, not {_lead(c)}."))
    return Problem(
        help="knownvar",
        story=story,
        expr=f"{known} = {k}\n{second}",
        ask=f"What is {unknown}?",
        choices=_numeric_choices(ctx, ans, mistakes, allow_neg=True),
        solution=(
            f"Put {known} = {k} into the second equation: {put_in(unknown)} = {_lead(c)}.",
            f"{a} × {k} = {ak}, so {ak} + {unknown} = {_lead(c)}.",
            f"Take {ak} away from both sides: {unknown} = {_lead(ans)}.",
        ),
        hint=f"Write {k} wherever you see {known} in the second equation. Then only {unknown} is left.",
    )


@gen("sys", 2)
def elimination_add(ctx: Context) -> Problem:
    """ax + by = c and dx − by = e: add the equations so the y's cancel."""
    while True:
        x, y = ctx.rand(1, 9), ctx.rand(-4, 9)
        a1, a2, b = ctx.rand(1, 6), ctx.rand(1, 6), ctx.rand(1, 5)
        if y and a1 != a2:
            break
    c1, c2 = a1 * x + b * y, a2 * x - b * y
    A, C = a1 + a2, c1 + c2
    by = _coef(b, "y")
    story = ctx.pick([
        "Two plotting equations have y terms that are opposites. Add them to find x.",
        "The quartermaster's two tallies give the equations below. Eliminate y to find x.",
        "Signals decodes two lines of a cipher. Adding them makes one unknown vanish.",
    ])
    mistakes = [
        (_whole((c1 - c2) / (a1 - a2)), f"Subtracting leaves the y's: {by} − (−{by}) = {_coef(2 * b, 'y')}. Add the equations so they cancel."),
        (C, f"{_lead(C)} is {A}x. Divide by {A} to get x."),
        (_whole(C / a1), f"Adding gives {_coef(a1)} + {_coef(a2)} = {A}x. Divide by {A}, not {a1}."),
        (_whole((c1 - c2) / A), f"You added the x's but subtracted the right-hand sides. Add both sides: {_lead(c1)} + {_par(c2)} = {_lead(C)}."),
        (y, f"{_lead(y)} is y. The question asks for x."),
        (x - 1, f"Check: adding the equations gives {A}x = {_lead(C)}, and {A} × {x - 1} = {A * (x - 1)}."),
        (x + 1, f"Check: adding the equations gives {A}x = {_lead(C)}, and {A} × {x + 1} = {A * (x + 1)}."),
    ]
    return Problem(
        help="elim",
        story=story,
        expr=f"{_coef(a1)} + {by} = {_lead(c1)}\n{_coef(a2)} − {by} = {_lead(c2)}",
        ask="Solve for x.",
        choices=_numeric_choices(ctx, x, mistakes, allow_neg=True),
        solution=(
            f"The y terms are +{by} and −{by}: adding the equations cancels them.",
            f"{_coef(a1)} + {_coef(a2)} = {_lead(c1)} + {_par(c2)} → {A}x = {_lead(C)}.",
            f"x = {_lead(C)} ÷ {A} = {x}. (Then y = {_lead(y)}.)",
        ),
        hint="The y terms are opposites. Add the two equations, left side to left side and right to right, and the y's disappear.",
    )


@gen("sys", 2)
def set_equal(ctx: Context) -> Problem:
    """y = m₁x + b₁ and y = m₂x + b₂: set them equal to find where the lines cross."""
    while True:
        x, m1, m2, b1 = ctx.rand(-4, 10), ctx.rand(-4, 8), ctx.rand(-4, 8), ctx.rand(-12, 15)
        b2 = (m1 - m2) * x + b1
        if x and m1 and m2 and m1 != m2 and m1 + m2 and b1 and b2 and b2 != b1 and abs(b2) <= 40:
            break
    k, y = m1 - m2, m1 * x + b1
    undo, wrong = _undo(b1)
    move = f"Take {_coef(m2)} away from both sides" if m2 > 0 else f"Add {_coef(-m2)} to both sides"
    story = ctx.pick([
        "Two course lines are plotted on the chart. Where they cross, both give the same y.",
        "Two radar tracks are written as lines. Find the x where the tracks meet.",
        "The fire-control computer has two equations for y. Find the x where they agree.",
    ])
    mistakes = [
        (y, f"{_lead(y)} is y where the lines cross. The question asks for x."),
        (_whole((b2 - b1) / (m1 + m2)), f"{move}: that leaves {_lead(m1)} − {_par(m2)} = {_lead(k)} x's, not {_lead(m1 + m2)}."),
        (_whole((b2 + b1) / k), f"To undo the {_sgn(b1)}, {undo} on both sides. You {wrong} instead."),
        (-x, f"Check the sign: {_coef(k)} = {_lead(b2 - b1)}, and {_lead(b2 - b1)} ÷ {_par(k)} = {_lead(x)}."),
        (b2 - b1, f"{_lead(b2 - b1)} is {_coef(k)}, not x. Divide by {_par(k)}."),
    ]
    for v in (x - 1, x + 1):
        mistakes.append((v, f"Check x = {_lead(v)}: the first line gives y = {_lead(m1 * v + b1)} but the second y = {_lead(m2 * v + b2)}."))
    rhs1, rhs2 = _line(m1, b1)[4:], _line(m2, b2)[4:]
    return Problem(
        help="setequal",
        story=story,
        expr=f"{_line(m1, b1)}\n{_line(m2, b2)}",
        ask="At what x do the lines cross?",
        choices=_numeric_choices(ctx, x, mistakes, allow_neg=True),
        solution=(
            f"Both equal y, so set them equal: {rhs1} = {rhs2}.",
            f"{move}: {_coef(k)} {_sgn(b1)} = {_lead(b2)}.",
            f"{_cap(undo)} on both sides: {_coef(k)} = {_lead(b2 - b1)}.",
            (f"Divide by {_par(k)}: x = {_lead(x)}." if k != 1 else f"So x = {_lead(x)}.") + f" (Then y = {_lead(y)}.)",
        ),
        hint="Both right-hand sides equal y, so they equal each other. Set them equal and solve for x.",
    )


# ---------------- More quadratics ----------------


@gen("quad", 2)
def dropped_object(ctx: Context) -> Problem:
    """h = H − 16t²: time to hit the deck."""
    k = ctx.rand(2, 6)
    H = 16 * k * k
    story = ctx.pick([
        f"A wrench slips from a sailor's hand {H} feet up the mast. Its height after t seconds is given by the equation.",
        f"A signal lamp is dropped from a crane {H} feet above the pier. Its height in feet after t seconds is below.",
        f"A flare is released from a helicopter hovering {H} feet above the deck. Its height follows the equation.",
    ])
    kk = k * k
    mistakes = [
        (kk, f"{H} ÷ 16 = {kk} is t{sup(2)}. Take the square root to get t."),
        (4 * k, f"You took the square root of {H} before dividing by 16. Divide by 16 first, then take the root."),
        (-k, "Time can't be negative. Take the positive square root."),
        (_whole(math.sqrt(H - 16)), f"You subtracted 16 instead of dividing by it: 16t{sup(2)} means 16 times t{sup(2)}."),
        (k - 1, f"Check: 16 × {k - 1}{sup(2)} = {16 * (k - 1) ** 2}, not {H}."),
        (k + 1, f"Check: 16 × {k + 1}{sup(2)} = {16 * (k + 1) ** 2}, not {H}."),
    ]
    if k % 2 == 0:
        mistakes.append((kk // 2, f"A square root isn't half: {kk // 2} × {kk // 2} isn't {kk}."))
    return Problem(
        help="drop",
        story=story,
        expr=f"h = {H} − 16t{sup(2)}",
        ask="After how many seconds does it hit the deck (h = 0)?",
        choices=_numeric_choices(ctx, k, mistakes, allow_neg=True),
        solution=(
            f"Set h = 0: {H} − 16t{sup(2)} = 0 → 16t{sup(2)} = {H}.",
            f"t{sup(2)} = {H} ÷ 16 = {k * k}.",
            f"t = √{k * k} = {k} seconds.",
        ),
        hint=f"Get t² by itself: t² = {H} ÷ 16. Then take the square root.",
    )


@gen("quad", 3)
def projectile_from_height(ctx: Context) -> Problem:
    """h = −16t² + vt + h₀: time to splash down."""
    T = ctx.rand(3, 7)
    r = ctx.rand(1, min(3, T - 1))
    v = 16 * (T - r)
    h0 = 16 * T * r
    story = ctx.pick([
        f"A deck gun {h0} feet above the waterline fires a shell straight up at {v} ft/s. Its height in feet after t seconds is given below.",
        f"A rescue swimmer tosses a line upward from a {h0}-foot-high deck at {v} ft/s. The equation gives its height over the water.",
    ])
    mistakes = [
        (r, f"You dropped a minus sign. That solution is t = −{r}, and a time can't be negative."),
        (-r, f"Time can't be negative, so throw out t = −{r} and use the other solution."),
        (T - r, f"You left out the {h0}-foot height. {v} ÷ 16 is when it falls back to deck level, not to the water."),
        ((T - r) / 2, "That's when it's highest, not when it hits the water."),
        (_whole(math.sqrt(T * r)), f"You treated it as dropped: {h0} = 16t{sup(2)} leaves out the {v} ft/s upward throw."),
        (T * r, f"You divided only the {h0} by 16. Divide every term by −16, then factor."),
        (_whole((v + h0) / 16), f"You added {v} and {h0}, but {v}t and {h0} aren't like terms."),
        (2 * T, "In the quadratic formula the bottom is 2 × (−16) = −32; you divided by 16."),
    ]
    return Problem(
        help="traj2",
        story=story,
        expr=f"h = −16t{sup(2)} + {v}t + {h0}",
        ask="After how many seconds does it hit the water (h = 0)?",
        choices=_numeric_choices(ctx, T, mistakes, allow_neg=True),
        solution=(
            f"Set h = 0 and divide every term by −16: t{sup(2)} − {T - r}t − {T * r} = 0.",
            f"Factor: (t − {T})(t + {r}) = 0.",
            f"t = {T} or t = −{r}. Time can't be negative, so {T} seconds.",
        ),
        hint=f"Divide everything by −16 first: t² − {T - r}t − {T * r} = 0. Then factor.",
    )


@gen("quad", 2)
def difference_of_squares(ctx: Context) -> Problem:
    """Factor x² − k²."""
    k = ctx.rand(2, 12)
    K = k * k
    ans = f"(x − {k})(x + {k})"
    wrong = [
        (f"(x − {k})(x − {k})", f"That multiplies out to x{sup(2)} − {2 * k}x + {K}. Use one + and one − so the middle terms cancel."),
        (f"(x + {k})(x + {k})", f"That multiplies out to x{sup(2)} + {2 * k}x + {K}. Use one + and one − so the middle terms cancel."),
        (f"(x − {K})(x + {K})", f"You used {K} itself. Each bracket needs the square root of {K}."),
    ]
    if K % 2 == 0 and K // 2 != k:
        wrong.append((f"(x − {K // 2})(x + {K // 2})", f"A square root isn't half: {K // 2} × {K // 2} isn't {K}."))
    pairs = [(u, K // u) for u in range(1, k) if K % u == 0]
    for u, v in ctx.shuffle(pairs)[:2]:
        if ctx.rand(0, 1):
            wrong.append((f"(x − {u})(x + {v})", f"Those multiply to −{K}, but leave a middle term of {v - u}x. The two numbers must be the same."))
        else:
            wrong.append((f"(x − {v})(x + {u})", f"Those multiply to −{K}, but leave a middle term of −{v - u}x. The two numbers must be the same."))
    for u, v in ctx.shuffle(pairs)[:1]:
        sign = ctx.pick(["+", "−"])
        wrong.append((f"(x {sign} {u})(x {sign} {v})", f"Those multiply to +{K}, but the last term is −{K}. Use one + and one −."))
    story = ctx.pick([
        "The gunnery table has a binomial with no middle term. Factor it.",
        "A sonar equation reduces to a difference of squares. Factor it.",
        "The shipwright's formula for hull stress contains this expression. Factor.",
    ])
    return Problem(
        help="diffsq",
        story=story,
        expr=f"x{sup(2)} − {K}",
        ask="Which is the factored form?",
        choices=_string_choices(ctx, ans, wrong),
        solution=(f"√x{sup(2)} = x and √{k * k} = {k}.", f"Difference of squares: {ans}.", f"Check the middle: −{k}x + {k}x = 0 ✓"),
        hint="No middle term and a minus sign — that's a difference of squares: (x − √c)(x + √c).",
    )


@gen("quad", 2)
def solve_by_square_roots(ctx: Context) -> Problem:
    """x² = c or ax² − c = 0: x = ±k."""
    k = ctx.rand(2, 12)
    a = ctx.pick([1, 1, 2, 3, 4, 5])
    c = a * k * k
    K = k * k
    ans = f"x = ±{k}"
    story = ctx.pick([
        "The stabilizer equation has an x² but no plain x term. Solve it.",
        "Fire control's range check reduces to the equation below. Find all solutions.",
        "A radar cross-section formula gives this equation. Solve for x.",
    ])
    if a == 1:
        solution = ("Take the square root of both sides — remember both signs.", f"x = ±√{c} = ±{k}.")
    else:
        solution = (f"Add {c}: {a}x{sup(2)} = {c}. Divide by {a}: x{sup(2)} = {k * k}.", f"Square root both sides, both signs: {ans}.")
    wrong = [
        (f"x = {k}", f"You forgot the negative answer: (−{k}){sup(2)} is {K} too."),
        (f"x = ±{K}", f"{K} is x{sup(2)}, not x. Take its square root."),
        (f"x = ±{_num(K / 2)}", f"A square root isn't half. Find the number that times itself makes {K}."),
        (f"x = −{k}", "You kept only the negative answer. The positive one works too."),
        (f"x = {K}", f"x{sup(2)} = {K} doesn't mean x = {K}. Take the square root, and remember the negative answer."),
    ]
    if a != 1:
        wrong.append((f"x = ±√{c}", f"You took the square root before dividing by {a}. Get x{sup(2)} by itself first."))
    return Problem(
        help="sqroot",
        story=story,
        expr=f"x{sup(2)} = {c}" if a == 1 else f"{a}x{sup(2)} − {c} = 0",
        ask="What are all the solutions?",
        choices=_string_choices(ctx, ans, wrong),
        solution=solution,
        hint="Get x² alone first. Then take the square root — and don't forget the negative answer.",
    )


@gen("quad", 3)
def consecutive_product(ctx: Context) -> Problem:
    """x(x + 1) = P."""
    x = ctx.rand(6, 25)
    P = x * (x + 1)
    story = ctx.pick([
        f"Two ships moored side by side have consecutive hull numbers whose product is {P}.",
        f"Two consecutive pier numbers multiply to {P}.",
        f"The width and length of a storage bay are consecutive whole numbers of feet, and the area is {P} square feet.",
    ])
    mistakes = [
        (x + 1, f"{x + 1} is the bigger of the two numbers. The question asks for the smaller one."),
        (math.sqrt(P), f"√{P} is only an estimate: it lands between the two numbers. Test whole numbers near it."),
        (_whole((P - 1) / 2), f"You added the two numbers: x + (x + 1) = {P}. The problem says they multiply."),
        (-(x + 1), "That's the negative solution. These numbers are positive."),
        (x - 1, f"Check: {x - 1} × {x} = {(x - 1) * x}, not {P}."),
    ]
    pairs = [(u, P // u) for u in range(2, x) if P % u == 0]
    for u, v in ctx.shuffle(pairs)[:2]:
        mistakes.append((u, f"{u} × {v} = {P}, but {u} and {v} aren't next to each other: they're {v - u} apart."))
    return Problem(
        help="consecprod",
        story=story,
        expr=f"x(x + 1) = {P}",
        ask="What is the smaller number, x?",
        choices=_numeric_choices(ctx, x, mistakes, allow_neg=True),
        solution=(
            f"Expand: x{sup(2)} + x − {P} = 0.",
            f"Factor: (x − {x})(x + {x + 1}) = 0, since {x} × {x + 1} = {P}.",
            f"x = {x} (the negative root is thrown out).",
        ),
        hint=f"√{P} is about {_num(_js_round(math.sqrt(P) * 10) / 10)}, so try the two whole numbers on either side of that.",
    )


# ---------------- One-step quadratics ----------------


@gen("quad", 1)
def zero_product(ctx: Context) -> Problem:
    """(x − p)(x − q) = 0, so x − p = 0 or x − q = 0."""
    if ctx.rand(0, 3) == 0:  # x(x − p) = 0
        p = ctx.pick([v for v in range(-9, 10) if v])
        expr = f"x(x {_sgn(-p)}) = 0"
        ans = _pair_roots(0, p)
        wrong = [
            (f"x = {_lead(p)}", "x = 0 works too: the first factor is x itself, and 0 times anything is 0."),
            (_pair_roots(0, -p), f"x {_sgn(-p)} = 0 gives x = {_lead(p)}: the sign flips when you solve it."),
            (f"x = {_lead(-p)}", f"x {_sgn(-p)} = 0 gives x = {_lead(p)}, not {_lead(-p)}. And x = 0 works too."),
            ("x = 0", f"That's only one of them. The other factor, x {_sgn(-p)}, can be 0 too."),
        ]
        steps = ("Set the first factor to zero: x = 0.", f"Set the second to zero: x {_sgn(-p)} = 0, so x = {_lead(p)}.")
    else:
        while True:
            p, q = ctx.rand(-9, 9), ctx.rand(-9, 9)
            if p and q and p != q and p != -q:
                break
        expr = f"{_factor_form(-p, -q)} = 0"
        ans = _pair_roots(p, q)

        def check(x: int) -> str:
            return f"Check x = {_lead(x)}: ({_lead(x)} {_sgn(-p)})({_lead(x)} {_sgn(-q)}) = {_lead((x - p) * (x - q))}, not 0."

        wrong = [
            (_pair_roots(-p, -q), f"Those are the numbers in the factors. x {_sgn(-p)} = 0 gives x = {_lead(p)}: the sign flips when you solve it."),
            (_pair_roots(p, -q), f"Only x = {_lead(p)} works. {check(-q)}"),
            (_pair_roots(-p, q), f"Only x = {_lead(q)} works. {check(-p)}"),
            (f"x = {_lead(p)}", f"That's only one of them. The other factor, x {_sgn(-q)}, can be 0 too."),
            (f"x = {_lead(q)}", f"That's only one of them. The other factor, x {_sgn(-p)}, can be 0 too."),
        ]
        steps = (f"Set the first factor to zero: x {_sgn(-p)} = 0, so x = {_lead(p)}.", f"Set the second to zero: x {_sgn(-q)} = 0, so x = {_lead(q)}.")
    story = ctx.pick([
        "Fire control has already factored the shell's path. Find when it is at sea level.",
        "The sonar equation is already factored. Read off the solutions.",
        "A product of two factors is zero. Find every x that makes it true.",
    ])
    return Problem(
        help="zeroprod",
        story=story,
        expr=expr,
        ask="What are the solutions?",
        choices=_string_choices(ctx, ans, wrong),
        solution=("If two factors multiply to 0, one of them must be 0.", *steps, f"So {ans}."),
        hint="Set each factor equal to 0 and solve each one. Watch the sign: x − 3 = 0 gives x = 3.",
    )


@gen("quad", 1)
def evaluate_quadratic(ctx: Context) -> Problem:
    """h = −16t² + vt + h₀ at a given t: square first, then multiply."""
    k = ctx.rand(4, 8)
    v, s = 16 * k, ctx.rand(2, k - 1)
    h0 = ctx.pick([8, 12, 16, 20, 24, 32, 40])
    H = -16 * s * s + v * s + h0
    sq = s * s
    thing, story = ctx.pick([
        ("flare", f"A signal flare is fired straight up from a deck {h0} feet above the water."),
        ("line", f"A line-throwing gun on a deck {h0} feet above the water fires a weighted line upward."),
        ("round", f"A deck gun {h0} feet above the waterline fires a practice round straight up."),
    ])
    t2 = f"t{sup(2)}"
    mistakes = [
        (v * s - 16 * s + h0, f"You left out the square: {t2} is {s} × {s} = {sq}, so −16{t2} is −16 × {sq}."),
        (v * s - 32 * s + h0, f"{t2} is {s} × {s} = {sq}, not 2 × {s}."),
        (v * s + 256 * sq + h0, f"Only t is squared: −16{t2} is −16 × {s}{sup(2)}, not (−16 × {s}){sup(2)}."),
        (v * s + 16 * sq + h0, f"The 16{t2} is taken away: −16 × {sq} = −{16 * sq}."),
        (v * s + h0, f"You left out the −16{t2} term. It pulls the {thing} back down: take away 16 × {sq}."),
        (v - 16 * sq + h0, f"{v}t means {v} × {s}. You added just {v}."),
        (H - h0, f"You left out the {h0}: the {thing} starts {h0} feet up."),
        (H - 2 * h0, f"The {h0} is added: the deck is {h0} feet above the water, not below it."),
    ]
    return Problem(
        help="evalquad",
        story=story + " Its height in feet after t seconds is given by the equation.",
        expr=f"h = −16{t2} + {v}t + {h0}",
        ask=f"How high is it after {s} seconds, in feet?",
        choices=_numeric_choices(ctx, H, mistakes),
        solution=(
            f"Put t = {s} in: h = −16({s}){sup(2)} + {v}({s}) + {h0}.",
            f"Square first: {s}{sup(2)} = {sq}, so −16 × {sq} = −{16 * sq}. And {v} × {s} = {v * s}.",
            f"h = −{16 * sq} + {v * s} + {h0} = {H} feet.",
        ),
        hint="Put the time in for t. Square it first, then multiply by −16, then add the other terms.",
    )


def _quadratic(a: int, b: int, c: int) -> str:
    """y = ax² + bx + c, with b and c not zero: (2, -12, 7) -> "y = 2x² − 12x + 7"."""
    return f"y = {_coef(a, 'x' + sup(2))} {'−' if b < 0 else '+'} {_coef(abs(b))} {_sgn(c)}"


@gen("quad", 1)
def axis_of_symmetry(ctx: Context) -> Problem:
    """The axis of symmetry of y = ax² + bx + c: x = −b ÷ (2a)."""
    a = ctx.pick([1, 1, 2, 3, -1, -2])
    h = ctx.pick([v for v in range(-6, 9) if v])
    b = -2 * a * h
    c = ctx.pick([v for v in range(-12, 16) if v and v not in (h, -h, 2 * h, -2 * h, b)])
    story = ctx.pick([
        "A shell's path is a parabola. The gunnery officer wants the line it is symmetric about.",
        "The cross-section of the radar dish is the parabola below. Find its axis of symmetry.",
        "The arc of water from the fireboat's monitor follows the equation below. Find its axis of symmetry.",
    ])
    two_a = 2 * a
    mistakes = [
        (-h, f"You left out the minus in −b ÷ (2a): it's −({_lead(b)}) ÷ {_par(two_a)}."),
        (2 * h, f"You forgot the 2 in 2a: divide by {_par(two_a)}, not {_par(a)}." if a != 1
         else "You forgot the 2: the formula is −b ÷ (2a), so divide by 2."),
        (_whole(-b / 2), f"You divided by 2 but forgot a = {_lead(a)}: 2a = {_lead(two_a)}."),
        (c, f"{_lead(c)} is c, where the parabola crosses the y-axis, not where its axis is."),
        (b, f"{_lead(b)} is b. The axis is at x = −b ÷ (2a)."),
        (-2 * h, "−b ÷ (2a) needs both the minus sign and the 2."),
    ]
    return Problem(
        help="axis",
        story=story,
        expr=_quadratic(a, b, c),
        ask="The axis of symmetry is the line x = ?",
        choices=_numeric_choices(ctx, h, mistakes, allow_neg=True),
        solution=(f"Here a = {_lead(a)} and b = {_lead(b)}.", f"x = −b ÷ (2a) = −({_lead(b)}) ÷ {_par(two_a)} = {_lead(h)}."),
        hint="Use x = −b ÷ (2a). Read a (the number with x²) and b (the number with x) off the equation, signs included.",
    )


# ---------------- More powers & roots ----------------


@gen("exp", 2)
def pythagorean_missing_leg(ctx: Context) -> Problem:
    """b² = c² − a²."""
    trip = ctx.pick(_TRIPLES)
    a, b, c = trip if ctx.rand(0, 1) else [trip[1], trip[0], trip[2]]
    story = ctx.pick([
        f"Radar shows a contact at a range of {c} nautical miles, and it is {a} nautical miles east of you.",
        f"A {c}-foot ladder leans against the hangar wall with its foot {a} feet from the wall.",
        f"A {c}-foot anchor chain runs from the bow to the seabed; the anchor is {a} feet horizontally from the ship.",
    ])
    bb = b * b
    mistakes = [
        (c - a, f"You subtracted the sides. Subtract their squares, {c}{sup(2)} − {a}{sup(2)}, then take the square root."),
        (c + a, "You added the sides. For a missing leg, subtract the squares, then take the square root."),
        (_whole(math.sqrt(c * c + a * a)), "You added the squares; that finds the longest side. For a leg, subtract them."),
        (bb, f"{bb} is b{sup(2)}. Take its square root to get b."),
        (bb / 2, f"A square root isn't half. Find the number that times itself makes {bb}."),
        (_whole(math.sqrt(c - a)), f"You took the square root of {c} − {a}. Square each side first, then subtract."),
    ]
    return Problem(
        help="pythleg",
        story=story,
        expr=f"{a}{sup(2)} + b{sup(2)} = {c}{sup(2)}",
        ask="Find the missing leg, b.",
        choices=_numeric_choices(ctx, b, mistakes),
        solution=(f"b{sup(2)} = {c}{sup(2)} − {a}{sup(2)} = {c * c} − {a * a} = {b * b}.", f"b = √{b * b} = {b}."),
        hint="Rearrange: b² = c² − a². Subtract the squares, then take the square root.",
    )


@gen("exp", 2)
def distance_between_points(ctx: Context) -> Problem:
    """Distance formula on the plotting grid."""
    trip = ctx.pick([[3, 4, 5], [5, 12, 13], [6, 8, 10], [8, 15, 17], [9, 12, 15], [7, 24, 25]])
    dx, dy, d = trip if ctx.rand(0, 1) else [trip[1], trip[0], trip[2]]
    x1 = ctx.rand(-5, 5)
    y1 = ctx.rand(-5, 5)
    x2 = x1 + (dx if ctx.rand(0, 1) else -dx)
    y2 = y1 + (dy if ctx.rand(0, 1) else -dy)
    p1, p2 = f"({_lead(x1)}, {_lead(y1)})", f"({_lead(x2)}, {_lead(y2)})"
    story = ctx.pick([
        f"On the plotting board, your ship is at {p1} and a contact is at {p2}. Each grid unit is one nautical mile.",
        f"Two buoys are charted at {p1} and {p2} on a grid of nautical miles.",
    ])
    dd = d * d
    mistakes = [
        (dx + dy, "You added the two differences. Square them first, add the squares, then take the square root."),
        (dd, f"{dd} is d{sup(2)}. Take its square root to get d."),
        (dd / 2, f"A square root isn't half. Find the number that times itself makes {dd}."),
        (abs(dx - dy), "You subtracted the two differences. Square them, add the squares, then take the square root."),
        (_whole(math.sqrt(dx + dy)), "You added the differences before squaring. Square each one first, then add."),
        (_whole(math.sqrt(abs(dx * dx - dy * dy))), "You subtracted the squares. For a distance, add them."),
    ]
    slips = []
    if x1:
        slips.append((_whole(math.hypot(x2 + x1, dy)), f"Watch the signs: {_lead(x2)} − {_par(x1)} = {_lead(x2 - x1)}, not {_lead(x2 + x1)}."))
    if y1:
        slips.append((_whole(math.hypot(dx, y2 + y1)), f"Watch the signs: {_lead(y2)} − {_par(y1)} = {_lead(y2 - y1)}, not {_lead(y2 + y1)}."))
    mistakes += ctx.shuffle(slips)[:1]
    return Problem(
        help="dist",
        story=story,
        expr=f"d = √(({_lead(x2)} − {_par(x1)}){sup(2)} + ({_lead(y2)} − {_par(y1)}){sup(2)})",
        ask="What is the distance between them?",
        choices=_numeric_choices(ctx, d, mistakes),
        solution=(
            f"Δx = {_lead(x2)} − {_par(x1)} = {_lead(x2 - x1)}, Δy = {_lead(y2)} − {_par(y1)} = {_lead(y2 - y1)}.",
            f"({_lead(x2 - x1)}){sup(2)} + ({_lead(y2 - y1)}){sup(2)} = {dx * dx} + {dy * dy} = {d * d}.",
            f"d = √{d * d} = {d} nm.",
        ),
        hint="Subtract the x's, subtract the y's, square both, add, and square-root. Negatives disappear when you square.",
    )


@gen("exp", 1)
def scientific_notation(ctx: Context) -> Problem:
    """Convert between scientific notation and a standard number."""
    m = ctx.pick([1.2, 2.5, 3.2, 4.8, 6.1, 7.5, 9.3, 2, 5, 8])
    n = ctx.rand(3, 7)
    val = _js_round(m * 10**n)
    mode = ctx.rand(0, 1)
    ms = _num(m)
    sci = f"{ms} × 10{sup(n)}"
    item = ctx.pick([
        "gallons of fuel in the fleet oiler",
        "pounds of displacement",
        "rivets in the hull",
        "square feet of steel plating",
        "miles the ship has steamed since commissioning",
    ])
    m10 = _js_round(m * 10)  # the digits of m with the point taken out: 3.2 -> 32
    if mode == 0:

        def std(v: Number) -> tuple[str, float]:
            return _locale(v), float(v)

        more = (
            f"You wrote {n} zeros after {m10}, but the digit after the point already uses up one of the {n} places."
            if not _is_int(m) else f"You moved the point {n + 1} places. 10{sup(n)} moves it {n} places."
        )
        wrong = [
            (*std(_js_round(m * 10 ** (n - 1))), f"You moved the point only {n - 1} places. 10{sup(n)} moves it {n} places to the right."),
            (*std(_js_round(m * 10 ** (n + 1))), more),
            (*std(float(_num(round(m * n, 4)))), f"You multiplied {ms} by {n}. 10{sup(n)} means {n} tens multiplied together, not {n}."),
            (*std(_js_round(m * 10 * n)), f"10{sup(n)} isn't 10 × {n}. It means {n} tens multiplied together."),
        ]
        if not _is_int(m):
            wrong.append((*std(int(m) * 10**n), "You dropped the digits after the point. They move along with the point."))
        return Problem(
            help="sci",
            story=f"The ship's log lists {sci} {item}.",
            expr=sci,
            ask="Write it as a standard number.",
            choices=_string_choices(ctx, _locale(val), [(t, why, v) for t, v, why in wrong], float(val), same_value_ok=True),
            solution=(f"10{sup(n)} means move the decimal point {n} places to the right.", f"{ms} → {_locale(val)}."),
            hint=f"Move the decimal point {n} places to the right, filling in zeros.",
        )
    m_tenth = _num(round(m / 10, 4))
    wrong = [
        (f"{ms} × 10{sup(n - 1)}", f"The point moves {n} places, not {n - 1}. Count every digit after the first one.", m * 10 ** (n - 1)),
        (f"{ms} × 10{sup(n + 1)}", f"You counted all {n + 1} digits. Count only the places the point moves: the digits after the first one.", m * 10 ** (n + 1)),
        (f"{m10} × 10{sup(n - 1)}", f"That's the same number, but it isn't in scientific notation: {m10} isn't between 1 and 10.", float(val)),
        (f"{m_tenth} × 10{sup(n + 1)}", f"That's the same number, but it isn't in scientific notation: {m_tenth} isn't between 1 and 10.", float(val)),
        (f"{m10} × 10{sup(n)}", f"{m10} isn't between 1 and 10, and {m10} × 10{sup(n)} is ten times too big.", m * 10 ** (n + 1)),
    ]
    if not _is_int(m):
        wrong.append((f"{int(m)} × 10{sup(n)}", f"You dropped the digits after the point. Keep all of {ms}.", int(m) * 10.0**n))
    return Problem(
        help="sci",
        story=f"The ship's log lists {_locale(val)} {item}.",
        expr=_locale(val),
        ask="Write it in scientific notation.",
        choices=_string_choices(ctx, sci, wrong, float(val), same_value_ok=True),
        solution=(f"Put the decimal point after the first digit: {ms}.", f"Count how many places it moved: {n}. So {sci}."),
        hint="The first number must be between 1 and 10. Count how many places the decimal moves to get there.",
    )


@gen("exp", 2)
def growth_from_start(ctx: Context) -> Problem:
    """start × baseⁿ."""
    start = ctx.pick([5, 8, 10, 12, 20, 25])
    base = ctx.pick([2, 3])
    n = ctx.rand(2, 5)
    N = start * base**n
    per = ctx.pick(["week", "year", "month"])
    grows = "doubles" if base == 2 else "triples"
    story = ctx.pick([
        f"Barnacle colonies on the hull: {start} colonies today, and the number {grows} every {per}.",
        f"A new squadron starts with {start} patrol boats and {grows} in size every {per}.",
        f"{start} sailors know the rumor, and the number who know it {grows} every {per}.",
    ])
    mistakes = [
        (start * base * n, f"{base}{sup(n)} isn't {base} × {n}. Multiply {n} {base}s together, then multiply by {start}."),
        (start * base ** (n - 1), f"You multiplied by {base} only {'once' if n == 2 else f'{n - 1} times'}. It {grows} once for each of the {n} {per}s."),
        (start * base ** (n + 1), f"You multiplied by {base} {n + 1} times. It {grows} once for each of the {n} {per}s."),
        ((start * base) ** n, f"You raised {start} × {base} to the power {n}. Only the {base} gets the power; then multiply by {start}."),
        (start + base**n, f"You added {start}. Multiply {base}{sup(n)} by the starting {start}."),
        (base**n, f"{base**n} is {base}{sup(n)}. Now multiply it by the starting {start}."),
    ]
    return Problem(
        help="growth",
        story=story,
        expr=f"{start} × {base}{sup(n)}",
        ask=f"How many after {n} {per}s?",
        choices=_numeric_choices(ctx, N, mistakes),
        solution=(f"{base}{sup(n)} = {base**n}.", f"{start} × {base**n} = {N}."),
        hint=f"Work out {base}{sup(n)} first (multiply {base} by itself {n} times), then multiply by {start}.",
    )


@gen("exp", 1)
def zero_negative_exponents(ctx: Context) -> Problem:
    """b⁰ = 1 and b⁻ⁿ = 1⁄bⁿ."""
    mode = ctx.rand(0, 2)
    b = ctx.pick([2, 3, 4, 5, 10])
    if mode == 0:
        story = ctx.pick([
            "The reactor gauge reads a power with an exponent of zero.",
            "A signal-strength formula simplifies to a power of zero. Evaluate it.",
        ])
        wrong = [
            ("0", "A power of 0 isn't 0. Any number except 0 to the power 0 is 1.", 0.0),
            (str(b), f"{b} is {b}{sup(1)}. With the power 0 the answer is 1.", float(b)),
            (f"1⁄{b}", f"1⁄{b} is {b}{sup(-1)}. With the power 0 the answer is 1.", 1 / b),
            ("no answer", "It does have an answer: any number except 0 to the power 0 is 1."),
        ]
        return Problem(
            help="negexp",
            story=story,
            expr=f"{b}{sup(0)}",
            ask="Evaluate.",
            choices=_string_choices(ctx, "1", wrong, 1.0),
            solution=("Any nonzero base to the power 0 equals 1.",),
            hint="Exponent 0 → the answer is always 1.",
        )
    n = ctx.rand(1, 3)
    val = b**n
    story = ctx.pick([
        "Sonar attenuation is written with a negative exponent. Evaluate it as a fraction.",
        "The depth-pressure chart uses a negative exponent. Evaluate.",
    ])
    neg = sup(f"−{n}")
    wrong = [
        (f"−{val}", f"A negative power doesn't make the number negative. It means 1 over {b}{sup(n)}.", -val),
        (f"−1⁄{val}", "The answer isn't negative: a negative power means 1 over, not minus.", -1 / val),
        (str(val), f"You dropped the minus sign in the power. {b}{neg} means 1 over {b}{sup(n)}.", float(val)),
        (f"−{b * n}", f"{b}{neg} isn't {b} × (−{n}). A negative power means 1 over {b}{sup(n)}.", -b * n),
    ]
    wrong.append((f"1⁄{val * b}", f"That's 1 over {b}{sup(n + 1)}: one {b} too many. {b}{neg} is 1 over {b}{sup(n)}.", 1 / (val * b)))
    if n > 1:
        wrong.append((f"1⁄{b}", f"You flipped it but dropped the power. {b}{neg} is 1 over {b}{sup(n)}, not 1 over {b}.", 1 / b))
    if b * n != val:
        wrong.append((f"1⁄{b * n}", f"{b}{sup(n)} isn't {b} × {n}. Multiply {n} {b}s together.", 1 / (b * n)))
    return Problem(
        help="negexp",
        story=story,
        expr=f"{b}{neg}",
        ask="Evaluate.",
        choices=_string_choices(ctx, f"1⁄{val}", wrong, 1 / val),
        solution=(f'A negative exponent means "one over": {b}{neg} = 1 ÷ {b}{sup(n)}.', f"{b}{sup(n)} = {val}, so the answer is 1⁄{val}."),
        hint=f"Negative exponent → flip it to a fraction: 1 over {b}{sup(n)}. The answer is positive.",
    )


@gen("exp", 1)
def square_root_perfect_square(ctx: Context) -> Problem:
    """Side of a square from its area."""
    k = ctx.pick([9, 11, 12, 13, 14, 15, 16, 18, 20, 25, 30])
    A = k * k
    story = ctx.pick([
        f"A square helipad covers {A:,} square feet.",
        f"A square hatch cover has an area of {A:,} square inches.",
        f"A square storage bay has a floor area of {A:,} square feet.",
    ])
    mistakes = [
        (A / 2, f"A square root isn't half. Find the number that times itself makes {A:,}."),
        (_whole(A / 4), "Dividing by 4 finds a side from the distance around a square, not from its area."),
        (k - 2, f"Check: {k - 2} × {k - 2} = {(k - 2) ** 2:,}, not {A:,}."),
        (k - 1, f"Check: {k - 1} × {k - 1} = {(k - 1) ** 2:,}, not {A:,}."),
        (k + 1, f"Check: {k + 1} × {k + 1} = {(k + 1) ** 2:,}, not {A:,}."),
    ]
    last = k % 10
    if last not in (0, 5) and k > 10:
        twin = k - last + 10 - last
        mistakes.append((twin, f"{twin} × {twin} = {twin * twin:,}. It ends in the same digit as {A:,}, but it's not {A:,}."))
    return Problem(
        help="sqrtnum",
        story=story,
        expr=f"s{sup(2)} = {A:,}",
        ask="How long is each side, s?",
        choices=_numeric_choices(ctx, k, mistakes),
        solution=(f"s = √{A:,}.", f"{k} × {k} = {A:,}, so s = {k}."),
        hint=f"What number times itself gives {A:,}? Try numbers near √{A:,}.",
    )


_RADICAL_PAIRS = [
    (2, 8, "4"), (3, 12, "6"), (2, 18, "6"), (5, 20, "10"), (3, 27, "9"), (2, 32, "8"),
    (6, 24, "12"), (2, 10, "2√5"), (3, 6, "3√2"), (5, 10, "5√2"), (2, 6, "2√3"), (7, 14, "7√2"),
]


@gen("exp", 2)
def multiply_radicals(ctx: Context) -> Problem:
    """√a · √b = √(ab), simplified."""
    a, b, ans = ctx.pick(_RADICAL_PAIRS)
    prod = a * b
    story = ctx.pick([
        "Two range measurements are multiplied in the fire-control formula. Simplify the product.",
        "The navigator multiplies two square roots. Simplify.",
    ])
    s = math.isqrt(a + b)
    added = str(s) if s * s == a + b else f"√{a + b}"
    wrong = [
        (added, f"You added under the root. Multiplying roots multiplies the insides: √({a} × {b}).", math.sqrt(a + b)),
        (str(prod), f"{a} × {b} = {prod}, but that's still under the square root. Take the root of {prod}.", float(prod)),
        (f"{a}√{b}", f"You took {a} out of √{a}, but √{a} isn't {a}.", a * math.sqrt(b)),
        (str(a + b), "You added the numbers and dropped the roots. Multiply under one root instead.", float(a + b)),
    ]
    if prod % 2 == 0:
        wrong.append((str(prod // 2), f"A square root isn't half: {prod // 2} × {prod // 2} isn't {prod}.", float(prod // 2)))
    if "√" in ans:
        k, m = (int(v) for v in ans.split("√"))
        wrong += [
            (f"{k * k}√{m}", f"√{k * k} is {k}, not {k * k}. Take the root as it comes out.", k * k * math.sqrt(m)),
            (f"{m}√{k}", "You swapped the numbers. The root of the perfect square goes in front.", m * math.sqrt(k)),
            (f"√{m}", f"The {k} that came out of the root is missing. Write it in front.", math.sqrt(m)),
            (str(k), "You dropped the part that stays under the root.", float(k)),
        ]
    elif b % a == 0 and math.isqrt(b // a) ** 2 == b // a and math.isqrt(b // a) != int(ans):
        wrong.append((str(math.isqrt(b // a)), f"You divided {b} by {a}. Roots multiply: √{a} · √{b} = √({a} × {b}).", float(math.isqrt(b // a))))
    value = float(ans) if "√" not in ans else _root_value(*(int(v) for v in ans.split("√")))
    return Problem(
        help="mulrad",
        story=story,
        expr=f"√{a} · √{b}",
        ask="Which is the simplified product?",
        choices=_string_choices(ctx, ans, wrong, value),
        solution=(f"Multiply under one root: √({a} × {b}) = √{prod}.", f"Simplify: √{prod} = {ans}."),
        hint=f"Multiply the insides: √({a} × {b}). Then look for a perfect-square factor.",
    )


# ---------------- Multi-step powers and roots ----------------


def _simplest(k: int, n: int) -> tuple[str, float]:
    """k√n in simplest form, and its value: (1, 12) -> ("2√3", 3.46...), (2, 9) -> ("6", 6.0)."""
    for f in range(math.isqrt(n), 1, -1):
        if n % (f * f) == 0:
            k, n = k * f, n // (f * f)
            break
    return (str(k) if n == 1 else _root_text(k, n)), k * math.sqrt(n)


@gen("exp", 3)
def add_radicals(ctx: Context) -> Problem:
    """√(p²m) + √(q²m) = (p + q)√m: simplify each root, then add the like roots."""
    m = ctx.pick([2, 3, 5, 6, 7])
    p, q = ctx.shuffle(range(1, 6))[:2]
    a, b, k = p * p * m, q * q * m, p + q
    ans = _root_text(k, m)
    rp, rq = _root_text(p, m), _root_text(q, m)
    big = max(p, q)
    sc = ctx.pick([
        dict(story=f"A search pattern has two legs: √{a} nautical miles, then √{b} nautical miles.", unit="nm"),
        dict(story=f"The navigator adds two radar ranges that came out as square roots: √{a} and √{b} nautical miles.", unit="nm"),
        dict(story=f"The radar mast is braced by two cables, one √{a} feet long and one √{b} feet long.", unit="ft"),
    ])
    wrong = [
        (*_simplest(1, a + b), f"√{a} + √{b} isn't √({a} + {b}): roots don't add like that. Simplify each root first, then add the like roots."),
        (*_simplest(k, 2 * m), f"Only the numbers in front add: {rp} + {rq} = {ans}, just as {p}x + {q}x = {k}x. The √{m} stays as it is."),
        (_root_text(p * p + q * q, m), (p * p + q * q) * math.sqrt(m), f"√{big * big} is {big}, not {big * big}. Take the square root of each perfect square as it comes out."),
        (_root_text(p * q, m), p * q * math.sqrt(m), f"The numbers in front add: {p} + {q} = {k}, not {p} × {q}."),
        (_root_text(abs(p - q), m), abs(p - q) * math.sqrt(m), f"You subtracted. The two roots are added: {rp} + {rq} = {ans}."),
        (str(k), float(k), f"The √{m} is missing. It stays in the answer: {rp} + {rq} = {ans}."),
    ]

    def step(n: int, f: int) -> str:
        return f"√{n} is already in simplest form." if f == 1 else f"Simplify √{n}: {n} = {f * f} × {m}, so √{n} = {f}√{m}."

    return Problem(
        help="addrad",
        story=sc["story"],
        expr=f"√{a} + √{b}",
        ask="What is the total, in simplest form?",
        choices=_string_choices(ctx, ans, [(t, why, v) for t, v, why in wrong], k * math.sqrt(m)),
        solution=(step(a, p), step(b, q), f"Add the like roots: {rp} + {rq} = {ans} {sc['unit']}."),
        hint="Simplify each root first: which perfect square (4, 9, 16, 25) divides the number? Then add the numbers in front.",
    )


# Numbers in front, in tenths: 12 is 1.2. Every pair used multiplies to 10 or more.
_SCI_TENTHS = [12, 15, 20, 25, 30, 35, 40, 50, 60, 70, 80, 90]
_SCI_PAIRS = [(u, v) for u in _SCI_TENTHS for v in _SCI_TENTHS if u * v >= 1000]


@gen("exp", 3)
def scientific_product(ctx: Context) -> Problem:
    """(a × 10ᵐ)(b × 10ⁿ): multiply, add the exponents, then move the point back so 1 ≤ front < 10."""
    u, v = ctx.pick(_SCI_PAIRS)
    m, n = ctx.rand(3, 7), ctx.rand(2, 4)
    a, b = _num(u / 10), _num(v / 10)
    ab, c = _num(u * v / 100), _num(u * v / 1000)  # a × b is 10 or more, so the point moves: c = ab ÷ 10
    e = m + n + 1
    value = u * v / 1000 * 10.0**e

    def sci(front: str, power: int) -> str:
        return f"{front} × 10{sup(power)}"

    A, B, ans = sci(a, m), sci(b, n), sci(c, e)
    story = ctx.pick([
        f"The radar computer does {A} calculations a second. How many calculations does it do in {B} seconds?",
        f"Each radar sweep logs {A} echoes. How many echoes do {B} sweeps log?",
        f"A radar dish sends out {A} pulses an hour. How many pulses does it send in {B} hours?",
    ])
    added = (u + v) / 10  # the numbers in front added instead of multiplied
    added_text = sci(_num(added / 10), m + n + 1) if added >= 10 else sci(_num(added), m + n)
    wrong = [
        (sci(ab, m + n), f"That's the right size, but it isn't in scientific notation: {ab} isn't between 1 and 10.", value),
        (sci(c, m + n), f"Moving the point in {ab} one place left makes the number 10 times smaller, so add 1 to the exponent to make up for it.", value / 10),
        (sci(c, m + n - 1), f"When {ab} becomes {c}, the exponent goes up by 1, not down.", value / 100),
        (sci(ab, e), f"You added 1 to the exponent but left {ab} as it was. Moving the point to make {c} and adding 1 go together.", value * 10),
        (sci(c, m * n + 1), f"10{sup(m)} × 10{sup(n)} is 10{sup(m + n)}: multiplying powers of 10 adds the exponents.", value * 10.0 ** (m * n - m - n)),
        (added_text, f"You added {a} and {b}. The numbers in front multiply: {a} × {b} = {ab}.", added * 10.0 ** (m + n)),
    ]
    return Problem(
        help="sciprod",
        story=story,
        expr=f"({A}) × ({B})",
        ask="What is the answer, in scientific notation?",
        choices=_string_choices(ctx, ans, wrong, value, same_value_ok=True),
        solution=(
            f"Multiply the numbers in front: {a} × {b} = {ab}.",
            f"Add the exponents: 10{sup(m)} × 10{sup(n)} = 10{sup(m + n)}. So far: {sci(ab, m + n)}.",
            f"{ab} isn't between 1 and 10. Move the point one place left and add 1 to the exponent: {ans}.",
        ),
        hint="Multiply the numbers in front, add the exponents, then move the point so the number in front is between 1 and 10.",
    )


@gen("exp", 3)
def solve_for_exponent(ctx: Context) -> Problem:
    """start × baseⁿ = end: find n, then the distance or time that many halvings (or doublings) take."""
    fading = bool(ctx.rand(0, 1))
    if fading:  # a signal halving with distance
        base, n = 2, ctx.rand(2, 5)
        end = ctx.pick([5, 10, 15, 20, 25, 30, 40, 50, 75, 100])
        start = end * 2**n
        k, unit = ctx.pick([20, 40, 50, 100, 150]), "meters"
        times, each, change = "halvings", "halving", "weaker"
        story = ctx.pick([
            f"A sonar ping leaves the ship at {start:,} units of strength and loses half its strength every {k} meters.",
            f"A distress beacon's signal is {start:,} units strong at the beacon, and it loses half its strength every {k} meters through the water.",
        ])
        ask = f"How far out has it faded to {end} units, in meters?"
        expr = f"{start:,} × (½){sup('n')} = {end}"
        ratio_line = f"How many times weaker? {start:,} ÷ {end} = {2**n}."
        steps = [start // 2**i for i in range(n + 1)]
        past = f"after {n + 1} halvings it's down to {_fmt(end / 2)} units"
        short = f"after {n - 1} halvings it's still {end * 2} units"
        linear = (start - end) / (start / 2) * k
        linear_why = f"It doesn't lose the same amount every {k} meters: it loses half of what is left, so less each time."
    else:  # something doubling or tripling over time
        base = ctx.pick([2, 3])
        n = ctx.rand(3, 6) if base == 2 else ctx.rand(2, 4)
        start = ctx.pick([3, 4, 5, 6, 8, 10, 12, 15, 20, 25])
        end = start * base**n
        k, unit = ctx.rand(2, 6), ctx.pick(["hours", "days", "weeks"])
        grows = "doubles" if base == 2 else "triples"
        times, each = ("doublings", "doubling") if base == 2 else ("triplings", "tripling")
        change = "bigger"
        story, ask = ctx.pick([
            (f"A barnacle colony on the hull covers {start} square inches, and it {grows} every {k} {unit}.",
             f"In how many {unit} will it cover {end:,} square inches?"),
            (f"{start} sailors have heard a rumor, and the number who have heard it {grows} every {k} {unit}.",
             f"In how many {unit} will {end:,} sailors have heard it?"),
            (f"Algae on the radar dome covers {start} square inches, and it {grows} every {k} {unit}.",
             f"In how many {unit} will it cover {end:,} square inches?"),
        ])
        expr = f"{start} × {base}{sup('n')} = {end:,}"
        ratio_line = f"How many times bigger? {end:,} ÷ {start} = {base**n}."
        steps = [start * base**i for i in range(n + 1)]
        past = f"after {(n + 1) * k} {unit} there would be {end * base:,}"
        short = f"after {(n - 1) * k} {unit} there are only {end // base:,}"
        linear = (end - start) / (start * (base - 1)) * k
        linear_why = f"It doesn't grow by the same amount every {k} {unit}: it {grows}, so it grows by more each time."
    ratio = base**n
    answer = n * k
    mistakes = [
        (n, f"{n} is the number of {times}. Each one takes {k} {unit}, so multiply: {n} × {k}."),
        ((n + 1) * k, f"That's one {each} too many: {past}."),
        ((n - 1) * k, f"That's one {each} too few: {short}."),
        (ratio * k, f"{ratio} is how many times {change} it gets, not how many {times}. {ratio} = {base}{sup(n)}, so there are {n}."),
        (ratio // base * k, f"You divided {ratio} by {base} just once. Count how many {base}s multiply together to make {ratio}: {n} of them."),
        (_whole(linear), linear_why),
        (n + k, f"Multiply the {n} {times} by the {k} {unit} each one takes. Don't add them."),
    ]
    if not fading and start in (base, base * base, base**3):  # counting from 1 instead of the start
        j = round(math.log(start, base))
        mistakes.append(((n + j) * k, f"You counted from 1 instead of from {start}. Divide {end:,} by the {start} it starts at first."))
    return Problem(
        help="solvexp",
        story=story,
        expr=expr,
        ask=ask,
        choices=_numeric_choices(ctx, answer, mistakes),
        solution=(
            ratio_line,
            f"Count the {times}: {' → '.join(f'{s:,}' for s in steps)}. That's n = {n}.",
            f"Each one takes {k} {unit}: {n} × {k} = {answer} {unit}.",
        ),
        hint=f"Divide to see how many times {change} it gets, count the {times} that takes, then multiply by {k}.",
    )


@gen("exp", 3)
def power_of_a_product(ctx: Context) -> Problem:
    """(kxᵐ)ⁿ times or divided by xᵖ: the power goes to the number and the x, then add or subtract exponents."""
    k = ctx.pick([2, 3, 5])
    n = 2 if k == 5 else ctx.pick([2, 3])
    m = ctx.rand(2, 5)
    mn = m * n
    dividing = bool(ctx.rand(0, 1))
    p = ctx.rand(1, mn - 2) if dividing else ctx.rand(1, 6)
    E = mn - p if dividing else mn + p
    K = k**n

    def mono(coef: int, power: int) -> str:
        return f"{coef}x{sup(power) if power != 1 else ''}"

    def then(power: int) -> int:  # what multiplying or dividing by xᵖ does to an exponent
        return power - p if dividing else power + p

    ans = mono(K, E)
    op = "÷" if dividing else "·"
    xp = mono(1, p)[1:]
    wrong = [
        (mono(k, E), f"The {k} is inside the brackets, so the power {n} goes on it too: {k}{sup(n)} = {K}."),
        (mono(k * n, E), f"{k}{sup(n)} means {' × '.join([str(k)] * n)} = {K}, not {k} × {n}."),
        (mono(K, mn), f"That's ({mono(k, m)}){sup(n)}, but you haven't {'divided' if dividing else 'multiplied'} by {xp} yet."),
    ]
    for power, why in (
        (m + n, f"A power of a power multiplies the exponents: (x{sup(m)}){sup(n)} = x{sup(mn)}, not x{sup(m + n)}."),
        (m, f"The power {n} goes on the x as well: (x{sup(m)}){sup(n)} = x{sup(mn)}."),
    ):
        if then(power) > 0:
            wrong.append((mono(K, then(power)), why))
    if dividing:
        wrong.append((mono(K, mn + p), f"Dividing subtracts the exponents: {mn} − {p} = {E}."))
        if mn % p == 0 and mn // p > 1:
            wrong.append((mono(K, mn // p), f"Dividing subtracts the exponents, it doesn't divide them: {mn} − {p} = {E}."))
    else:
        wrong.append((mono(K, mn * p), f"Multiplying adds the exponents, it doesn't multiply them: {mn} + {p} = {E}."))
        wrong.append((mono(K, mn - p), f"Multiplying adds the exponents: {mn} + {p} = {E}."))
    story = ctx.pick([
        "The radar range formula has a power of a product in it. Simplify it.",
        "Signal strength in the radar equation comes down to the expression below. Simplify.",
        "The plotting computer needs this expression as a single power of x. Simplify it.",
    ])
    return Problem(
        help="powprod",
        story=story,
        expr=f"({mono(k, m)}){sup(n)} {op} {xp}",
        ask="Which is the simplified form?",
        choices=_string_choices(ctx, ans, wrong),
        solution=(
            f"Raise each part in the brackets to the power {n}: {k}{sup(n)} = {K} and (x{sup(m)}){sup(n)} = x{sup(mn)}.",
            f"{'Divide' if dividing else 'Multiply'} by {xp}: {'subtract' if dividing else 'add'} the exponents, {mn} {'−' if dividing else '+'} {p} = {E}.",
            f"Result: {ans}.",
        ),
        hint="The power outside the brackets goes on the number AND on the x. Then add exponents to multiply, subtract them to divide.",
    )


# Pairs of numbers in front, in tenths, whose quotient has at most two decimals and is under 1: 1.2 ÷ 4 = 0.3.
_SCI_QUOTIENTS = [(u, v) for u in _SCI_TENTHS for v in _SCI_TENTHS if u < v and u * 100 % v == 0]


@gen("exp", 3)
def scientific_quotient(ctx: Context) -> Problem:
    """(a × 10ᵐ) ÷ (b × 10ⁿ) with a < b: divide, subtract the exponents, then move the point so 1 ≤ front < 10."""
    u, v = ctx.pick(_SCI_QUOTIENTS)
    m, n = ctx.rand(7, 10), ctx.rand(2, 4)
    a, b, q, front = _num(u / 10), _num(v / 10), _num(u / v), _num(u * 10 / v)
    e = m - n - 1
    value = u / v * 10.0 ** (m - n)

    def sci(f: str, power: int) -> str:
        return f"{f} × 10{sup(power)}"

    A, B, ans = sci(a, m), sci(b, n), sci(front, e)
    story = ctx.pick([
        f"The fleet burned {A} gallons of fuel in {B} hours. How many gallons an hour is that?",
        f"The radar logged {A} echoes in {B} sweeps. How many echoes a sweep is that, on average?",
        f"A reactor delivers {A} joules, shared equally among {B} laser shots. How many joules does each shot get?",
    ])
    wrong = [
        (sci(q, m - n), f"That's the right size, but it isn't in scientific notation: {q} isn't between 1 and 10.", value),
        (sci(front, m - n), f"Moving the point in {q} one place right makes the number 10 times bigger, so take 1 off the exponent to make up for it.", value * 10),
        (sci(front, m - n + 1), f"When {q} becomes {front}, the exponent goes down by 1, not up.", value * 100),
        (sci(front, m + n - 1), f"10{sup(m)} ÷ 10{sup(n)} is 10{sup(m - n)}: dividing powers of 10 subtracts the exponents.", value * 10.0 ** (2 * n)),
        (sci(front, e - 1), f"{a} ÷ {b} is {q}, not {_num(u / (v * 10))}: check by multiplying back, {q} × {b} = {a}.", value / 10),
        (sci(q, e), f"You took 1 off the exponent but left {q} as it was. Moving the point to make {front} and taking 1 off go together.", value / 10),
    ]
    if m % n == 0 and m // n - 1 != e:
        wrong.append((sci(front, m // n - 1), f"Dividing powers of 10 subtracts the exponents, it doesn't divide them: 10{sup(m)} ÷ 10{sup(n)} = 10{sup(m - n)}.",
                      value * 10.0 ** (m // n - m + n)))
    if v * 100 % u == 0:
        wrong.append((sci(_num(v / u), n - m), f"You divided the wrong way round: it's {a} ÷ {b}, and 10{sup(m)} ÷ 10{sup(n)}.", v / u * 10.0 ** (n - m)))
    return Problem(
        help="sciquot",
        story=story,
        expr=f"({A}) ÷ ({B})",
        ask="What is the answer, in scientific notation?",
        choices=_string_choices(ctx, ans, wrong, value, same_value_ok=True),
        solution=(
            f"Divide the numbers in front: {a} ÷ {b} = {q}.",
            f"Subtract the exponents: 10{sup(m)} ÷ 10{sup(n)} = 10{sup(m - n)}. So far: {sci(q, m - n)}.",
            f"{q} isn't between 1 and 10. Move the point one place right and take 1 off the exponent: {ans}.",
        ),
        hint="Divide the numbers in front, subtract the exponents, then move the point so the number in front is between 1 and 10.",
    )


# ---------------- Reactor · Exponentials ----------------
#
# Written for this game (the browser game stops at doubling and halving): the
# fleet's new technology grows and decays exponentially. Plasma reactors warm
# up, laser capacitors charge, plasma stores and force fields fade. Every number
# is picked so the working comes out exactly by hand.

_T = sup("t")  # the power in y = a × bᵗ
_SECONDS = {"second": 1, "minute": 60, "hour": 3600, "day": 86400}


def _exact(x: Union[Number, Fraction]) -> str:
    """An exact decimal, never rounded, with thousands separators: Fraction(121, 100) -> "1.21", 1331 -> "1,331"."""
    f = Fraction(x)
    d = (Decimal(f.numerator) / Decimal(f.denominator)).normalize()
    return ("−" if d < 0 else "") + f"{abs(d):,f}"


def _clean(x: Union[Number, Fraction]) -> bool:
    """Does x have at most two decimals, so a choice can show it exactly?"""
    return 100 % Fraction(x).denominator == 0


def _exact_choices(ctx: Context, ans: Fraction, mistakes: Sequence[Mistake], allow_neg: bool = False) -> Choices:
    """:func:`_numeric_choices` for exact answers. A Fraction mistake with more than two decimals is
    left out; a float one (a division that doesn't come out) is shown rounded, as a player would give it."""
    usable = [(float(v), why) for v, why in mistakes if not (isinstance(v, Fraction) and not _clean(v))]
    return _numeric_choices(ctx, float(ans), usable, allow_neg)


def _pc(v: Union[Number, Fraction]) -> str:
    """A percent, as a choice shows it: 20 -> "20%", Fraction(8, 100) -> "0.08%"."""
    return _fmt(float(v)) + "%"


def _pc_choices(ctx: Context, pct: Fraction, wrong: Sequence[tuple]) -> Choices:
    """Percent choices, balanced around the answer by value: ``wrong`` holds (value, why) pairs."""
    return _string_choices(ctx, _pc(pct), [(_pc(v), why, float(v)) for v, why in wrong], float(pct))


def _units(n: int, unit: str) -> str:
    """'1 hour', '3 hours'."""
    return f"{n} {unit}" + ("" if n == 1 else "s")


def _every(n: int, unit: str) -> str:
    """'every hour', 'every 3 hours'."""
    return f"every {unit}" if n == 1 else f"every {n} {unit}s"


def _all(k: int) -> str:
    """'both' (hours), 'all 3' (hours)."""
    return "both" if k == 2 else f"all {k}"


def _times(n: int) -> str:
    """'once', 'twice', 'three times'..."""
    return {1: "once", 2: "twice", 3: "three times", 4: "four times", 5: "five times", 6: "six times"}.get(n, f"{n} times")


def _root(x: Fraction, k: int) -> Fraction:
    """The exact k-th root of a fraction that has one: _root(Fraction(144, 100), 2) == Fraction(6, 5)."""

    def iroot(n: int) -> int:
        r = round(n ** (1 / k))
        for c in (r - 1, r, r + 1):
            if c >= 0 and c**k == n:
                return c
        raise ValueError(f"{n} has no whole {k}-th root")

    return Fraction(iroot(x.numerator), iroot(x.denominator))


def _point_slip(r: int) -> tuple[Fraction, str]:
    """r% with the point moved the wrong number of places, and why: 5% read as 0.5, 20% as 0.02."""
    p = Fraction(r, 100)
    if r % 10:
        return p * 10, f"{r}% is {_exact(p)}, not {_exact(p * 10)}: move the point two places, not one."
    return p / 10, f"{r}% is {_exact(p)}, not {_exact(p / 10)} (that would be {r // 10}%)."


@gen("rx", 1)
def growth_factor(ctx: Context) -> Problem:
    """The factor for a percent rate: +15% an hour multiplies by 1.15, −20% a cycle by 0.8."""
    ship = _fleet_ship(ctx).name
    r = ctx.pick([4, 5, 6, 8, 10, 12, 15, 20, 25, 30, 40])
    p = Fraction(r, 100)
    ps = _exact(p)
    slip, slip_why = _point_slip(r)
    grow = bool(ctx.rand(0, 1))
    if grow:
        b = 1 + p
        bs = _exact(b)
        story, what, per = ctx.pick([
            (f"{ship}'s new plasma reactor is warming up, and its output grows {r}% every hour.", "output", "hour"),
            (f"The laser capacitors on {ship} are charging: the charge in them grows {r}% every second.", "charge", "second"),
            (f"{ship}'s force field is powering up, and its strength grows {r}% every minute.", "strength", "minute"),
        ])
        mistakes = [
            (p, f"{ps} is the rate, {r}% as a decimal. The {what} keeps all of itself and gains {r}% more: 1 + {ps} = {bs}."),
            (1 - p, f"{_exact(1 - p)} is the factor for a {r}% loss. Growing {r}% means multiplying by 1 + {ps}."),
            (r, f"{r} is the percent. Write it as a decimal, {ps}, and add it to 1."),
            (100 + r, f"{100 + r}% is right, but a factor is written as a decimal: {100 + r}% = {bs}."),
            (1 + slip, slip_why),
        ]
        solution = (
            f"{r}% as a decimal: {r} ÷ 100 = {ps}.",
            f"The {what} keeps all of itself (1) and gains {ps} more: 1 + {ps} = {bs}.",
            f"So each {per} the {what} is multiplied by {bs}.",
        )
        hint = f"Write {r}% as a decimal, then add it to 1."
    else:
        b = 1 - p
        bs = _exact(b)
        story, what, per = ctx.pick([
            (f"{ship}'s reserve store has sprung a leak: it loses {r}% of its plasma every day.", "plasma", "day"),
            (f"The coolant loop in {ship}'s reactor loses {r}% of its coolant every cycle.", "coolant", "cycle"),
            (f"Under fire, {ship}'s force field loses {r}% of its strength every second.", "strength", "second"),
        ])
        mistakes = [
            (p, f"{ps} is the part lost each {per}. The factor is the part that's left: 1 − {ps} = {bs}."),
            (1 + p, f"{_exact(1 + p)} is the factor for {r}% growth. Losing {r}% means multiplying by 1 − {ps}."),
            (100 - r, f"{100 - r}% is what's left, but a factor is written as a decimal: {100 - r}% = {bs}."),
            (r, f"{r} is the percent lost. As a decimal it's {ps}, and the factor is 1 − {ps} = {bs}."),
            (1 / float(1 + p), f"Dividing by {_exact(1 + p)} would undo a {r}% rise, but that isn't a {r}% loss. {100 - r}% is left, so multiply by {bs}."),
        ]
        if slip < 1:
            mistakes.append((1 - slip, slip_why))
        solution = (
            f"{r}% as a decimal: {r} ÷ 100 = {ps}.",
            f"What's left each {per} is 1 − {ps} = {bs} of the {what}.",
            f"So each {per} the {what} is multiplied by {bs}.",
        )
        hint = f"Write {r}% as a decimal, then take it away from 1."
    return Problem(
        help="pctfactor",
        story=story,
        expr=f"{'+' if grow else '−'}{r}% each {per}",
        ask=f"What is the {'growth' if grow else 'decay'} factor: the number the {what} is multiplied by each {per}?",
        choices=_exact_choices(ctx, b, mistakes),
        solution=solution,
        hint=hint,
    )


@gen("rx", 1)
def factor_from_readings(ctx: Context) -> Problem:
    """The factor from two readings one step apart: new ÷ old."""
    ship = _fleet_ship(ctx).name
    while True:
        y0 = ctx.pick([200, 250, 400, 500, 800])
        r = ctx.pick([5, 10, 12, 15, 20, 25, 30, 40])
        if y0 * r % 100 == 0:
            break
    p = Fraction(r, 100)
    grow = bool(ctx.rand(0, 1))
    b = 1 + p if grow else 1 - p
    y1 = int(y0 * b)
    d = abs(y1 - y0)
    bs, ratio = _exact(b), f"{y1} ÷ {y0}"
    if grow:
        story, what, per, unit = ctx.pick([
            (f"At 0900 {ship}'s plasma reactor was putting out {y0} MW, and at 1000 it was putting out {y1} MW. While it warms up, its output is multiplied by the same number every hour.", "output", "hour", "MW"),
            (f"The charge in {ship}'s laser capacitors reads {y0} kJ, and one second later {y1} kJ. While they charge, the charge is multiplied by the same number every second.", "charge", "second", "kJ"),
        ])
        mistakes = [
            (d, f"{d} {unit} is how much it went up. The factor is how many times bigger it got: {ratio}."),
            (p, f"{_exact(p)} is the rate, {r}% growth. The factor also counts the {y0} that was already there: 1 + {_exact(p)} = {bs}."),
            (y0 / y1, f"You divided the wrong way round. The factor is new ÷ old: {ratio}."),
            (1 + Fraction(d, 100), f"{d} more isn't {d}% more: {d} out of {y0} is {r}%."),
            (1 + d / y1, f"You measured the {d} against {y1}, the new reading. Measure it against {y0}, where it started: {ratio} = {bs}."),
            (100 * b, f"{_exact(100 * b)}% is right, but a factor is written as a decimal: {bs}."),
            (1 - p, f"{_exact(1 - p)} would make it smaller, but it went up from {y0} to {y1}. The factor is {ratio}."),
        ]
    else:
        story, what, per, unit = ctx.pick([
            (f"{ship}'s reserve store held {y0} units of plasma yesterday and holds {y1} units today. Stored plasma decays by the same factor every day.", "plasma", "day", "units"),
            (f"{ship}'s force field read {y0} units of strength, and one minute later {y1} units. Under fire it fades by the same factor every minute.", "strength", "minute", "units"),
        ])
        mistakes = [
            (d, f"{d} {unit} is how much it went down. The factor is new ÷ old: {ratio}."),
            (p, f"{_exact(p)} is the part lost, {r}%. The factor is the part that's left: {ratio} = {bs}."),
            (y0 / y1, f"You divided the wrong way round. The factor is new ÷ old: {ratio}."),
            (1 - d / y1, f"You measured the {d} lost against {y1}, the new reading. Measure it against {y0}, where it started: {ratio} = {bs}."),
            (100 * b, f"{_exact(100 * b)}% is right, but a factor is written as a decimal: {bs}."),
            (1 + p, f"{_exact(1 + p)} would make it bigger, but it went down from {y0} to {y1}. The factor is {ratio}."),
        ]
        if d < 100:
            mistakes.append((1 - Fraction(d, 100), f"{d} less isn't {d}% less: {d} out of {y0} is {r}%."))
    return Problem(
        help="newold",
        story=story,
        expr=f"y(0) = {y0},   y(1) = {y1}",
        ask=f"What is the {'growth' if grow else 'decay'} factor b: the number the {what} is multiplied by each {per}?",
        choices=_exact_choices(ctx, b, mistakes),
        solution=(
            f"The factor is new ÷ old: {ratio} = {bs}.",
            f"Check: {y0} × {bs} = {y1} ✓",
            f"So the {what} {'grows' if grow else 'drops'} {r}% each {per}.",
        ),
        hint="Divide the later reading by the earlier one.",
    )


@gen("rx", 1)
def read_exponential(ctx: Context) -> Problem:
    """The percent rate in y = a × bᵗ: 0.9 is a 10% drop, 1.08 an 8% rise."""
    ship = _fleet_ship(ctx).name
    a = ctx.pick([200, 300, 400, 500, 600, 800])
    grow = bool(ctx.rand(0, 1))
    # Two-digit rates: "6%" among "0.94%", "0.06%" and "94%" would stand out as the shortest choice.
    r = ctx.pick([10, 12, 15, 20, 25, 30, 40, 50] if grow else [10, 12, 15, 20, 25, 30, 40])
    p = Fraction(r, 100)
    b = 1 + p if grow else 1 - p
    bs, ps, left = _exact(b), _exact(p), _exact(100 * b)
    first = _exact(a * p)
    if grow:
        story, what, per, unit = ctx.pick([
            (f"The output of {ship}'s plasma reactor, in MW, t hours after it is switched on:", "output", "hour", "MW"),
            (f"The charge in {ship}'s laser capacitors, in kJ, t seconds after they start charging:", "charge", "second", "kJ"),
        ])
        wrong = [
            (100 * b, f"{bs} means {left}% of the {per} before: all of it plus {r}% more. So it grows {r}%."),
            (b, f"{bs} as a percent is {left}%, not {bs}%: all of it plus {r}% more. So it grows {r}%."),
            (p, f"{bs} − 1 = {ps} is the growth as a decimal. As a percent that's {r}%."),
            (10 * p, f"{bs} − 1 = {ps}, and {ps} is {r}%, not {_exact(10 * p)}%: move the point two places."),
            (a * p, f"{a} × {ps} = {first} {unit} is how much it grows in the first {per}. That's an amount; as a share of {a} it's {r}%."),
        ]
        solution = (
            f"In y = a × b{_T}, b = {bs} is the factor: each {per} the {what} is {left}% of what it was.",
            f"It grows {bs} − 1 = {ps} each {per}.",
            f"{ps} = {r}%.",
        )
        hint = "The number with the power t is the factor. Take 1 away from it and write what's left as a percent."
    else:
        story, what, per, unit = ctx.pick([
            (f"The plasma left in {ship}'s reserve store, in units, t days after it was filled:", "plasma", "day", "units"),
            (f"The strength of {ship}'s force field, in units, t seconds after a hit:", "strength", "second", "units"),
        ])
        wrong = [
            (100 * b, f"{bs} is the part that's left each {per}: {left}%. So it drops 100% − {left}% = {r}%."),
            (b, f"{bs} as a percent is {left}%, not {bs}%. That's the part left, so it drops {r}%."),
            (p, f"1 − {bs} = {ps} is the drop as a decimal. As a percent that's {r}%."),
            (10 * p, f"1 − {bs} = {ps}, and {ps} is {r}%, not {_exact(10 * p)}%: move the point two places."),
            (a * p, f"{a} × {ps} = {first} {unit} is how much it loses in the first {per}. That's an amount; as a share of {a} it's {r}%."),
        ]
        solution = (
            f"In y = a × b{_T}, b = {bs} is the factor: each {per}, {left}% of the {what} is left.",
            f"It drops 1 − {bs} = {ps} each {per}.",
            f"{ps} = {r}%.",
        )
        hint = "The number with the power t is the factor. Take it away from 1 and write the result as a percent."
    return Problem(
        help="readexp",
        story=story,
        expr=f"y = {a} × {bs}{_T}",
        ask=f"By what percent does the {what} {'grow' if grow else 'drop'} each {per}?",
        choices=_pc_choices(ctx, Fraction(r), wrong),
        solution=solution,
        hint=hint,
    )


def _half_life_story(ctx: Context, ship: str, S0: int, h: int, unit: str, T: int, tunit: str) -> tuple[str, str]:
    """Something with a half-life, and the question: (story, ask)."""
    hl, after = _units(h, unit), _units(T, tunit)
    return ctx.pick([
        (f"{ship} carries {S0:,} units of plasma in her reserve store. Stored plasma has a half-life of {hl}.",
         f"How many units of plasma are left after {after}?"),
        (f"A spent plasma cell taken out of {ship}'s reactor gives off {S0:,} units of radiation. The cell has a half-life of {hl}.",
         f"How many units of radiation does it give off after {after}?"),
        (f"{ship}'s force field is switched off with {S0:,} kJ still stored in it. The stored energy has a half-life of {hl}.",
         f"How many kJ are still stored after {after}?"),
    ])


def _halvings(S0: int, n: int) -> str:
    """'800 → 400 → 200'"""
    return " → ".join(_exact(Fraction(S0, 2**k)) for k in range(n + 1))


@gen("rx", 1)
def half_life(ctx: Context) -> Problem:
    """What is left after one or two half-lives."""
    ship = _fleet_ship(ctx).name
    h, unit = ctx.pick([(1, "hour"), (2, "hour"), (3, "hour"), (4, "hour"), (6, "hour"), (12, "hour"), (2, "day"),
                        (3, "day"), (5, "day"), (10, "minute"), (20, "minute"), (30, "minute"), (5, "second")])
    n = 2 if h == 1 else ctx.rand(1, 2)
    T = n * h
    S0 = ctx.pick([160, 240, 320, 400, 480, 640, 800, 960, 1200, 1600])
    A = Fraction(S0, 2**n)
    story, ask = _half_life_story(ctx, ship, S0, h, unit, T, unit)
    hl, after, times = _units(h, unit), _units(T, unit), _times(n)
    if n == 2:
        mistakes = [(S0 // 2, f"That's after one half-life ({hl}). After {after} it has halved twice.")]
    else:
        mistakes = [(S0, f"{S0:,} is what there was at the start. After one half-life ({hl}), half of it has gone.")]
    mistakes += [
        (Fraction(S0, 2 ** (n + 1)), f"That's one halving too many: {after} is {'one half-life' if n == 1 else 'two half-lives'}."),
        (S0 - A, f"{_exact(S0 - A)} is how much has decayed. The question asks how much is left."),
        (n, f"{n} is the number of half-lives. Now halve {S0:,} {times}."),
        (S0 * 2**n, "It decays, so halve it; don't double it."),
    ]
    if h > 1 and T <= 6:
        mistakes.append((Fraction(S0, 2**T), f"You halved it {_every(1, unit)}. It halves once {_every(h, unit)}, so {times} in {after}."))
    if n == 2:
        mistakes.append((0, f"It doesn't lose the same {S0 // 2:,} {_every(h, unit)}. Each half-life takes away half of what is LEFT."))
    return Problem(
        help="halflife",
        story=story,
        expr=f"{S0:,} × (½)ⁿ",
        note="n = the number of half-lives",
        ask=ask,
        choices=_exact_choices(ctx, A, mistakes),
        solution=(
            f"Number of half-lives: {T} ÷ {h} = {n}.",
            f"Halve {times}: {_halvings(S0, n)}.",
            f"{_exact(A)} left after {after}.",
        ),
        hint=f"How many half-lives fit into {after}? Halve {S0:,} that many times.",
    )


# (half-life, its unit, time, its unit): the time is 3 to 5 half-lives once it's in the half-life's units
_HALF_LIVES_CONVERT = [
    (20, "minute", 1, "hour"), (15, "minute", 1, "hour"), (12, "minute", 1, "hour"), (30, "minute", 2, "hour"),
    (40, "minute", 2, "hour"), (45, "minute", 3, "hour"), (20, "second", 1, "minute"), (15, "second", 1, "minute"),
    (12, "second", 1, "minute"), (30, "second", 2, "minute"), (6, "hour", 1, "day"), (8, "hour", 1, "day"),
]


@gen("rx", 2)
def half_life_periods(ctx: Context) -> Problem:
    """What is left after three to five half-lives, sometimes with the time in bigger units than the half-life."""
    ship = _fleet_ship(ctx).name
    convert = bool(ctx.rand(0, 1))
    if convert:
        h, unit, T, tunit = ctx.pick(_HALF_LIVES_CONVERT)
    else:
        h, unit = ctx.pick([(2, "hour"), (3, "hour"), (4, "hour"), (5, "hour"), (6, "hour"), (8, "hour"), (12, "hour"),
                            (2, "day"), (3, "day"), (10, "minute"), (20, "minute"), (30, "minute"), (15, "second")])
        T, tunit = h * ctx.rand(3, 5), unit
    Tc = T * _SECONDS[tunit] // _SECONDS[unit]  # the time in the half-life's units
    n = Tc // h
    S0 = ctx.pick([320, 480, 640, 800, 960, 1600, 3200])
    A = Fraction(S0, 2**n)
    story, ask = _half_life_story(ctx, ship, S0, h, unit, T, tunit)
    hl, after = _units(h, unit), _units(T, tunit)
    mistakes = []
    if convert:
        mistakes.append((Fraction(S0, 2**T), f"You halved once per {tunit}, but it halves once {_every(h, unit)}: {Tc} ÷ {h} = {n}, so {_times(n)} in {after}."))
    else:
        if h != n and h <= 8:
            mistakes.append((Fraction(S0, 2**h), f"You halved {h} times, but {hl} is how long ONE halving takes. There are {T} ÷ {h} = {n} half-lives."))
        if T <= 8:
            mistakes.append((Fraction(S0, 2**T), f"You halved it {_every(1, unit)}. It halves once {_every(h, unit)}: {_times(n)} in {after}."))
    mistakes += [
        (n, f"{n} is the number of half-lives. Now halve {S0:,} {_times(n)}."),
        (Fraction(S0, 2 ** (n - 1)), f"That's one halving too few: {after} is {n} half-lives."),
        (Fraction(S0, 2 ** (n + 1)), f"That's one halving too many: {after} is {n} half-lives."),
        (_whole(S0 / (2 * n)), f"Halving {_times(n)} isn't dividing by 2 × {n}. Halve, then halve again: {n} halvings in all."),
        (_whole(S0 / n), f"You divided by {n}. Each half-life halves it: divide by 2, {_times(n)}."),
        (S0 - A, f"{_exact(S0 - A)} is how much has decayed. The question asks how much is left."),
    ]
    count = f"Number of half-lives: {Tc} ÷ {h} = {n}."
    return Problem(
        help="halflife",
        story=story,
        expr=f"{S0:,} × (½)ⁿ",
        note="n = the number of half-lives",
        ask=ask,
        choices=_exact_choices(ctx, A, mistakes),
        solution=((f"Put the time in {unit}s: {after} = {Tc} {unit}s.",) if convert else ()) + (
            count,
            f"Halve {_times(n)}: {_halvings(S0, n)}.",
            f"{_exact(A)} left after {after}.",
        ),
        hint=(f"Put {after} into {unit}s first. Then count" if convert else "Count") + " the half-lives (time ÷ half-life) and halve that many times.",
    )


# (rate %, growing?, steps, starting amounts): every amount along the way is a whole number
_COMPOUND = [
    (10, True, 2, (100, 200, 300, 400, 500, 600, 800)),
    (10, True, 3, (1000,)),
    (20, True, 2, (100, 200, 250, 300, 400, 500)),
    (20, True, 3, (125, 250, 500)),
    (50, True, 2, (40, 60, 80, 100, 200)),
    (50, True, 3, (16, 40, 80)),
    (5, True, 2, (400, 800)),
    (25, True, 2, (64, 160, 320)),
    (10, False, 2, (200, 300, 400, 500, 800, 1000)),
    (10, False, 3, (1000,)),
    (20, False, 2, (100, 200, 250, 400, 500, 1000)),
    (20, False, 3, (125, 250, 500, 1000)),
    (25, False, 2, (64, 160, 320, 800)),
    (30, False, 2, (100, 200, 500)),
    (40, False, 2, (100, 500)),
]


@gen("rx", 2)
def repeated_percent(ctx: Context) -> Problem:
    """start × (1 ± rate)ⁿ, worked out step by step: 200 growing 10% an hour for 2 hours is 242, not 240."""
    ship = _fleet_ship(ctx).name
    r, up, n, starts = ctx.pick(_COMPOUND)
    a = ctx.pick(starts)
    p = Fraction(r, 100)
    f = 1 + p if up else 1 - p
    steps = [a * f**k for k in range(n + 2)]
    A = steps[n]
    fs, ps = _exact(f), _exact(p)
    if up:
        story, ask, what, per, unit = ctx.pick([
            (f"{ship}'s plasma reactor is putting out {a:,} MW, and while it warms up its output grows {r}% every hour.",
             f"What is the output after {n} hours, in MW?", "output", "hour", "MW"),
            (f"The laser capacitors on {ship} hold {a:,} kJ, and while they charge, the charge grows {r}% every second.",
             f"How much charge do they hold after {n} seconds, in kJ?", "charge", "second", "kJ"),
        ])
        mistakes = [
            (a + n * a * p, f"You added {r}% of {a:,} each {per}: {_exact(a * p)} every time. Each {per}'s {r}% is of the new, bigger amount, so multiply by {fs} each {per}."),
            (a * p**n, f"You multiplied by {ps}, the rate. Growing {r}% means multiplying by 1 + {ps} = {fs}."),
            (a * (1 - p) ** n, f"It grows, so multiply by {fs}, not {_exact(1 - p)}."),
            (A - a, f"{_exact(A - a)} {unit} is how much it grew. The question asks for the {what} after {n} {per}s."),
        ]
    else:
        story, ask, what, per, unit = ctx.pick([
            (f"{ship}'s reserve store holds {a:,} units of plasma, and it loses {r}% of its plasma every day.",
             f"How many units of plasma are left after {n} days?", "plasma", "day", "units"),
            (f"{ship}'s force field is at {a:,} units of strength, and under fire it loses {r}% of its strength every minute.",
             f"What is its strength after {n} minutes, in units?", "strength", "minute", "units"),
            (f"The coolant tank on {ship}'s reactor holds {a:,} liters, and a leak loses {r}% of what's in it every hour.",
             f"How many liters are left after {n} hours?", "coolant", "hour", "liters"),
        ])
        mistakes = [
            (a - n * a * p, f"You took {r}% of {a:,} off each {per}: {_exact(a * p)} every time. Each {per}'s {r}% is of what's left, so less comes off each time: multiply by {fs} each {per}."),
            (a * p**n, f"You multiplied by {ps}, the part lost. What's left each {per} is 1 − {ps} = {fs}."),
            (a * (1 + p) ** n, f"It shrinks, so multiply by {fs}, not {_exact(1 + p)}."),
            (a - A, f"{_exact(a - A)} {unit} is how much was lost. The question asks how much is left."),
        ]
    mistakes += [
        (steps[1], f"That's after 1 {per}. Multiply by {fs} once for each of the {n} {per}s."),
        (steps[n + 1], f"You multiplied by {fs} {_times(n + 1)}, but there are only {n} {per}s."),
        (a * f * n, f"{fs}{sup(n)} isn't {fs} × {n}. Multiply by {fs}, {_times(n)}."),
    ]
    if (a * f) ** n < 100_000:
        mistakes.append(((a * f) ** n, f"Only the {fs} gets the power {n}. Work out {fs}{sup(n)}, then multiply it by {a:,}."))
    return Problem(
        help="compound",
        story=story,
        expr=f"y = {a:,} × b{_T}",
        ask=ask,
        choices=_exact_choices(ctx, A, mistakes),
        solution=(
            f"The factor: 1 {'+' if up else '−'} {ps} = {fs}.",
            f"Multiply by {fs} once for each {per}: {' → '.join(_exact(s) for s in steps[: n + 1])}.",
            f"After {n} {per}s: {_exact(A)} {unit}.",
        ),
        hint=f"Find the factor first (1 {'+' if up else '−'} {ps}). Then multiply by it once for each {per}.",
    )


_EXP_TABLES = [  # (ratio, first values): every value up to t = 4 is a whole number
    (Fraction(2), (2, 3, 5, 6, 7, 9, 10, 12, 15, 25)),
    (Fraction(3), (1, 2, 4, 5, 10)),
    (Fraction(3, 2), (16, 32, 48, 64)),
    (Fraction(1, 2), (48, 80, 96, 160, 320, 480, 800)),
]


@gen("rx", 2)
def linear_or_exponential(ctx: Context) -> Problem:
    """Linear (same jump) or exponential (same ratio) from a table, and the next value."""
    ship = _fleet_ship(ctx).name
    story = ctx.pick([
        f"Engineers on {ship} log the output of an experimental plasma reactor, in MW, every hour.",
        f"{ship}'s crew logs the charge in a test laser capacitor, in kJ, every second.",
        f"{ship}'s quartermaster measures the plasma in a sealed test tank every day.",
        f"The strength of {ship}'s force field is logged every minute during a drill.",
    ])
    exponential = bool(ctx.rand(0, 1))
    if exponential:
        b, firsts = ctx.pick(_EXP_TABLES)
        start = ctx.pick(firsts)
        ys = [start * b**k for k in range(5)]
    elif ctx.rand(0, 3):  # going up
        d = ctx.pick([2, 3, 4, 5, 6, 7, 8, 9, 12, 15, 20, 25])
        start = d if ctx.rand(0, 3) == 0 else ctx.rand(2, 20)
        ys = [Fraction(start + d * k) for k in range(5)]
    else:
        d = -ctx.pick([5, 8, 10, 12, 15, 20, 25])
        start = ctx.pick([v for v in (60, 80, 90, 100, 120, 150, 200) if v + 4 * d > 0])
        ys = [Fraction(start + d * k) for k in range(5)]
    y0, y1, y2, y3, y4 = ys
    s0, s1, s2, s3, s4 = (_exact(y) for y in ys)
    jumps = [_exact(abs(v - u)) for u, v in zip(ys, ys[1:4])]
    if exponential:
        bs = _exact(b)
        if b > 1:
            mistakes = [
                (y3 + (y3 - y2), f"The jumps ({', '.join(jumps)}) keep changing, so it isn't linear. Each value is {bs} times the one before: {s3} × {bs} = {s4}."),
                (y3 + (y1 - y0), f"Adding {jumps[0]} only fits the first step; the jumps keep growing ({', '.join(jumps)}). Each value is {bs} times the one before."),
                (y3 + b, f"Each value is {bs} TIMES the one before, not {bs} more."),
                (y3 * b * b, f"That's t = 5: you multiplied by {bs} twice. t = 4 is one step after t = 3."),
            ]
            if y3 * (y3 - y2) < 10_000:
                mistakes.append((y3 * (y3 - y2), f"{jumps[2]} is the jump from {s2} to {s3}, not the ratio. The ratio is {s3} ÷ {s2} = {bs}."))
        else:
            mistakes = [
                (y3 + (y3 - y2), f"The drops ({', '.join(jumps)}) keep shrinking, so it isn't linear. Each value is half the one before: {s3} × {bs} = {s4}."),
                (y3 * 2, "It's shrinking, so each value is 0.5 times the one before, not 2 times."),
                (y3 / 4, "That's t = 5: you halved twice. t = 4 is one step after t = 3."),
                (y3 - 2, "Each value is HALF the one before, not 2 less."),
            ]
        solution = (
            f"Jumps: {', '.join(jumps)}. They aren't all the same, so it isn't linear.",
            f"Ratios: {s1} ÷ {s0} = {bs}, {s2} ÷ {s1} = {bs}, {s3} ÷ {s2} = {bs}. All the same, so it's exponential.",
            f"Next: {s3} × {bs} = {s4}.",
        )
    elif d > 0:
        mistakes = [
            (y3 * d, f"The values go up by {d} each time; they aren't multiplied by {d}."),
            (_whole(y3 * y3 / y2), f"The ratios ({s1} ÷ {s0}, {s2} ÷ {s1}...) aren't all the same, so it isn't exponential. The jumps are all {d}: {s3} + {d} = {s4}."),
            (y3 + 2 * d, f"That's t = 5: you added {d} twice. t = 4 is one step after t = 3."),
            (y3 + 1, f"t goes up by 1 each step, but y goes up by {d}."),
        ]
        if y0 == d:
            mistakes.append((2 * y3, f"{s1} is double {s0}, but {s2} isn't double {s1}. The jumps are all {d}, so it's linear: add {d}."))
        else:
            mistakes.append((y3 + y0, f"{s0} is where it starts. Each step adds {s1} − {s0} = {d}."))
    else:
        D = -d
        mistakes = [
            (_whole(y3 * y3 / y2), f"The ratios ({s1} ÷ {s0}, {s2} ÷ {s1}...) aren't all the same, so it isn't exponential. The drops are all {D}: {s3} − {D} = {s4}."),
            (y3 + D, f"It goes down by {D} each time, so take {D} away."),
            (y3 - 1, f"t goes up by 1 each step, but y goes down by {D}."),
            (y3 - 2 * D, f"That's t = 5: you took {D} away twice. t = 4 is one step after t = 3."),
        ]
    if not exponential:
        solution = (
            f"Jumps: {s1} − {s0}, {s2} − {s1}, {s3} − {s2} are all {_lead(d)}. The same every time, so it's linear.",
            f"Next: {s3} {_sgn(d)} = {s4}.",
        )
    return Problem(
        help="linexp",
        story=story,
        expr=f"t = 0, 1, 2, 3, 4\ny = {s0}, {s1}, {s2}, {s3}, ?",
        ask="Is the pattern linear or exponential? Use it to find y at t = 4.",
        choices=_exact_choices(ctx, y4, mistakes),
        solution=solution,
        hint="Check the jumps first: the same jump every time means linear. If they change, check the ratios: the same multiplier means exponential.",
    )


@gen("rx", 2)
def exponential_model(ctx: Context) -> Problem:
    """Write y = a × bᵗ from a starting amount and a percent rate."""
    ship = _fleet_ship(ctx).name
    while True:
        a = ctx.pick([40, 50, 60, 80, 120, 150, 200, 250, 300, 400, 500, 600, 800])
        r = ctx.pick([2, 3, 4, 5, 6, 8, 10, 12, 15, 20, 25, 30])
        if a * r % 100 == 0:
            break
    p = Fraction(r, 100)
    grow = bool(ctx.rand(0, 1))
    b = 1 + p if grow else 1 - p
    A, bs, ps, step = _exact(a), _exact(b), _exact(p), _exact(a * p)
    slip, slip_why = _point_slip(r)

    def model(front: str, factor: str) -> str:
        return f"y = {front} × {factor}{_T}"

    ans = model(A, bs)
    if grow:
        story, what, per, unit = ctx.pick([
            (f"{ship}'s plasma reactor starts at {A} MW, and while it warms up its output grows {r}% every hour.", "output", "hour", "MW"),
            (f"The charge in {ship}'s laser capacitors starts at {A} kJ and grows {r}% every second while they charge.", "charge", "second", "kJ"),
        ])
        wrong = [
            (model(A, ps), f"{ps} is the rate. Each {per} the {what} keeps all of itself and gains {r}%, so b = 1 + {ps} = {bs}."),
            (model(A, _exact(1 - p)), f"{_exact(1 - p)} would take {r}% away each {per}. It grows, so b = 1 + {ps} = {bs}."),
            (f"y = {A} + {step}t", f"That adds the same {step} {unit} every {per}. Growing {r}% adds more each {per}, because it's {r}% of more: multiply by {bs} instead."),
            (model(A, _exact(1 + slip)), slip_why),
        ]
    else:
        story, what, per, unit = ctx.pick([
            (f"{ship}'s reserve store starts at {A} units of plasma and loses {r}% of its plasma every day.", "plasma", "day", "units"),
            (f"{ship}'s force field starts at {A} units of strength and loses {r}% of its strength every minute under fire.", "strength", "minute", "units"),
        ])
        wrong = [
            (model(A, ps), f"{ps} is the part lost each {per}. The part that's left is b = 1 − {ps} = {bs}."),
            (model(A, _exact(1 + p)), f"{_exact(1 + p)} would add {r}% each {per}. It shrinks, so b = 1 − {ps} = {bs}."),
            (f"y = {A} − {step}t", f"That takes the same {step} {unit} away every {per}. Losing {r}% takes less each {per}, because it's {r}% of less: multiply by {bs} instead."),
        ]
        if slip < 1:
            wrong.append((model(A, _exact(1 - slip)), slip_why))
    wrong += [
        (model(_exact(a * b), bs), f"{_exact(a * b)} is the {what} after 1 {per}. At t = 0 it's {A}."),
        (f"y = {bs} × {A}{_T}", f"The start, {A}, goes in front. The factor, {bs}, is what gets the power t."),
        (model(A, str(100 + r if grow else 100 - r)), f"{100 + r if grow else 100 - r}% is right, but the factor is written as a decimal: {bs}."),
        (model(A, str(r)), f"{r}% as a decimal is {ps}, so the factor is 1 {'+' if grow else '−'} {ps} = {bs}, not {r}."),
    ]
    return Problem(
        help="expmodel",
        story=story,
        expr=f"y = ?   (t in {per}s)",
        ask=f"Which equation gives the {what}, y, after t {per}s?",
        choices=_string_choices(ctx, ans, wrong),
        solution=(
            f"The starting amount (t = 0) is {A}: that's a.",
            f"Each {per} it {'gains' if grow else 'loses'} {r}%, so b = 1 {'+' if grow else '−'} {ps} = {bs}.",
            ans,
        ),
        hint="The start goes in front. The factor (1 + rate or 1 − rate, as a decimal) gets the power t.",
    )


# (first t, second t, factor b, starting amounts a): every reading is a whole number, and so is the
# slope of the straight line through them when the first reading is at t = 0
_TWO_POINTS = [
    (0, 2, Fraction(2), (4, 6, 10, 20)),
    (0, 2, Fraction(3), (2, 4, 5, 10)),
    (0, 2, Fraction(4), (2, 6, 10)),
    (0, 2, Fraction(5), (2, 3, 4)),
    (0, 2, Fraction(1, 2), (40, 80, 200, 400, 800)),
    (0, 3, Fraction(2), (3, 6, 12)),
    (0, 3, Fraction(3), (6, 12)),
    (0, 3, Fraction(1, 2), (96, 192, 480, 960)),
    (1, 3, Fraction(2), (3, 5, 10)),
    (1, 3, Fraction(3), (2, 4, 5)),
    (1, 3, Fraction(1, 2), (160, 320, 400, 800)),
]


@gen("rx", 3)
def model_from_two_points(ctx: Context) -> Problem:
    """y = a × bᵗ through two readings: divide, take the root for b, work back to t = 0 for a."""
    ship = _fleet_ship(ctx).name
    t1, t2, b, starts = ctx.pick(_TWO_POINTS)
    a = ctx.pick(starts)
    y1, y2 = a * b**t1, a * b**t2
    k = t2 - t1
    R = y2 / y1
    grow = b > 1
    if grow:
        story, what, per = ctx.pick([
            (f"Two readings of {ship}'s plasma reactor output, in MW, t hours after it was switched on:", "output", "hour"),
            (f"Two readings of the charge in {ship}'s laser capacitors, in kJ, t seconds after they started charging:", "charge", "second"),
        ])
    else:
        story, what, per = ctx.pick([
            (f"Two readings of the plasma in {ship}'s reserve store, t days after it was filled:", "plasma", "day"),
            (f"Two readings of {ship}'s force-field strength, t minutes after a hit:", "strength", "minute"),
        ])

    def model(front: Fraction, factor: Fraction) -> str:
        return f"y = {_exact(front)} × {_exact(factor)}{_T}"

    ans = model(a, b)
    A, B, Rs, bb = _exact(a), _exact(b), _exact(R), " × ".join(["b"] * k)
    wrong = [(model(a, R), f"{Rs} is what it's multiplied by over {_all(k)} {per}s. Each {per} it's multiplied by b, and {bb} = {Rs}, so b = {B}.")]
    if _clean(R / k):
        wrong.append((model(a, R / k), f"{Rs} ÷ {k} shares the change out as if it were added. It's multiplied: {bb} = {Rs}, so b = {B}."))
    if not grow:
        wrong.append((model(a, 1 / b), f"It's shrinking, so b is less than 1: {_exact(y2)} ÷ {_exact(y1)} = {Rs}, and b = {B}."))
    if t1 == 0:
        wrong.append((model(y2, b), f"{_exact(y2)} is the reading at t = {t2}. a is the reading at t = 0: {A}."))
        m = (y2 - y1) / k
        if m.denominator == 1:
            wrong.append((f"y = {A} {'+' if m > 0 else '−'} {_exact(abs(m))}t", f"That's the straight line through the two readings. An exponential model multiplies by the same number every {per}; it doesn't add the same amount."))
            if grow:
                wrong.append((model(a, m), f"{_exact(m)} is how much it goes up per {per} on average. The factor comes from dividing: {_exact(y2)} ÷ {_exact(y1)} = {Rs}, so b = {B}."))
        last = f"The reading at t = 0 is {A}, so a = {A}."
    else:
        wrong += [
            (model(y1, b), f"{_exact(y1)} is the reading at t = 1, not t = 0. Go back one {per}: {_exact(y1)} ÷ {B} = {A}."),
            (model(y1 * b, b), f"Going back one {per} undoes one multiplication: divide {_exact(y1)} by {B}; don't multiply."),
            (model(y1, R), f"You put the two numbers straight in. {_exact(y1)} is the reading at t = 1, not t = 0, and {Rs} is the change over {k} {per}s, not one: b = {B} and a = {A}."),
        ]
        last = f"Go back one {per} to t = 0: a = {_exact(y1)} ÷ {B} = {A}."
    return Problem(
        help="twopoints",
        story=story,
        expr=f"y({t1}) = {_exact(y1)},   y({t2}) = {_exact(y2)}",
        ask=f"Which exponential model y = a × b{_T} fits both readings?",
        choices=_string_choices(ctx, ans, wrong),
        solution=(
            f"From t = {t1} to t = {t2} the {what} is multiplied by {_exact(y2)} ÷ {_exact(y1)} = {Rs}.",
            f"That's {k} {per}s, so {bb} = {Rs}, and b = {B}.",
            last,
            f"So {ans}.",
        ),
        hint="Divide the later reading by the earlier one. Then find the number that multiplies by itself once per step to make that.",
    )


# (steps between the readings, factor over all of them, first readings): every reading a whole number
_SPLIT = [
    (2, Fraction(121, 100), (100, 200, 300, 400, 500)),
    (2, Fraction(144, 100), (100, 200, 250, 400, 500)),
    (2, Fraction(169, 100), (100, 200, 300)),
    (2, Fraction(196, 100), (100, 200, 500)),
    (2, Fraction(225, 100), (40, 80, 200, 400)),
    (2, Fraction(81, 100), (100, 200, 500, 1000)),
    (2, Fraction(64, 100), (100, 200, 250, 500)),
    (2, Fraction(49, 100), (100, 200, 300)),
    (2, Fraction(36, 100), (100, 500)),
    (3, Fraction(1331, 1000), (1000,)),
    (3, Fraction(1728, 1000), (125, 250, 500)),
    (3, Fraction(729, 1000), (1000,)),
    (3, Fraction(512, 1000), (125, 250, 500, 1000)),
]


@gen("rx", 3)
def rate_from_two_readings(ctx: Context) -> Problem:
    """The percent rate per step from a change over two or three steps: split the factor, not the percent."""
    ship = _fleet_ship(ctx).name
    k, B, starts = ctx.pick(_SPLIT)
    y0 = ctx.pick(starts)
    yk = y0 * B
    b = _root(B, k)
    grow = b > 1
    rate = abs(b - 1)
    pct, total = 100 * rate, 100 * abs(B - 1)
    Bs, bs, bb = _exact(B), _exact(b), " × ".join(["b"] * k)
    Y0, Yk = _exact(y0), _exact(yk)
    if grow:
        story, what, per = ctx.pick([
            (f"{ship}'s plasma reactor was putting out {Y0} MW when it was switched on and {Yk} MW {k} hours later. Its output grows by the same percent every hour.", "output", "hour"),
            (f"The charge in {ship}'s laser capacitors went from {Y0} kJ to {Yk} kJ in {k} seconds, growing by the same percent every second.", "charge", "second"),
        ])
        wrong = [
            (total, f"{_exact(total)}% is the growth over {_all(k)} {per}s together. Each {per} it's multiplied by the same b, and {bb} = {Bs}, so b = {bs}."),
            (_whole(total / k), f"You shared the {_exact(total)}% out evenly, but each {per}'s growth builds on the one before, so it takes less than that each {per}."),
            (100 * b, f"{bs} is the factor each {per}: {_exact(100 * b)}% of the {per} before. That's growth of {_exact(pct)}%."),
            (100 * B, f"{_exact(100 * B)}% is the whole {k}-{per} change as a percent. Split the factor {Bs} into {k} equal factors: b = {bs}."),
        ]
    else:
        story, what, per = ctx.pick([
            (f"{ship}'s reserve store held {Y0} units of plasma; {k} days later it held {Yk}. It loses the same percent of its plasma every day.", "plasma", "day"),
            (f"{ship}'s force field fell from {Y0} to {Yk} units of strength in {k} minutes, losing the same percent every minute.", "strength", "minute"),
        ])
        wrong = [
            (total, f"{_exact(total)}% is the loss over {_all(k)} {per}s together. Each {per} it's multiplied by the same b, and {bb} = {Bs}, so b = {bs}."),
            (_whole(total / k), f"You shared the {_exact(total)}% out evenly, but each {per} loses a share of what's LEFT, so it takes more than that each {per}."),
            (100 * b, f"{bs} is the factor each {per}: {_exact(100 * b)}% is left. That's a drop of {_exact(pct)}%."),
            (100 * B, f"{_exact(100 * B)}% is what's left after {_all(k)} {per}s. Split the factor {Bs} into {k} equal factors: b = {bs}."),
        ]
    root = "square root" if k == 2 else "cube root"
    wrong += [
        (rate, f"{_exact(rate)} is the rate as a decimal. As a percent that's {_exact(pct)}%."),
        (rate * 10, f"{_exact(rate)} is {_exact(pct)}%, not {_exact(rate * 10)}%: move the point two places."),
        (_whole(float(total) ** (1 / k)), f"You took the {root} of the {_exact(total)}% {'growth' if grow else 'lost'}. The root goes on the factor, {Bs}, not on the percent."),
    ]
    return Problem(
        help="splitrate",
        story=story,
        expr=f"y(0) = {Y0},   y({k}) = {Yk}",
        ask=f"By what percent does the {what} {'grow' if grow else 'drop'} each {per}?",
        choices=_pc_choices(ctx, pct, wrong),
        solution=(
            f"Over the {k} {per}s it's multiplied by {Yk} ÷ {Y0} = {Bs}.",
            f"Each {per} it's multiplied by b, so {bb} = {Bs}, and b = {bs}.",
            f"{'b − 1' if grow else '1 − b'} = {_exact(rate)}, which is {_exact(pct)}% each {per}.",
        ),
        hint="Divide to get the factor for the whole time. Then find b, the number that multiplies by itself once per step to make it.",
    )


def _race_traps(a: int, b: int, c: int, m: int) -> tuple[int, int, int]:
    """When a × bᵗ passes c (where c + mt starts), first gains more than m in an hour, and passes mt."""
    return (
        next(s for s in range(40) if a * b**s > c),
        next(s for s in range(1, 40) if a * b**s - a * b ** (s - 1) > m),
        next(s for s in range(1, 40) if a * b**s > m * s),
    )


def _race_setups() -> list[tuple[int, int, int, int, int]]:
    """(a, b, c, m, t): a × bᵗ first beats c + mt at t, never ties with it, stays small enough to work
    out by hand, and at least one trap (see :func:`_race_traps`) comes two or more hours early."""
    out = []
    for b, first, last in ((2, 4, 7), (3, 3, 5)):
        for a in (1, 2, 3, 4, 5, 10, 20):
            for c in (50, 60, 80, 100, 120, 150, 200, 250, 300, 400, 500):
                for m in (10, 20, 25, 30, 40, 50, 60, 75, 80, 100):
                    t = next(t for t in range(40) if a * b**t > c + m * t)
                    if (a < c and first <= t <= last and a * b**t <= 1500 and min(_race_traps(a, b, c, m)) <= t - 2
                            and all(a * b**s != c + m * s for s in range(t + 2))):
                        out.append((a, b, c, m, t))
    return out


_RACES = _race_setups()


@gen("rx", 3)
def exponential_passes_linear(ctx: Context) -> Problem:
    """The first whole t at which a × bᵗ is bigger than c + mt."""
    ship = _fleet_ship(ctx).name
    a, b, c, m, t = ctx.pick(_RACES)

    def E(s: int) -> int:
        return a * b**s

    def L(s: int) -> int:
        return c + m * s

    grows = "doubles" if b == 2 else "triples"
    story, ask, new, old, per, size = ctx.pick([
        (f"{ship}'s new plasma reactor is coming online, and its output {grows} every hour: {a} × {b}{_T} MW after t hours. Her old steam plant is run up at the same time, from {c} MW plus {m} MW every hour: {c} + {m}t.",
         "After how many whole hours is the reactor putting out more than the steam plant for the first time?", "reactor", "steam plant", "hour", "output"),
        (f"{ship} is testing a new force field against her old deflector screen. The field's strength {grows} every second: {a} × {b}{_T} units after t seconds. The screen starts at {c} units and gains {m} every second: {c} + {m}t.",
         "After how many whole seconds is the force field stronger than the screen for the first time?", "force field", "screen", "second", "strength"),
    ])
    mistakes = [
        (t - 1, f"At t = {t - 1} the {new} is still behind: {E(t - 1)} against {L(t - 1)}."),
        (t + 1, f"It's already ahead at t = {t}: {E(t)} against {L(t)}. The question asks for the first {per}."),
    ]
    t_start, t_gain, t_nostart = _race_traps(a, b, c, m)
    if t_start < t:
        mistakes.append((t_start, f"That's when the {new} passes {c}, where the {old} started. But the {old} keeps growing: at t = {t_start} it's at {L(t_start)}, and the {new} at {E(t_start)}."))
    if t_gain < t:
        mistakes.append((t_gain, f"That's when the {new} starts gaining more each {per} than the {old} ({E(t_gain) - E(t_gain - 1)} against {m}), but it's still behind in total: {E(t_gain)} against {L(t_gain)}."))
    if t_nostart < t:
        mistakes.append((t_nostart, f"You left out the {c} the {old} starts with: {a} × {b}{sup(t_nostart)} = {E(t_nostart)} is more than {m} × {t_nostart}, but {c} + {m}t is at {L(t_nostart)}."))
    mistakes.append((E(t), f"{E(t)} is the {new}'s {size} at t = {t}, not the time."))
    lo = max(0, t - 3)
    return Problem(
        help="versus",
        story=story,
        expr=f"{a} × {b}{_T} > {c} + {m}t",
        ask=ask,
        choices=_exact_choices(ctx, t, mistakes),
        solution=(
            f"The {new}, t = {lo} to {t}: {' → '.join(str(E(s)) for s in range(lo, t + 1))}.",
            f"The {old}, t = {lo} to {t}: {' → '.join(str(L(s)) for s in range(lo, t + 1))}.",
            f"At t = {t - 1} it's {E(t - 1)} against {L(t - 1)}: still behind. At t = {t} it's {E(t)} against {L(t)}: ahead for the first time.",
        ),
        hint="Make a table of both for t = 1, 2, 3... and compare the totals. The answer is the first t where the exponential one is bigger.",
    )


@gen("rx", 3)
def decay_to_threshold(ctx: Context) -> Problem:
    """When a halving amount first drops below a limit: count the halvings, then turn them into time."""
    ship = _fleet_ship(ctx).name
    S0 = ctx.pick([640, 800, 1000, 1200, 1600, 2000, 3200, 4000, 5000])
    n = ctx.rand(3, 5)
    lo, hi = Fraction(S0, 2**n), Fraction(S0, 2 ** (n - 1))
    step = next(s for s in (100, 50, 25, 10, 5) if (hi - lo) / s >= 3)
    thr = ctx.pick([v for v in range(step, int(hi) + 1, step) if lo < v < hi])
    h, unit = ctx.pick([(2, "minute"), (3, "minute"), (5, "minute"), (10, "second"), (15, "second"), (2, "hour"),
                        (3, "hour"), (4, "hour"), (6, "hour"), (2, "day"), (5, "day")])
    T = n * h
    story = ctx.pick([
        f"{ship} takes on {S0:,} units of plasma. Stored plasma has a half-life of {_units(h, unit)}, and she must refuel once her store drops below {thr} units.",
        f"A hit knocks out {ship}'s force-field generator. The field's strength, {S0:,} units, halves {_every(h, unit)}, and the field collapses once it drops below {thr} units.",
        f"{ship}'s laser capacitors are cut off from the reactor with {S0:,} kJ stored. The charge has a half-life of {_units(h, unit)}, and the lasers can't fire once it drops below {thr} kJ.",
    ])
    mistakes = [
        (n, f"{n} is the number of halvings. Each one takes {_units(h, unit)}: {n} × {h} = {T}."),
        ((n - 1) * h, f"At {_units((n - 1) * h, unit)} there's still {_exact(hi)}, above {thr}."),
        ((n + 1) * h, f"It's already down to {_exact(lo)} at {_units(T, unit)}, below {thr}. The question asks when it FIRST drops below."),
        (lo, f"{_exact(lo)} is how much is left at {_units(T, unit)}, not the time."),
        (_whole((S0 - thr) / (S0 / 2) * h), f"It doesn't lose the same {S0 // 2:,} {_every(h, unit)}: it loses half of what's LEFT, so less each time."),
        (_whole(S0 / thr * h), f"{S0:,} ÷ {thr} is about {_fmt(S0 / thr)}: that's how many times smaller it has to get, not how many halvings. Halving {_times(n)} makes it {2**n} times smaller."),
    ]
    return Problem(
        help="threshold",
        story=story,
        expr=f"{S0:,} × (½)ⁿ < {thr}",
        note="n = the number of half-lives",
        ask=f"After how many {unit}s does it first drop below {thr}?",
        choices=_exact_choices(ctx, T, mistakes),
        solution=(
            f"Halve step by step: {_halvings(S0, n)}.",
            f"The first amount below {thr} is {_exact(lo)}, after {n} halvings ({_exact(hi)} was still above it).",
            f"Each halving takes {_units(h, unit)}: {n} × {h} = {T} {unit}s.",
        ),
        hint=f"Keep halving {S0:,} and count until you're under {thr}. Then multiply the count by {h}.",
    )
