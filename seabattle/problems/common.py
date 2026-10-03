"""Shared building blocks for the workshop's math problems.

The problems are ports of two browser games: Fleet Algebra (Algebra I) and
Broadside (Geometry & Trig). Each game module provides:

* ``HELP``: dict of briefing id -> :class:`Briefing` (the "?" help screen)
* ``GENERATORS``: list of :class:`Generator`, each tagged with a topic id and
  a difficulty tier (1 = one step, 2 = two or three steps, 3 = multi-step or
  the formula is not given; Broadside's "missile" problems are all tier 3)

A generator takes a :class:`Context` and returns a :class:`Problem`. All text
is plain Unicode (no HTML); line breaks are "\\n". The first of the four
choices is always the correct one; the workshop shuffles them.

Every wrong choice is a particular mistake, and says which one: ``Problem.why``
holds, for each choice, the short explanation shown to a player who picks it
("You added the two sides; the hypotenuse needs a² + b²."). The choice helpers
take ``(value, why)`` pairs and return :class:`Choices`, which ``Problem``
splits into ``choices`` and ``why``.

Shared by all three problem engines (the two above and Math Boost's Dino Math):
JavaScript's number arithmetic and printing (:func:`js_round`, :func:`js_str`,
:func:`js_fixed`, :func:`is_int`), and :func:`pick_three`, which picks the
wrong choices so the answer can't be spotted without doing the math.
"""

from __future__ import annotations

import collections
import itertools
import math
import random
import re
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Callable, NamedTuple, Optional, Protocol, Sequence, TypeVar

T = TypeVar("T")


# --------------------------------------------------------------------------- JavaScript numbers
# The problems are ports of browser games, so they round and print numbers the way JavaScript does.


def js_round(v: float) -> float:
    """Math.round: the nearest integer, halves toward +infinity."""
    if not math.isfinite(v):
        return v
    f = math.floor(v)
    return f + 1 if v - f >= 0.5 else f


def js_str(v: Any) -> str:
    """String(v) as JavaScript writes it: 3 not 3.0, 0.00005 not 5e-05."""
    if isinstance(v, str):
        return v
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if math.isnan(v):
        return "NaN"
    if math.isinf(v):
        return "Infinity" if v > 0 else "-Infinity"
    if v == 0:
        return "0"
    sign = "-" if v < 0 else ""
    digits, exp = _shortest(abs(v))
    k, n = len(digits), exp + len(digits)
    if k <= n <= 21:
        body = digits + "0" * (n - k)
    elif 0 < n <= 21:
        body = digits[:n] + "." + digits[n:]
    elif -6 < n <= 0:
        body = "0." + "0" * (-n) + digits
    else:
        e = n - 1
        body = (digits[0] + ("." + digits[1:] if k > 1 else "")) + "e" + ("+" if e >= 0 else "-") + str(abs(e))
    return sign + body


def _shortest(v: float) -> tuple[str, int]:
    """The shortest digits that round-trip (as JavaScript picks them too), and the power of ten of the last one."""
    t = Decimal(repr(v)).as_tuple()
    digits = "".join(map(str, t.digits))
    stripped = digits.rstrip("0")
    return stripped, t.exponent + len(digits) - len(stripped)


def js_fixed(v: float, places: int) -> str:
    """Number.prototype.toFixed: halves round away from zero, on the exact binary value."""
    q = Decimal(abs(v)).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
    return ("-" if v < 0 else "") + f"{q:f}"


def is_int(v: Any) -> bool:
    """Number.isInteger."""
    return isinstance(v, int) and not isinstance(v, bool) or isinstance(v, float) and v.is_integer()

_SUPERSCRIPTS = str.maketrans("0123456789-−+nt()", "⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁻⁺ⁿᵗ⁽⁾")


def sup(n: Any) -> str:
    """Superscript: sup(2) -> '²', sup('-3') -> '⁻³', sup('n') -> 'ⁿ', sup('t') -> 'ᵗ'."""
    return str(n).translate(_SUPERSCRIPTS)


@dataclass(frozen=True)
class ShipRef:
    """One of the player's ships, as it appears in word problems."""

    name: str  # e.g. "USS Kestrel"
    cls: str  # lowercase class name, e.g. "destroyer"
    speed: int  # knots
    crew: int


