"""7th-grade problems for the Math Boost in battle, ported from Dino Math: Realistic.

The problem engine of the Dino Math: Realistic game (games/dinomathrealistic.html
in muds42/website), ported line by line: 15 topics, from integers and one-step
equations to probability, statistics, and surface area & volume. Every wrong
choice is a common mistake with a "why", and every problem has a hint and
worked steps.

LEVELS are 0-4 (shown as 1-5). A topic opens at its ``min`` level, and harder
kinds of problem and bigger numbers open inside each topic as the level rises:

    0  Integers, One-step equations, Proportions, Percents
    1  Two-step equations, Fractions, Decimals, Angles
    2  Percent change, Expressions, Inequalities
    3  Probability, Circles & area, Statistics
    4  Surface area & volume

The generators keep the original's HTML markup for fractions, repeating
digits and exponents; :func:`plain` turns it into the Unicode the game shows
(2⁄3, 0.83̅, x²). Geometry sketches are figure dicts (``{"kind": "dm_box", ...}``)
drawn by ``ui/figures.py``, and the answer choices of a graphing problem are
number lines (:attr:`Choice.graph`).

Randomness comes from any object with a ``random()`` method, used exactly as
the original uses ``Math.random()``, and the arithmetic and number formatting
follow JavaScript's. So fed the same stream of random numbers, the port writes
the same problems as the original, character for character, with
``make_problem(..., faithful=True)``. The game itself picks the wrong choices
more carefully than the original (see :func:`make_choices`), so the answer
can't be found by where it sits among them.
"""

from __future__ import annotations

import math
import random
import re
from dataclasses import dataclass
from typing import Any, Callable, Optional, Protocol

from .common import is_int, js_fixed, js_round, js_str, pick_three

__all__ = ["Choice", "DinoProblem", "TOPICS", "LEVELS", "make_problem", "random_topic", "plain", "to_text"]


class RandomSource(Protocol):
    def random(self) -> float: ...


# --------------------------------------------------------------------------- JavaScript numbers


def div(a: float, b: float) -> float:
    """a / b with JavaScript's answer for b = 0 (Infinity or NaN), which the choice checks then drop."""
    if b == 0:
        return math.nan if a == 0 or math.isnan(a) else math.copysign(math.inf, a) * math.copysign(1, b)
    return a / b


# --------------------------------------------------------------------------- numbers & formatting

MINUS = "−"
EQ = "="


class Dice:
    """The original's rand, pick, sgn, neg and shuffle, on one source of random numbers."""

    def __init__(self, rng: RandomSource) -> None:
        self.random = rng.random

    def rand(self, lo: int, hi: int) -> int:
        return math.floor(self.random() * (hi - lo + 1)) + lo

    def pick(self, seq):
        return seq[math.floor(self.random() * len(seq))]

    def sgn(self) -> int:
        return -1 if self.random() < 0.5 else 1

    def neg(self, chance: float) -> int:
        return -1 if self.random() < chance else 1

    def shuffle(self, arr: list) -> list:
        for i in range(len(arr) - 1, 0, -1):
            j = self.rand(0, i)
            arr[i], arr[j] = arr[j], arr[i]
        return arr


def sign(v: float) -> int:
    return (v > 0) - (v < 0)


def gcd(a, b):
    a, b = abs(a), abs(b)
    while b:
        a, b = b, a % b
    return a or 1


def lcm(a: int, b: int) -> int:
    return a // gcd(a, b) * b


def round4(v: float) -> float:
    return js_round(v * 10000) / 10000


def num(v: float) -> str:
    """A number with a true minus sign and no float noise (0.1 + 0.2 shows 0.3)."""
    v = round4(v)
    return (MINUS if v < 0 else "") + js_str(abs(v))


def pn(v: float) -> str:  # 5 − (−3)
    return "(" + num(v) + ")" if v < 0 else num(v)


def term(v: float) -> str:  # "+ 4" / "− 4"
    return (MINUS if v < 0 else "+") + " " + num(abs(v))


def plus(v: float) -> str:  # the next term of an expression
    return " " + term(v)


def coef(a: float) -> str:  # the number in front of x
    return "" if a == 1 else MINUS if a == -1 else num(a)


def undo_term(b: float) -> str:
    return (f"Subtract {num(b)} from" if b > 0 else f"Add {num(-b)} to") + " both sides"


def money(v: float) -> str:
    v = js_round(v * 100) / 100
    return (MINUS if v < 0 else "") + "$" + (js_str(abs(v)) if is_int(v) else js_fixed(abs(v), 2))


def J(v: Any) -> str:
    """A value as a template literal writes it."""
    return js_str(v)


def stack(top: Any, bot: Any) -> str:
    """A stacked fraction exactly as given."""
    return f'<span class="frac"><span>{J(top)}</span><span>{J(bot)}</span></span>'


def raw(n, d) -> str:
    """An unreduced n/d (for worked steps)."""
    if d < 0:
        n, d = -n, -d
    return (MINUS if n < 0 else "") + stack(abs(n), d)


def frac(n, d) -> str:
    """n/d reduced; whole numbers print plain."""
    if d < 0:
        n, d = -n, -d
    g = gcd(n, d)
    n, d = _exact(n / g), _exact(d / g)
    return num(n) if d == 1 else raw(n, d)


def _exact(v: float):
    return int(v) if is_int(v) else v


def pfrac(n, d) -> str:
    return "(" + frac(n, d) + ")" if n * d < 0 else frac(n, d)


def praw(n, d) -> str:
    return "(" + raw(n, d) + ")" if n * d < 0 else raw(n, d)


def sup(s: Any) -> str:
    return f"<sup>{J(s)}</sup>"


# --------------------------------------------------------------------------- answer choices
# Every choice has a key (equal values share one, so 2/4 can never sit beside
# 1/2), the HTML for its button and, for the common mistakes, a `why` naming
# the slip that produces it. `mk` rebuilds the same kind of choice from a
# number, for near-miss fillers.


@dataclass
class Opt:
    key: str
    html: str
    why: Optional[str] = None
    v: Optional[float] = None
    mk: Optional[Callable[..., "Opt"]] = None
    n: Optional[int] = None
    d: Optional[int] = None
    say: Optional[str] = None  # the answer in words when the choice is a picture
    graph: Optional[tuple] = None  # a number line: (at, rel, lo, hi)


def opt(v, html: str, why, mk) -> Opt:
    return Opt("v" + js_str(js_round(v * 1e6)), html, why or None, v, mk)


def N(v, why=None) -> Opt:
    return opt(round4(v), num(v), why, N)


def M(v, why=None) -> Opt:
    return opt(js_round(v * 100) / 100, money(v), why, M)


def D(v, why=None) -> Opt:
    return opt(v, num(v) + "°", why, D)


def P(v, why=None) -> Opt:
    v = js_round(v * 100) / 100
    return opt(v, num(v) + "%", why, P)


def PC(v, why=None) -> Opt:
    v = js_round(v * 10) / 10
    return opt(v, ("+" if v > 0 else "") + num(v) + "%", why, PC)


def T(html: str, why=None) -> Opt:
    return Opt("s" + html, html, why or None)


def PI(v, why=None) -> Opt:  # 12π: an answer that keeps π
    return opt(v, ("" if v == 1 else num(v)) + "π", why, PI)


def Q(n, d, why=None) -> Optional[Opt]:
    if not is_int(n) or not is_int(d) or d == 0:
        return None
    n, d = int(n), int(d)
    if d < 0:
        n, d = -n, -d
    g = gcd(n, d)
    o = opt(n / d, frac(n, d), why, None)
    o.n, o.d = n // g, d // g
    return o


def near_q(o: Opt, dice: Dice) -> Callable[[], Optional[Opt]]:
    return lambda: Q(o.n + dice.rand(1, 2) * dice.sgn(), o.d)


def ok_opt(o: Optional[Opt], p: dict) -> bool:
    if not o:
        return False
    if o.v is None:  # text choices
        return True
    if not math.isfinite(o.v) or abs(o.v) > 99999:
        return False
    if p.get("pos") and o.v <= 0:  # a price, angle or count
        return False
    if p.get("ints") and o.mk in (N, D) and not is_int(o.v):
        return False
    if o.d is not None:
        return o.d <= 144
    return abs(o.v * 1000 - js_round(o.v * 1000)) < 1e-6  # no repeating decimals


def unit_of(v: float) -> float:
    s = js_str(abs(round4(v)))
    dot = s.find(".")
    return 1 if dot < 0 else math.pow(10, dot + 1 - len(s))


NEAR_WHY = "Close, but that's not what the working gives. Check the arithmetic in each step."


def make_choices(p: dict, dice: Dice, faithful: bool = False) -> list[Opt]:
    """The answer plus three wrong choices, in random order.

    The wrong choices are the problem's common mistakes, with near misses (small
    slips either side of the answer) to fall back on, picked by
    :func:`common.pick_three`. So the answer is as often the smallest choice as
    the largest, and never the one that stands out: the choice sharing the most
    digits with the others, the one exactly halfway between two others...

    ``faithful`` picks them as the original game does instead (see
    :func:`_original_choices`), to check the port against it.
    """
    if faithful:
        return _original_choices(p, dice)
    a = p["answer"]
    # A whole-number answer to a problem with no decimals in it only gets
    # whole-number distractors, so a stray 18.4 can't be ruled out by eye.
    p["ints"] = a.mk in (N, D) and is_int(a.v) and not _DECIMAL.search(p["expr"])
    seen = {a.key}

    def usable(opts) -> list[Opt]:
        out = []
        for o in opts:
            if ok_opt(o, p) and o.key not in seen:
                seen.add(o.key)
                out.append(o)
        return out

    mistakes = usable(p["wrong"])
    near = p.get("near")
    if near is not None:
        spare = usable([near() for _ in range(12)])
    elif a.mk:
        unit = unit_of(a.v)
        spare = usable([a.mk(a.v + k * unit) for k in (1, -1, 2, -2, 3, -3, 4, -4)])
        if len(mistakes) + len(spare) < 3:  # e.g. a small count that can't go below zero
            spare += usable([a.mk(a.v + k * unit) for k in range(5, 60)])
    else:
        spare = []
    picked = pick_three(dice, _shown(a), _value(a), [_candidate(o) for o in mistakes], [_candidate(o) for o in spare])
    out = [c[3] for c in picked]
    for o in out:
        if not o.why and any(o is x for x in spare):
            o.why = NEAR_WHY
    return dice.shuffle([a, *out])


def _shown(o: Opt) -> str:
    return plain(o.say or o.html)


def _value(o: Opt) -> Optional[float]:
    """The number a choice stands for, to put the choices in order: 12π is about 37.7."""
    if o.v is None or o.graph is not None:
        return None
    return o.v * math.pi if o.mk is PI else o.v


def _candidate(o: Opt) -> tuple:
    return _shown(o), o.why or "", _value(o), o


def _original_choices(p: dict, dice: Dice) -> list[Opt]:
    """The original game's choices: common mistakes first, then near misses
    (small slips) if the mistakes collapse onto each other. The answer is far
    more often the smallest choice than the largest this way, which a player
    can learn to exploit; :func:`make_choices` balances them instead."""
    a = p["answer"]
    # A whole-number answer to a problem with no decimals in it only gets
    # whole-number distractors, so a stray 18.4 can't be ruled out by eye.
    p["ints"] = a.mk in (N, D) and is_int(a.v) and not _DECIMAL.search(p["expr"])
    seen = {a.key}
    out: list[Opt] = []

    def add(o):
        if len(out) < 3 and ok_opt(o, p) and o.key not in seen:
            seen.add(o.key)
            out.append(o)

    for o in dice.shuffle(list(p["wrong"])):
        add(o)
    near = p.get("near")
    if near is None:
        near = (lambda: a.mk(a.v + dice.sgn() * dice.rand(1, 3) * unit_of(a.v))) if a.mk else (lambda: None)
    i = 0
    while len(out) < 3 and i < 200:
        add(near())
        i += 1
    k = 1
    while len(out) < 3 and a.mk and k < 60:
        add(a.mk(a.v + k * unit_of(a.v)))
        k += 1
    return dice.shuffle([a, *out])


_DECIMAL = re.compile(r"\d\.\d")


# --------------------------------------------------------------------------- problem generators
# Each takes the dice and the level (0-4) and returns a dict
#   {expr, ask, answer, wrong, near?, pos?, words?, hint, steps, line?, ray?, fig?}
# expr and ask are HTML (a "?" in ask marks where the answer goes, else it goes
# at the end). wrong holds this problem's common mistakes (None where the
# original has a mistake that doesn't apply), hint shows after a miss, and
# steps are the [math, note] rows of the walkthrough.


def signed_sum(x, op: str, y) -> dict:
    """x op y where either can be negative. Mistakes are the classic sign slips:
    dropping the minus when both moves go left (−8 − 9 → 17), adding the sizes
    when the signs differ, and reading − (−b) as − b."""
    e = y if op == "+" else -y  # the move actually made on the number line
    ans = round4(x + e)
    expr = num(x) + " " + op + " " + pn(y)
    direction = "left" if e < 0 else "right"
    sx, se = abs(x), abs(e)
    wrong: list = []
    steps: list = []
    if op == MINUS and y < 0:
        wrong.append(N(x + y, f"Subtracting a negative is adding: − ({num(y)}) becomes + {num(-y)}."))
        steps.append([f"{expr} = {num(x)} + {num(-y)}", "Subtracting a negative = adding"])
    elif op == MINUS:
        steps.append([f"{expr} = {num(x)} + ({num(e)})", "Subtracting = adding the opposite"])
    if sign(x) == sign(e):
        why = "You subtracted the sizes. When both moves go the same way, add them."
        wrong.append(N(-ans, f"Both moves go {direction}, so the answer is {'negative' if ans < 0 else 'positive'}."))
        wrong += [N(sx - se, why), N(se - sx, why)]
        steps.append([f"{num(sx)} + {num(se)} = {num(abs(ans))}",
                      f"Same direction: add the sizes. The answer is {'negative' if ans < 0 else 'positive'}."])
    else:
        big = x if sx > se else e
        why = "You added the sizes. Moves in opposite directions partly cancel, so subtract them."
        wrong.append(N(-ans, f"Right size, wrong sign. {num(big)} is farther from 0, so the answer takes its sign."))
        wrong += [N(sign(ans) * (sx + se), why), N(-sign(ans) * (sx + se), why)]
        steps.append([f"{num(max(sx, se))} − {num(min(sx, se))} = {num(abs(ans))}",
                      f"Opposite directions: subtract the sizes, keep the sign of {num(big)}"])
    steps.append([f"{expr} = {num(ans)}", f"Start at {num(x)}, move {num(se)} {direction}"])
    return {
        "expr": expr, "ask": EQ, "answer": N(ans), "wrong": wrong, "steps": steps,
        "hint": f"Picture a number line: start at {num(x)}, then move {num(se)} {direction}.",
        "line": {"from": x, "to": ans} if is_int(x) and is_int(y) else None,
    }


def gen_integers(d: Dice, lvl: int) -> dict:
    kinds = ["sum", "sum"]
    if lvl >= 1:
        kinds += ["product", "quotient"]
    if lvl >= 3:
        kinds += ["order", "power"]
    kind = d.pick(kinds)

    if kind == "sum":
        R = [12, 15, 20, 20, 25][lvl]
        while True:
            x = d.rand(1, R) * d.neg(0.65)
            y = d.rand(1, R) * d.sgn()
            op = MINUS if d.random() < 0.55 else "+"
            if not (abs(x) == abs(y) or (x > 0 and y > 0 and (op == "+" or x > y))):  # skip plain positive sums
                break
        return signed_sum(x, op, y)

    if kind in ("product", "quotient"):
        hi = 12 if lvl >= 3 else 9
        a = d.rand(2, hi) * d.sgn()
        b = d.rand(2, hi) * d.sgn()
        if a > 0 and b > 0:
            if d.random() < 0.5:
                a = -a
            else:
                b = -b
        if kind == "product":
            ans, expr = a * b, f"{num(a)} × {pn(b)}"
            rule = "Negative × negative is positive." if a < 0 and b < 0 else "Negative × positive is negative."
            return {
                "expr": expr, "ask": EQ, "answer": N(ans),
                "wrong": [N(-ans, "Right size, wrong sign. " + rule), N(a + b, "You added. × means multiply.")],
                "hint": "Multiply the sizes, then pick the sign: two negatives make a positive.",
                "steps": [[f"{abs(a)} × {abs(b)} = {abs(ans)}", "Multiply the sizes"], [f"{expr} = {num(ans)}", rule]],
            }
        n, expr = a * b, f"{num(a * b)} ÷ {pn(b)}"  # the answer is a
        rule = "Same signs divide to a positive." if (n < 0) == (b < 0) else "Different signs divide to a negative."
        return {
            "expr": expr, "ask": EQ, "answer": N(a),
            "wrong": [N(-a, "Right size, wrong sign. " + rule)],
            "hint": "Divide the sizes, then pick the sign: same signs → positive, different → negative.",
            "steps": [[f"{abs(n)} ÷ {abs(b)} = {abs(a)}", "Divide the sizes"], [f"{expr} = {num(a)}", rule]],
        }

    if kind == "order":
        if d.random() < 0.5:
            x = d.rand(2, 12) * d.sgn()
            y = d.rand(2, 6)
            z = -d.rand(2, 6)
            ans = x + y * z
            return {
                "expr": f"{num(x)} + {y} × {pn(z)}", "ask": EQ, "answer": N(ans),
                "wrong": [
                    N((x + y) * z, "You went left to right. Multiply before you add."),
                    N(x - y * z, f"{y} × {pn(z)} is negative: {num(y * z)}."),
                    N(-ans, "Check the sign at the end."),
                ],
                "hint": "Order of operations: multiply first, then add.",
                "steps": [[f"{y} × {pn(z)} = {num(y * z)}", "Multiply first"], [f"{num(x)} + {pn(y * z)} = {num(ans)}", "Then add"]],
            }
        a = -d.rand(2, 6)
        b = d.rand(1, 9)
        c = d.rand(b + 1, b + 9)
        ans = a * (b - c)
        return {
            "expr": f"{num(a)}({b} − {c})", "ask": EQ, "answer": N(ans),
            "wrong": [
                N(a * b - c, f"The {num(a)} multiplies everything in the parentheses, not just the {b}."),
                N(-ans, f"{b} − {c} is negative, and negative × negative is positive."),
                N(a * (b + c), f"Inside the parentheses, {b} − {c} = {num(b - c)}."),
            ],
            "hint": "Parentheses first, then multiply.",
            "steps": [[f"{b} − {c} = {num(b - c)}", "Parentheses first"],
                      [f"{num(a)} × {pn(b - c)} = {num(ans)}", "Negative × negative is positive"]],
        }

    # power: −a² vs (−a)²
    a = d.rand(2, 12 if lvl >= 4 else 9)
    times2 = "² means times itself, not times 2."
    if d.random() < 0.5:
        return {
            "expr": f"{MINUS}{a}{sup(2)}", "ask": EQ, "answer": N(-a * a),
            "wrong": [
                N(a * a, f"The square happens before the minus: {MINUS}{a}{sup(2)} = {MINUS}({a} × {a})."),
                N(-2 * a, times2), N(2 * a, times2),
            ],
            "hint": "Exponents come before the minus sign in front.",
            "steps": [[f"{a}{sup(2)} = {a} × {a} = {a * a}", "Square first"], [f"{MINUS}{a}{sup(2)} = {num(-a * a)}", "Then apply the minus"]],
        }
    return {
        "expr": f"({MINUS}{a}){sup(2)}", "ask": EQ, "answer": N(a * a),
        "wrong": [
            N(-a * a, f"({MINUS}{a}) × ({MINUS}{a}): two negatives multiply to a positive."),
            N(-2 * a, times2), N(2 * a, times2),
        ],
        "hint": "The parentheses mean the whole negative number gets squared.",
        "steps": [[f"({MINUS}{a}){sup(2)} = ({MINUS}{a}) × ({MINUS}{a})", "Square everything in the parentheses"],
                  [f"= {a * a}", "Negative × negative is positive"]],
    }