@dataclass
class Context:
    """Everything a generator may use. Always use ``ctx.rng`` for randomness."""

    rng: random.Random
    fleet: list[ShipRef] = field(default_factory=list)  # the player's ships; may be empty
    my_name: str = "USS Kestrel"  # the player's flagship (Broadside's ME())
    enemy_name: str = "Red destroyer"  # the ship being fought (Broadside's EN())

    def rand(self, a: int, b: int) -> int:
        """Random integer from a to b inclusive (the games' ``rand``)."""
        return self.rng.randint(a, b)

    def pick(self, seq: Sequence[T]) -> T:
        return seq[self.rng.randrange(len(seq))]

    def shuffle(self, seq: Sequence[T]) -> list[T]:
        out = list(seq)
        self.rng.shuffle(out)
        return out


class Choices(NamedTuple):
    """Answer choices, the correct one first, and why each one is wrong ("" for the answer)."""

    texts: tuple[str, ...]
    why: tuple[str, ...]


@dataclass(frozen=True)
class Problem:
    help: str  # key into the game's HELP briefings
    story: str
    expr: str  # the equation or expression; several lines separated by "\n"
    ask: str
    choices: tuple[str, ...]  # four distinct strings; choices[0] is correct. A Choices is split into this and ``why``
    solution: tuple[str, ...]  # worked solution, one step per entry
    hint: str
    note: str = ""  # small grey line under the expression (e.g. "subtract 360° if you go past it")
    fig: Optional[dict] = None  # figure description (Broadside), e.g. {"kind": "compass", ...}
    why: tuple[str, ...] = ()  # why[i] explains the mistake behind choices[i]; why[0] is ""

    def __post_init__(self) -> None:
        if isinstance(self.choices, Choices):
            object.__setattr__(self, "why", tuple(self.choices.why))
            object.__setattr__(self, "choices", tuple(self.choices.texts))
        if not self.why:
            object.__setattr__(self, "why", ("",) * len(self.choices))


@dataclass(frozen=True)
class Briefing:
    title: str
    concept: str
    steps: tuple[str, ...]
    example: str  # plain text; "\n" between lines


@dataclass(frozen=True)
class Generator:
    topic: str
    tier: int  # 1..3
    fn: Callable[[Context], Problem]

    @property
    def name(self) -> str:
        return self.fn.__name__

    @property
    def key(self) -> str:
        """Unique across both games (a name like ``pythagorean_leg`` is used in each): "tri.pythagorean_leg"."""
        return f"{self.topic}.{self.name}"


def registry(generators: list[Generator]) -> Callable[[str, int], Callable[[Callable[[Context], Problem]], Callable[[Context], Problem]]]:
    """Decorator factory: ``@gen("lin", 2)`` registers a generator function."""

    def gen(topic: str, tier: int):
        def wrap(fn: Callable[[Context], Problem]) -> Callable[[Context], Problem]:
            generators.append(Generator(topic, tier, fn))
            return fn

        return wrap

    return gen


# --------------------------------------------------------------------------- picking wrong choices


class Picker(Protocol):
    """The randomness :func:`pick_three` needs: a :class:`Context`, or Dino Math's dice."""

    def rand(self, lo: int, hi: int) -> int: ...

    def pick(self, seq: Sequence[T]) -> T: ...

    def shuffle(self, seq: list[T]) -> list[T]: ...


# A wrong choice: ``(text, why, value, ...)``, the text as shown, the mistake behind it and
# the number it stands for (None if it isn't one). Anything after those is carried along.
Candidate = tuple

_PLAIN_DIGITS = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁻", "0123456789-")


def shape(text: str) -> str:
    """How a choice is written, with the digits taken out: "12.5 nm" -> "#.# nm"."""
    return re.sub(r"\d+", "#", text)


def parts(text: str) -> collections.Counter:
    """The numbers, words and symbols a choice is made of: "12√2 nm" -> 12, √, 2, nm."""
    return collections.Counter(re.findall(r"\d+(?:\.\d+)?|[^\W\d_]+|[^\s\w]", text.translate(_PLAIN_DIGITS)))