def gen_one_step(d: Dice, lvl: int) -> dict:
    R = [12, 15, 20, 20, 25][lvl]
    kinds = ["add", "add", "mul", "div"]
    if lvl >= 2:
        kinds.append("decimal")
    if lvl >= 3:
        kinds.append("fraction")
    kind = d.pick(kinds)
    sign_slip = "Sign slip. Plug your answer back in to check it."

    # x + a = c
    if kind == "add" or (kind == "decimal" and d.random() < 0.5):
        while True:
            if kind == "add":
                x = d.rand(1, R) * d.neg(0.6)
                a = d.rand(1, 12) * d.sgn()
            else:
                x = d.rand(1, 90) / 10 * d.sgn()
                a = d.rand(1, 90) / 10 * d.sgn()
            if round4(x + a) != 0:
                break
        c = round4(x + a)
        lhs = f"x + ({num(a)})" if a < 0 and lvl >= 1 and d.random() < 0.3 else f"x{plus(a)}"
        return {
            "expr": f"{lhs} = {num(c)}", "ask": "x =", "answer": N(x),
            "wrong": [
                N(c + a, f"You added {num(a)}. To undo + {num(a)}, subtract it." if a > 0
                  else f"You subtracted {num(-a)}. To undo − {num(-a)}, add it."),
                N(-x, sign_slip),
                N(c, f"That's the right side as it is. x still has {term(a)} with it; undo that first."),
            ],
            "hint": f"Do the opposite of {term(a)} to both sides.",
            "steps": [[f"x = {num(c)}{plus(-a)}", undo_term(a)], [f"x = {num(x)}", f"Check: {num(x)}{plus(a)} = {num(c)} ✓"]],
        }

    # a·x = c (integer or decimal a)
    if kind in ("mul", "decimal"):
        if kind == "mul":
            a = d.rand(2, 9) * d.sgn()
            x = d.rand(1, 10 if R <= 12 else 12) * d.sgn()
            if a > 0 and x > 0:
                a = -a
        else:
            a = d.pick([0.5, 0.2, 0.25, 0.4, 1.5, 2.5]) * d.sgn()
            x = d.rand(2, 12) * d.sgn()
        c = round4(a * x)
        return {
            "expr": f"{coef(a)}x = {num(c)}", "ask": "x =", "answer": N(x),
            "wrong": [
                N(-x, "Dividing by a negative flips the sign." if a < 0 else "Check the sign: negative ÷ positive is negative."),
                N(c - a, f"{num(a)}x means {num(a)} times x, so divide instead of subtracting."),
                N(c * a, f"You multiplied. To undo × {pn(a)}, divide."),
            ],
            "hint": f"{num(a)}x means {num(a)} × x. Undo it by dividing both sides by {num(a)}.",
            "steps": [[f"x = {num(c)} ÷ {pn(a)}", f"Divide both sides by {num(a)}"],
                      [f"x = {num(x)}", f"Check: {num(a)} × {pn(x)} = {num(c)} ✓"]],
        }

    # x ÷ a = c
    if kind == "div":
        a = d.rand(2, 9) * (d.neg(0.4) if lvl >= 1 else 1)
        c = d.rand(1, 10) * d.sgn()
        if a > 0 and c > 0:
            c = -c
        x = a * c
        lhs = stack("x", a) if a > 0 else f"x ÷ ({num(a)})"
        return {
            "expr": f"{lhs} = {num(c)}", "ask": "x =", "answer": N(x),
            "wrong": [
                N(-x, "Check the sign: same signs multiply to a positive." if (a < 0) == (c < 0)
                  else "Check the sign: different signs multiply to a negative."),
                N(c / a, f"You divided. To undo ÷ {num(a)}, multiply."),
            ],
            "hint": f"x is divided by {num(a)}. Undo it by multiplying both sides by {num(a)}.",
            "steps": [[f"x = {num(c)} × {pn(a)}", f"Multiply both sides by {num(a)}"], [f"x = {num(x)}", ""]],
        }

    # (n/d)·x = c: multiply by the reciprocal
    n, dd = d.pick([[2, 3], [3, 4], [2, 5], [3, 5], [4, 5], [5, 6], [3, 8], [5, 8]])
    sa = d.neg(0.4)
    k = d.rand(1, 6) * d.sgn()
    x, c = dd * k, sa * n * k
    coef_html = (MINUS if sa < 0 else "") + stack(n, dd)
    return {
        "expr": f"{coef_html}x = {num(c)}", "ask": "x =", "answer": N(x),
        "wrong": [
            Q(c * n * sa, dd, f"You multiplied by {coef_html}. Multiply by its reciprocal instead."),
            N(c / (sa * n), f"Dividing by {stack(n, dd)} means × {stack(dd, n)}. You still need the × {dd}."),
            N(c * dd * sa, f"You multiplied by {dd} but forgot to divide by {n}."),
            N(-x, sign_slip),
        ],
        "hint": f"Multiply both sides by the reciprocal of {coef_html}.",
        "steps": [
            [f"x = {num(c)} × {'(' + MINUS + stack(dd, n) + ')' if sa < 0 else stack(dd, n)}", "Multiply both sides by the reciprocal"],
            [f"x = {num(c)} ÷ {pn(sa * n)} × {dd} = {num(x)}", f"Divide by {num(sa * n)}, then multiply by {dd}"],
        ],
    }


def linear(a, b, x) -> dict:
    """a·x + b = c, solved by undoing b and then a."""
    c = round4(a * x + b)
    ax = round4(c - b)
    return {
        "expr": f"{coef(a)}x{plus(b)} = {num(c)}", "ask": "x =", "answer": N(x),
        "wrong": [
            N((c + b) / a, f"To undo {term(b)}, {'subtract' if b > 0 else 'add'} {num(abs(b))}. You went the wrong way."),
            N(-x, "Dividing by a negative flips the sign." if a < 0 else "Sign slip. Plug your answer back in to check it."),
            N(ax, f"That's what {coef(a)}x equals. One more step: divide by {num(a)}."),
            N(c / a - b, f"If you divide first, divide every term: {num(b)} ÷ {pn(a)} too."),
        ],
        "hint": f"Undo the {term(b)} first, then divide by {num(a)}.",
        "steps": [
            [f"{coef(a)}x = {num(c)}{plus(-b)} = {num(ax)}", undo_term(b)],
            [f"x = {num(ax)} ÷ {pn(a)} = {num(x)}", f"Divide both sides by {num(a)}"],
        ],
    }


def gen_two_step(d: Dice, lvl: int) -> dict:
    kinds = ["linear", "linear"]
    if lvl >= 2:
        kinds += ["distribute", "divide"]
    if lvl >= 3:
        kinds.append("decimal")
    if lvl >= 4:
        kinds.append("like")
    kind = d.pick(kinds)
    sign_slip = "Sign slip. Plug your answer back in to check it."

    if kind == "linear":
        a = d.rand(2, [5, 6, 8, 9, 9][lvl]) * d.neg(0.6)
        b = d.rand(1, 15) * d.sgn()
        return linear(a, b, d.rand(1, 10) * d.sgn())
    if kind == "decimal":
        a = d.pick([0.5, 0.2, 0.25, 1.5, 2.5, 0.4]) * d.sgn()
        b = d.rand(1, 12) * d.sgn()
        return linear(a, b, d.rand(1, 8) * d.sgn() * (4 if abs(a) == 0.25 else 2))

    if kind == "distribute":
        while True:
            a = d.rand(2, 6) * d.sgn()
            b = d.rand(1, 9) * d.sgn()
            x = d.rand(1, 10) * d.sgn()
            if x + b != 0:
                break
        c = a * (x + b)
        return {
            "expr": f"{num(a)}(x{plus(b)}) = {num(c)}", "ask": "x =", "answer": N(x),
            "wrong": [
                N((c - b) / a, f"The {num(a)} multiplies the {num(b)} too, not just the x."),
                N(c / a + b, f"After dividing, undo the {term(b)} by {'subtracting' if b > 0 else 'adding'}."),
                N(c - a * b, f"That's what {num(a)}x equals. Divide by {num(a)} to finish."),
                N(-x, "Dividing by a negative flips the sign." if a < 0 else sign_slip),
            ],
            "hint": f"Divide both sides by {num(a)} first, then undo the {term(b)}.",
            "steps": [
                [f"x{plus(b)} = {num(c)} ÷ {pn(a)} = {num(x + b)}", f"Divide both sides by {num(a)}"],
                [f"x = {num(x + b)}{plus(-b)} = {num(x)}", undo_term(b)],
            ],
        }

    if kind == "divide":
        a = d.rand(2, 6)
        k = d.rand(1, 8) * d.sgn()
        b = d.rand(1, 12) * d.sgn()
        x, c = a * k, k + b
        return {
            "expr": f"{stack('x', a)}{plus(b)} = {num(c)}", "ask": "x =", "answer": N(x),
            "wrong": [
                N((c + b) * a, f"To undo {term(b)}, {'subtract' if b > 0 else 'add'} {num(abs(b))}. You went the wrong way."),
                N((c - b) / a, f"You divided by {a}. To undo ÷ {a}, multiply."),
                N(c * a - b, f"Undo the {term(b)} before you multiply by {a}."),
                N(-x, sign_slip),
            ],
            "hint": f"Undo the {term(b)} first, then multiply both sides by {a}.",
            "steps": [
                [f"{stack('x', a)} = {num(c)}{plus(-b)} = {num(k)}", undo_term(b)],
                [f"x = {num(k)} × {a} = {num(x)}", f"Multiply both sides by {a}"],
            ],
        }

    # like terms: a·x + b + c·x = d
    while True:
        a = d.rand(2, 8)
        c = d.rand(1, 6) * d.sgn()
        s = a + c
        if abs(s) > 1:
            break
    b = d.rand(1, 12) * d.sgn()
    x = d.rand(1, 9) * d.sgn()
    dd = s * x + b
    return {
        "expr": f"{a}x{plus(b)} {MINUS if c < 0 else '+'} {coef(abs(c))}x = {num(dd)}", "ask": "x =", "answer": N(x),
        "wrong": [
            N(div(dd - b, a - c), f"Combine carefully: {a}x {MINUS if c < 0 else '+'} {coef(abs(c))}x = {coef(s)}x."),
            N((dd + b) / s, f"To undo {term(b)}, {'subtract' if b > 0 else 'add'} {num(abs(b))}."),
            N((dd - b) / a, f"Don't forget the {coef(c)}x. Combine the x terms first."),
            N(-x, sign_slip),
        ],
        "hint": "Combine the x terms into one, then solve the two-step equation.",
        "steps": [
            [f"{coef(s)}x{plus(b)} = {num(dd)}", "Combine like terms"],
            [f"{coef(s)}x = {num(dd - b)}", undo_term(b)],
            [f"x = {num(dd - b)} ÷ {pn(s)} = {num(x)}", f"Divide both sides by {num(s)}"],
        ],
    }


RATIOS = [[1, 2], [1, 3], [2, 3], [1, 4], [3, 4], [2, 5], [3, 5], [4, 5], [5, 6], [3, 8], [5, 8], [7, 10], [4, 3], [5, 2], [7, 4]]
RATE_ITEMS = ["notebooks", "bags of chips", "bus tickets", "fossil kits", "granola bars", "packs of cards"]


def gen_proportion(d: Dice, lvl: int) -> dict:
    kinds = ["ratio", "ratio", "rate"]
    if lvl >= 2:
        kinds.append("scale")
    if lvl >= 3:
        kinds.append("constant")
    kind = d.pick(kinds)

    def additive(gap, k):
        return f"You added {gap} to both parts. Equal ratios multiply (× {k}), they don't add."

    if kind == "ratio":
        a, b = d.pick(RATIOS)
        k = d.rand(2, [5, 6, 8, 10, 12][lvl])
        if d.random() < 0.6:  # a/b = x/(bk)
            bot, ans = b * k, a * k
            return {
                "expr": f"{stack(a, b)} = {stack('x', bot)}", "ask": "x =", "answer": N(ans), "pos": True,
                "wrong": [
                    N(a + bot - b, additive(bot - b, k)),
                    N(a * bot, f"{a} × {bot} is only half of cross-multiplying. Now divide by {b}."),
                    N(k, f"{k} is the scale factor ({b} × {k} = {bot}). Now multiply {a} by it."),
                    N(b * bot / a, f"That flips the ratio. {a} goes on top, like x."),
                ],
                "hint": f"What do you multiply {b} by to get {bot}? Do the same to {a}.",
                "steps": [[f"{b} × {k} = {bot}", f"Scale factor: × {k}"], [f"x = {a} × {k} = {ans}", "Multiply the top by the same number"]],
            }
        top, ans = a * k, b * k  # a/b = (ak)/x
        return {
            "expr": f"{stack(a, b)} = {stack(top, 'x')}", "ask": "x =", "answer": N(ans), "pos": True,
            "wrong": [
                N(b + top - a, additive(top - a, k)),
                N(b * top, f"{b} × {top} is only half of cross-multiplying. Now divide by {a}."),
                N(k, f"{k} is the scale factor ({a} × {k} = {top}). Now multiply {b} by it."),
                N(a * top / b, f"That flips the ratio. {b} goes on the bottom, like x."),
            ],
            "hint": f"What do you multiply {a} by to get {top}? Do the same to {b}.",
            "steps": [[f"{a} × {k} = {top}", f"Scale factor: × {k}"], [f"x = {b} × {k} = {ans}", "Multiply the bottom by the same number"]],
        }

    if kind == "rate":
        unit = d.pick([0.5, 1.5, 2, 3, 4, 5] if lvl < 2 else [0.5, 0.75, 1.25, 1.5, 2, 2.5, 3, 4, 6])
        n1 = d.rand(2, 8)
        while True:
            n2 = d.rand(2, 15)
            if n2 != n1:
                break
        c1, ans, gap = n1 * unit, n2 * unit, abs(n2 - n1)
        return {
            "expr": f"{n1} {d.pick(RATE_ITEMS)} cost {money(c1)}. How much do {n2} cost?", "ask": "Cost =",
            "words": True, "pos": True, "answer": M(ans),
            "wrong": [
                M(c1 + n2 - n1, f"{gap} {'more' if n2 > n1 else 'fewer'} isn't {money(gap)} {'more' if n2 > n1 else 'less'}. Find the price of 1 first."),
                M(unit, f"That's the price of 1. Now multiply by {n2}."),
                M(c1 * n2, f"That's {n2} groups of {n1}. Find the price of 1 first."),
            ],
            "hint": f"Find the price of 1 (the unit rate), then multiply by {n2}.",
            "steps": [[f"{money(c1)} ÷ {n1} = {money(unit)}", "Unit rate: the price of 1"], [f"{money(unit)} × {n2} = {money(ans)}", f"Scale up to {n2}"]],
        }

    if kind == "scale":
        u = d.rand(2, 5)
        r = d.pick([5, 10, 15, 20, 25, 50])
        v = u * r
        while True:
            w = d.rand(2, 12)
            if w != u:
                break
        ans = w * r
        return {
            "expr": f"On a map, {u} cm stands for {v} km. How many km is {w} cm?", "ask": "? km",
            "words": True, "pos": True, "answer": N(ans),
            "wrong": [
                N(v + w - u, f"{abs(w - u)} cm {'more' if w > u else 'less'} isn't {abs(w - u)} km. Find the km for 1 cm first."),
                N(v * w, f"{v} km is for {u} cm, not 1 cm. Divide by {u} first."),
                N(r, f"{r} km is what 1 cm stands for. Now multiply by {w}."),
            ],
            "hint": f"How many km does 1 cm stand for? Then multiply by {w}.",
            "steps": [[f"{v} ÷ {u} = {r} km per cm", "Unit rate"], [f"{r} × {w} = {ans} km", f"Scale up to {w} cm"]],
        }

    # constant of proportionality: y = kx
    k = d.pick([1.5, 2.5, 0.5, 3, 4, 1.2, 0.75, 6])
    x1 = d.rand(2, 10)
    y1 = round4(k * x1)
    if d.random() < 0.5:
        return {
            "expr": f"y is proportional to x. When x = {x1}, y = {num(y1)}. What is the constant of proportionality?", "ask": "k =",
            "words": True, "pos": True, "answer": N(k),
            "wrong": [
                N(x1 / y1, "That's x ÷ y. In y = kx, k = y ÷ x."),
                N(y1 - x1, "k is how many times bigger y is (y ÷ x), not the difference."),
                N(y1 * x1, "You multiplied. In y = kx, k = y ÷ x."),
            ],
            "hint": "In y = kx, k = y ÷ x.",
            "steps": [[f"k = y ÷ x = {num(y1)} ÷ {x1}", "In y = kx, k = y ÷ x"], [f"k = {num(k)}", f"Check: {num(k)} × {x1} = {num(y1)} ✓"]],
        }
    while True:
        x2 = d.rand(2, 12)
        if x2 != x1:
            break
    ans = round4(k * x2)
    return {
        "expr": f"y is proportional to x, and y = {num(y1)} when x = {x1}. Find y when x = {x2}.", "ask": "y =",
        "words": True, "pos": True, "answer": N(ans),
        "wrong": [
            N(y1 + x2 - x1, "Proportional means multiply, not add. Find k = y ÷ x first."),
            N(k, f"That's k. Now y = {num(k)} × {x2}."),
            N(x2 / k, f"y = k · x, so multiply by {num(k)}, don't divide."),
            N(y1 * x2, f"That's {num(y1)} × {x2}. Divide by {x1} too."),
        ],
        "hint": "Find k = y ÷ x, then use y = k · x.",
        "steps": [[f"k = {num(y1)} ÷ {x1} = {num(k)}", "Find the constant"], [f"y = {num(k)} × {x2} = {num(ans)}", "y = kx"]],
    }


def multiple_of(d: Dice, step, top):
    """A multiple of ``step`` from 1×step up to about ``top`` (for friendly percents)."""
    return step * d.rand(1, max(1, math.floor(top / step)))


def gen_percent(d: Dice, lvl: int) -> dict:
    kinds = ["of", "of"]
    if lvl >= 2:
        kinds.append("what")
    if lvl >= 3:
        kinds.append("whole")
    kind = d.pick(kinds)

    if kind == "of":
        p = d.pick([10, 20, 25, 50, 75, 5, 30, 40, 60, 15] if lvl < 2 else [15, 35, 45, 12, 8, 120, 150, 125, 200, 65, 75])
        n = multiple_of(d, 100 / gcd(p, 100), [100, 200, 200, 400, 400][lvl])
        ans = p * n / 100
        return {
            "expr": f"{p}% of {J(n)}", "ask": EQ, "answer": N(ans), "pos": True,
            "wrong": [
                N(p * n, f"You forgot to divide by 100. {p}% means {p} ÷ 100 = {num(p / 100)}."),
                N(p * n / 10, f"Decimal slip: {p}% = {num(p / 100)} (two places, not one)."),
                N(n - p, f'"Of" means multiply, not subtract: {num(p / 100)} × {J(n)}.'),
            ],
            "hint": f'{p}% = {num(p / 100)}, and "of" means multiply.',
            "steps": [[f"{p}% = {num(p / 100)}", 'Percent means "out of 100"'], [f"{num(p / 100)} × {J(n)} = {num(ans)}", '"Of" means multiply']],
        }

    p = d.pick([10, 20, 25, 40, 50, 75, 5, 30, 60, 80, 150])
    if kind == "what":
        whole = multiple_of(d, 100 / gcd(p, 100), 200)
        part = p * whole / 100
        return {
            "expr": f"{J(part)} is what percent of {J(whole)}?", "ask": "Percent =", "words": True, "answer": P(p),
            "wrong": [
                P(whole / part * 100, f"That's {J(whole)} ÷ {J(part)}, upside down. Use part ÷ whole: {J(part)} ÷ {J(whole)}."),
                P(part, f"{J(part)} is the amount, not the percent. Divide {J(part)} by {J(whole)}."),
                P(part / whole, f"{num(part / whole)} is the decimal. Multiply by 100 to get a percent."),
            ],
            "hint": "Percent = part ÷ whole × 100.",
            "steps": [[f"{J(part)} ÷ {J(whole)} = {num(part / whole)}", "Part ÷ whole"],
                      [f"{num(part / whole)} × 100 = {p}%", "Turn the decimal into a percent"]],
        }
    q = d.pick([10, 20, 25, 50]) if p > 100 else p  # keep the whole-finding ones friendly
    whole = multiple_of(d, 100 / gcd(q, 100), 200)
    part = q * whole / 100
    return {
        "expr": f"{q}% of what number is {J(part)}?", "ask": "Number =", "words": True, "pos": True, "answer": N(whole),
        "wrong": [
            N(part * q / 100, f"That's {q}% of {J(part)}. Here {J(part)} is the part; you need the whole."),
            N(part * (1 + q / 100), f"You added {q}% to {J(part)}. Divide instead: {J(part)} ÷ {num(q / 100)}."),
            N(part / q, f"{q}% is {num(q / 100)}, not {q}. Divide by {num(q / 100)}."),
        ],
        "hint": f"{num(q / 100)} × (the number) = {J(part)}, so divide {J(part)} by {num(q / 100)}.",
        "steps": [[f"{num(q / 100)} × n = {J(part)}", f"{q}% of the number is {J(part)}"],
                  [f"n = {J(part)} ÷ {num(q / 100)} = {J(whole)}", "Divide both sides"]],
    }


ITEMS = ["jacket", "video game", "skateboard", "backpack", "dinosaur model", "bike helmet", "soccer ball"]


def gen_percent_change(d: Dice, lvl: int) -> dict:
    kinds = ["discount", "markup", "change", "change"]
    if lvl >= 3:
        kinds.append("total")
    if lvl >= 4:
        kinds += ["original", "interest"]
    kind = d.pick(kinds)
    item = d.pick(ITEMS)

    if kind in ("discount", "markup", "total"):
        if kind == "total":
            if d.random() < 0.5:
                p = d.pick([10, 15, 20])
                price = d.pick([20, 24, 30, 36, 40, 45, 50, 60, 80])
                what = "tip"
                text = f"Dinner costs {money(price)}. You leave a {p}% tip. What's the total?"
            else:
                p = d.pick([5, 6, 8, 10])
                price = d.pick([20, 25, 30, 40, 50, 60, 80, 100])
                what = "tax"
                text = f"A {money(price)} {item} has {p}% sales tax. What's the total?"
            ask = "Total ="
        else:
            p = d.pick([10, 20, 25, 50, 15, 30, 40, 75, 5])
            price = d.pick([20, 40, 50, 60, 80, 120, 150, 200, 36, 48])
            if kind == "discount":
                what, ask = "discount", "Sale price ="
                text = f"A {money(price)} {item} is {p}% off. What's the sale price?"
            else:
                what, ask = "markup", "New price ="
                text = f"A store buys a {item} for {money(price)} and marks it up {p}%. What's the new price?"
        up = kind != "discount"
        change = price * p / 100
        ans = price + change if up else price - change
        return {
            "expr": text, "ask": ask, "words": True, "pos": True, "answer": M(ans),
            "wrong": [
                M(change, f"That's just the {what}. {'Add it to' if up else 'Subtract it from'} {money(price)}."),
                M(price + p if up else price - p, f"That's {money(p)} {'more' if up else 'off'}, not {p}%."),
                M(price - change if up else price + change, f"A {what} makes the price go up." if up else "A discount makes the price go down."),
            ],
            "hint": f"Find {p}% of {money(price)}, then {'add it on' if up else 'take it off'}.",
            "steps": [
                [f"{p}% of {money(price)} = {num(p / 100)} × {price} = {money(change)}", f"Find the {what}"],
                [f"{money(price)} {'+' if up else MINUS} {money(change)} = {money(ans)}", "Add it on" if up else "Take it off"],
                [f"Shortcut: {money(price)} × {num(1 + (p if up else -p) / 100)} = {money(ans)}",
                 f"The new price is {100 + p if up else 100 - p}% of the old one"],
            ],
        }

    if kind == "change":
        p = d.pick([10, 20, 25, 50, 75, 5, 30, 40, 60])
        up = d.random() < 0.5
        s = 1 if up else -1
        a = multiple_of(d, 100 / gcd(p, 100), 200)
        diff = a * p / 100
        b = a + s * diff
        text, f = d.pick([
            (f"A price goes from {money(a)} to {money(b)}.", money),
            (f"A dinosaur herd goes from {J(a)} to {J(b)} animals.", num),
            (f"A school club goes from {J(a)} to {J(b)} members.", num),
        ])
        return {
            "expr": f"{text} What's the percent change?", "ask": "Change =", "words": True, "answer": PC(s * p),
            "wrong": [
                PC(s * diff / b * 100, f"You divided by the new amount ({f(b)}). Percent change divides by the original, {f(a)}."),
                PC(s * diff, f"{f(diff)} is the change in amount, not in percent. Divide it by {f(a)}."),
                PC(-s * p, f"It went {'up' if up else 'down'}, so the change is {'positive' if up else 'negative'}."),
            ],
            "hint": "Percent change = (new − original) ÷ original.",
            "steps": [
                [f"{f(b)} − {f(a)} = {'' if up else MINUS}{f(diff)}", "Find the change"],
                [f"{'' if up else MINUS}{f(diff)} ÷ {f(a)} = {num(s * p / 100)}", "Divide by the original"],
                [f"{num(s * p / 100)} = {'+' if up else ''}{num(s * p)}%", "Positive: an increase" if up else "Negative: a decrease"],
            ],
        }

    if kind == "original":
        p = d.pick([10, 20, 25, 40, 50, 30])
        orig = d.pick([20, 30, 40, 50, 60, 80, 100, 120, 150, 200])
        sale = orig * (100 - p) / 100
        return {
            "expr": f"After {p}% off, a {item} costs {money(sale)}. What was the original price?", "ask": "Original =",
            "words": True, "pos": True, "answer": M(orig),
            "wrong": [
                M(sale * (1 + p / 100), f"You added {p}% of {money(sale)}. The {p}% came off the original, so {money(sale)} is {100 - p}% of it."),
                M(sale * (1 - p / 100), f"You took another {p}% off. Work backwards instead."),
                M(sale + p, f"That adds {money(p)}, not {p}%."),
            ],
            "hint": f"{money(sale)} is {100 - p}% of the original price.",
            "steps": [
                [f"{num((100 - p) / 100)} × original = {money(sale)}", f"{p}% off leaves {100 - p}%"],
                [f"original = {money(sale)} ÷ {num((100 - p) / 100)} = {money(orig)}", "Divide to undo it"],
            ],
        }

    P0 = d.pick([100, 200, 300, 400, 500, 1000])
    r = d.pick([2, 3, 4, 5, 6, 10])
    t = d.rand(2, 5)
    I = P0 * r * t / 100
    return {
        "expr": f"You put {money(P0)} in an account paying {r}% simple interest per year. How much interest do you earn in {t} years?",
        "ask": "Interest =", "words": True, "pos": True, "answer": M(I),
        "wrong": [
            M(P0 * r / 100, f"That's one year of interest. Multiply by {t} years."),
            M(P0 + I, "That's the whole balance. The question asks for the interest only."),
            M(r * t, f"Rate × time is {r * t}%. Now take that percent of {money(P0)}."),
        ],
        "hint": "Simple interest = principal × rate × time.",
        "steps": [["I = P × r × t", "Simple interest"], [f"{money(P0)} × {num(r / 100)} × {t} = {money(I)}", f"{r}% = {num(r / 100)}"]],
    }


def rand_frac(d: Dice, dens: list[int]) -> list[int]:
    dd = d.pick(dens)
    while True:
        n = d.rand(1, dd - 1)
        if gcd(n, dd) == 1:
            break
    return [n, dd]


def frac_sum(d: Dice, a, b, op: str, c, dd) -> dict:
    """a/b ± c/d (either may be negative) over their least common denominator."""
    L = lcm(b, dd)
    A, C = a * L // b, c * L // dd
    top = A + C if op == "+" else A - C
    ans = Q(top, L)
    verb = "add" if op == "+" else "subtract"
    wrong = [
        Q(a + c if op == "+" else a - c, b + dd if op == "+" else b - dd, f"You {verb}ed the tops and the bottoms. Get a common denominator first."),
        Q(a + c if op == "+" else a - c, L, f"{L} is the right denominator, but the tops change too: {frac(a, b)} = {raw(A, L)}."),
        Q(-top, L, "Right size, wrong sign. Check which fraction is bigger."),
    ]
    e = C if op == "+" else -C
    if sign(A) != sign(e):
        wrong.append(Q(sign(top) * (abs(A) + abs(e)), L,
                       "You added instead of subtracting." if a > 0 and c > 0 else "You added the sizes, but the signs are different, so subtract them."))
    steps = [
        [f"{frac(a, b)} = {raw(A, L)}, &nbsp;{frac(c, dd)} = {raw(C, L)}", f"Common denominator: {L}"],
        [f"{raw(A, L)} {'+' if op == '+' else MINUS} {praw(C, L)} = {raw(top, L)}", f"{verb[0].upper() + verb[1:]} the tops, keep the bottom"],
    ]
    if gcd(top, L) != 1:
        steps.append([f"{raw(top, L)} = {frac(top, L)}", "Simplify"])
    return {
        "expr": f"{frac(a, b)} {'+' if op == '+' else MINUS} {pfrac(c, dd)}", "ask": EQ, "answer": ans, "wrong": wrong,
        "near": near_q(ans, d), "hint": f"Rewrite both fractions over {L}, then {verb} the tops.", "steps": steps,
    }


def gen_fractions(d: Dice, lvl: int) -> dict:
    dens = [2, 3, 4, 5, 6, 8] if lvl < 3 else [2, 3, 4, 5, 6, 8, 10, 12]
    kinds = ["add", "sub"]
    if lvl >= 2:
        kinds += ["mul", "div", "whole"]
    if lvl >= 3:
        kinds += ["signed", "signed"]
    kind = d.pick(kinds)

    if kind in ("add", "sub", "signed"):
        a, b = rand_frac(d, dens)
        c, dd = rand_frac(d, dens)
        while dd == b or lcm(b, dd) > 24:
            c, dd = rand_frac(d, dens)
        op = "+" if kind == "add" else MINUS if kind == "sub" else d.pick(["+", MINUS])
        if kind == "signed":
            if d.random() < 0.7:
                a = -a
            else:
                c = -c
        return frac_sum(d, a, b, MINUS if op == MINUS else "+", c, dd)

    if kind == "mul":
        a, b = rand_frac(d, dens)
        c, dd = rand_frac(d, dens)
        if lvl >= 3 and d.random() < 0.5:
            a = -a
        ans = Q(a * c, b * dd)
        steps = [[f"{frac(a, b)} × {frac(c, dd)} = {raw(a * c, b * dd)}", "Top × top, bottom × bottom"]]
        if gcd(a * c, b * dd) != 1:
            steps.append([f"{raw(a * c, b * dd)} = {frac(a * c, b * dd)}", "Simplify"])
        return {
            "expr": f"{frac(a, b)} × {frac(c, dd)}", "ask": EQ, "answer": ans, "near": near_q(ans, d),
            "wrong": [
                Q(a * dd, b * c, f"You flipped {frac(c, dd)}. Only flip when dividing."),
                Q(a + c, b + dd, "You added. To multiply, multiply the tops and multiply the bottoms."),
                Q(-a * c, b * dd, "Check the sign: one negative makes the product negative.") if a < 0 else None,
            ],
            "hint": "Multiply top × top and bottom × bottom, then simplify.",
            "steps": steps,
        }

    if kind == "div":
        a, b = rand_frac(d, dens)
        c, dd = rand_frac(d, dens)
        while c == a and dd == b:
            c, dd = rand_frac(d, dens)
        if lvl >= 3 and d.random() < 0.5:
            c = -c
        ans = Q(a * dd, b * c)
        steps = [[f"{frac(a, b)} × {pfrac(dd, c)}", "Keep, change, flip"], [f"= {raw(a * dd, b * c)}", "Top × top, bottom × bottom"]]
        if gcd(a * dd, b * c) != 1:
            steps.append([f"= {frac(a * dd, b * c)}", "Simplify"])
        return {
            "expr": f"{frac(a, b)} ÷ {pfrac(c, dd)}", "ask": EQ, "answer": ans, "near": near_q(ans, d),
            "wrong": [
                Q(a * c, b * dd, f"You multiplied without flipping. Dividing by {frac(c, dd)} means × {frac(dd, c)}."),
                Q(b * c, a * dd, "You flipped the first fraction. Keep the first, flip the second."),
                Q(-a * dd, b * c, "Check the sign: one negative makes the answer negative.") if c < 0 else None,
            ],
            "hint": "Keep the first fraction, change ÷ to ×, flip the second.",
            "steps": steps,
        }

    # whole number × fraction, e.g. −12 × 3/4
    c, dd = rand_frac(d, dens)
    w = dd * d.rand(1, 5) * d.neg(0.5)
    ans = Q(w * c, dd)
    return {
        "expr": f"{num(w)} × {frac(c, dd)}", "ask": EQ, "answer": ans, "near": near_q(ans, d),
        "wrong": [
            Q(c, w * dd, f"You multiplied the bottom by {num(w)}. Multiply the top instead."),
            Q(w * dd, c, f"That flips the fraction. {frac(c, dd)} of {num(w)} is {num(w)} ÷ {dd} × {c}."),
            Q(-w * c, dd, "Check the sign: one negative makes the product negative.") if w < 0 else None,
        ],
        "hint": f"Divide {num(w)} by {dd}, then multiply by {c}.",
        "steps": [[f"{num(w)} ÷ {dd} = {num(w / dd)}", f"Split {num(w)} into {dd} equal parts"],
                  [f"{num(w / dd)} × {c} = {num(w * c / dd)}", f"Take {c} of them"]],
    }