class Look(NamedTuple):
    """What a blind guesser can see of one choice."""

    shape: str
    parts: collections.Counter
    value: Optional[float]


def look(text: str, value: Optional[float]) -> Look:
    return Look(shape(text), parts(text), value)


def gives_away(looks: Sequence[Look]) -> tuple[bool, bool]:
    """Would the answer (``looks[0]``) stand out from the three wrong choices without any math?

    Returns (stands out, pairs up). It stands out if it is the only choice written differently,
    if it alone shares the most (or the fewest) parts with the others (wrong answers made by
    changing one part of the answer all look like it), or if it sits exactly halfway between
    two of the others (or halfway by ratio, as with ×2 and ÷2). It pairs up if the choices are
    angles and it and one other are the only pair making 90° or 180°: fine now and then (the
    complement is a real mistake), but not every time.
    """
    shapes = [x.shape for x in looks]
    if [i for i in range(4) if shapes.count(shapes[i]) == 1] == [0]:
        return True, False
    shared = [sum(sum((looks[i].parts & looks[j].parts).values()) for j in range(4) if j != i) for i in range(4)]
    if shared.count(shared[0]) == 1 and shared[0] in (max(shared), min(shared)):
        return True, False
    vals = [x.value for x in looks]
    if any(v is None for v in vals):
        return False, False
    a = vals[0]
    for i in range(1, 4):
        for j in range(i + 1, 4):
            x, y = vals[i], vals[j]
            if math.isclose((x + y) / 2, a, rel_tol=1e-9, abs_tol=1e-9):
                return True, False
            if min(x, y, a) > 0 and math.isclose(math.sqrt(x * y), a, rel_tol=0.01):
                return True, False
    pairs = [(i, j) for i in range(4) for j in range(i + 1, 4) if round(vals[i] + vals[j]) in (90, 180)]
    return False, "°" in shapes[0] and len(pairs) == 1 and 0 in pairs[0]


def pick_three(rng: Picker, ans_text: str, ans_val: Optional[float], cands: Sequence[Candidate],
               spare: Sequence[Candidate] = ()) -> list[Candidate]:
    """Three of ``cands``, chosen with ``rng`` so the answer gives nothing away.

    When the choices are numbers, first the answer's place in order (smallest, second
    smallest...) is drawn evenly from the places the candidates allow, then three wrong
    choices that put it there: picking mistakes at random would put the answer in the middle
    most of the time. Among those, only picks that don't give the answer away (see
    :func:`gives_away`); if a place has none, another place is tried.

    ``spare`` candidates are near misses with no particular mistake behind them. They widen
    the places the answer can take when the mistakes all fall on one side of it, but a pick
    uses as few of them as it can.
    """
    pool = list(cands) + list(spare)
    real = len(cands)
    ans_look = look(ans_text, ans_val)
    looks = [look(c[0], c[2]) for c in pool]

    def choose(groups: list[tuple[int, ...]]) -> Optional[list[Candidate]]:
        good, paired = [], []
        for g in groups:
            out, pair = gives_away([ans_look] + [looks[i] for i in g])
            if not out:
                (paired if pair else good).append(g)
        if paired and (not good or rng.rand(0, 1)):
            good = good + paired
        if not good:
            return None
        if spare:
            fewest = min(sum(i >= real for i in g) for g in good)
            good = [g for g in good if sum(i >= real for i in g) == fewest]
        return [pool[i] for i in rng.shuffle(list(rng.pick(good)))]

    idx = range(len(pool))
    if ans_val is not None and all(c[2] is not None for c in pool):
        lo = [i for i in idx if pool[i][2] < ans_val]
        hi = [i for i in idx if pool[i][2] >= ans_val]  # the same number written another way counts as above
        ranks = [k for k in range(4) if k <= len(lo) and 3 - k <= len(hi)]
        while ranks:
            k = rng.pick(ranks)
            got = choose([a + b for a in itertools.combinations(lo, k) for b in itertools.combinations(hi, 3 - k)])
            if got:
                return got
            ranks.remove(k)
    else:
        got = choose(list(itertools.combinations(idx, 3)))
        if got:
            return got
    return (rng.shuffle(list(cands)) + rng.shuffle(list(spare)))[:3]