def long_divide(n: int, d: int) -> dict:
    """n/d (both positive) by long division, with a bar over the digits that
    repeat: 3/8 → 0.375, 5/6 → 0.83̄ (fixed "8", cycle "3")."""
    whole, seen = n // d, {}
    r, digits = n % d, ""
    while r and r not in seen:
        seen[r] = len(digits)
        r *= 10
        digits += str(r // d)
        r %= d
    at = seen[r] if r else len(digits)
    fixed, cycle = digits[:at], digits[at:]
    html = str(whole) + ("." + fixed + (f'<span class="rep">{cycle}</span>' if cycle else "") if digits else "")
    return {"html": html, "whole": whole, "fixed": fixed, "cycle": cycle}


def gen_decimals(d: Dice, lvl: int) -> dict:
    kinds = ["sum", "sum", "product", "quotient"]
    if lvl >= 3:
        kinds.append("convert")
    if lvl >= 4:
        kinds += ["convert", "order"]
    kind = d.pick(kinds)

    if kind == "sum":
        # tenths up to 9.9, then 14.9 and 19.9; hundredths on one side from level 3
        top = [99, 99, 149, 199, 199][lvl]
        fine = lvl >= 3 and d.random() < (0.6 if lvl >= 4 else 0.4)
        while True:
            x = d.rand(1, top) / 10 * d.neg(0.65)
            y = (d.rand(1, 999) / 100 if fine else d.rand(1, top) / 10) * d.sgn()
            op = MINUS if d.random() < 0.55 else "+"
            if not (abs(x) == abs(y) or (is_int(x) and is_int(y)) or (x > 0 and y > 0 and (op == "+" or x > y))):
                break
        return signed_sum(x, op, y)

    if kind == "product":
        # tt: tenths × tenths, wt: whole × tenths, ht: tenths above 1 × tenths,
        # th: tenths × hundredths, wh: whole × hundredths
        forms = ["tt", "wt"]
        if lvl >= 2:
            forms.append("ht")
        if lvl >= 3:
            forms.append("th")
        if lvl >= 4:
            forms += ["th", "wh"]
        form = d.pick(forms)
        HUND = [0.25, 0.15, 0.05, 0.75, 0.12, 0.35, 0.45, 0.08, 0.06, 0.24]
        while True:
            if form == "tt":
                a, b, da, db = d.rand(2, 9) / 10, d.rand(2, 9) / 10, 1, 1
            elif form == "wt":
                a = d.rand(2, 12)
                b = d.pick([d.rand(2, 9), d.rand(11, 25)]) / 10
                da, db = 0, 1
            elif form == "ht":
                a, b, da, db = d.rand(11, 25) / 10, d.rand(2, 9) / 10, 1, 1
            elif form == "th":
                a = d.pick([d.rand(2, 9), d.rand(11, 25)]) / 10
                b = d.pick(HUND)
                da, db = 1, 2
            else:
                a, b, da, db = d.rand(2, 24), d.pick(HUND), 0, 2
            if is_int(b):
                b += 0.5  # 2.0 → 2.5, keep a real decimal
            if da and is_int(a):
                a = round4(a + 0.1)
            ia = round4(a * math.pow(10, da))
            ib = round4(b * math.pow(10, db))
            if not (da + db > 2 and math.fmod(ia * ib, 10) == 0):  # no trailing zero to explain away
                break
        if lvl >= 2 and d.random() < 0.5:
            if d.random() < 0.5:
                a = -a
            else:
                b = -b
        ans, expr = round4(a * b), f"{num(a)} × {pn(b)}"
        places = f"Count decimal places: {da} + {db} = {da + db}, so the answer has {da + db}."
        return {
            "expr": expr, "ask": EQ, "answer": N(ans),
            "wrong": [
                N(ans * 10, places), N(ans / 10, places), N(ans * 100, places) if da + db > 2 else None,
                N(a + b, "You added. × means multiply."),
                N(-ans, "Check the sign: one negative makes the product negative.") if ans < 0 else None,
            ],
            "hint": "Multiply as if there were no decimal points, then count the decimal places in both numbers.",
            "steps": [
                [f"{J(ia)} × {J(ib)} = {J(round4(ia * ib))}", "Multiply without the decimal points"],
                [f"{da} + {db} = {da + db} decimal place{'' if da + db == 1 else 's'}", "Count the decimal places"],
                [f"{expr} = {num(ans)}", "One negative → negative" if ans < 0 else ""],
            ],
        }

    if kind == "quotient":
        # a ÷ b with a decimal divisor: shift both decimal points (two places
        # for a hundredths divisor at level 4)
        two = lvl >= 4 and d.random() < 0.4
        b = d.pick([0.05, 0.04, 0.25, 0.12, 0.08, 0.15, 0.06]) if two else d.rand(2, 9) / 10
        q = d.rand(2, 20 if lvl >= 4 else 12) * (d.neg(0.4) if lvl >= 2 else 1)
        if not two and lvl >= 3 and d.random() < 0.3:
            b = d.rand(11, 25) / 10
            if is_int(b):
                b += 0.1
        a, k = round4(q * b), 100 if two else 10
        expr = f"{num(a)} ÷ {pn(b)}"
        shift = f"Move the decimal point in both numbers: {num(a)} ÷ {num(b)} is the same as {num(a * k)} ÷ {num(b * k)}."
        return {
            "expr": expr, "ask": EQ, "answer": N(q),
            "wrong": [
                N(q / 10, shift), N(q * 10, shift),
                N(a * b, "You multiplied. ÷ means divide."),
                N(-q, "Check the sign: a negative divided by a positive is negative.") if q < 0 else None,
            ],
            "hint": f"Multiply both numbers by {k} so you divide by a whole number.",
            "steps": [[f"{expr} = {num(a * k)} ÷ {num(b * k)}", f"Multiply both by {k}"],
                      [f"= {num(q)}", "Negative ÷ positive → negative" if q < 0 else ""]],
        }

    if kind == "convert":
        # n/d as a decimal: it ends, or (level 4) a block of digits repeats forever
        rep = lvl >= 4 and d.random() < 0.5
        n, dd = d.pick(
            [[1, 3], [2, 3], [1, 6], [5, 6], [4, 9], [7, 9], [2, 11], [5, 12], [7, 12], [4, 15]] if rep
            else [[1, 4], [3, 4], [1, 8], [3, 8], [5, 8], [7, 8], [2, 5], [4, 5], [3, 20], [7, 20], [9, 20], [7, 25], [11, 25]]
        )
        L = long_divide(n, dd)
        wrong = [
            T(f"{n}.{dd}", f"The fraction bar means divide: {n} ÷ {dd}, not {n} point {dd}."),
            T(long_divide(dd, n)["html"], f"That's {dd} ÷ {n}. Divide the top by the bottom."),
        ]
        if rep:
            forever = f"{L['whole']}.{L['fixed']}{L['cycle'] * 3}…"
            wrong.append(T(f"{L['whole']}.{L['fixed']}{L['cycle']}",
                           f"It doesn't stop there: {n} ÷ {dd} = {forever}, so a bar goes over the {L['cycle']}."))
            wrong.append(
                T(f"{L['whole']}.<span class=\"rep\">{L['fixed']}{L['cycle']}</span>", f"Only the {L['cycle']} repeats: {forever}")
                if L["fixed"]
                else T(js_fixed(n / dd, 3), f"That stops too soon: {n} ÷ {dd} goes on forever, so a bar goes over the {L['cycle']}.")
            )
            steps = [
                [f"{n} ÷ {dd} = {forever}", "Divide: the same remainder keeps coming back"],
                [f"= {L['html']}", f"The bar means the {L['cycle']} repeats forever"],
            ]
        else:
            pw = next(t for t in (10, 100, 1000) if t % dd == 0)
            top = n * pw // dd
            wrong.append(T(long_divide(n * 10, dd)["html"], f"Decimal point slip: {n} ÷ {dd} is less than 1."))
            wrong.append(T(long_divide(n, dd * 10)["html"], f"Decimal point slip: {stack(n, dd)} = {stack(top, pw)}."))
            steps = [
                [f"{stack(n, dd)} = {stack(top, pw)}", f"Multiply top and bottom by {pw // dd}"],
                [f"= {L['html']}", f"{top} {'tenths' if pw == 10 else 'hundredths' if pw == 100 else 'thousandths'}"],
            ]
        return {"expr": stack(n, dd), "ask": EQ, "answer": T(L["html"]), "wrong": wrong, "steps": steps,
                "hint": "A fraction bar means divide: the top ÷ the bottom."}

    # x ± y × z with decimals: multiply first
    while True:
        x = d.rand(11, 99)
        if x % 10 != 0:
            break
    x = x / 10 * d.neg(0.4)
    y = d.rand(2, 9) / 10
    z = d.rand(2, 9) * d.neg(0.4)
    op = d.pick(["+", MINUS])
    s = 1 if op == "+" else -1
    yz = round4(y * z)
    ans = round4(x + s * yz)
    return {
        "expr": f"{num(x)} {op} {num(y)} × {pn(z)}", "ask": EQ, "answer": N(ans),
        "wrong": [
            N((x + s * y) * z, f"You went left to right. Multiply first: {num(y)} × {pn(z)} = {num(yz)}."),
            N(x + s * yz * 10, f"Decimal slip: {num(y)} × {pn(z)} = {num(yz)}, one decimal place."),
            N(x - s * yz, f"Check the sign: {num(y)} × {pn(z)} = {num(yz)}."),
        ],
        "hint": "Order of operations: multiply before you add or subtract.",
        "steps": [[f"{num(y)} × {pn(z)} = {num(yz)}", "Multiply first"],
                  [f"{num(x)} {op} {pn(yz)} = {num(ans)}", "Then add" if op == "+" else "Then subtract"]],
    }


def borrow_slip(a: int, b: int) -> int:
    """Column-by-column subtraction without borrowing (smaller digit from the
    larger in each column): 180 − 115 → 75, 90 − 35 → 65."""
    out, place = 0, 1
    while a > 0 or b > 0:
        out += abs(a % 10 - b % 10) * place
        a //= 10
        b //= 10
        place *= 10
    return out


def borrow_why(a: int, b: int) -> str:
    return f"Borrowing slip in {a} − {b}: line up the columns and borrow when the top digit is smaller."


def _cap(s: str) -> str:
    return s[0].upper() + s[1:]


def gen_angles(d: Dice, lvl: int) -> dict:
    kinds = ["supplement", "complement", "triangle", "crossing"]
    if lvl >= 3:
        kinds.append("algebra")
    kind = d.pick(kinds)
    base = {"words": True, "pos": True, "ask": EQ}

    if kind == "supplement":
        while True:
            x = d.rand(10, 170)
            if x != 90:
                break
        return {
            **base, "expr": f"Find the supplement of {x}°.", "answer": D(180 - x),
            "wrong": [
                D(90 - x, "That's the complement (they add to 90°). Supplements add to 180°."),
                D(360 - x, "Supplements add to 180°, not 360°."),
                D(borrow_slip(180, x), borrow_why(180, x)),
            ],
            "hint": "Supplementary angles add up to 180°.",
            "steps": [[f"180° − {x}° = {180 - x}°", "Supplementary angles add to 180°"]],
        }
    if kind == "complement":
        x = d.rand(10, 80)
        return {
            **base, "expr": f"Find the complement of {x}°.", "answer": D(90 - x),
            "wrong": [
                D(180 - x, "That's the supplement (they add to 180°). Complements add to 90°."),
                D(360 - x, "Complements add to 90°, not 360°."),
                D(borrow_slip(90, x), borrow_why(90, x)),
            ],
            "hint": "Complementary angles add up to 90°.",
            "steps": [[f"90° − {x}° = {90 - x}°", "Complementary angles add to 90°"]],
        }
    if kind == "triangle":
        a = d.rand(25, 100)
        b = d.rand(20, 150 - a)
        c = 180 - a - b
        return {
            **base, "expr": f"A triangle has angles of {a}° and {b}°. What is the third angle?", "answer": D(c),
            "wrong": [
                D(360 - a - b, "A triangle's angles add to 180°, not 360°."),
                D(a + b, f"That's {a}° + {b}°. Subtract it from 180°."),
                D(borrow_slip(180, a + b), borrow_why(180, a + b)),
            ],
            "hint": "The three angles of a triangle add up to 180°.",
            "steps": [[f"{a}° + {b}° = {a + b}°", "Add the angles you know"], [f"180° − {a + b}° = {c}°", "A triangle's angles add to 180°"]],
        }
    if kind == "crossing":
        while True:
            x = d.rand(20, 160)
            if x != 90:
                break
        intro = f"Two straight lines cross. One of the four angles is {x}°."
        if d.random() < 0.6:
            return {
                **base, "expr": f"{intro} What is the angle right next to it?", "answer": D(180 - x),
                "wrong": [
                    D(x, "That's the angle across from it (vertical angles are equal). Angles side by side on a line add to 180°."),
                    D(90 - x, "Angles side by side on a straight line add to 180°, not 90°."),
                    D(360 - x, "All four angles add to 360°, but two side by side add to 180°."),
                    D(borrow_slip(180, x), borrow_why(180, x)),
                ],
                "hint": "Two angles side by side on a straight line add to 180°.",
                "steps": [[f"180° − {x}° = {180 - x}°", "Side by side on a line: they add to 180°"]],
            }
        return {
            **base, "expr": f"{intro} What is the angle straight across from it?", "answer": D(x),
            "wrong": [
                D(180 - x, "That's the angle next to it. The angle straight across (the vertical angle) is equal."),
                D(360 - x, "Vertical angles (straight across) are equal."),
            ],
            "hint": "Angles straight across from each other are equal (vertical angles).",
            "steps": [[f"{x}°", "Vertical angles are equal"]],
        }

    # x° and (m·x + b)° are supplementary or complementary
    total = 180 if d.random() < 0.6 else 90
    other = 270 - total
    m = d.rand(2, 4)
    # x range that keeps the constant b between −40 and 40
    x_lo = max(8, math.ceil((total - 40) / (m + 1)))
    x_hi = math.floor((total + 40) / (m + 1))
    while True:
        x = d.rand(x_lo, x_hi)
        b = total - (m + 1) * x
        if b != 0:
            break
    name = "supplementary" if total == 180 else "complementary"
    return {
        "expr": f"Two angles are {name}. One is x°, the other is ({m}x{plus(b)})°. Find x.", "ask": "x =",
        "words": True, "pos": True, "answer": N(x),
        "wrong": [
            N((other - b) / (m + 1), f"{_cap(name)} angles add to {total}°, not {other}°."),
            N((total + b) / (m + 1), f"To undo {term(b)}, {'subtract' if b > 0 else 'add'} {abs(b)}."),
            N(total - b, f"x + {m}x = {m + 1}x, so divide by {m + 1} at the end."),
            N((total - b) / m, f"x + {m}x is {m + 1}x, not {m}x."),
        ],
        "hint": f"The two angles add to {total}°: x + {m}x{plus(b)} = {total}.",
        "steps": [
            [f"x + {m}x{plus(b)} = {total}", f"{_cap(name)}: they add to {total}°"],
            [f"{m + 1}x = {total - b}", "Combine like terms, then " + undo_term(b).lower()],
            [f"x = {total - b} ÷ {m + 1} = {x}", f"Divide by {m + 1}"],
        ],
    }


# ---------- Inequalities ----------
INEQ = {"<": "&lt;", ">": "&gt;", "≤": "≤", "≥": "≥"}
FLIP = {"<": ">", ">": "<", "≤": "≥", "≥": "≤"}
DOT = {"<": "≤", ">": "≥", "≤": "<", "≥": ">"}  # same direction, the other kind of dot
RELS = ["<", ">", "≤", "≥"]


def ineq(r: str, v) -> str:
    return f"x {INEQ[r]} {num(v)}"


def rightward(r: str) -> bool:
    return r in (">", "≥")


def flip_why(a, verb: str) -> str:
    return (f"{verb} both sides by a negative ({num(a)}) flips the inequality sign." if a < 0
            else f"Only flip the sign when you multiply or divide by a negative. {num(a)} is positive.")


SIGN_WHY = "Check the sign of the number."
BOTH_WHY = "Check the sign of the number, and whether the inequality flips."


def approx(v: float) -> str:
    """A positive quotient to two places, with … when it goes on: 38 ÷ 6 = 6.33…"""
    return num(v) if abs(v * 100 - js_round(v * 100)) < 1e-9 else num(math.floor(v * 100) / 100) + "…"


def ineq_solve(d: Dice, expr, rel, c, f, sol, x0, wrong, steps, hint, tstep=1) -> dict:
    """Solved like an equation and answered as x > 3. f is the left side, for a
    test point tstep past the answer; the walkthrough graphs the solution."""
    t = x0 + (tstep if rightward(sol) else -tstep)
    steps.append([f"Test x = {num(t)}: {num(f(t))} {INEQ[rel]} {num(c)} ✓", "A number from the shaded side works"])
    return {
        "expr": expr, "ask": "→", "answer": T(ineq(sol, x0)), "wrong": wrong, "steps": steps, "hint": hint,
        "ray": {"at": x0, "rel": sol},
        "near": lambda: T(ineq(d.pick([sol, FLIP[sol]]), x0 + d.sgn() * d.rand(1, 2))),
    }


def solve_step(a, sol, x0, verb="Divide") -> list:
    return [ineq(sol, x0), f"{verb} both sides by {num(a)}{' and flip the sign' if a < 0 else ''}"]


def gen_inequality(d: Dice, lvl: int) -> dict:
    """One-step at level 2; two-step, graphing and word problems join at 3,
    and a(x + b) and x ÷ a + b at 4, with the numbers growing as they go."""
    kinds = ["add", "mul", "mul"]
    if lvl >= 3:
        kinds += ["two", "two", "graph", "words"]
    if lvl >= 4:
        kinds += ["distribute", "divide", "graph", "words"]
    kind = d.pick(kinds)
    if kind == "graph":
        return ineq_graph(d, lvl)
    if kind == "words":
        return ineq_words(d, lvl)
    R = [9, 9, 9, 12, 15][lvl]  # how far from 0 the answer can be
    rel = d.pick(RELS)

    # x + b rel c: adding and subtracting never flip it
    if kind == "add":
        x0 = d.rand(1, R) * d.sgn()
        b = d.rand(1, 12) * d.sgn()
        c = x0 + b
        return ineq_solve(d, f"x{plus(b)} {INEQ[rel]} {num(c)}", rel, c, lambda x: x + b, rel, x0, [
            T(ineq(rel, c + b), f"To undo {term(b)}, {'subtract' if b > 0 else 'add'} {abs(b)}."),
            T(ineq(FLIP[rel], x0), "Adding or subtracting never flips the sign. Only multiplying or dividing by a negative does."),
            T(ineq(rel, -x0), SIGN_WHY),
        ], [[ineq(rel, x0), undo_term(b)]], f"Undo the {term(b)} on both sides, as in an equation.")

    if kind == "mul":
        # x ÷ a rel k (written −x/3 when a is negative)
        if d.random() < 0.3:
            a = d.rand(2, 6) * d.neg(0.5)
            k = d.rand(1, 9) * d.sgn()
            x0 = a * k
            sol = FLIP[rel] if a < 0 else rel
            return ineq_solve(d, f"{MINUS if a < 0 else ''}{stack('x', abs(a))} {INEQ[rel]} {num(k)}", rel, k, lambda x: x / a, sol, x0, [
                T(ineq(FLIP[sol], x0), flip_why(a, "Multiplying")),
                T(ineq(sol, -x0), SIGN_WHY),
                T(ineq(FLIP[sol], -x0), BOTH_WHY),
                T(ineq(sol, k / a), f"You divided. To undo ÷ {pn(a)}, multiply.") if is_int(k / a) else None,
            ], [solve_step(a, sol, x0, "Multiply")], f"Multiply both sides by {num(a)}. Multiplying by a negative flips the sign.", abs(a))
        # a·x rel c
        a = d.rand(2, 9) * d.neg(0.6)
        x0 = d.rand(1, R) * d.sgn()
        c = a * x0
        sol = FLIP[rel] if a < 0 else rel
        return ineq_solve(d, f"{coef(a)}x {INEQ[rel]} {num(c)}", rel, c, lambda x: a * x, sol, x0, [
            T(ineq(FLIP[sol], x0), flip_why(a, "Dividing")),
            T(ineq(sol, -x0), SIGN_WHY),
            T(ineq(FLIP[sol], -x0), BOTH_WHY),
        ], [solve_step(a, sol, x0)], f"Divide both sides by {num(a)}. Dividing by a negative flips the sign.")

    # a·x + b rel c
    if kind == "two":
        a = d.rand(2, 9 if lvl >= 4 else 6) * d.neg(0.65)
        x0 = d.rand(1, R) * d.sgn()
        b = d.rand(1, 20 if lvl >= 4 else 12) * d.sgn()
        c = a * x0 + b
        sol = FLIP[rel] if a < 0 else rel
        wrong = [T(ineq(FLIP[sol], x0), flip_why(a, "Dividing")), T(ineq(sol, -x0), SIGN_WHY)]
        slip = (c + b) / a
        if is_int(slip) and abs(slip) != abs(x0):
            wrong.append(T(ineq(sol, slip), f"To undo {term(b)}, {'subtract' if b > 0 else 'add'} {abs(b)}."))
        else:
            wrong.append(T(ineq(FLIP[sol], -x0), BOTH_WHY))
        return ineq_solve(d, f"{coef(a)}x{plus(b)} {INEQ[rel]} {num(c)}", rel, c, lambda x: a * x + b, sol, x0, wrong,
                          [[f"{coef(a)}x {INEQ[rel]} {num(c - b)}", undo_term(b)], solve_step(a, sol, x0)],
                          "Solve it like an equation. If you multiply or divide by a negative, flip the sign.")

    # a(x + b) rel c: divide by a, then undo b
    if kind == "distribute":
        while True:
            a = d.rand(2, 6) * d.neg(0.6)
            b = d.rand(1, 9) * d.sgn()
            x0 = d.rand(1, R) * d.sgn()
            if x0 + b != 0:
                break
        c = a * (x0 + b)
        sol = FLIP[rel] if a < 0 else rel
        slip = (c - b) / a
        return ineq_solve(d, f"{num(a)}({lin(1, b)}) {INEQ[rel]} {num(c)}", rel, c, lambda x: a * (x + b), sol, x0, [
            T(ineq(FLIP[sol], x0), flip_why(a, "Dividing")),
            T(ineq(sol, slip), f"The {num(a)} multiplies the {num(b)} too.") if is_int(slip) else None,
            T(ineq(sol, c / a + b), f"After dividing, undo the {term(b)} by {'subtracting' if b > 0 else 'adding'}."),
            T(ineq(sol, -x0), SIGN_WHY),
        ], [
            [f"{lin(1, b)} {INEQ[sol]} {num(x0 + b)}", f"Divide both sides by {num(a)}{' and flip the sign' if a < 0 else ''}"],
            [ineq(sol, x0), undo_term(b)],
        ], f"Divide both sides by {num(a)}, then undo the {term(b)}. Dividing by a negative flips the sign.")

    # x ÷ a + b rel c: undo b, then multiply by a
    a = d.rand(2, 5) * d.neg(0.5)
    k = d.rand(1, 8) * d.sgn()
    b = d.rand(1, 12) * d.sgn()
    x0, c = a * k, k + b
    sol = FLIP[rel] if a < 0 else rel
    part = f"{MINUS if a < 0 else ''}{stack('x', abs(a))}"
    return ineq_solve(d, f"{part}{plus(b)} {INEQ[rel]} {num(c)}", rel, c, lambda x: x / a + b, sol, x0, [
        T(ineq(FLIP[sol], x0), flip_why(a, "Multiplying")),
        T(ineq(sol, (c + b) * a), f"To undo {term(b)}, {'subtract' if b > 0 else 'add'} {abs(b)}."),
        T(ineq(sol, c * a - b), f"Undo the {term(b)} before you multiply by {num(a)}."),
        T(ineq(sol, -x0), SIGN_WHY),
    ], [[f"{part} {INEQ[rel]} {num(k)}", undo_term(b)], solve_step(a, sol, x0, "Multiply")],
        f"Undo the {term(b)} first, then multiply both sides by {num(a)}. Multiplying by a negative flips the sign.", abs(a))


def ineq_graph(d: Dice, lvl: int) -> dict:
    """Which graph shows it? Filled or open dot, shaded left or right. Level 3
    mixes in the number-first form (3 > x); level 4 adds a step to solve."""
    rel = d.pick(RELS)
    r = d.random()
    x0 = d.rand(1, 8) * d.sgn()
    sol, expr, first, a = rel, ineq(rel, x0), None, 0
    if lvl >= 4 and r < 0.4:
        a = d.rand(2, 6) * d.neg(0.5)
        expr = f"{coef(a)}x {INEQ[rel]} {num(a * x0)}"
        sol = FLIP[rel] if a < 0 else rel
        first = solve_step(a, sol, x0)
    elif r < (0.7 if lvl >= 4 else 0.35):
        expr = f"{num(x0)} {INEQ[rel]} x"
        sol = FLIP[rel]
        first = [f"{expr} is the same as {ineq(sol, x0)}", "Read it starting from x"]
    lo, hi = -abs(x0) - 2, abs(x0) + 2
    incl = sol in ("≤", "≥")
    right = rightward(sol)

    def G(rr, v, why=None) -> Opt:
        o = T(ineq(rr, v), why)
        o.key = "g" + o.key
        o.say, o.graph = ineq(rr, v), (v, rr, lo, hi)
        return o

    dir_why = (flip_why(a, "Dividing") if a < 0
               else f"{expr} means x is {'bigger' if right else 'smaller'} than {num(x0)}. Read it starting from x." if first and not a
               else f"{ineq(sol, x0)} means the numbers {'bigger' if right else 'smaller'} than {num(x0)}: shade to the {'right' if right else 'left'}.")
    return {
        "expr": expr, "ask": "Graph:", "answer": G(sol, x0),
        "wrong": [
            G(DOT[sol], x0, f"{INEQ[sol]} includes {num(x0)} itself, so its dot is filled in." if incl
              else f"{INEQ[sol]} leaves {num(x0)} out, so its dot is open."),
            G(FLIP[sol], x0, dir_why),
            G(DOT[FLIP[sol]], x0, "Check both the dot and the direction."),
            G(sol, -x0, SIGN_WHY),
        ],
        "hint": f"A filled dot means the number itself counts (≤ or ≥), an open dot means it doesn't ({INEQ['<']} or {INEQ['>']}). "
                "Then shade toward the numbers that work.",
        "steps": [
            *([first] if first else []),
            [f"{'Filled' if incl else 'Open'} dot on {num(x0)}", f"{num(x0)} itself {'is' if incl else 'is not'} a solution"],
            [f"Shade to the {'right' if right else 'left'}", f"Every number {'bigger' if right else 'smaller'} than {num(x0)}"],
        ],
        "ray": {"at": x0, "rel": sol},
    }


# Word problems: a budget (at most) or a goal (at least). Only whole ones
# count, so a budget rounds down and a goal rounds up; below level 4 the
# numbers come out even. A third of them ask which inequality fits instead.
BUDGETS = [
    {"what": "rides", "one": "ride", "ask": "Rides =", "fee": "the entry fee", "f": [4, 10], "p": [2, 5], "money": True,
     "text": lambda B, f, p: f"You have {money(B)} at the fair. It costs {money(f)} to get in and {money(p)} for each ride.",
     "q": "What is the greatest number of rides you can go on?"},
    {"what": "books", "one": "book", "ask": "Books =", "fee": "shipping", "f": [4, 8], "p": [6, 12], "money": True,
     "text": lambda B, f, p: f"You have a {money(B)} gift card. Each book costs {money(p)}, and shipping is {money(f)} for the whole order.",
     "q": "What is the greatest number of books you can buy?"},
    {"what": "boxes", "one": "box", "ask": "Boxes =", "fee": "the worker", "f": [60, 95], "p": [20, 45],
     "text": lambda B, f, p: f"An elevator can carry {J(B)} kg. A worker who weighs {J(f)} kg is loading boxes of {J(p)} kg each.",
     "q": "What is the greatest number of boxes the worker can bring on one trip?"},
]
GOALS = [
    {"what": "weeks", "one": "week", "ask": "Weeks =", "start": "the money you've saved", "s": [20, 60], "p": [5, 15], "money": True,
     "text": lambda s, p: f"You've saved {money(s)} and save {money(p)} more each week.",
     "q": lambda G: f"After how many weeks will you have at least {money(G)}?"},
    {"what": "sales", "one": "sale", "ask": "Sales =", "start": "the base pay", "s": [40, 100], "p": [3, 8], "money": True,
     "text": lambda s, p: f"A job pays {money(s)} a week plus {money(p)} for each sale.",
     "q": lambda G: f"What is the fewest sales that earn at least {money(G)} in a week?"},
    {"what": "weeks", "one": "week", "ask": "Weeks =", "start": "what it weighs now", "s": [8, 30], "p": [3, 9],
     "text": lambda s, p: f"A baby dinosaur weighs {J(s)} kg and gains {J(p)} kg a week.",
     "q": lambda G: f"After how many weeks will it weigh at least {J(G)} kg?"},
]


def ineq_words(d: Dice, lvl: int) -> dict:
    exact = lvl < 4
    write = d.random() < 0.33
    n = d.rand(3, 12)
    # The first two of each list suit "which inequality". The elevator only
    # comes with a remainder to round, so it can hold a round 600 kg.
    even = exact or write
    if d.random() < 0.5:
        sc = d.pick(BUDGETS[:2] if even else BUDGETS)
    else:
        sc = d.pick(GOALS[:2] if write else GOALS)
    fmt = money if sc.get("money") else (lambda v: f"{num(v)} kg")
    p = d.rand(2 * sc["p"][0], 2 * sc["p"][1]) / 2 if sc.get("money") and not exact else d.rand(*sc["p"])  # $2.50 a ride at level 4
    extra = 0 if even else (d.rand(1, 2 * p - 1) / 2 if sc.get("money") else d.rand(1, p - 1))

    if "fee" in sc:  # p·n + f ≤ B
        while True:
            f = d.rand(*sc["f"])
            if f != p:  # else "p·n + f" and "f·n + p" read the same
                break
        B = round4(p * n + f + extra) if sc.get("money") else math.ceil((p * n + f + 1) / 10) * 10
        lhs = f"{num(p)}n + {num(f)}"
        if write:
            return {
                "expr": f"{sc['text'](B, f, p)} Which inequality fits n, the number of {sc['what']}?", "ask": "→", "words": True,
                "answer": T(f"{lhs} ≤ {num(B)}"),
                "wrong": [
                    T(f"{lhs} ≥ {num(B)}", f"You can't spend more than {fmt(B)}, so the total is at most {num(B)}: ≤."),
                    T(f"{num(f)}n + {num(p)} ≤ {num(B)}", f"{fmt(p)} is for each {sc['one']}, so it goes with n."),
                    T(f"{num(p + f)}n ≤ {num(B)}", f"{_cap(sc['fee'])} is paid once, not for each {sc['one']}."),
                ],
                "hint": f"n {sc['what']} cost {num(p)}n. Add what you pay once, and the total can be at most {fmt(B)}.",
                "steps": [[f"{num(p)}n", f"{fmt(p)} for each of n {sc['what']}"], [lhs, f"Plus {fmt(f)}, paid once"], [f"{lhs} ≤ {num(B)}", f"At most {fmt(B)}"]],
            }
        return {
            "expr": f"{sc['text'](B, f, p)} {sc['q']}", "ask": sc["ask"], "words": True, "pos": True, "answer": N(n),
            "wrong": [
                N(n + 1, f"{n + 1} {sc['what']} would come to {fmt(p * (n + 1) + f)}, over {fmt(B)}.{'' if exact else ' Round down.'}"),
                N(math.floor((B + f) / p), f"{_cap(sc['fee'])} uses up {fmt(f)} too: subtract it, don't add it."),
                N(math.floor(B / p), f"Don't forget {sc['fee']}: take {fmt(f)} off first."),
            ],
            "hint": f"Solve {lhs} ≤ {num(B)}, then keep whole {sc['what']} only.",
            "steps": [
                [f"{lhs} ≤ {num(B)}", f"The total can't go over {fmt(B)}"],
                [f"{num(p)}n ≤ {num(B - f)}", f"Subtract {num(f)}"],
                [f"n ≤ {num(B - f)} ÷ {num(p)} = {approx((B - f) / p)}", f"Divide by {num(p)}"],
                *([] if exact else [[f"n = {n}", f"Round down: whole {sc['what']} only, and {n + 1} would go over"]]),
            ],
        }

    # s + p·n ≥ G
    s = d.rand(*sc["s"])
    G = round4(s + p * n - extra)
    lhs = f"{num(s)} + {num(p)}n"
    if write:
        return {
            "expr": f"{sc['text'](s, p)} Which inequality fits n, the number of {sc['what']} it takes to reach {fmt(G)} or more?",
            "ask": "→", "words": True, "answer": T(f"{lhs} ≥ {num(G)}"),
            "wrong": [
                T(f"{lhs} ≤ {num(G)}", f'"{fmt(G)} or more" means at least {num(G)}: ≥.'),
                T(f"{num(p)} + {num(s)}n ≥ {num(G)}", f"{fmt(p)} is for each {sc['one']}, so it goes with n."),
                T(f"{num(p)}n ≥ {num(G)}", f"Count {sc['start']} too."),
            ],
            "hint": f"Start with {fmt(s)}, add {num(p)}n, and the total has to be at least {fmt(G)}.",
            "steps": [[f"{num(p)}n", f"{fmt(p)} for each of n {sc['what']}"], [lhs, f"Plus {sc['start']}"], [f"{lhs} ≥ {num(G)}", f"{fmt(G)} or more"]],
        }
    return {
        "expr": f"{sc['text'](s, p)} {sc['q'](G)}", "ask": sc["ask"], "words": True, "pos": True, "answer": N(n),
        "wrong": [
            N(n - 1, f"After {n - 1} {sc['what']} it's only {fmt(s + p * (n - 1))}, short of {fmt(G)}.{'' if exact else ' Round up.'}"),
            N(math.ceil((G + s) / p), f"{_cap(sc['start'])} counts toward the goal: subtract it, don't add it."),
            N(math.ceil(G / p), f"Don't forget {sc['start']}: take {fmt(s)} off the goal first."),
        ],
        "hint": f"Solve {lhs} ≥ {num(G)}, then round to a whole number that reaches the goal.",
        "steps": [
            [f"{lhs} ≥ {num(G)}", f"Reach {fmt(G)} or more"],
            [f"{num(p)}n ≥ {num(G - s)}", f"Subtract {num(s)}"],
            [f"n ≥ {num(G - s)} ÷ {num(p)} = {approx((G - s) / p)}", f"Divide by {num(p)}"],
            *([] if exact else [[f"n = {n}", f"Round up: {n - 1} falls short"]]),
        ],
    }


# ---------- Expressions (7.EE.1-2) ----------


def sum_of(terms: list) -> str:
    """Terms [coefficient, letter] written the usual way, zeros left out:
    [[3, 'x'], [-5, ''], [1, 'x']] → 3x − 5 + x."""
    kept = [(round4(k), v) for k, v in terms]
    kept = [(k, v) for k, v in kept if k and not math.isnan(k)]
    out = []
    for i, (k, v) in enumerate(kept):
        body = coef(abs(k)) + v if v else num(abs(k))
        out.append(f" {MINUS if k < 0 else '+'} {body}" if i else (MINUS if k < 0 else "") + body)
    return "".join(out) or "0"


def lin(a, b, v: str = "x") -> str:  # ax + b
    return sum_of([[a, v], [b, ""]])


def px(k) -> str:  # −3 × (−2x)
    return f"({lin(k, 0)})" if k < 0 else lin(k, 0)


def gen_expressions(d: Dice, lvl: int) -> dict:
    """Combine like terms and distribute from level 2; subtracting a
    parenthesis, factoring out the GCF and percent change as one product
    (p + 0.08p = 1.08p) at 3; fraction and decimal coefficients at 4."""
    kinds = ["combine", "combine", "distribute", "distribute"]
    if lvl >= 3:
        kinds += ["subtract", "factor", "percent"]
    if lvl >= 4:
        kinds += ["subtract", "rational", "rational"]
    kind = d.pick(kinds)
    R = 12 if lvl >= 4 else 9
    signs = "Each sign belongs to the term after it:"

    # a·x + b + c·x + d in any order (decimals at level 4)
    if kind == "combine" or (kind == "rational" and d.random() < 0.5):
        dec = kind == "rational"
        while True:
            if dec:
                a = d.pick([0.5, 1.5, 2.5, 0.25, 0.75, 1.2, 0.4, 3.5])
                c = d.pick([0.5, 1.5, 0.25, 0.75, 0.2, 1.4]) * d.sgn()
                b = d.rand(1, 90) / 10 * d.sgn()
                e = d.rand(1, 90) / 10 * d.sgn()
            else:
                a = d.rand(2, R)
                c = d.rand(1, R) * d.sgn()
                b = d.rand(1, 12) * d.sgn()
                e = d.rand(1, 12) * d.sgn()
            if not (round4(a + c) == 0 or round4(b + e) == 0 or round4(a + b + c + e) == 0 or a == c):
                break
        X, K = round4(a + c), round4(b + e)
        xs, ks = sum_of([[a, "x"], [c, "x"]]), sum_of([[b, ""], [e, ""]])
        return {
            "expr": sum_of(d.shuffle([[a, "x"], [b, ""], [c, "x"], [e, ""]])), "ask": EQ, "answer": T(lin(X, K)),
            "wrong": [
                T(lin(a - c, K), f"{signs} {xs} = {lin(X, 0)}."),
                T(lin(X, b - e), f"{signs} {ks} = {num(K)}."),
                T(lin(X + K, 0), "Only like terms combine: x terms with x terms, numbers with numbers."),
                T(lin(-X, -K), "Sign slip. Check the sign in front of each term."),
            ],
            "near": lambda: T(lin(X + d.sgn() * d.rand(1, 2), K)),
            "hint": "Collect the x terms and the plain numbers separately. Each sign stays with the term after it.",
            "steps": [[f"{xs} = {lin(X, 0)}", "Combine the x terms"], [f"{ks} = {num(K)}", "Combine the numbers"], [f"= {lin(X, K)}", "Put them together"]],
        }

    # a(bx + c)
    if kind == "distribute":
        a = d.rand(2, R if lvl >= 3 else 6) * d.sgn()
        b = d.rand(1, 6 if lvl >= 3 else 4) * (d.neg(0.3) if lvl >= 3 else 1)
        c = d.rand(1, 9) * d.sgn()
        if a > 0 and c > 0 and d.random() < 0.6:
            a = -a
        expr, A, B = f"{num(a)}({lin(b, c)})", a * b, a * c
        return {
            "expr": expr, "ask": EQ, "answer": T(lin(A, B)),
            "wrong": [
                T(lin(A, c), f"{num(a)} multiplies every term inside, the {num(c)} too."),
                T(lin(A, -B), f"Sign slip: {num(a)} × {pn(c)} = {num(B)}."),
                T(lin(-A, B), f"Sign slip: {num(a)} × {px(b)} = {lin(A, 0)}."),
                T(lin(A, a + c), f"That adds {num(a)} and {pn(c)}. Multiply: {num(a)} × {pn(c)} = {num(B)}."),
            ],
            "near": lambda: T(lin(A, B + d.sgn() * d.rand(1, 3))),
            "hint": f"Multiply {num(a)} by each term inside the parentheses. Watch the signs.",
            "steps": [[f"{num(a)} × {px(b)} = {lin(A, 0)}", "Multiply the x term"], [f"{num(a)} × {pn(c)} = {num(B)}", "Multiply the number too"],
                      [f"{expr} = {lin(A, B)}", ""]],
        }

    if kind == "subtract":
        # (ax + b) − (cx + d): the minus reaches every term inside
        if d.random() < 0.5:
            while True:
                a = d.rand(2, R)
                b = d.rand(1, 12) * d.sgn()
                c = d.rand(1, R)
                e = d.rand(1, 12) * d.sgn()
                if not (a == c or b == e):
                    break
            X, K = a - c, b - e
            return {
                "expr": f"({lin(a, b)}) {MINUS} ({lin(c, e)})", "ask": EQ, "answer": T(lin(X, K)),
                "wrong": [
                    T(lin(X, b + e), f"The minus in front of the parentheses changes every sign inside, so {term(e)} becomes {term(-e)}."),
                    T(lin(a + c, K), f"The minus reaches the {lin(c, 0)} too: {lin(a, 0)} {MINUS} {lin(c, 0)} = {lin(X, 0)}."),
                    T(lin(a + c, b + e), "You added. The minus subtracts everything in the parentheses."),
                ],
                "near": lambda: T(lin(X, K + d.sgn() * d.rand(1, 2))),
                "hint": "Subtracting a parenthesis subtracts every term in it: flip each sign inside, then combine.",
                "steps": [[sum_of([[a, "x"], [b, ""], [-c, "x"], [-e, ""]]), "Drop the parentheses: flip every sign inside the second one"],
                          [f"= {lin(X, K)}", "Combine like terms"]],
            }
        # p(x + q) − r(x + s)
        while True:
            p = d.rand(2, 6)
            q = d.rand(1, 9) * d.sgn()
            r = d.rand(2, 6)
            s = d.rand(1, 9) * d.sgn()
            if p != r:
                break
        X, K = p - r, p * q - r * s
        return {
            "expr": f"{p}({lin(1, q)}) {MINUS} {r}({lin(1, s)})", "ask": EQ, "answer": T(lin(X, K)),
            "wrong": [
                T(lin(X, p * q + r * s), f"The minus goes with the {r}: {MINUS}{r} × {pn(s)} = {num(-r * s)}."),
                T(lin(X, p * q - s), f"The {r} multiplies the {num(s)} too."),
                T(lin(p + r, K), f"{p}x {MINUS} {r}x = {lin(X, 0)}."),
                T(lin(X, q - s), f"Distribute before you combine: {p} × {pn(q)} and {MINUS}{r} × {pn(s)}."),
            ],
            "near": lambda: T(lin(X, K + d.sgn() * d.rand(1, 3))),
            "hint": f"Distribute the {p} and the {MINUS}{r} (the minus sign goes with it), then combine like terms.",
            "steps": [[sum_of([[p, "x"], [p * q, ""], [-r, "x"], [-r * s, ""]]), f"Distribute {p} and {MINUS}{r}"], [f"= {lin(X, K)}", "Combine like terms"]],
        }

    # Factor out the greatest common factor: 12x + 18 = 6(2x + 3)
    if kind == "factor":
        g = d.pick([4, 6, 8, 9, 10, 12])
        f = d.pick([k for k in [2, 3, 4, 5, 6] if k < g and g % k == 0])
        while True:
            m = d.rand(1, 5)
            n = d.rand(1, 9) * d.sgn()
            if gcd(m, n) == 1:
                break
        whole, ans = lin(g * m, g * n), f"{g}({lin(m, n)})"
        return {
            "expr": "Factor out the greatest common factor.", "ask": f"{whole} = ?", "words": True, "answer": T(ans),
            "wrong": [
                T(f"{f}({lin(g * m / f, g * n / f)})", f"That's equal, but {f} isn't the greatest common factor: {g} goes into {g * m} and {abs(g * n)} too."),
                T(f"{g}({lin(m, g * n)})", f"Divide every term by {g}: {num(g * n)} ÷ {g} = {num(n)}."),
                T(f"{g}({lin(m, -n)})", f"Check the sign: {g} × {pn(-n)} is {num(-g * n)}, not {num(g * n)}."),
            ],
            "hint": f"Find the biggest number that goes into both {g * m} and {abs(g * n)}. Divide each term by it and write it in front.",
            "steps": [
                [f"{g * m} = {g} × {m}, &nbsp;{abs(g * n)} = {g} × {abs(n)}", f"{g} is the greatest common factor"],
                [f"{whole} = {ans}", f"Divide each term by {g}"],
                [f"{g} × {px(m)} = {lin(g * m, 0)}, &nbsp;{g} × {pn(n)} = {num(g * n)} ✓", "Check: multiply back out"],
            ],
        }

    # Percent change as one product: n + 0.08n = 1.08n
    if kind == "percent":
        up = d.random() < 0.5
        p = d.pick([3, 5, 6, 8, 12, 15, 20]) if up else d.pick([10, 15, 20, 25, 30, 40])
        v, text, ask = d.pick([
            ("n", f"A town has n people. The population grows {p}%.", "New population ="),
            ("p", f"A store raises a price p by {p}%.", "New price ="),
        ] if up else [
            ("p", f"A jacket that costs p dollars is {p}% off.", "Sale price ="),
            ("n", f"A herd of n dinosaurs shrinks by {p}%.", "New herd ="),
        ])
        r = p / 100
        k = 1 + r if up else 1 - r
        return {
            "expr": f"{text} Which expression shows the new amount?", "ask": ask, "words": True, "answer": T(f"{num(k)}{v}"),
            "wrong": [
                T(f"{num(r)}{v}", f"That's just the {'increase' if up else 'drop'}. {'Add it to' if up else 'Take it from'} {v}: {v} {'+' if up else MINUS} {num(r)}{v}."),
                T(f"{v} {'+' if up else MINUS} {p}", f"{p}% of {v} isn't {p}: it's {num(r)}{v}."),
                T(f"{num(1 - r if up else 1 + r)}{v}", "It grows, so the new amount is more than 1 whole." if up else "It drops, so the new amount is less than 1 whole."),
                T(f"{num(1 + p / 10)}{v}", f"{p}% = {num(r)}, not {num(p / 10)}.") if up else None,
            ],
            "hint": f"{p}% of {v} is {num(r)}{v}. {'Add it to' if up else 'Take it from'} {v}, which is 1{v}.",
            "steps": [
                [f"{v} {'+' if up else MINUS} {num(r)}{v}", f"{'Add' if up else 'Take off'} {p}% of {v}"],
                [f"= {num(k)}{v}", f"1{v} {'+' if up else MINUS} {num(r)}{v}: combine like terms"],
                [f"{num(k)}{v}", f"The new amount is {100 + p if up else 100 - p}% of the old one"],
            ],
        }

    # (n/d)(d·u·x + d·v): the fraction multiplies every term
    n, dd = d.pick([[1, 2], [1, 3], [2, 3], [1, 4], [3, 4], [2, 5], [3, 5]])
    s = d.neg(0.3)
    u = d.rand(1, 4)
    v = d.rand(1, 6) * d.sgn()
    k = (MINUS if s < 0 else "") + stack(n, dd)
    A, B = s * n * u, s * n * v
    return {
        "expr": f"{k}({lin(dd * u, dd * v)})", "ask": EQ, "answer": T(lin(A, B)),
        "wrong": [
            T(lin(A, dd * v), f"{k} multiplies every term inside, the {num(dd * v)} too."),
            T(lin(s * u, s * v), f"That divides by {dd} but doesn't multiply by {n}.") if n > 1
            else T(lin(s * dd * dd * u, s * dd * dd * v), f"Multiplying by {stack(1, dd)} divides by {dd}. You multiplied by {dd}."),
            T(lin(s * n * dd * u, s * n * dd * v), f"That multiplies by {n} but doesn't divide by {dd}.") if n > 1 else None,
            T(lin(A, -B), f"Sign slip: {k} × {pn(dd * v)} = {num(B)}."),
        ],
        "near": lambda: T(lin(A, B + d.sgn() * d.rand(1, 2))),
        "hint": (f"Multiplying by {k} divides each term by {dd}{' and flips its sign' if s < 0 else ''}." if n == 1
                 else f"Multiply each term by {k}: divide by {dd}, then multiply by {n}."),
        "steps": [[f"{k} × {lin(dd * u, 0)} = {lin(A, 0)}", "Multiply the x term"], [f"{k} × {pn(dd * v)} = {num(B)}", "Multiply the number too"],
                  [f"= {lin(A, B)}", ""]],
    }


# ---------- Probability (7.SP.5-8) ----------
COLORS = ["red", "blue", "green", "yellow", "purple", "orange"]


def is_prime(v) -> bool:  # enough for 1 to 12
    return v in (2, 3, 5, 7, 11)


def list_of(xs: list) -> str:
    return ", ".join(xs[:-1]) + " and " + xs[-1]


def simplify(n, dd) -> str:
    return f" = {frac(n, dd)}" if gcd(n, dd) > 1 and dd > 0 else ""


def gen_probability(d: Dice, lvl: int) -> dict:
    """One pick from a bag, a number cube or spinner, expected counts and
    experimental probability; two things at once at level 4."""
    kinds = ["bag", "bag", "number", "number", "expect", "data"]
    if lvl >= 4:
        kinds += ["both", "both", "both"]
    kind = d.pick(kinds)

    if kind == "bag":
        things, box = d.pick([["marbles", "bag"], ["tiles", "box"], ["gumballs", "jar"], ["socks", "drawer"]])
        cols = d.shuffle(list(COLORS))[:3]
        cnt = [d.rand(1, 12 if lvl >= 4 else 8) for _ in cols]
        total = cnt[0] + cnt[1] + cnt[2]
        i = d.rand(0, 2)
        j = (i + 1) % 3
        col = cols[i]
        form = d.pick(["one", "not", "or"]) if lvl >= 4 else d.pick(["one", "one", "not"])
        k = cnt[i] if form == "one" else total - cnt[i] if form == "not" else cnt[i] + cnt[j]
        what = col if form == "one" else f"not {col}" if form == "not" else f"{col} or {cols[j]}"
        answer = Q(k, total)
        steps = [[f"{' + '.join(map(str, cnt))} = {total}", f"{_cap(things)} in all"]]
        if form == "not":
            steps.append([f"{total} − {cnt[i]} = {k}", f"{_cap(things)} that aren't {col}"])
        if form == "or":
            steps.append([f"{cnt[i]} + {cnt[j]} = {k}", f"{_cap(things)} that are {what}"])
        steps.append([f"P({what}) = {raw(k, total)}{simplify(k, total)}", f"{k} out of all {total}"])
        return {
            "expr": f"A {box} holds {cnt[0]} {cols[0]}, {cnt[1]} {cols[1]} and {cnt[2]} {cols[2]} {things}. You pick one without looking. "
                    f"What is the probability it's {what}?",
            "ask": f"P({what}) =", "words": True, "answer": answer, "near": near_q(answer, d), "steps": steps,
            "wrong": [
                Q(k, total - k, f"That compares the {things} that work to the ones that don't. Probability divides by all {total}."),
                Q(total - k, total, f"That's the chance it's NOT {col}." if form == "one" else f"That's the chance it IS {col}." if form == "not"
                  else "That's the chance it's neither."),
                Q(cnt[i], total, f"That's just {col}. Add the {cols[j]} ones too.") if form == "or"
                else Q(1, 3, f"There are 3 colors, but they aren't equally likely. Count the {things}."),
            ],
            "hint": f"Probability = the {things} that work ÷ all the {things}.",
        }

    if kind == "number":
        devices = [[6, "roll a number cube (1 to 6)", "rolling"], [8, "spin a spinner with 8 equal parts numbered 1 to 8", "spinning"]]
        if lvl >= 4:
            devices.append([10, "pick one of 10 cards numbered 1 to 10 without looking", "picking"])
        n, act, verb = d.pick(devices)
        k = d.rand(2, n - 2)
        ev = d.pick([
            {"short": f"more than {k}", "long": f"a number greater than {k}", "ok": lambda v: v > k, "slip": lambda v: v >= k,
             "why": f"Greater than {k} leaves {k} itself out."},
            {"short": f"less than {k}", "long": f"a number less than {k}", "ok": lambda v: v < k, "slip": lambda v: v <= k,
             "why": f"Less than {k} leaves {k} itself out."},
            {"short": f"{k} or more", "long": f"{k} or more", "ok": lambda v: v >= k, "slip": lambda v: v > k, "why": f"{k} or more counts {k} itself."},
            {"short": "even", "long": "an even number", "ok": lambda v: v % 2 == 0},
            {"short": "prime", "long": "a prime number", "ok": is_prime, "slip": lambda v: v == 1 or is_prime(v), "why": "1 isn't a prime number."},
            {"short": "multiple of 3", "long": "a multiple of 3", "ok": lambda v: v % 3 == 0},
        ])
        every = list(range(1, n + 1))
        good = [v for v in every if ev["ok"](v)]
        g = len(good)
        answer = Q(g, n)
        return {
            "expr": f"You {act}. What is the probability of {verb} {ev['long']}?", "ask": f"P({ev['short']}) =", "words": True,
            "answer": answer, "near": near_q(answer, d),
            "wrong": [
                Q(n - g, n, f"That's the chance of NOT {verb} {ev['long']}."),
                Q(g, n - g, f"That compares the numbers that work to the ones that don't. Divide by all {n}."),
                Q(1, n, f"That's the chance of one number. Count every number that works: {', '.join(map(str, good))}.") if g > 1 else None,
                Q(len([v for v in every if ev["slip"](v)]), n, ev["why"]) if "slip" in ev else None,
            ],
            "hint": f"List the numbers that work, then divide by all {n} equally likely numbers.",
            "steps": [[", ".join(map(str, good)), f"The numbers that work: {g} of them"],
                      [f"P = {raw(g, n)}{simplify(g, n)}", f"{g} out of {n} equally likely numbers"]],
        }

    # About how many times? probability × tries
    if kind == "expect":
        form = d.pick(["cube", "spinner", "shots"])
        if form == "shots":
            pct = d.pick([40, 60, 75, 80, 90])
            n = 100 // gcd(pct, 100) * d.rand(2, 10 if lvl >= 4 else 5)
            ans = pct * n / 100
            return {
                "expr": f"A player makes {pct}% of free throws. About how many of the next {n} free throws should go in?",
                "ask": "About ? shots", "words": True, "pos": True, "answer": N(ans),
                "wrong": [
                    N(n - ans, "That's how many should miss."),
                    N(pct, f"{pct} is the percent, not the number of shots. Take {pct}% of {n}."),
                    N(pct * n / 10, f"Decimal slip: {pct}% = {num(pct / 100)}, two places."),
                ],
                "hint": f"Take {pct}% of the {n} free throws.",
                "steps": [[f"{pct}% = {num(pct / 100)}", "The chance of a make"], [f"{num(pct / 100)} × {n} = {J(ans)}", "Chance × number of tries"]],
            }
        k, dd = [1, 6] if form == "cube" else d.pick([[1, 4], [3, 8], [2, 5], [1, 3], [3, 4], [5, 8], [2, 3], [3, 10]])
        n = dd * d.rand(5 if lvl >= 4 else 3, 20 if lvl >= 4 else 10)
        ans = n * k / dd
        color = d.pick(COLORS)
        return {
            "expr": (f"You roll a number cube {n} times. About how many times should you expect to roll a {d.rand(1, 6)}?" if form == "cube"
                     else f"A spinner lands on {color} with probability {frac(k, dd)}. If you spin it {n} times, about how many times should it land on {color}?"),
            "ask": "About ? times", "words": True, "pos": True, "answer": N(ans),
            "wrong": [
                N(n - ans, "That's how many times it should NOT happen."),
                N(n * k, f"Divide by {dd} too: {frac(k, dd)} of {n} is {n} ÷ {dd} × {k}.") if k > 1
                else N(n / 2, f"It happens or it doesn't, but those aren't equally likely. The chance is {frac(1, dd)}."),
                N(n / dd, f"That's {frac(1, dd)} of {n}. Multiply by {k}.") if k > 1 else None,
            ],
            "hint": f"Each number has a {frac(1, 6)} chance. Take {frac(1, 6)} of {n}." if form == "cube" else "Multiply the probability by the number of spins.",
            "steps": [[f"{frac(k, dd)} × {n} = {n} ÷ {dd}{f' × {k}' if k > 1 else ''}",
                       f"Each number has a {frac(1, 6)} chance" if form == "cube" else "Probability × number of tries"],
                      [f"= {J(ans)}", "About that many: chance won't hit it exactly"]],
        }

    # Experimental probability: what happened ÷ how many tries
    if kind == "data":
        coin = d.random() < 0.5
        n = d.pick([20, 30, 40, 50, 60, 80, 100]) if coin else d.pick([30, 60, 90, 120])
        while True:
            h = d.rand(js_round(n * 0.3), js_round(n * 0.7)) if coin else d.rand(js_round(n / 10), js_round(n / 4))
            if h * (2 if coin else 6) != n:
                break
        what, theory, tries = ("heads", frac(1, 2), "flips") if coin else ("6", frac(1, 6), "rolls")
        answer = Q(h, n)
        return {
            "expr": (f"You flip a coin {n} times and get {h} heads. What is the experimental probability of heads?" if coin
                     else f"You roll a number cube {n} times and get a 6 on {h} of them. What is the experimental probability of rolling a 6?"),
            "ask": f"P({what}) =", "words": True, "answer": answer, "near": near_q(answer, d),
            "wrong": [
                Q(1, 2 if coin else 6, f"That's the theoretical probability. Experimental probability uses what happened: {h} out of {n} {tries}."),
                Q(n - h, n, "That's the chance of tails." if coin else "That's the chance of NOT rolling a 6."),
                Q(h, n - h, f"Divide by all {n} {tries}."),
            ],
            "hint": "Experimental probability = times it happened ÷ times you tried.",
            "steps": [[f"P({what}) = {raw(h, n)}{simplify(h, n)}", f"{h} out of {n} {tries}"], [f"In theory it's {theory}", f"More {tries} usually land closer to that"]],
        }

    # Two things at once: multiply the chances, or count the pairs
    form = d.pick(["coinCube", "coins", "dice", "spin"])
    if form == "coinCube":
        v = d.rand(1, 6)
        return {
            "expr": f"You flip a coin and roll a number cube. What is the probability of heads and a {v}?", "ask": f"P(heads, {v}) =", "words": True,
            "answer": Q(1, 12),
            "wrong": [
                Q(2, 3, f"You added. When both have to happen, multiply: {frac(1, 2)} × {frac(1, 6)}."),
                Q(1, 8, "There are 2 × 6 = 12 pairs, not 2 + 6."),
                Q(1, 6, "That's just the cube. The coin has to land heads too."),
                Q(1, 2, f"That's just the coin. The cube has to show a {v} too."),
            ],
            "hint": "Both have to happen: multiply the two chances.",
            "steps": [[f"{frac(1, 2)} × {frac(1, 6)} = {frac(1, 12)}", f"Heads and a {v}: multiply"], ["2 × 6 = 12 pairs", f"Only heads-{v} works: 1 of 12"]],
        }
    if form == "coins":
        c = d.pick([2, 3])
        every = 4 if c == 2 else 8
        return {
            "expr": f"You flip {'two' if c == 2 else 'three'} coins. What is the probability they all land heads?", "ask": "P(all heads) =", "words": True,
            "answer": Q(1, every),
            "wrong": [
                Q(1, 3, "HH, HT and TT look like 3 outcomes, but HT and TH are different: there are 4."),
                Q(1, 2, "That's one coin. Both have to land heads."),
                Q(1, 1, f"You added. For both, multiply: {frac(1, 2)} × {frac(1, 2)}."),
            ] if c == 2 else [
                Q(1, 6, "There are 2 × 2 × 2 = 8 outcomes, not 2 + 2 + 2."),
                Q(1, 4, "That's two coins. All three have to land heads."),
                Q(3, 2, f"You added. For all three, multiply: {frac(1, 2)} × {frac(1, 2)} × {frac(1, 2)}."),
            ],
            "hint": "Each coin is heads half the time. All of them have to happen: multiply.",
            "steps": [
                [f"{' × '.join([frac(1, 2)] * c)} = {frac(1, every)}", "Multiply one chance per coin"],
                ["HH, HT, TH, TT" if c == 2 else "HHH, HHT, HTH, HTT, THH, THT, TTH, TTT", f"{every} outcomes, and 1 is all heads"],
            ],
        }
    if form == "dice":
        s = d.rand(3, 11)
        ways = 6 - abs(7 - s)
        pairs = [f"{a}+{s - a}" for a in range(1, 7) if 1 <= s - a <= 6]
        return {
            "expr": f"You roll two number cubes and add the numbers. What is the probability the sum is {s}?", "ask": f"P(sum {s}) =", "words": True,
            "answer": Q(ways, 36),
            "wrong": [
                Q(1, 11, "There are 11 possible sums, but they aren't equally likely. Count the 36 pairs."),
                Q(ways, 12, "Two cubes make 6 × 6 = 36 pairs, not 6 + 6."),
                Q(1, 36, f"There's more than one way to roll {s}: {', '.join(pairs)}."),
            ],
            "hint": "Two cubes make 6 × 6 = 36 equally likely pairs. Count the pairs that add up right.",
            "steps": [[", ".join(pairs), f"{ways} ways to make {s}"], ["6 × 6 = 36", "Pairs in all"], [f"P = {raw(ways, 36)}{simplify(ways, 36)}", f"{ways} out of 36"]],
        }
    m = d.rand(3, 5)
    cols = d.shuffle(list(COLORS))[:m]
    c1 = d.pick(cols)
    c2 = d.pick(cols)
    return {
        "expr": f"A spinner has {m} equal parts: {list_of(cols)}. You spin it twice. What is the probability of "
                f"{f'{c1} both times' if c1 == c2 else f'{c1} and then {c2}'}?",
        "ask": f"P({c1}, {c2}) =", "words": True, "answer": Q(1, m * m),
        "wrong": [
            Q(2, m, f"You added. Both spins have to happen: multiply {frac(1, m)} × {frac(1, m)}."),
            Q(1, 2 * m, f"There are {m} × {m} = {m * m} outcomes, not {m} + {m}."),
            Q(1, m, "That's one spin. The second spin has to match too."),
        ],
        "hint": "Both spins have to happen: multiply the two chances.",
        "steps": [[f"{frac(1, m)} × {frac(1, m)} = {frac(1, m * m)}", "Both spins: multiply"], [f"{m} × {m} = {m * m}", "Equally likely pairs, and 1 of them works"]],
    }


# ---------- Statistics (7.SP.1-4) ----------
# [label, lowest, highest] for made-up data sets
DATASETS = [
    (lambda n: f"Goals in {n} soccer games:", 0, 7),
    (lambda n: f"Minutes of reading on {n} days:", 10, 60),
    (lambda n: f"Eggs in {n} dinosaur nests:", 3, 25),
    (lambda n: f"Scores on {n} quizzes:", 60, 100),
    (lambda n: f"Points in {n} basketball games:", 30, 80),
]
TEMPS = (lambda n: f"Low temperatures (°C) on {n} days:", -9, 9)


def list_nums(xs) -> str:
    return ", ".join(num(v) for v in xs)


def gen_stats(d: Dice, lvl: int) -> dict:
    """Mean, median and predictions from a random sample; mean absolute
    deviation and the score you need for a mean at level 4."""
    kinds = ["mean", "median", "sample"]
    if lvl >= 4:
        kinds += ["mad", "mad", "missing"]
    kind = d.pick(kinds)
    sets = DATASETS + [TEMPS] if lvl >= 4 else DATASETS

    if kind == "mean":
        label, lo, hi = d.pick(sets)
        n = d.rand(4, 6)
        while True:
            m = d.rand(lo + 1, hi - 1)
            xs = [d.rand(lo, hi) for _ in range(n - 1)]
            xs.append(n * m - sum(xs))
            if not (xs[n - 1] < lo or xs[n - 1] > hi):
                break
        d.shuffle(xs)
        total, srt = n * m, sorted(xs)
        med = srt[(n - 1) // 2] if n % 2 else (srt[n // 2 - 1] + srt[n // 2]) / 2
        return {
            "expr": f"{label(n)} {list_nums(xs)}. What is the mean?", "ask": "Mean =", "words": True, "answer": N(m),
            "wrong": [
                N(med, "That's the median, the middle number. The mean adds them all up and divides by how many."),
                N(total / (n - 1), f"Count again: there are {n} numbers, so divide by {n}."),
                N(total / (n + 1), f"Count again: there are {n} numbers, so divide by {n}."),
                N(srt[n - 1] - srt[0], "That's the range, the biggest minus the smallest."),
            ],
            "hint": "Mean: add them all up, then divide by how many there are.",
            "steps": [["".join(plus(v) if i else num(v) for i, v in enumerate(xs)) + f" = {num(total)}", "Add them up"],
                      [f"{num(total)} ÷ {n} = {num(m)}", f"Divide by how many there are ({n})"]],
        }

    if kind == "median":
        label, lo, hi = d.pick(sets)
        n = d.pick([5, 6, 7] if lvl >= 4 else [5, 7])
        while True:
            xs = [d.rand(lo, hi) for _ in range(n)]
            srt = sorted(xs)
            med = srt[(n - 1) // 2] if n % 2 else (srt[n // 2 - 1] + srt[n // 2]) / 2
            mid = xs[(n - 1) // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2  # the middle before sorting
            if not (mid == med or len(set(xs)) < n - 1):
                break
        a, b = srt[n // 2 - 1], srt[n // 2]
        two = f"With {n} numbers, two are in the middle. The median is halfway between {num(a)} and {num(b)}."
        return {
            "expr": f"{label(n)} {list_nums(xs)}. What is the median?", "ask": "Median =", "words": True, "answer": N(med),
            "wrong": [
                N(mid, "Put the numbers in order first. The median is the middle of the sorted list."),
                N(sum(xs) / n, "That's the mean. The median is the middle number once they're in order."),
                N(a, two) if n % 2 == 0 else None,
                N(b, two) if n % 2 == 0 else None,
                N(srt[n - 1] - srt[0], "That's the range, the biggest minus the smallest."),
            ],
            "hint": "Put the numbers in order. The median is the middle one, or halfway between the middle two.",
            "steps": [
                [list_nums(srt), "Put them in order"],
                [f"Median = {num(med)}", f"The middle one: {(n - 1) // 2} on each side"] if n % 2
                else [f"({num(a)} + {num(b)}) ÷ 2 = {num(med)}", "Halfway between the two middle numbers"],
            ],
        }

    # A random sample stands for everyone: same rate, scaled up
    if kind == "sample":
        s = d.pick([20, 25, 40, 50])
        k = d.pick([10, 12, 15, 20, 25, 30, 40])
        every = s * k
        c = d.rand(2, s - 3)
        ans = c * k
        text, rest = d.pick([
            (f"In a random sample of {s} students, {c} walk to school. The school has {every} students. About how many walk to school?", "don't walk"),
            (f"A factory checks {s} phones picked at random and finds {c} with scratches. It made {every} phones today. About how many have scratches?",
             "have no scratches"),
            (f"A paleontologist picks {s} fossils at random from a dig site, and {c} of them are teeth. The site has {every} fossils. About how many are teeth?",
             "aren't teeth"),
        ])
        return {
            "expr": text, "ask": "About", "words": True, "pos": True, "answer": N(ans),
            "wrong": [
                N(c + every - s, f"Samples scale by multiplying, not adding: {every} is {k} × {s}, so it's about {k} × {c}."),
                N(every * c / 100, f"{c} out of {s} isn't {c}%. It's {c} ÷ {s} = {num(c * 100 / s)}%."),
                N(every - ans, f"That's about how many {rest}."),
            ],
            "hint": f"The sample says {c} out of every {s}. Use the same rate for all {every}.",
            "steps": [[f"{c} ÷ {s} = {num(c / s)}", "The rate in the sample"], [f"{num(c / s)} × {every} = {ans}", "Same rate for everyone"]],
        }

    # Mean absolute deviation: the average distance from the mean
    if kind == "mad":
        label, lo, hi = d.pick([t for t in sets if t[2] - t[1] >= 16])
        n = d.pick([4, 5])
        while True:
            ds = [d.rand(-6, 6) for _ in range(n - 1)]
            ds.append(-sum(ds))
            if not (abs(ds[n - 1]) > 7 or all(not v for v in ds)):
                break
        m = d.rand(lo + 7, hi - 7)
        xs = d.shuffle([m + v for v in ds])
        dist = [abs(v - m) for v in xs]
        S = sum(dist)
        return {
            "expr": f"{label(n)} {list_nums(xs)}. The mean is {num(m)}. What is the mean absolute deviation (MAD)?", "ask": "MAD =", "words": True,
            "answer": N(S / n),
            "wrong": [
                N(max(xs) - min(xs), "That's the range. The MAD is the average distance from the mean."),
                N(S, f"That's the total distance. Divide by {n} to get the average."),
                N(0, "Distances are never negative: use how far each number is from the mean, not which way."),
                N(S / (n - 1), f"Divide by all {n} numbers."),
            ],
            "hint": f"Find how far each number is from {num(m)}, then average those distances.",
            "steps": [[", ".join(map(str, dist)), f"How far each number is from {num(m)}"], [f"{' + '.join(map(str, dist))} = {S}", "Add the distances"],
                      [f"{S} ÷ {n} = {num(S / n)}", "Average them"]],
        }

    # The score that brings the mean to a target
    n = d.pick([4, 5])
    target = d.rand(78, 92)
    while True:
        xs = [d.rand(target - 12, min(100, target + 10)) for _ in range(n - 1)]
        need = n * target - sum(xs)
        if not (need < 60 or need > 100 or need == target):
            break
    total = sum(xs)
    now = total / (n - 1)
    return {
        "expr": f"Your first {n - 1} test scores are {list_nums(xs)}. What score on test {n} makes your mean exactly {target}?", "ask": "Score =",
        "words": True, "pos": True, "answer": N(need),
        "wrong": [
            N(target, f"Every test counts: all {n} scores have to add up to {n} × {target} = {n * target}."),
            N(2 * target - now, f"Averaging the new score with your old mean counts the first {n - 1} tests as one."),
            N(now, "That's your mean so far."),
        ],
        "hint": f"A mean of {target} on {n} tests means the scores add up to {n} × {target}.",
        "steps": [[f"{n} × {target} = {n * target}", f"The total a mean of {target} needs"], [f"{' + '.join(map(str, xs))} = {total}", "Your total so far"],
                  [f"{n * target} − {total} = {need}", f"What test {n} has to add"]],
    }


# ---------- Geometry (7.G.4, 7.G.6) ----------
UNITS = ["cm", "m", "in", "ft"]
HALF = stack(1, 2)
USE_PI = "Use 3.14 for&nbsp;π."
TRIPLES = [[3, 4, 5], [4, 3, 5], [6, 8, 10], [8, 6, 10], [5, 12, 13], [12, 5, 13], [9, 12, 15], [12, 9, 15]]  # leg, leg, slanted side


def sq(u: str) -> str:
    return f"{u}{sup(2)}"


def cubic(u: str) -> str:
    return f"{u}{sup(3)}"


def gen_area(d: Dice, lvl: int) -> dict:
    """Circumference and area of circles (from a radius or a diameter),
    triangles, parallelograms and trapezoids; at level 4, shapes made of
    two pieces, working back from a circumference, and answers left in π."""
    kinds = ["circumference", "circle", "circle", "triangle", "quad"]
    if lvl >= 4:
        kinds += ["composite", "composite", "backward"]
    kind = d.pick(kinds)
    u = d.pick(UNITS)
    keep = lvl >= 4 and d.random() < 0.4  # leave π in the answer
    pi = PI if keep else (lambda k, why=None: N(3.14 * k, why))  # k × π, either way
    pi_note, about = ("Leave π in your&nbsp;answer.", "=") if keep else (USE_PI, "≈")

    if kind in ("circumference", "circle"):
        r = d.rand(2, 12 if lvl >= 4 else 10)
        dd = 2 * r
        by_d = d.random() < 0.45
        fig = fig_circle(dd if by_d else r, by_d, u)
        if kind == "circumference":
            return {
                "expr": f"Find the circumference of the circle. {pi_note}", "ask": f"C {about} ? {u}", "words": True, "pos": True, "fig": fig,
                "answer": pi(dd),
                "wrong": [
                    pi(r, "That's π × the radius. The circumference is π × the diameter."),
                    pi(2 * dd, f"{dd} {u} is already the diameter, all the way across: C = π × {dd}, no doubling."),
                    pi(r * r, "That's the area, πr². The circumference is π × the diameter."),
                ] if by_d else [
                    pi(r, "C = 2πr: you used the radius once. Double it."),
                    pi(2 * dd, f"2 × {r} = {dd} is the diameter, and C = π × {dd}. Don't double it twice."),
                    pi(r * r, "That's the area, πr². The circumference is 2πr."),
                ],
                "near": lambda: pi(dd + d.sgn() * d.rand(1, 3)),
                "hint": "Circumference = π × diameter (or 2 × π × radius).",
                "steps": [
                    *([] if by_d else [[f"d = 2 × {r} = {dd}", "The diameter is twice the radius"]]),
                    [f"C = π × {dd} = {dd}π" if keep else f"C = π × {dd} ≈ 3.14 × {dd} = {num(3.14 * dd)}", "Circumference = π × diameter"],
                ],
            }
        return {
            "expr": f"Find the area of the circle. {pi_note}", "ask": f"A {about} ? {sq(u)}", "words": True, "pos": True, "fig": fig,
            "answer": pi(r * r),
            "wrong": [
                pi(dd, "That's the circumference. Area is π × r × r."),
                pi(dd * dd, f"{dd} is the diameter. Use the radius, half of it: {r}.") if by_d else pi(2 * r * r, "Area is πr², not 2πr²."),
                pi(dd if by_d else r, f"Square the radius: {r} × {r} = {r * r}."),
            ],
            "near": lambda: pi((r + d.sgn()) ** 2),
            "hint": "Area of a circle = π × radius × radius.",
            "steps": [
                *([[f"r = {dd} ÷ 2 = {r}", "The radius is half the diameter"]] if by_d else []),
                [f"A = π × {r} × {r} = {r * r}π" if keep else f"A = π × {r} × {r} ≈ 3.14 × {r * r} = {num(3.14 * r * r)}", "Area = π × r²"],
            ],
        }

    if kind == "triangle":
        # With a labeled slanted side, run (the base up to the height), h and
        # that side make a right triangle, so the sketch can be to scale.
        slant = d.random() < 0.6
        s = 0
        while True:
            if slant:
                run, h, s = d.pick(TRIPLES)
                b = run + d.rand(2, 10)
            else:
                b = d.rand(4, 20)
                h = d.rand(3, 14)
                run = js_round(b * d.pick([0.3, 0.6, 0.7]))
            if not ((b * h) % 2 or (s and (b * s) % 2)):
                break
        A = b * h // 2
        return {
            "expr": "Find the area of the triangle.", "ask": f"A = ? {sq(u)}", "words": True, "pos": True, "fig": fig_triangle(b, h, run, s, u), "answer": N(A),
            "wrong": [
                N(b * h, f"A triangle is half of a rectangle: {HALF} × {b} × {h}."),
                N(b * s / 2, "Use the height (the dashed line, square to the base), not the slanted side.") if s else None,
                N(b + h, f"Area multiplies: {HALF} × base × height."),
            ],
            "hint": f"Area of a triangle = {HALF} × base × height. The height meets the base at a right angle.",
            "steps": [[f"A = {HALF} × {b} × {h}", f"{HALF} × base × height"], [f"= {A}", "Half of the rectangle around it"]],
        }

    if kind == "quad":
        if d.random() < 0.5:
            off, h, s = d.pick([t for t in TRIPLES if t[0] <= 9])
            b = d.rand(max(5, off + 2), 16)
            return {
                "expr": "Find the area of the parallelogram.", "ask": f"A = ? {sq(u)}", "words": True, "pos": True, "fig": fig_para(b, h, off, s, u),
                "answer": N(b * h),
                "wrong": [
                    N(b * s, "Use the height (the dashed line), not the slanted side."),
                    N(b * h / 2, "That's a triangle's area. A parallelogram is base × height, like a rectangle."),
                    N(2 * (b + s), "That's the perimeter, the distance around."),
                ],
                "hint": "Area of a parallelogram = base × height. Slide the slanted end over and it's a rectangle.",
                "steps": [[f"A = {b} × {h} = {b * h}", "Base × height"]],
            }
        while True:
            b1 = d.rand(3, 10)
            b2 = b1 + d.rand(2, 8)
            h = d.rand(3, 10)
            if not ((b1 + b2) * h) % 2:
                break
        A = (b1 + b2) * h // 2
        return {
            "expr": "Find the area of the trapezoid.", "ask": f"A = ? {sq(u)}", "words": True, "pos": True, "fig": fig_trap(b1, b2, h, u), "answer": N(A),
            "wrong": [
                N((b1 + b2) * h, f"Average the two bases: {HALF} × ({b1} + {b2})."),
                N(b2 * h, "That's a rectangle as wide as the long base. Use the average of both bases."),
                N(b1 * h, "That's a rectangle as wide as the short base. Use the average of both bases."),
            ],
            "hint": f"Area of a trapezoid = {HALF} × (base + base) × height.",
            "steps": [[f"({b1} + {b2}) ÷ 2 = {num((b1 + b2) / 2)}", "Average the two parallel sides"], [f"{num((b1 + b2) / 2)} × {h} = {A}", "Times the height"]],
        }

    if kind == "composite":
        form = d.pick(["house", "L", "round"])
        if form == "house":
            w = 2 * d.rand(3, 8)
            h1 = d.rand(4, 10)
            h2 = d.rand(3, 8)
            A = w * h1 + w * h2 // 2
            return {
                "expr": "Find the area of the whole shape: a rectangle with a triangle on top.", "ask": f"A = ? {sq(u)}", "words": True, "pos": True,
                "fig": fig_house(w, h1, h2, u), "answer": N(A),
                "wrong": [
                    N(w * h1 + w * h2, f"The top is a triangle: {HALF} × {w} × {h2}."),
                    N(w * h1, "Add the triangle on top."),
                    N(w * (h1 + h2) / 2, "Only the top is a triangle. The rectangle counts in full."),
                ],
                "hint": "Split it into a rectangle and a triangle, find each area, then add.",
                "steps": [[f"{w} × {h1} = {w * h1}", "The rectangle"], [f"{HALF} × {w} × {h2} = {w * h2 // 2}", "The triangle"],
                          [f"{w * h1} + {w * h2 // 2} = {A}", "Add the pieces"]],
            }
        if form == "L":
            W = d.rand(9, 16)
            H = d.rand(7, 12)
            a = d.rand(3, W - 4)
            b = d.rand(2, H - 3)
            A = a * H + (W - a) * b
            return {
                "expr": "Find the area of the shape. All its corners are square.", "ask": f"A = ? {sq(u)}", "words": True, "pos": True,
                "fig": fig_l(W, H, a, b, u), "answer": N(A),
                "wrong": [
                    N(W * H, "That's the whole rectangle around it. The missing corner doesn't count."),
                    N(a * H + W * b, f"Those two pieces overlap. Split it into rectangles that don't: {a} × {H} and {W - a} × {b}."),
                    N(2 * (W + H), "That's the perimeter, the distance around."),
                ],
                "hint": "Split it into two rectangles, find each area, then add.",
                "steps": [[f"{a} × {H} = {a * H}", "The tall part"], [f"{W - a} × {b} = {(W - a) * b}", f"The rest: {W} − {a} = {W - a} wide"],
                          [f"{a * H} + {(W - a) * b} = {A}", "Add the pieces"]],
            }
        w = d.rand(6, 14)
        r = d.rand(2, 5)
        h = 2 * r
        semi = round4(3.14 * r * r / 2)
        A = round4(w * h + semi)
        return {
            "expr": f"Find the area of the shape: a rectangle with half a circle on one end. {USE_PI}", "ask": f"A ≈ ? {sq(u)}", "words": True, "pos": True,
            "fig": fig_round(w, h, u), "answer": N(A),
            "wrong": [
                N(w * h + 3.14 * r * r, f"The end is half a circle: take half of π × {r} × {r}."),
                N(w * h + 3.14 * h * h / 2, f"{h} is the half circle's diameter. Its radius is {r}."),
                N(w * h, "Add the half circle too."),
            ],
            "near": lambda: N(w * h + 3.14 * (r + d.sgn()) ** 2 / 2),
            "hint": f"Split it into a rectangle and half a circle. Half a circle = {HALF} × π × r × r.",
            "steps": [[f"{w} × {h} = {w * h}", "The rectangle"], [f"{HALF} × 3.14 × {r} × {r} = {num(semi)}", f"Half a circle, radius {h} ÷ 2 = {r}"],
                      [f"{w * h} + {num(semi)} = {num(A)}", "Add the pieces"]],
        }

    # From the circumference back to the radius
    r = d.rand(2, 12)
    dd = 2 * r
    C = round4(3.14 * dd)
    return {
        "expr": f"A circle's circumference is {num(C)} {u}. What is its radius? {USE_PI}", "ask": f"r = ? {u}", "words": True, "pos": True, "answer": N(r),
        "wrong": [
            N(dd, f"{num(C)} ÷ 3.14 = {dd} is the diameter. The radius is half of it."),
            N(C / 2, "Divide by π first: C = π × diameter."),
            N(2 * dd, "The radius is half the diameter, not double."),
        ],
        "hint": "C = π × diameter, so the diameter is C ÷ π. The radius is half the diameter.",
        "steps": [[f"d = {num(C)} ÷ 3.14 = {dd}", "C = π × d, so divide by π"], [f"r = {dd} ÷ 2 = {r}", "The radius is half the diameter"]],
    }


def gen_solids(d: Dice, lvl: int) -> dict:
    """Volume and surface area of boxes, cubes and triangular prisms, and a
    box's height from its volume."""
    kind = d.pick(["box", "box", "boxArea", "boxArea", "cube", "prism", "height"])
    u = d.pick(UNITS)

    if kind in ("box", "boxArea", "height"):
        while True:
            l, w, h = d.rand(3, 12), d.rand(2, 9), d.rand(2, 10)
            if not (l == w or w == h or l == h):
                break
        V, S = l * w * h, 2 * (l * w + l * h + w * h)
        if kind == "box":
            return {
                "expr": "Find the volume of the box.", "ask": f"V = ? {cubic(u)}", "words": True, "pos": True, "fig": fig_box(l, w, h, u), "answer": N(V),
                "wrong": [
                    N(S, "That's the surface area, the wrapping on the outside. Volume is length × width × height."),
                    N(l * w, f"That's the area of the base. Multiply by the height, {h}, too."),
                    N(l + w + h, "Volume multiplies the three edges: length × width × height."),
                ],
                "hint": "Volume of a box = length × width × height.",
                "steps": [[f"{l} × {w} = {l * w}", "Area of the base"], [f"{l * w} × {h} = {V}", "Times the height"]],
            }
        if kind == "boxArea":
            return {
                "expr": "Find the surface area of the box.", "ask": f"SA = ? {sq(u)}", "words": True, "pos": True, "fig": fig_box(l, w, h, u), "answer": N(S),
                "wrong": [
                    N(S / 2, "That's 3 of the 6 faces. Each face has a twin on the opposite side."),
                    N(V, "That's the volume. Surface area adds up the areas of the 6 faces."),
                    N(2 * (l * w + l * h), f"Don't forget the two {w} × {h} ends."),
                ],
                "hint": "A box has 6 faces in 3 matching pairs. Add up the areas of all 6.",
                "steps": [
                    [f"{l} × {w} = {l * w}, &nbsp;{l} × {h} = {l * h}, &nbsp;{w} × {h} = {w * h}", "The three different faces"],
                    [f"{l * w} + {l * h} + {w * h} = {S // 2}", "One of each"],
                    [f"2 × {S // 2} = {S}", "Each face has a twin on the opposite side"],
                ],
            }
        return {
            "expr": f"The box holds {V} {cubic(u)}. How tall is it?", "ask": f"h = ? {u}", "words": True, "pos": True, "fig": fig_box(l, w, "?", u), "answer": N(h),
            "wrong": [
                N(V - l * w, f"Volume = base × height, so divide by the base ({l * w}), don't subtract."),
                N(V / l, f"Divide by the whole base: {l} × {w} = {l * w}."),
                N(V / w, f"Divide by the whole base: {l} × {w} = {l * w}."),
                N(l * w, "That's the area of the base. Divide the volume by it."),
            ],
            "hint": "Volume = length × width × height, so the height = volume ÷ (length × width).",
            "steps": [[f"{l} × {w} = {l * w}", "Area of the base"], [f"{V} ÷ {l * w} = {h}", "Volume ÷ base = height"]],
        }

    if kind == "cube":
        s = d.rand(2, 10)
        fig = fig_box(s, s, s, u, True)
        if d.random() < 0.5:
            return {
                "expr": "Find the volume of the cube.", "ask": f"V = ? {cubic(u)}", "words": True, "pos": True, "fig": fig, "answer": N(s ** 3),
                "wrong": [
                    N(3 * s, f"{s}{sup(3)} means {s} × {s} × {s}, not 3 × {s}."),
                    N(s * s, f"That's one face. Multiply by the height, {s}, too."),
                    N(6 * s * s, "That's the surface area. Volume is edge × edge × edge."),
                ],
                "hint": "Volume of a cube = edge × edge × edge.",
                "steps": [[f"{s} × {s} × {s} = {s ** 3}", f"Edge × edge × edge, or {s}{sup(3)}"]],
            }
        return {
            "expr": "Find the surface area of the cube.", "ask": f"SA = ? {sq(u)}", "words": True, "pos": True, "fig": fig, "answer": N(6 * s * s),
            "wrong": [
                N(s ** 3, "That's the volume. Surface area adds up the 6 faces."),
                N(4 * s * s, "A cube has 6 faces: the top and bottom count too."),
                N(6 * s, f"Each face is {s} × {s} = {s * s}, not {s}."),
            ],
            "hint": "A cube has 6 square faces, all the same size.",
            "steps": [[f"{s} × {s} = {s * s}", "One face"], [f"6 × {s * s} = {6 * s * s}", "Six faces"]],
        }

    # Triangular prism: the triangle end × the length
    while True:
        b, h = d.rand(3, 10), d.rand(3, 10)
        if not (b * h) % 2:
            break
    L = d.rand(4, 15)
    end = b * h // 2
    V = end * L
    return {
        "expr": "Find the volume of the triangular prism.", "ask": f"V = ? {cubic(u)}", "words": True, "pos": True, "fig": fig_prism(b, h, L, u), "answer": N(V),
        "wrong": [
            N(b * h * L, f"The end is a triangle: its area is {HALF} × {b} × {h} = {end}."),
            N(end, f"That's the area of the triangle end. Multiply by the length, {L}."),
            N(b * h + L, "Volume = the area of the end × the length."),
        ],
        "hint": "Volume of a prism = area of the end × length.",
        "steps": [[f"{HALF} × {b} × {h} = {end}", "Area of the triangle end"], [f"{end} × {L} = {V}", "Times the length"]],
    }


# ---------- Figures ----------
# Labeled sketches for the geometry problems, drawn to scale by ui/figures.py.
# Each dict holds its kind and the original's arguments; describe() says in
# words what it shows, so a problem still makes sense as plain text.


def fig_circle(length, across, u):  # across: length is the diameter, not the radius
    return {"kind": "dm_circle", "len": length, "across": across, "u": u}


def fig_triangle(b, h, run, s, u):  # base b; the top sits `run` along it at height h. s labels the left side.
    return {"kind": "dm_triangle", "b": b, "h": h, "run": run, "s": s, "u": u}


def fig_para(b, h, off, s, u):  # base b, height h, top slid `off` to the right; s labels the right side.
    return {"kind": "dm_para", "b": b, "h": h, "off": off, "s": s, "u": u}


def fig_trap(b1, b2, h, u):  # b1 on top, centered over b2
    return {"kind": "dm_trap", "b1": b1, "b2": b2, "h": h, "u": u}


def fig_house(w, h1, h2, u):  # a w × h1 rectangle with a triangle of height h2 on top
    return {"kind": "dm_house", "w": w, "h1": h1, "h2": h2, "u": u}


def fig_l(W, H, a, b, u):  # W × H with the top-right corner cut out: a across the top, b up the right side
    return {"kind": "dm_L", "W": W, "H": H, "a": a, "b": b, "u": u}


def fig_round(w, h, u):  # a w × h rectangle with half a circle (diameter h) on its right end
    return {"kind": "dm_round", "w": w, "h": h, "u": u}


def fig_box(l, w, h, u, cube=False):  # length l across the front, width w going back, height h ("?" when unknown)
    return {"kind": "dm_box", "l": l, "w": w, "h": h, "u": u, "cube": cube}


def fig_prism(b, h, L, u):  # a prism whose ends are right triangles (legs b and h), L long
    return {"kind": "dm_prism", "b": b, "h": h, "L": L, "u": u}


def describe(fig: dict) -> str:
    k, u = fig["kind"], fig.get("u", "")
    if k == "dm_circle":
        return f"A circle; its {'diameter' if fig['across'] else 'radius'} is {fig['len']} {u}."
    if k == "dm_triangle":
        s = fig["s"]
        return f"A triangle with a base of {fig['b']} {u} and a height of {fig['h']} {u}{f'; one slanted side is {s} {u}' if s else ''}."
    if k == "dm_para":
        return f"A parallelogram with a base of {fig['b']} {u}, a height of {fig['h']} {u} and slanted sides of {fig['s']} {u}."
    if k == "dm_trap":
        return f"A trapezoid with parallel sides of {fig['b1']} {u} and {fig['b2']} {u}, {fig['h']} {u} apart."
    if k == "dm_house":
        w = fig["w"]
        return (f"A rectangle {w} {u} wide and {fig['h1']} {u} tall, with a triangle on top whose base is the {w} {u} side "
                f"and whose height is {fig['h2']} {u}.")
    if k == "dm_L":
        return (f"An L shape with square corners: {fig['W']} {u} along the bottom and {fig['H']} {u} up the left side. "
                f"The top edge is {fig['a']} {u} across, and the lower right side is {fig['b']} {u} tall.")
    if k == "dm_round":
        return f"A rectangle {fig['w']} {u} long and {fig['h']} {u} tall, with half a circle on one {fig['h']} {u} end."
    if k == "dm_box":
        if fig["cube"]:
            return f"A cube with {fig['l']} {u} edges."
        h = fig["h"]
        return f"A box {fig['l']} {u} long and {fig['w']} {u} wide{'; its height is unknown' if h == '?' else f', {h} {u} tall'}."
    if k == "dm_prism":
        return f"A triangular prism {fig['L']} {u} long. Each end is a right triangle with legs of {fig['b']} {u} and {fig['h']} {u}."
    return ""


# --------------------------------------------------------------------------- topics


@dataclass(frozen=True)
class Topic:
    name: str
    min: int  # the level (0-based) the topic opens at
    weight: int  # how often it comes up once open
    gen: Callable[[Dice, int], dict]


TOPICS: list[Topic] = [
    Topic("Integers", 0, 2, gen_integers),
    Topic("One-step equations", 0, 2, gen_one_step),
    Topic("Proportions", 0, 2, gen_proportion),
    Topic("Percents", 0, 2, gen_percent),
    Topic("Two-step equations", 1, 3, gen_two_step),
    Topic("Fractions", 1, 2, gen_fractions),
    Topic("Decimals", 1, 2, gen_decimals),
    Topic("Angles", 1, 1, gen_angles),
    Topic("Percent change", 2, 2, gen_percent_change),
    Topic("Expressions", 2, 2, gen_expressions),
    Topic("Inequalities", 2, 2, gen_inequality),
    Topic("Probability", 3, 2, gen_probability),
    Topic("Circles & area", 3, 2, gen_area),
    Topic("Statistics", 3, 2, gen_stats),
    Topic("Surface area & volume", 4, 2, gen_solids),
]
LEVELS = range(5)  # 0-4, shown as 1-5


def random_topic(d: Dice, level: int, avoid: Optional[str] = None) -> Topic:
    """A topic open at ``level``, by weight. ``avoid`` skips one topic (never the same topic twice in a row)."""
    open_ = [t for t in TOPICS if t.min <= level and t.name != avoid]
    r = d.random() * sum(t.weight for t in open_)
    for t in open_:
        r -= t.weight
        if r < 0:
            return t
    return open_[-1]


# --------------------------------------------------------------------------- the problem, ready to show

SUPER = "⁰¹²³⁴⁵⁶⁷⁸⁹"
OVERLINE = "̅"  # a combining bar over the digit before it: repeating digits
_SVG = re.compile(r"<svg[^>]*>(?:<desc>([\s\S]*?)</desc>)?[\s\S]*?</svg>")
_FRAC = re.compile(r'<span class="frac"><span>([^<]*)</span><span>([^<]*)</span></span>(\(|[a-z](?![a-z]))?')
_REP = re.compile(r'<span class="rep">(\d+)</span>')
_SUP = re.compile(r"<sup>(\d+)</sup>")
_TAG = re.compile(r"<[^>]+>")


def _frac_text(m: re.Match) -> str:
    t, b, after = m.group(1), m.group(2), m.group(3)
    if after:  # (2⁄3)(6x + 9) and (2⁄3)x: a coefficient in parentheses, so the x isn't read as part of the 3
        return f"({t}⁄{b}){after}"
    return f"{t}⁄{b}"


def plain(html: str) -> str:
    """The engine's HTML as the Unicode text the game shows: 2⁄3 for a fraction
    (a coefficient in parentheses: (2⁄3)x), x² for x<sup>2</sup> and a bar over
    repeating digits (0.83̅)."""
    s = _SVG.sub(lambda m: f"[Figure: {m.group(1)}]" if m.group(1) else "[figure]", str(html))
    s = _FRAC.sub(_frac_text, s)
    s = _REP.sub(lambda m: "".join(c + OVERLINE for c in m.group(1)), s)
    s = _SUP.sub(lambda m: "".join(SUPER[int(c)] for c in m.group(1)), s)
    s = _TAG.sub("", s)
    return s.replace("&lt;", "<").replace("&gt;", ">").replace("&nbsp;", " ").replace("&amp;", "&")


@dataclass(frozen=True)
class Choice:
    text: str  # plain text; for a number line, the same answer in words ("x ≤ 3")
    why: str = ""  # the mistake behind a wrong choice
    graph: Optional[tuple] = None  # a number line to draw instead of the text: (at, rel, lo, hi), rel one of < > ≤ ≥


@dataclass(frozen=True)
class DinoProblem:
    """One problem, choices shuffled, all text plain."""

    topic: str
    level: int  # 0-4
    question: str  # the expression or the word problem
    ask: str  # what's asked for, "?" where the answer goes: "x = ?", "A = ? cm²"
    choices: tuple[Choice, ...]
    answer: int  # index into choices
    hint: str
    steps: tuple[tuple[str, str], ...]  # the worked solution: (math, note)
    words: bool = False  # a word problem (the question is sentences, not an expression)
    fig: Optional[dict] = None  # a geometry sketch for ui/figures.py
    ray: Optional[tuple] = None  # an inequality's solution as (at, rel), for a graph of the answer

    def reason(self, i: int) -> str:
        """What went wrong if the player picked choice ``i`` ("" for the right answer)."""
        return self.choices[i].why if 0 <= i < len(self.choices) and i != self.answer else ""

    @property
    def figure_text(self) -> str:
        return describe(self.fig) if self.fig else ""


def _ask(ask: str) -> str:
    return ask if "?" in ask else (ask + " ?" if ask else "?")


def make_problem(rng: RandomSource, level: int, topic: Optional[str] = None, avoid: Optional[str] = None,
                 faithful: bool = False) -> DinoProblem:
    """A problem at ``level`` (0-4): from ``topic`` (a name in TOPICS), or a random
    topic open at that level other than ``avoid``. ``faithful`` picks the wrong
    choices exactly as the original game does (see :func:`make_choices`)."""
    dice = Dice(rng)
    if topic:
        t = next((t for t in TOPICS if t.name == topic), None)
        if t is None:
            raise ValueError(f"No topic named {topic}")
    else:
        t = random_topic(dice, level, avoid)
    p = t.gen(dice, max(level, t.min))
    options = make_choices(p, dice, faithful)
    ray = p.get("ray")
    return DinoProblem(
        topic=t.name,
        level=max(level, t.min),
        question=plain(p["expr"]),
        ask=plain(_ask(p["ask"])),
        choices=tuple(Choice(plain(o.say or o.html), plain(o.why or "") if o is not p["answer"] else "", o.graph) for o in options),
        answer=options.index(p["answer"]),
        hint=plain(p["hint"]),
        steps=tuple((plain(m), plain(n)) for m, n in p["steps"]),
        words=bool(p.get("words")),
        fig=p.get("fig"),
        ray=(ray["at"], ray["rel"]) if ray else None,
    )


def to_text(p: DinoProblem) -> str:
    """A whole problem as plain text: question, choices A-D, the answer, why
    each wrong choice is wrong, the hint and the worked steps."""
    letters = "ABCD"
    out = [f"Topic: {p.topic}"]
    if p.fig:
        out.append(f"[Figure: {describe(p.fig)}]")
    out.append(f"{p.question}   {p.ask}")
    out += [f"  {letters[i]}. {c.text}" for i, c in enumerate(p.choices)]
    out.append(f"Answer: {letters[p.answer]}. {p.choices[p.answer].text}")
    out += [f"  Why not {letters[i]}: {c.why}" for i, c in enumerate(p.choices) if i != p.answer and c.why]
    out.append(f"Hint: {p.hint}")
    out.append("Steps:")
    out += [f"  {m}{f'   ({n})' if n else ''}" for m, n in p.steps]
    if p.ray:
        at, r = p.ray
        out.append(f"Graph: x {r} {num(at)}, {'an open' if r in ('<', '>') else 'a filled'} dot on {num(at)}, "
                   f"shaded to the {'right' if r in ('>', '≥') else 'left'}")
    return "\n".join(out)


if __name__ == "__main__":  # a few problems at each level, as text
    rng = random.Random()
    for lvl in LEVELS:
        print(f"===== level {lvl + 1}")
        print(to_text(make_problem(rng, lvl)), end="\n\n")
