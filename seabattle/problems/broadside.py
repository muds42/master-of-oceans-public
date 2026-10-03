"""Broadside (Geometry & Trig) problems, ported from the browser game.

Five topics. Four are the game's: ``ang`` (Lookout · Angles), ``tri`` (Plot ·
Triangles), ``trig`` (Gunnery · Trig) and ``geo`` (Engineering · Area &
Volume). The fifth, ``circ`` (Shields · Circles), is new: the fleet has
circular force fields, and its problems are circle theorems and circles on the
coordinate plane. The game's standard "shell" problems are tiers 1 and 2; its
"missile" problems (multi-step, or the formula is not spelled out) are all
tier 3, and so are the hardest Shields problems.

Every generator of the first four topics is a port of one ``G(...)`` /
``GH(...)`` generator in the original: same stories, solution steps, hints and
help key, and mostly the same number ranges. The Shields generators follow the
same conventions. Text is plain Unicode; the original's ``<small>`` line under
the expression is :attr:`Problem.note`.

The wrong choices are not the original's. Each generator lists the real
mistakes a student makes on that kind of problem, each with the sentence the
workshop shows a player who picks it (:attr:`Problem.why`), and the choice
helpers pick three so that the answer can't be spotted without the math: it is
not always the middle value, the smallest, the odd one out... (see
``tests/test_problem_guessing.py``). Where that needed it, a generator's numbers
or questions changed a little (e.g. no 180° course change, where port and
starboard land in the same place; a few problems ask for either of two sides or
angles). Trig answers come from the trig table (:data:`TRIG`, :data:`SMALL_TAN`),
which the workshop can show; no wrong choice is what a calculator would give.

Figures
=======

A problem that the original drew a diagram for has ``fig`` set to a plain,
JSON-able dict ``{"kind": <kind>, ...}``. The keys are the original ``fig*``
function's arguments (JS names kept). Screen geometry below is the original's
SVG layout, given so a renderer can reproduce it; y grows downwards.

Colours. Wherever a key says "colour" the value is one of these names (the
original's palette): "line" #F2EFE6 cream (outlines, default text), "given"
#FFC94A gold (known values), "ask" #5FE3C0 mint (what is asked for), "arc"
#4ECBEE blue (angle arcs), "dim" #8FA9BD grey-blue (captions, helper lines),
"fill" rgba(78,203,238,.13) (shape fill), "red" #F4694E, "lav" #8AA8FF. See
:data:`FIG_COLOURS`.

Labels. A label is ``{"t": text, "c": colour}``; "c" may be missing, in which
case the default named for that slot applies. ``{"t": t, "c": "given"}`` is a
known value, ``{"t": t, "c": "ask"}`` the unknown.

Marks (ship icons). ``{"kind": k, "dx": x, "dy": y, "label": text}``, all but
"kind" optional: an icon drawn at a vertex offset by (dx, dy) px, with an
optional small dim caption 17 px below it. Kinds: "you" (cream ship
silhouette), "target" (red ring with a dot), "escort" (small lavender ship),
"plane" (red aircraft glyph), "torpedo" (small red torpedo; not in the
original). The original's shorthands are YOU =
``{"kind": "you", "dx": -18, "dy": 10}`` and TGT =
``{"kind": "target", "dx": 14, "dy": -10}``.

"right_tri"  -- a right triangle with vertices P (the angle vertex, usually
    you), R (the right angle, drawn with a small square) and Q (the far
    vertex).
    ratio: opp ÷ adj, sets the shape; if absent, ``deg`` (the angle at P in
        degrees, default 37) sets it via tan(deg). Clamped to 0.3..2.2. The
        figure is only roughly to scale.
    orient: absent = "east": P bottom-left, R bottom-right, Q top-right. The
        adjacent side is the bottom edge P-R (label centred below it), the
        opposite side the right edge R-Q (label to its right), the
        hypotenuse P-Q (label above-left of its midpoint).
        "mast": looking down from a height. P top-left (the observer up the
        mast), R bottom-left (foot of the mast, right angle), Q bottom-right
        (the target). The opposite side is the left edge P-R (label to its
        left), the adjacent side the bottom edge R-Q (label below), the
        hypotenuse P-Q (label below-right of its midpoint). A dashed dim
        horizontal line runs right from P; ``ang`` is the angle of depression
        between that line and the hypotenuse.
    adj, opp, hyp: side labels (default colour "line"); missing = unlabelled.
    ang: label on an arc at P between the adjacent side (or, for "mast", the
        dashed horizontal) and the hypotenuse; default colour "arc".
    ang2: label on an arc at Q between the hypotenuse and the opposite side
        (east only); default colour "arc".
    marks: {"P"|"R"|"Q": mark} icons at those vertices.
    note: small dim caption centred along the top of the figure. Problems
        that ask for the angle draw ratio 1 with note "not to scale", so the
        angle can't be judged by eye.

"compass"  -- a compass rose (circle, ticks every 30°, N/E/S/W letters). All
    angles are bearings in degrees clockwise from north.
    course: heading of the small ship arrow drawn at the centre.
    rays: list of {"deg", "label"?, "c"?, "dash"?, "mark"?}: a line from the
        centre to the rim at bearing ``deg`` (colour c, default "line";
        dashed if ``dash``), its label just outside the rim in the same
        direction (the original pushes it further out when another ray is
        nearly opposite), and a mark icon of kind ``mark`` at the ray's tip.
    arcs: list of {"from", "to", "label", "c"?, "r"?}: an arc around the
        centre sweeping clockwise from bearing ``from`` to bearing ``to``
        (to >= from; either may be below 0 or above 360, e.g. from 330 to
        380 crosses north), radius r (default 40 on a 72 px rose), label at
        the middle of the sweep just outside the arc; colour default "arc".

"triangle"  -- a general triangle: vertex 0 bottom-left, 1 bottom-right, 2 at
    the top. Base from x=40 to x=260 at y=172, top vertex at y=42.
    apex: x of the top vertex (default 150; 60 leans left, 180 leans right).
    angles: 3 entries (vertex 0, 1, 2), each a label or None: an arc inside
        that corner with the label; default colour "arc".
    sides: 3 entries (side 0-1 = bottom, 1-2 = right, 2-0 = left), each a
        label or None, drawn outside the midpoint of that side; default
        colour "given".
    ticks: 3 booleans (same side order): an "equal length" tick across the
        middle of that side.
    marks: up to 3 entries (per vertex), each a mark (kind and optional
        label; no dx/dy - the icon sits just below vertices 0 and 1 and just
        above vertex 2) or None.

"angle_split"  -- one angle split off a straight line or a right angle.
    total: 180 = a horizontal straight line with the vertex in the middle;
        names[0] is written at its left end, names[1] at its right end.
        90 = a right angle, vertex bottom-left, one arm running right
        (names[0] at its end) and one straight up (names[2] at its top;
        names[1] is unused), right-angle square at the vertex.
    t: the given angle in degrees; the ray is drawn in "given".
    given: "h" = t is measured up from the right-hand horizontal arm: a given
        arc labelled "t°" between that arm and the ray, and an asked arc "?"
        between the ray and the rest (the left arm for 180, the vertical arm
        for 90). "v" (used with 90) = t is measured from the vertical arm: the
        given arc "t°" is between the vertical and the ray, the asked arc "?"
        between the ray and the horizontal arm.
    names: arm captions (dim), see ``total``.
    rayLabel: caption at the tip of the ray (given colour).

"polygon"  -- a regular polygon, one vertex at the top, "{n} equal sides"
    written in the middle.
    n: number of sides.
    mode: "int" = an asked arc "?" inside one corner (the interior angle).
        "ext" = at that corner one side is extended as a dashed dim line; the
        asked arc "?" is between the extension and the next side (the
        exterior angle), with a small dim arc for the interior angle.

"parallel"  -- two horizontal parallel lines (caption "column 1" above the
    top one at the left, "column 2" below the bottom one at the right) cut
    by one slanted transversal (given colour) rising to the right.
    t: the acute angle between the transversal and the lines. At the top
        crossing it is marked "t°" (given) between column 1 running left and
        the transversal running down towards column 2.
    mode: (the original's ``kind`` argument, renamed so it does not clash
        with the figure's "kind") which angle at the bottom crossing is
        asked ("?", ask colour):
        "alt" = between column 2 running right and the transversal running
        up (alternate interior, Z shape); "corr" = between column 2 running
        left and the transversal running down (corresponding, F shape);
        "coint" = between column 2 running left and the transversal running
        up (co-interior, C shape).

"scale_line"  -- a plotting-sheet ruler. Caption "Scale: 1 cm on the plot =
    {k} nm at sea" on top; a "you" icon at the left end of the line and a
    "target" icon at the right end.
    k: nm per cm.
    ask: "nm" = the line is m cm long (m: paper length in cm, may be
        fractional) with a small tick every cm; above it "{m} cm" (given),
        below it "? nm" (ask).
        "cm" = the paper length is the answer, so there is no m: the line has
        a fixed length and a tick only at each end (no centimetres to
        count), "? cm" (ask) above it, "{d} nm" (given; d: the distance at
        sea) below it, and a dim "not to scale" under it.

"similar"  -- two similar right triangles side by side (right angle at the
    bottom-right, like right_tri "east"), "×{k}" written between them.
    a, b, c: the small triangle's base, vertical side and hypotenuse, all
        labelled (given). k: scale factor; the big triangle's base is
        labelled a*k (given), its vertical side is unlabelled and its
        hypotenuse is "?" (ask).

"grid"  -- a plotting grid from (0, 0) to (max x + 1, max y + 1), axes drawn,
    origin labelled 0. Both points are labelled "(x, y)" in given colour.
    p1, p2: [x, y] integer grid points.
    mode: (the original's ``kind`` argument, renamed as for "parallel")
        "dist" = dashed given legs from p1 horizontally then vertically to
        p2, labelled "Δx = |dx|" and "Δy = |dy|"; the straight segment p1-p2
        in ask colour with "?"; a "you" icon at p1, "target" at p2.
        "mid" = a sketch instead of a grid (drawn to scale, the midpoint's
        coordinates could be counted off the squares): no grid or axes, the
        two points at fixed places (p1 left or right, low or high, as it is
        from p2), "escort" icons and "(x, y)" labels at both, a dashed dim
        segment between them, an ask-colour circle at its middle labelled
        "(?, ?)" with a dim "halfway", and a dim "sketch, not to scale".

"rect"  -- a rectangle (width fixed, height from Wv/Lv, clamped).
    Lv, Wv: length (bottom edge label "{Lv} ft") and width (right edge label
        "{Wv} ft"), both given.
    mode: "area" = "A = ?" (ask) in the middle; "perim" = "P = ?" (ask) in
        the middle and the outline drawn thick, dashed, in ask colour;
        "L" = bottom label "? ft" (ask) and "A = {Lv*Wv with thousands
        separators}" (given) in the middle.

"tri_area"  -- a triangle on a horizontal base with its top vertex at 62% of
    the way along, the dashed height drawn from it (given) with a
    right-angle square. Labels "b = {b} ft" under the base, "h = {h} ft"
    beside the height, "A = ?" (ask) inside.
    b, h: base and height in feet.

"circle"  -- a circle with its centre dot.
    Exactly one of d / r is present: d = a horizontal diameter labelled
        "d = {d} {unit}"; r = a radius drawn up-right labelled
        "r = {r} {unit}" (both given).
    mode: "circ" = the circumference is drawn thick in ask colour with
        "C = ?" beside it; "area" = the disc is filled, "A = ?" inside.
    unit: "ft" or "nm".

"arc"  -- a ship's turning circle: a dashed dim full circle with a centre
    dot; the asked arc drawn thick (ask colour) from 12 o'clock clockwise
    through th°, labelled "arc = ?" outside its middle; a radius to its start
    labelled "r = {r} yd" (given) and a dashed radius to its end; a small
    angle arc at the centre labelled "{th}°"; a "you" icon at the start.
    r: radius in yards. th: turn in degrees.

"box"  -- a box (rectangular prism) drawn in oblique projection: front face,
    top face and right side face.
    Lv: length, labelled "{Lv} ft" under the front face. Hv: height,
        labelled "{Hv} ft" beside the right side. Wv: depth, labelled
        "{Wv} ft" along the receding bottom-right edge. All given.
    mode: "vol" = "V = ?" (ask) on the front face; "surf" = the three visible
        faces tinted blue / mint / gold (one colour per pair of opposite
        faces) and "6 faces = ?" (ask) on the front.

"cyl"  -- an upright cylinder (dashed back half of the bottom ellipse), a
    radius drawn on the top ellipse labelled "r = {r} ft", "h = {h} ft"
    beside it, "V = ?" (ask) in the middle.
    r, h: radius and height in feet.

"trap"  -- an isosceles trapezoid, the shorter parallel side on top; a dashed
    height with a right-angle square. Labels "{a} ft" above the top, "{b} ft"
    below the bottom, "h = {h} ft" beside the height, "A = ?" (ask) inside.
    a, b, h: top, bottom (b > a) and height in feet.

"composite"  -- a deck seen from above: a rectangle with a triangular bow on
    its right end (the triangle's base is the rectangle's right edge, its
    tip points right at mid-height, tinted mint). Labels "{Lv} ft" under
    the rectangle, "{Wv} ft" left of it, "{b} ft" above the triangle,
    "A = ?" (ask) in the rectangle.
    Lv, Wv: rectangle length and width. b: length of the bow triangle.

Shield figures (Shields · Circles; not in the original). Each is a sketch in a
fixed layout, whatever the numbers: no length, angle or centre can be read off
it. The shield is a tinted circle outlined in "lav". Unless a key says
otherwise, side labels default to "given" and angle labels to "arc".

"shield"  -- a shield on the plot, with no grid or axes, a dot at its centre
    and a dim caption under it (``note``, default "sketch, not to scale").
    ship: mark kind drawn at the centre ("target" rings the dot; others sit
        just above it), or absent.
    centre: label just below the centre dot (above it when ``point`` lies
        below the centre).
    point: {"label", "c"?, "mark"?, "dir"?, "on"?}: a point 40° off the
        horizontal in the direction ``dir`` = [±1, ±1] (grid x right, grid y
        up; default [1, 1]): on the edge if ``on``, otherwise outside it. A
        dashed dim line runs to it from the centre; its label (default
        "given") sits just beyond it and ``mark`` is an icon drawn on it.
    gap: (point outside only) the stretch of that line outside the shield,
        drawn thick in the label's colour (default "ask"), labelled beside it.
    radius: label on a radius: beside the dashed line to ``point`` when that
        is on the edge; otherwise a solid radius in the label's colour, drawn
        up and to the right (no point) or mirrored left-right from ``point``,
        with the label just past its end, outside the shield.
    edge: label under the circle, for the edge itself (default "ask").

"tangents"  -- the shield on the left (centre O, dot), a ship P on the right.
    One tangent from P touches the top of the shield at T; with ``two``, a
    second touches the bottom at T2.
    two: draw the second tangent.
    radii: (default true) draw the radius to each touching point. right: a
        right-angle square where each radius meets its tangent.
    oline: draw the dashed dim line O-P (also drawn whenever ``op`` is given).
    op, ot, pt, pt2: labels on O-P (below it), the radius O-T (on its right,
        inside the triangle O-T-P), P-T (above) and P-T2 (below).
    angP: angle arc at P between P-O and P-T, or with ``two`` between the two
        tangents. angO: angle arc at O between O-T and O-P, or with ``two``
        between O-T and O-T2.
    arc: the short arc T-T2 facing P, drawn thick in the label's colour
        (default "ask") and labelled just outside it. far: the same for the
        long arc round the back.
    names: dim letters just outside the touching points (default ["T"], or
        ["A", "B"] with ``two``).
    marks: {"P": mark}: an icon just right of P. note: dim caption on top.

"chord"  -- a straight course across the shield below its centre: dashed dim
    outside the shield (a "you" icon at its left end), solid inside it (in
    ``chord``'s colour). A dashed line from the centre meets it at 90° (square
    at the foot), in ``d``'s colour; a dim "sketch, not to scale" underneath.
    chord: label under the part inside the shield (default "ask").
    d: label left of the centre-to-course line.
    r: label on a radius, drawn to the right end of the chord if
        ``radius_to`` is "end", otherwise up and to the left to the edge.
    half: label above the right half of the chord.

"chords"  -- two chords crossing inside the shield at a gold dot, off centre.
    The first runs down to the right: ``a`` labels its part left of the
    crossing, ``b`` the part right of it (labels above the chord). The second
    runs down to the left: ``c`` labels its upper part, ``d`` its lower part
    (labels to its left). A dim "sketch, not to scale" underneath.

"inscribed"  -- points on the shield's edge, joined up.
    mode: "arc" = pylons A (lower left) and B (lower right) and C near the
        top; radii from the centre to A and B, chords C-A and C-B. Angle arcs:
        ``central`` at the centre between the radii, ``rim`` at C.
        "semi" = A and B at the ends of a horizontal diameter, C up on the
        left; triangle A-B-C. Angle arcs ``angA``, ``angB``, ``angC``.
        "quad" = A, B, C, D round the edge (left, top, right, bottom), joined
        in order; no centre dot. Angle arcs ``angA`` to ``angD`` inside.
    names: dim letters just outside the points (default A, B (, C, D)).
    marks: {"C": mark}: an icon just above C (not "quad").
    note: dim caption along the bottom.
"""

from __future__ import annotations

import itertools
import math
import re
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Callable, Optional, Sequence

from .common import Briefing, Choices, Context, Generator, Problem, is_int, js_round, js_str, pick_three, registry, sup

__all__ = [
    "HELP", "HELP_FIGURES", "GENERATORS", "TOPICS", "TRIG", "TRIG_ANGLES", "SMALL_TAN",
    "FIG_COLOURS", "YOU", "TGT", "CLASSES", "ENEMIES", "ESCORTS", "NAME_POOL",
]

GENERATORS: list[Generator] = []
gen = registry(GENERATORS)

TOPICS: dict[str, str] = {
    "ang": "Lookout · Angles",
    "tri": "Plot · Triangles",
    "trig": "Gunnery · Trig",
    "geo": "Engineering · Area & Volume",
    "circ": "Shields · Circles",
}

FIG_COLOURS: dict[str, str] = {
    "line": "#F2EFE6", "given": "#FFC94A", "ask": "#5FE3C0", "arc": "#4ECBEE",
    "dim": "#8FA9BD", "fill": "rgba(78,203,238,.13)", "red": "#F4694E", "lav": "#8AA8FF",
}

YOU: dict[str, Any] = {"kind": "you", "dx": -18, "dy": 10}
TGT: dict[str, Any] = {"kind": "target", "dx": 14, "dy": -10}

# ---------------------------------------------------------------------------
# Ships (data from the original; the generators only need ESCORTS and the
# enemies' mast heights)
# ---------------------------------------------------------------------------

CLASSES: tuple[dict[str, Any], ...] = (
    {"id": "corvette", "name": "Corvette", "cls": "Flower class", "price": 0, "hp": 40, "dmg": 8, "gun": "one 4-inch gun", "len": 62, "speed": 16, "dname": "USS Temptress", "blurb": "Small, wet and stubborn. Built to hunt U-boats in the North Atlantic."},
    {"id": "destroyer", "name": "Destroyer", "cls": "Fletcher class", "price": 350, "hp": 70, "dmg": 14, "gun": "five 5-inch guns", "len": 115, "speed": 36, "dname": "USS Kidd", "blurb": "Fast, well armed and everywhere at once. The fleet workhorse."},
    {"id": "lcruiser", "name": "Light cruiser", "cls": "Cleveland class", "price": 900, "hp": 120, "dmg": 22, "gun": "twelve 6-inch guns", "len": 186, "speed": 32, "dname": "USS Santa Fe", "blurb": "Four rapid-fire triple turrets and a wall of anti-aircraft guns."},
    {"id": "hcruiser", "name": "Heavy cruiser", "cls": "Baltimore class", "price": 1600, "hp": 160, "dmg": 32, "gun": "nine 8-inch guns", "len": 205, "speed": 33, "dname": "USS Pittsburgh", "blurb": "Heavy armor and 8-inch guns that reach out fifteen miles."},
    {"id": "battleship", "name": "Battleship", "cls": "Iowa class", "price": 3200, "hp": 260, "dmg": 55, "gun": "nine 16-inch guns", "len": 270, "speed": 33, "dname": "USS New Jersey", "blurb": "Sixteen-inch shells that weigh as much as a car. Nothing afloat argues with her."},
)
ENEMIES: tuple[dict[str, Any], ...] = (
    {"id": "uboat", "name": "U-201", "cls": "Type VII U-boat", "hp": 16, "dmg": 5, "tons": 770, "len": 67, "speed": 17, "mast": 12},
    {"id": "sboat", "name": "S-38", "cls": "S-boat torpedo boat", "hp": 16, "dmg": 4, "tons": 100, "len": 35, "speed": 39, "mast": 10},
    {"id": "zdestroyer", "name": "Z-23", "cls": "Type 1936A destroyer", "hp": 40, "dmg": 10, "tons": 2600, "len": 127, "speed": 36, "mast": 25},
    {"id": "koenigsberg", "name": "Königsberg", "cls": "Light cruiser", "hp": 70, "dmg": 16, "tons": 6650, "len": 174, "speed": 32, "mast": 30},
    {"id": "hipper", "name": "Admiral Hipper", "cls": "Heavy cruiser", "hp": 120, "dmg": 24, "tons": 14000, "len": 210, "speed": 32, "mast": 35},
    {"id": "spee", "name": "Admiral Graf Spee", "cls": "Pocket battleship", "hp": 150, "dmg": 30, "tons": 12000, "len": 186, "speed": 28, "mast": 35},
    {"id": "bismarck", "name": "Bismarck", "cls": "Battleship", "hp": 240, "dmg": 45, "tons": 41700, "len": 251, "speed": 30, "mast": 40},
)
ESCORTS: tuple[str, ...] = ("HMS Vanoc", "HMCS Sackville", "USS Buck", "HMS Starling", "USS Borie", "HMCS Snowberry", "HMS Walker", "USS Roper")
NAME_POOL: tuple[str, ...] = ("Kestrel", "Harrier", "Tempest", "Marlin", "Osprey", "Sabre", "Cormorant", "Aurora", "Valiant", "Intrepid", "Resolute", "Dauntless", "Stingray", "Barracuda", "Thunderhead", "Vigilant", "Sentinel", "Talon", "Leviathan", "Meridian")

# ---------------------------------------------------------------------------
# Number helpers: reproduce the JavaScript arithmetic and formatting
# ---------------------------------------------------------------------------


_is_int, _js, _jround = is_int, js_str, js_round


def _round1(n: float) -> float:
    """round1: Math.round(n * 10) / 10."""
    return js_round(n * 10) / 10


def _to_fixed(x: float, dp: int) -> Decimal:
    """Number.prototype.toFixed: rounds the exact binary value, halves away from zero."""
    d = Decimal(x).quantize(Decimal(1).scaleb(-dp), rounding=ROUND_HALF_UP)
    return d if d != 0 else abs(d)


def _fixed_num(x: float, dp: int) -> float:
    """``+x.toFixed(dp)``."""
    return float(_to_fixed(x, dp))


def _fmt_n(n: float, dp: int) -> str:
    """fmtN: toLocaleString('en-US') with exactly ``dp`` decimals (thousands separators)."""
    src = Decimal(n) if isinstance(n, int) else Decimal(repr(float(n)))  # Intl rounds the shortest decimal form
    d = src.quantize(Decimal(1).scaleb(-dp), rounding=ROUND_HALF_UP)
    if d == 0:
        d = abs(d)
    return f"{d:,.{dp}f}"


def _deg360(n: int) -> int:
    return ((n % 360) + 360) % 360


def _pad3(n: int) -> str:
    """045° style bearing."""
    return f"{_deg360(n):03d}°"


# A wrong choice and the mistake that leads to it: ``(value, why)`` for numbers, ``(text, why)``
# for anything else. A generator lists every mistake it can think of (``None`` entries are
# skipped, so a mistake that only fits some numbers can be written ``(...) if ok else None``);
# the helpers keep the ones that show up as a different choice and pick three of them.
Mistake = Optional[tuple[Any, str]]

# Said about a filler choice, used only when a problem has fewer than three usable mistakes.
_FILLER_WHY = "That number doesn't come out of the working. Go through the steps again."


def _choice_value(text: str) -> Optional[float]:
    """The number a choice stands for ("045°", "12.5", "36π sq ft", "7√2 nm"), or None."""
    t = text.strip().replace("−", "-").replace(",", "")
    t = re.sub(r"\s*(sq nm|sq ft|cubic ft|nm|ft|yd|km|m)$", "", t).rstrip("°").strip()
    if re.fullmatch(r"-?\d+(\.\d+)?", t):
        return float(t)
    m = re.fullmatch(r"(-?\d+(?:\.\d+)?)?\s*π", t)
    if m:
        return float(m[1] or 1) * math.pi
    m = re.fullmatch(r"(-?\d+)?\s*√(\d+)", t)
    if m:
        return float(m[1] or 1) * math.sqrt(int(m[2]))
    return None


def _numeric_choices(ctx: Context, ans: float, pool: Sequence[Mistake], allow_neg: bool = False,
                     dp: Optional[int | str] = None, avoid: Sequence[float] = ()) -> Choices:
    """The answer and three mistakes from ``pool``, a list of ``(value, why)``.

    A mistake is skipped if it is not a finite number, is zero or negative (unless
    ``allow_neg``), would show as the answer or as another mistake, or would show as one of
    ``avoid`` (e.g. what a calculator gives, when the problem wants the trig table). ``dp``: the
    decimals shown; by default 0 for a whole-number answer (a mistake that isn't a whole number
    is then skipped rather than rounded, so pass it rounded if that's the mistake), else 1.
    ``"auto"`` shows 1 decimal unless all four choices are whole numbers.
    """
    auto = dp == "auto"
    kdp = 1 if auto else int(dp) if dp is not None else 0 if _is_int(ans) else 1

    def key(v: float) -> str:
        return str(_to_fixed(v, kdp))

    ans_r = _fixed_num(ans, kdp)
    seen = {key(ans)} | {key(a) for a in avoid if math.isfinite(a)}
    cands: list[tuple[str, str, Optional[float]]] = []

    def add(v: Any, why: str) -> None:
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
            return
        r = _fixed_num(v, kdp)
        if kdp == 0 and abs(r - v) > 1e-9 * max(1.0, abs(v)):
            return
        if (r <= 0 and not allow_neg) or key(r) in seen:
            return
        seen.add(key(r))
        cands.append((_fmt_n(r, kdp).replace("-", "−"), why, r))

    for m in pool:
        if m is not None:
            add(*m)
    for f in (2, 0.5, 3, 10, 0.1, 4, 1.5):  # a last resort, if the problem ran out of mistakes
        if len(cands) >= 3:
            break
        add(ans * f, _FILLER_WHY)
    pick = pick_three(ctx, _fmt_n(ans_r, kdp), ans_r, cands)
    vals = [ans_r] + [c[2] for c in pick]
    out_dp = kdp
    if auto and all(_is_int(v) for v in vals):
        shown = {_to_fixed(v, 0) for v in vals[1:]}
        out_dp = 1 if any(_to_fixed(a, 0) in shown for a in avoid if math.isfinite(a)) else 0
    return Choices(tuple(_fmt_n(v, out_dp).replace("-", "−") for v in vals), ("",) + tuple(c[1] for c in pick))


def _string_choices(ctx: Context, ans: str, pool: Sequence[Mistake],
                    fallback: Optional[Callable[[], str]] = None) -> Choices:
    """The answer and three mistakes from ``pool``, a list of ``(text, why)``.

    Repeats, and choices that stand for the same number as the answer or as another choice,
    are skipped. ``fallback()`` makes filler choices if fewer than three mistakes are left.
    """
    ans_v = _choice_value(ans)
    seen_t, seen_v = {ans}, [ans_v] if ans_v is not None else []
    cands: list[tuple[str, str, Optional[float]]] = []

    def add(t: str, why: str) -> None:
        v = _choice_value(t)
        if t in seen_t or (v is not None and any(math.isclose(v, s, rel_tol=1e-9, abs_tol=1e-9) for s in seen_v)):
            return
        seen_t.add(t)
        if v is not None:
            seen_v.append(v)
        cands.append((t, why, v))

    for m in pool:
        if m is not None:
            add(*m)
    guard = 0
    while len(cands) < 3 and fallback is not None and guard < 60:
        guard += 1
        add(fallback(), _FILLER_WHY)
    if len(cands) < 3:
        raise ValueError(f"only {len(cands)} wrong choices for {ans!r}")
    pick = pick_three(ctx, ans, ans_v, cands)
    return Choices((ans,) + tuple(c[0] for c in pick), ("",) + tuple(c[1] for c in pick))


# Trig table used by every trig problem (2-decimal values; answers are computed from these exact numbers).
TRIG: dict[int, tuple[float, float, float]] = {
    10: (0.17, 0.98, 0.18), 20: (0.34, 0.94, 0.36), 30: (0.5, 0.87, 0.58), 37: (0.6, 0.8, 0.75),
    40: (0.64, 0.77, 0.84), 45: (0.71, 0.71, 1), 50: (0.77, 0.64, 1.19), 53: (0.8, 0.6, 1.33),
    60: (0.87, 0.5, 1.73), 70: (0.94, 0.34, 2.75), 80: (0.98, 0.17, 5.67),
}
TRIG_ANGLES: tuple[int, ...] = tuple(TRIG)
SMALL_TAN: dict[int, float] = {1: 0.017, 2: 0.035, 3: 0.052, 4: 0.07, 5: 0.087}


def _sin(a: int) -> float:
    return TRIG[a][0]


def _cos(a: int) -> float:
    return TRIG[a][1]


def _tan(a: int) -> float:
    return TRIG[a][2]


# ---------------------------------------------------------------------------
# Small builders
# ---------------------------------------------------------------------------

TRIPLES: tuple[tuple[int, int, int], ...] = (
    (3, 4, 5), (5, 12, 13), (8, 15, 17), (7, 24, 25), (20, 21, 29), (9, 40, 41),
    (6, 8, 10), (9, 12, 15), (12, 16, 20), (15, 20, 25), (10, 24, 26),
)


def _triple(ctx: Context) -> tuple[int, int, int]:
    """A Pythagorean triple, legs swapped half the time."""
    t = ctx.pick(TRIPLES)
    return (t[1], t[0], t[2]) if ctx.rand(0, 1) else t


def _escort(ctx: Context) -> str:
    return ctx.pick(ESCORTS)


def _other_escort(ctx: Context, e1: str) -> str:
    return ctx.pick([n for n in ESCORTS if n != e1])


def _enemy_mast(ctx: Context) -> int:
    """B.enemy.mast: the enemy's mast height in metres (the recognition manual).

    Looked up by name in ENEMIES; an enemy the original did not have gets the
    mast of a randomly chosen original enemy.
    """
    name = ctx.enemy_name.strip().lower()
    for e in ENEMIES:
        if e["name"].lower() == name:
            return e["mast"]
    return ctx.pick([e["mast"] for e in ENEMIES])


def _gv(t: str) -> dict[str, str]:
    return {"t": t, "c": "given"}


def _ak(t: str) -> dict[str, str]:
    return {"t": t, "c": "ask"}


def _lab(t: str, c: Optional[str] = None) -> dict[str, str]:
    return {"t": t} if c is None else {"t": t, "c": c}


def _you(**kw: Any) -> dict[str, Any]:
    return {**YOU, **kw}


def _tgt(**kw: Any) -> dict[str, Any]:
    return {**TGT, **kw}


def _fig(fig_kind: str, /, **kw: Any) -> dict[str, Any]:
    return {"kind": fig_kind, **kw}


def _problem(help: str, story: str, expr: str, ask: str, choices: Sequence[str], solution: Sequence[str],
             hint: str, note: str = "", fig: Optional[dict] = None) -> Problem:
    return Problem(help=help, story=story, expr=expr, ask=ask,
                   choices=choices if isinstance(choices, Choices) else tuple(choices),
                   solution=tuple(solution), hint=hint, note=note, fig=fig)


def _pm(side: str) -> str:
    return "+" if side == "starboard" else "−"


def _signed(n: float) -> str:
    """A number with a proper minus sign: −85, not -85."""
    return f"−{_js(-n)}" if n < 0 else _js(n)


_FRACTIONS = {(1, 2): "½", (1, 3): "⅓", (2, 3): "⅔", (1, 4): "¼", (3, 4): "¾", (1, 6): "⅙", (5, 6): "⅚", (1, 8): "⅛", (3, 8): "⅜"}


def _fraction(num: int, den: int) -> str:
    """num/den in lowest terms, as a fraction character where there is one: _fraction(120, 360) -> "⅓"."""
    g = math.gcd(num, den)
    n, d = num // g, den // g
    return str(n) if d == 1 else _FRACTIONS.get((n, d), f"{n}/{d}")


# ---------------------------------------------------------------------------
# Help briefings (one per problem type)
# ---------------------------------------------------------------------------

HELP: dict[str, Briefing] = {
    "bearing": Briefing(
        title="Bearings: relative to true",
        concept="A true bearing is measured clockwise from north (000°). A relative bearing is measured clockwise from your own bow. To turn a lookout's relative bearing into a true bearing, add it to your course. Bearings only go up to 359°, so if you pass 360 you wrap around and subtract 360.",
        steps=("Write down your course (heading).", "Add the relative bearing.", "If the total is 360 or more, subtract 360.", "Write the answer with three digits, like 045°."),
        example="Course 300°, contact 090° relative.\n300 + 90 = 390. That passes 360, so 390 − 360 = 030°.",
    ),
    "between": Briefing(
        title="The angle between two bearings",
        concept="Two bearings are two directions from the same spot. The angle between them is just the difference. But the compass is a circle, so if the difference is bigger than 180° the short way around is 360° minus the difference.",
        steps=("Subtract the smaller bearing from the bigger one.", "If the result is more than 180°, subtract it from 360° to get the short way around."),
        example="Contacts at 350° and 020°.\n350 − 20 = 330. That's more than 180, so 360 − 330 = 30°.",
    ),
    "trisum": Briefing(
        title="Angles in a triangle add to 180°",
        concept="Every triangle, no matter its shape, has three angles that add up to exactly 180°. If you know two of them, the third is whatever is left over.",
        steps=("Add the two angles you know.", "Subtract that total from 180°."),
        example="Angles of 40° and 65°.\n40 + 65 = 105. 180 − 105 = 75°.",
    ),
    "supp": Briefing(
        title="Supplementary and complementary angles",
        concept="Two angles that make a straight line are supplementary: they add to 180°. Two angles that make a right angle (a corner) are complementary: they add to 90°. Bow-to-stern is a straight line; deck-to-mast is a right angle.",
        steps=("Decide: straight line (180°) or right angle (90°)?", "Subtract the angle you know from that total."),
        example="Gun trained 35° off the bow. Angle to the stern?\nBow to stern is 180°, so 180 − 35 = 145°.\nBarrel at 25° above the deck. Angle to the mast? 90 − 25 = 65°.",
    ),
    "turn": Briefing(
        title="Changing course",
        concept="Courses run clockwise around the compass from 000° (north). Turning to starboard (right) adds degrees; turning to port (left) subtracts. The compass wraps around: below 000° add 360, at 360° or more subtract 360.",
        steps=("Starboard → add the turn to the course. Port → subtract it.", "If the answer is negative, add 360. If it is 360 or more, subtract 360.", "Write it with three digits."),
        example="Course 020°, \"come port 50°\".\n20 − 50 = −30 → −30 + 360 = 330°.",
    ),
    "poly": Briefing(
        title="Angles of a regular polygon",
        concept="A regular polygon has n equal sides and n equal corners. Walk all the way around the outside and you turn a full 360°, so each outside (exterior) turn is 360 ÷ n. The inside (interior) angle at each corner is 180° minus that exterior angle, which is the same as (n − 2) × 180 ÷ n.",
        steps=("Count the sides, n.", "Exterior angle = 360 ÷ n.", "Interior angle = 180 − exterior, or (n − 2) × 180 ÷ n."),
        example="A hexagonal gun tub (n = 6).\nExterior: 360 ÷ 6 = 60°. Interior: 180 − 60 = 120°. Check: (6 − 2) × 180 ÷ 6 = 720 ÷ 6 = 120 ✓",
    ),
    "isos": Briefing(
        title="Isosceles triangles",
        concept="An isosceles triangle has two equal sides (marked with little ticks), and the two angles at the bottom of those sides (the base angles) are equal too. With the tip angle known, the other two share what is left of 180° equally.",
        steps=("Subtract the tip (apex) angle from 180°.", "Split the remainder in half: that is each base angle.", "Going the other way: apex = 180 − 2 × base angle."),
        example="Apex angle 40°.\n180 − 40 = 140. 140 ÷ 2 = 70° for each base angle.",
    ),
    "parallel": Briefing(
        title="Parallel lines and a transversal",
        concept="When one line cuts across two parallel lines, it makes the same angles at both crossings. Alternate interior angles (the \"Z\" shape) are equal. Corresponding angles (the \"F\" shape) are equal. Co-interior angles (the \"C\" shape, same side, between the lines) add to 180°.",
        steps=("Spot the shape: Z or F means equal; C means they add to 180°.", "Equal → same number. Add to 180 → subtract from 180."),
        example="Leg crosses column 1 at 70°.\nAlternate interior at column 2: 70°. Corresponding: 70°. Co-interior: 180 − 70 = 110°.",
    ),
    "pyth": Briefing(
        title="Pythagorean theorem: finding the range",
        concept="A contact that is east AND north of you makes a right triangle. The straight-line range is the longest side (the hypotenuse). a² + b² = c², so square the two legs, add, and take the square root.",
        steps=("Square the east distance and the north distance.", "Add them.", "Take the square root."),
        example="6 nm east and 8 nm north.\n36 + 64 = 100. √100 = 10 nm.",
    ),
    "pythleg": Briefing(
        title="Pythagorean theorem: finding a leg",
        concept="If you know the range (hypotenuse) and one leg, rearrange: b² = c² − a². Square, subtract, then square-root.",
        steps=("Square the range and the known leg.", "Subtract: range² − leg².", "Take the square root."),
        example="Range 13 nm, contact 5 nm east. How far north?\n169 − 25 = 144 → √144 = 12 nm.",
    ),
    "dist": Briefing(
        title="Distance between two grid points",
        concept="On a plotting grid the distance between two points is the hypotenuse of a right triangle whose legs are the change in x and the change in y. Distance = √((Δx)² + (Δy)²).",
        steps=("Subtract the x-coordinates; subtract the y-coordinates.", "Square both differences and add them.", "Take the square root."),
        example="(2, 3) and (8, 11).\nΔx = 6, Δy = 8 → √(36 + 64) = √100 = 10.",
    ),
    "scale": Briefing(
        title="Scale and similar triangles",
        concept="A chart scale is a multiplier: if 1 cm stands for 5 nm, every measurement on paper gets multiplied by 5 to become real distance. Similar triangles work the same way: every side of the big triangle is the small triangle's side times the same scale factor.",
        steps=("Find the scale factor (real ÷ paper, or big side ÷ matching small side).", "Multiply the paper measurement by it to get real distance.", "Going from real to paper: divide instead."),
        example="Scale 1 cm = 5 nm, line measures 3.5 cm.\n3.5 × 5 = 17.5 nm.\nSmall triangle 3-4-5, big one's short side is 9: factor 3, so longest side = 5 × 3 = 15.",
    ),
    "sqdiag": Briefing(
        title="The 45-45-90 triangle",
        concept="A right triangle with two 45° angles has two equal legs. Its hypotenuse is a leg times √2 (about 1.41). A contact exactly 45° off the bow is this shape: just as far ahead as it is to the side.",
        steps=("Confirm both legs are equal (45° angles).", "Hypotenuse = leg × √2. Leave the √2 in the answer unless asked for a decimal."),
        example="Legs of 7 nm.\nRange = 7√2 nm (≈ 9.9 nm).",
    ),
    "mid": Briefing(
        title="The midpoint of two points",
        concept="Halfway between two points means halfway in x AND halfway in y. Average the x-coordinates, then average the y-coordinates.",
        steps=("Add the two x values and divide by 2.", "Add the two y values and divide by 2.", "Write the answer as (x, y)."),
        example="Escorts at (2, 6) and (10, 12).\nx: (2 + 10) ÷ 2 = 6. y: (6 + 12) ÷ 2 = 9. Station: (6, 9).",
    ),
    "tri30": Briefing(
        title="The 30-60-90 triangle",
        concept="A right triangle with a 30° angle has a special shape: the side opposite the 30° angle is exactly half the hypotenuse, and the other leg is that short side times √3. No trig table needed.",
        steps=("Find the hypotenuse (the longest side, across from the right angle).", "Short leg (opposite 30°) = hypotenuse ÷ 2.", "Long leg (opposite 60°) = short leg × √3."),
        example="Contact 30° off the bow at 24 nm.\nCross-range = 24 ÷ 2 = 12 nm. Along-track = 12√3 ≈ 20.8 nm.",
    ),
    "perim": Briefing(
        title="Perimeter of a triangle",
        concept="The perimeter is the total distance all the way around a shape. For a triangle, add the three sides. That's it — but check you have all three.",
        steps=("List the three side lengths.", "Add them up."),
        example="Patrol legs 5, 12 and 13 nm.\n5 + 12 + 13 = 30 nm.",
    ),
    "trigside": Briefing(
        title="SOH-CAH-TOA: finding a side",
        concept="In a right triangle, each angle has an opposite side (across from it), an adjacent side (next to it, not the hypotenuse), and the hypotenuse (longest, across from the right angle). Sine, cosine and tangent are ratios of those sides: Sin = Opp ÷ Hyp, Cos = Adj ÷ Hyp, Tan = Opp ÷ Adj. Know the angle and one side, and you can find another side.",
        steps=("Label the sides from the angle's point of view: opposite, adjacent, hypotenuse.", "Pick the ratio that uses the side you know and the side you want.", "Look up the ratio's value in the table.", "Multiply (if the unknown is on top) or divide (if it is on the bottom)."),
        example="Contact 30° off the bow at 20 nm. Cross-range (opposite)?\nHave hypotenuse, want opposite → sine. sin 30° = 0.5. 20 × 0.5 = 10 nm.",
    ),
    "trigratio": Briefing(
        title="SOH-CAH-TOA: the three ratios",
        concept="Sine, cosine and tangent are fractions made from two sides of a right triangle, seen from one of its angles (θ). The opposite side is across from θ, the adjacent side runs from θ to the right angle, and the hypotenuse is the longest side, across from the right angle. Move θ to the other corner and opposite and adjacent swap.",
        steps=("Find θ in the figure.", "Label the sides from θ: opposite, adjacent, hypotenuse.", "Sin = Opp ÷ Hyp, Cos = Adj ÷ Hyp, Tan = Opp ÷ Adj: write the two sides as a fraction."),
        example="Sides 3, 4 and 5 nm, θ opposite the 3 nm side.\nsin θ = 3/5, cos θ = 4/5, tan θ = 3/4.\nFrom the other corner, 4 nm is opposite: sin = 4/5.",
    ),
    "trigsetup": Briefing(
        title="SOH-CAH-TOA: which ratio?",
        concept="To find a side from an angle, first pick the ratio. It has to use the side you know and the side you want: opposite and hypotenuse go with sine, adjacent and hypotenuse with cosine, opposite and adjacent with tangent. Then multiply if the side you want is on top of the ratio, divide if it is underneath.",
        steps=("Label the side you know and the side you want, from the angle.", "Pick the ratio that has both of them.", "Side you want on top of the ratio? Multiply. Underneath? Divide."),
        example="Angle 30°, hypotenuse 20 nm, want the opposite side.\nOpposite and hypotenuse → sin. x is on top: x = 20 × sin 30°.\nWant the hypotenuse from the opposite side 10 nm? It's underneath: x = 10 ÷ sin 30°.",
    ),
    "trigangle": Briefing(
        title="SOH-CAH-TOA: finding an angle",
        concept="If you know two sides of a right triangle, divide them to get a ratio, then find that ratio in the trig table to read off the angle. The pair of sides tells you which column to look in: opposite and hypotenuse → sine; adjacent and hypotenuse → cosine; opposite and adjacent → tangent.",
        steps=("Label the two sides you know (opposite, adjacent or hypotenuse).", "Pick the matching ratio and divide.", "Find the value in the right column of the table and read the angle."),
        example="Opposite 3 nm, adjacent 4 nm.\ntan θ = 3 ÷ 4 = 0.75. In the tan column, 0.75 is 37°.",
    ),
    "stadimeter": Briefing(
        title="The stadimeter: range from a known height",
        concept="A stadimeter measures the tiny angle that a ship's mast fills in the eyepiece. If you know the mast's real height from the recognition manual, tangent gives the range: tan(angle) = height ÷ range, so range = height ÷ tan(angle). Small angle means far away.",
        steps=("Get the mast height from the manual.", "Read the angle in the rangefinder and look up its tangent.", "Range = height ÷ tangent."),
        example="Mast 30 m, angle 2° (tan 2° ≈ 0.035).\n30 ÷ 0.035 ≈ 857 m.",
    ),
    "lead": Briefing(
        title="Lead angle: aiming ahead of a moving target",
        concept="Shells take time to fly, and the target keeps moving. You aim where the target WILL be. The lead distance is speed × flight time. Turn it into an angle with tangent: tan(lead angle) = lead distance ÷ range, then look the value up in the table.",
        steps=("Lead distance = target speed × shell flight time.", "Divide the lead distance by the range to get tan(lead).", "Find that tangent in the table to get the lead angle."),
        example="Target 12 m/s, flight time 30 s, range 1,000 m.\n12 × 30 = 360 m. 360 ÷ 1,000 = 0.36 → tan 20° ≈ 0.36 → lead 20°.",
    ),
    "rect": Briefing(
        title="Rectangles: area and perimeter",
        concept="Area is the space inside: length × width, in square units. Perimeter is the distance around: 2 × length + 2 × width, in plain units. If you know the area and one side, divide to find the other.",
        steps=("Area = length × width.", "Perimeter = 2 × length + 2 × width.", "Missing side = area ÷ known side."),
        example="Deck 60 ft × 20 ft.\nArea = 1,200 sq ft. Perimeter = 120 + 40 = 160 ft.",
    ),
    "tri": Briefing(
        title="Area of a triangle",
        concept="A triangle is half of a rectangle with the same base and height, so its area is ½ × base × height. The height must be measured straight across (perpendicular) from the base to the tip — the dashed line in the picture.",
        steps=("Multiply base × height.", "Halve it."),
        example="Base 40 ft, height 15 ft.\n40 × 15 = 600. 600 ÷ 2 = 300 sq ft.",
    ),
    "circle": Briefing(
        title="Circles: circumference and area",
        concept="Circumference (the distance around) = π × diameter = 2 × π × radius. Area (the space inside) = π × radius². The radius is half the diameter. Answers are often left \"in terms of π\" (like 36π) so nothing needs rounding; if you need a number, use π ≈ 3.14.",
        steps=("Find the radius (halve the diameter if needed).", "Around? C = 2πr. Inside? A = πr².", "Leave π in the answer, or multiply by 3.14 if asked for a decimal."),
        example="Radar reaches 15 nm (radius).\nArea = π × 15² = 225π sq nm (≈ 706.5).\nRing 10 ft across: C = π × 10 = 10π ft ≈ 31.4 ft.",
    ),
    "arc": Briefing(
        title="Arc length: turning through part of a circle",
        concept="A ship turning through 90° travels a quarter of the way around its turning circle. Arc length = (angle ÷ 360) × the full circumference (2πr). The fraction tells you how much of the circle you used.",
        steps=("Full circumference = 2πr.", "Fraction of the circle = angle ÷ 360.", "Multiply the two."),
        example="Radius 400 yd, turn 90°.\n2π × 400 = 800π. 90 ÷ 360 = ¼. ¼ × 800π = 200π yd (≈ 628 yd).",
    ),
    "vol": Briefing(
        title="Volume of a box",
        concept="Volume is how much space a solid holds, in cubic units. For a box (rectangular prism) multiply the three dimensions: length × width × height.",
        steps=("Multiply length × width to get the floor area.", "Multiply by the height."),
        example="Tank 10 ft × 6 ft × 4 ft.\n10 × 6 = 60. 60 × 4 = 240 cubic ft.",
    ),
    "cyl": Briefing(
        title="Volume of a cylinder",
        concept="A cylinder is a circle stretched up into a tube. Its volume is the area of the circular end (πr²) times the height. Leave π in the answer unless asked for a decimal.",
        steps=("Square the radius.", "Multiply by the height.", "Put π in front."),
        example="Radius 3 ft, height 10 ft.\n3² = 9. 9 × 10 = 90. Volume = 90π cubic ft.",
    ),
    "trap": Briefing(
        title="Area of a trapezoid",
        concept="A trapezoid has two parallel sides of different lengths. Its area is the average of those two sides times the height (the straight-across distance between them).",
        steps=("Add the two parallel sides.", "Divide by 2 to average them.", "Multiply by the height."),
        example="Top 10 ft, bottom 16 ft, height 6 ft.\n(10 + 16) ÷ 2 = 13. 13 × 6 = 78 sq ft.",
    ),
    "surf": Briefing(
        title="Surface area of a box",
        concept="Painting every face of a box means adding up the areas of all six faces. Opposite faces match, so there are three pairs (the three colors in the picture): 2 × (length × width) + 2 × (length × height) + 2 × (width × height).",
        steps=("Find the three different face areas: l×w, l×h, w×h.", "Add them together.", "Double the total (each face has a twin)."),
        example="Locker 4 × 3 × 2 ft.\n4×3 = 12, 4×2 = 8, 3×2 = 6. Sum 26. Double: 52 sq ft.",
    ),
    "composite": Briefing(
        title="Area of a combined shape",
        concept="A deck seen from above is a rectangle with a triangular bow on the end. Cut the shape into pieces you know, find each area, and add them up.",
        steps=("Rectangle: length × width.", "Triangle bow: ½ × width × bow length.", "Add the two areas."),
        example="Rectangle 200 × 40 ft, bow triangle 30 ft long.\n8,000 + ½ × 40 × 30 = 8,000 + 600 = 8,600 sq ft.",
    ),
    # Shields · Circles
    "circeq": Briefing(
        title="The equation of a circle",
        concept="Every point on a shield's edge is the same distance, the radius r, from its centre (h, k). Pythagoras turns that into an equation: (x − h)² + (y − k)² = r². Each bracket takes the centre away, so the signs inside the brackets are the opposite of the centre's: (x − 3) means h = 3, and (y + 2) means k = −2. The number on the right is r², not r.",
        steps=("Centre: flip the sign of the number in each bracket.", "Radius: take the square root of the number on the right.", "Writing an equation: put the centre into the brackets with its signs flipped, and square the radius.", "Only know a point on the edge? r² = (Δx)² + (Δy)² from the centre to that point. No square root needed."),
        example="(x − 3)² + (y + 2)² = 49.\nCentre (3, −2), radius √49 = 7.\nCentre (−1, 4), radius 5: (x + 1)² + (y − 4)² = 25.",
    ),
    "inscribed": Briefing(
        title="Angles at the centre and at the rim",
        concept="Two points on a shield's edge make an angle at the centre (the central angle) and an angle at any point on the rest of the rim (an inscribed angle). The angle at the rim is always half the angle at the centre. A diameter is a straight line through the centre, 180°, so an angle at the rim facing a diameter is 90°: an angle in a semicircle is a right angle.",
        steps=("Find the two points and the angle they make at the centre.", "Angle at the rim = angle at the centre ÷ 2. Going the other way, double it.", "Facing a diameter? The angle at the rim is 90°, and the triangle's other two angles share the other 90°."),
        example="Pylons 110° apart, seen from the centre.\nFrom the rim: 110 ÷ 2 = 55°.\nA diameter AB and 30° at A: the rim angle is 90°, so the angle at B is 180 − 90 − 30 = 60°.",
    ),
    "tangent": Briefing(
        title="A tangent meets the radius at 90°",
        concept="A course that just grazes a shield touches its edge at one point: it is a tangent. The radius to that point always meets the tangent at a right angle. So the ship, the touching point and the centre make a right triangle, with the right angle at the touching point.",
        steps=("Mark the right angle where the tangent touches the edge.", "The other two angles, at the ship and at the centre, share the other 90°.", "Subtract the angle you know from 90."),
        example="The line to the centre makes 35° with the course.\nThe right angle is at the touching point, so the angle at the centre is 90 − 35 = 55°.",
    ),
    "cyclic": Briefing(
        title="Quadrilaterals on a circle",
        concept="When all four corners of a quadrilateral sit on the edge of a circle, its opposite angles add to 180°. Each corner is an angle at the rim, half the angle at the centre facing it, and a pair of opposite corners faces the whole 360° between them: half of 360 is 180.",
        steps=("Find the corner opposite the one you know (across the shape, not next to it).", "Opposite corners add to 180°: subtract the angle you know from 180."),
        example="Four pylons on a shield; the angle at A is 105°.\nThe opposite corner C: 180 − 105 = 75°.\nB and D are the other pair, and they add to 180° too.",
    ),
    "circdist": Briefing(
        title="How far from a shield's edge",
        concept="On the plotting grid, the distance from a point to a shield's centre comes from the distance formula, √((Δx)² + (Δy)²). The edge is one radius nearer than the centre, so for a point outside the shield, take the radius away.",
        steps=("Find Δx and Δy between the point and the centre.", "Distance to the centre = √((Δx)² + (Δy)²).", "Distance to the edge = that − the radius."),
        example="Torpedo at (9, 12), shield of radius 10 centred at (0, 0).\n√(81 + 144) = √225 = 15 nm to the centre.\n15 − 10 = 5 nm to the edge.",
    ),
    "tanlen": Briefing(
        title="How long is a tangent?",
        concept="The radius meets a tangent at 90°, so the ship, the touching point and the centre make a right triangle. The line from the ship to the centre is across from the right angle, so it is the hypotenuse: tangent² + radius² = distance².",
        steps=("Square the distance to the centre and the radius.", "Subtract: distance² − radius².", "Take the square root."),
        example="13 nm from the centre of a shield of radius 5.\n169 − 25 = 144 → √144 = 12 nm along the tangent.",
    ),
    "tanseg": Briefing(
        title="Two tangents from one ship",
        concept="From a ship outside a shield there are two tangent courses, one grazing each side. They are the same length: the picture is symmetrical about the line from the ship to the centre. So if each is written with x, set the two expressions equal and solve.",
        steps=("Set the two tangent lengths equal.", "Solve for x: x terms on one side, numbers on the other.", "Put x back into either expression for the length. Check it with the other."),
        example="PA = 3x + 2 and PB = 5x − 6.\n3x + 2 = 5x − 6 → 8 = 2x → x = 4.\nPA = 3 × 4 + 2 = 14 nm. Check: PB = 20 − 6 = 14 ✓",
    ),
    "chord": Briefing(
        title="A course through a shield (chords)",
        concept="A straight course across a circle is a chord. The line from the centre that meets it at 90° cuts it exactly in half. The radius to one end of the chord, that line and half the chord make a right triangle, with the radius as the hypotenuse.",
        steps=("Draw the radius to one end of the chord: it is the hypotenuse.", "Half the chord = √(radius² − distance from the centre²).", "Double it for the whole chord. Going the other way: distance = √(radius² − half²)."),
        example="Course 6 nm from the centre of a shield of radius 10.\nHalf: √(100 − 36) = √64 = 8. The whole run: 2 × 8 = 16 nm.",
    ),
    "tanarc": Briefing(
        title="Two tangents and the arc between them",
        concept="Two tangents from one ship touch a shield at A and B. With the radii to A and B they make a four-sided shape, whose angles add to 360°. Two of those angles are right angles (a tangent meets the radius at 90°), so the angle at the ship and the angle at the centre add to 180°. An arc is measured by its angle at the centre.",
        steps=("The angles at A and B are 90° each.", "Angle at the centre = 360 − 90 − 90 − angle at the ship.", "The short arc AB is that many degrees; the long arc is 360 minus it."),
        example="Tangents meet at 50°.\nAngle at the centre: 360 − 90 − 90 − 50 = 130°, so the short arc AB is 130°.\nThe long arc: 360 − 130 = 230°.",
    ),
    "chords": Briefing(
        title="Crossing chords",
        concept="When two chords cross inside a circle, the crossing point cuts each one into two parts. The two parts of one chord multiply to the same number as the two parts of the other: a × b = c × d.",
        steps=("Multiply the two parts of the chord you know completely.", "Divide by the known part of the other chord: that is its missing part.", "Want the whole chord? Add its two parts."),
        example="One chord is cut into 4 and 9; the other has a part of 6.\n4 × 9 = 36 = 6 × x → x = 36 ÷ 6 = 6.\nThe whole second chord: 6 + 6 = 12.",
    ),
}

# The picture that goes with each briefing's worked example (same format as Problem.fig).
# "scale" has two: the scale ruler and the similar triangles.
HELP_FIGURES: dict[str, tuple[dict[str, Any], ...]] = {
    "bearing": (_fig("compass", course=300, rays=[{"deg": 300, "label": "course 300°", "dash": True, "c": "dim"}, {"deg": 30, "label": "true ?", "c": "ask", "mark": "target"}], arcs=[{"from": 300, "to": 390, "label": "90° rel.", "c": "given"}]),),
    "between": (_fig("compass", course=0, rays=[{"deg": 350, "label": "350°", "c": "given", "mark": "target"}, {"deg": 20, "label": "020°", "c": "given", "mark": "target"}], arcs=[{"from": 350, "to": 380, "label": "?", "c": "ask"}]),),
    "trisum": (_fig("triangle", apex=175, angles=[_gv("40°"), _gv("65°"), _ak("?")], marks=[{"kind": "you"}, {"kind": "escort"}, {"kind": "target"}]),),
    "supp": (_fig("angle_split", t=35, total=180, given="h", names=["stern", "bow"], rayLabel="gun"),),
    "turn": (_fig("compass", course=20, rays=[{"deg": 20, "label": "course 020°", "dash": True, "c": "dim"}, {"deg": 330, "label": "new ?", "c": "ask"}], arcs=[{"from": 330, "to": 380, "label": "50° port", "c": "given"}]),),
    "poly": (_fig("polygon", n=6, mode="int"),),
    "isos": (_fig("triangle", apex=150, angles=[_ak("?"), _ak("?"), _gv("40°")], ticks=[False, True, True], marks=[{"kind": "you"}, {"kind": "escort"}, {"kind": "target"}]),),
    "parallel": (_fig("parallel", t=70, mode="alt"),),
    "pyth": (_fig("right_tri", ratio=8 / 6, adj=_gv("6 nm east"), opp=_gv("8 nm north"), hyp=_ak("range ?"), marks={"P": _you(), "Q": _tgt()}),),
    "pythleg": (_fig("right_tri", ratio=12 / 5, adj=_gv("5 nm east"), opp=_ak("north ?"), hyp=_gv("range 13 nm"), marks={"P": _you(), "Q": _tgt()}),),
    "dist": (_fig("grid", p1=[2, 3], p2=[8, 11], mode="dist"),),
    "scale": (_fig("scale_line", k=5, m=3.5, ask="nm"), _fig("similar", a=3, b=4, c=5, k=3)),
    "sqdiag": (_fig("right_tri", ratio=1, adj=_gv("7 nm"), opp=_gv("7 nm"), hyp=_ak("?"), ang=_lab("45°"), ang2=_lab("45°"), marks={"P": _you(), "Q": _tgt()}),),
    "mid": (_fig("grid", p1=[2, 6], p2=[10, 12], mode="mid"),),
    "tri30": (_fig("right_tri", deg=30, hyp=_gv("24 nm"), opp=_ak("?"), adj=_lab("short leg × √3", "dim"), ang=_lab("30°"), ang2=_lab("60°"), marks={"P": _you(), "Q": _tgt()}),),
    "perim": (_fig("triangle", apex=60, sides=[_lab("5 nm"), _lab("13 nm"), _lab("12 nm")], marks=[{"kind": "you"}]),),
    "trigside": (_fig("right_tri", deg=30, hyp=_gv("hyp 20 nm"), opp=_ak("opp ?"), adj=_lab("adjacent", "dim"), ang=_lab("30°"), marks={"P": _you(), "Q": _tgt()}),),
    "trigratio": (_fig("right_tri", ratio=0.75, opp=_gv("3 nm"), adj=_gv("4 nm"), hyp=_gv("5 nm"), ang=_ak("θ"), marks={"P": _you(), "Q": _tgt()}),),
    "trigsetup": (_fig("right_tri", deg=30, hyp=_gv("20 nm"), opp=_ak("x"), adj=_lab("track", "dim"), ang=_lab("30°"), marks={"P": _you(), "Q": _tgt()}),),
    "trigangle": (_fig("right_tri", ratio=0.75, opp=_gv("opp 3 nm"), adj=_gv("adj 4 nm"), ang=_ak("θ = ?"), marks={"P": _you(), "Q": _tgt()}),),
    "stadimeter": (_fig("right_tri", ratio=0.32, adj=_ak("range ?"), opp=_gv("mast 30 m"), ang=_lab("2°"), marks={"P": _you(), "Q": _tgt()}, note="not to scale — the real angle is tiny"),),
    "lead": (_fig("right_tri", ratio=0.36, adj=_gv("range 1,000 m"), opp=_gv("lead 360 m"), ang=_ak("lead ?"), marks={"P": _you(), "R": {"kind": "target", "dx": 8, "dy": -12}, "Q": {"kind": "target", "label": "in 30 s", "dx": 22, "dy": -14}}),),
    "rect": (_fig("rect", Lv=60, Wv=20, mode="area"),),
    "tri": (_fig("tri_area", b=40, h=15),),
    "circle": (_fig("circle", r=15, mode="area", unit="nm"),),
    "arc": (_fig("arc", r=400, th=90),),
    "vol": (_fig("box", Lv=10, Wv=6, Hv=4, mode="vol"),),
    "cyl": (_fig("cyl", r=3, h=10),),
    "trap": (_fig("trap", a=10, b=16, h=6),),
    "surf": (_fig("box", Lv=4, Wv=3, Hv=2, mode="surf"),),
    "composite": (_fig("composite", Lv=200, Wv=40, b=30),),
    "circeq": (_fig("shield", centre=_gv("(3, −2)"), radius=_gv("r = √49 = 7"), edge=_gv("(x − 3)² + (y + 2)² = 49"), ship="target"),),
    "inscribed": (_fig("inscribed", mode="arc", central=_gv("110°"), rim=_ak("?"), marks={"C": {"kind": "you"}}),
                  _fig("inscribed", mode="semi", angA=_gv("30°"), angB=_ak("?"), angC=_lab("90°", "dim"), marks={"C": {"kind": "you"}})),
    "tangent": (_fig("tangents", oline=True, right=True, angP=_gv("35°"), angO=_ak("?"), marks={"P": {"kind": "you"}}),),
    "cyclic": (_fig("inscribed", mode="quad", angA=_gv("105°"), angC=_ak("?")),),
    "circdist": (_fig("shield", centre=_gv("(0, 0)"), radius=_gv("r = 10"), point={"label": "(9, 12)", "c": "given", "mark": "torpedo"},
                      gap=_ak("?"), ship="target"),),
    "tanlen": (_fig("tangents", op=_gv("13 nm"), ot=_gv("r = 5 nm"), pt=_ak("?"), right=True, marks={"P": {"kind": "you"}}),),
    "tanseg": (_fig("tangents", two=True, radii=False, pt=_gv("PA = 3x + 2"), pt2=_gv("PB = 5x − 6"), marks={"P": {"kind": "you", "label": "P"}}),),
    "chord": (_fig("chord", r=_gv("r = 10"), d=_gv("6"), half=_lab("8", "dim"), chord=_ak("?"), radius_to="end"),),
    "tanarc": (_fig("tangents", two=True, right=True, angP=_gv("50°"), arc=_ak("?"), marks={"P": {"kind": "you"}}),),
    "chords": (_fig("chords", a=_gv("4"), b=_gv("9"), c=_gv("6"), d=_ak("?")),),
}


# ===========================================================================
# Standard ("shell") problems
# ===========================================================================

# ---------------- Lookout · Angles ----------------


@gen("ang", 1)
def relative_to_true_bearing(ctx: Context) -> Problem:
    me, en = ctx.my_name, ctx.enemy_name
    H = ctx.rand(0, 35) * 10
    R = ctx.pick([15, 20, 30, 45, 60, 75, 90, 110, 120, 135, 150, 200, 225, 240, 270, 300, 315, 330, 345])
    T = (H + R) % 360
    return _problem(
        help="bearing",
        story=f'{me} is steaming on course {_pad3(H)}. The lookout shouts: "Contact! {en}, bearing {R}° relative!" Relative bearings are measured clockwise from your own bow.',
        expr=f"{_pad3(H)} + {R}° = ?",
        note="subtract 360° if you go past it",
        ask="What is the contact's true bearing?",
        choices=_string_choices(ctx, _pad3(T), [
            (f"{H + R}°", f"That's {H} + {R} = {H + R}, but bearings stop at 359°. Take away 360.") if H + R >= 360
            else (f"−{360 - H - R}°", f"That's {H} + {R} − 360. Only take away 360 when the total reaches 360 or more."),
            (_pad3(H - R), f"You took {R} away from {H}. A relative bearing goes clockwise from your bow, so add it to your course."),
            (_pad3(R - H), f"That's {R} − {H}: you took your course away from the relative bearing. Add the two instead.") if R > H else None,
            (_pad3(R), f"That's just the relative bearing. It's measured from your bow, so add your course, {_pad3(H)}."),
            (_pad3(H), f"That's your own course. The contact is {R}° further round, clockwise from your bow."),
            (_pad3(T + 180), "That points the opposite way, from the contact back to you. Her true bearing is course + relative bearing."),
        ]),
        solution=[
            f"True bearing = course + relative bearing: {H} + {R} = {H + R}.",
            f"That passes 360°, so subtract 360: {H + R} − 360 = {T}." if H + R >= 360 else "That is under 360°, so it stays as it is.",
            f"Write it with three digits: {_pad3(T)}.",
        ],
        hint="Add the relative bearing to your course. If the total reaches 360, subtract 360.",
        fig=_fig("compass", course=H,
                 rays=[{"deg": H, "label": f"course {_pad3(H)}", "dash": True, "c": "dim"},
                       {"deg": T, "label": "true ?", "c": "ask", "mark": "target"}],
                 arcs=[{"from": H, "to": H + R, "label": f"{R}° rel.", "c": "given"}]),
    )


@gen("ang", 2)
def angle_between_bearings(ctx: Context) -> Problem:
    en = ctx.enemy_name
    across_north = ctx.rand(0, 1)  # half the time the short way round crosses north, the case the note is about
    while True:  # and neither contact on 000°, where "the bigger bearing" and "the sum" run into the other mistakes
        a = ctx.rand(1, 71) * 5
        b = (a + ctx.pick([20, 35, 50, 70, 90, 120, 150, 200, 250, 300, 330])) % 360
        if b and (abs(a - b) > 180) == bool(across_north):
            break
    diff = abs(a - b)
    ans = min(diff, 360 - diff)
    lo, hi = min(a, b), max(a, b)
    return _problem(
        help="between",
        story=f"Radar holds two contacts. {en} bears {_pad3(a)} and an unknown echo bears {_pad3(b)}. The gunnery officer wants to know how far apart they are.",
        expr=f"{_pad3(a)} and {_pad3(b)}",
        note="the smaller angle between the two directions",
        ask="How many degrees apart are the two bearings? (Give the smaller angle.)",
        choices=_numeric_choices(ctx, ans, [
            (diff, f"That's {hi} − {lo}, the long way round. When the gap is more than 180°, take it away from 360.") if diff > 180
            else (360 - diff, f"That's 360 − {diff}, the long way round. When the difference is 180° or less, it's already the gap."),
            (a + b, f"You added the two bearings. The gap between them is the difference: {hi} − {lo}."),
            (diff - 180, f"That's {diff} − 180. For the short way round, take {diff} away from 360, not 180 away from it.") if diff > 180
            else (180 - diff, f"That's 180 − {diff}. The difference of the bearings is already the gap when it's 180° or less."),
            ((a + b) // 2, f"That's the bearing halfway between {_pad3(lo)} and {_pad3(hi)}, a direction, not the gap. Subtract the bearings instead.")
            if (a + b) % 2 == 0 else None,
            (hi, f"That's just the bigger bearing, {_pad3(hi)}. The gap between two bearings is their difference."),
            (360 - hi, f"That's only the part from {_pad3(hi)} up to north. Add the {lo}° past north too.") if diff > 180 else None,
            (lo, f"That's only the part past north, {lo}°. Add the {360 - hi}° from {_pad3(hi)} up to north too.") if diff > 180
            else (lo, f"That's just the smaller bearing, {_pad3(lo)}. The gap between two bearings is their difference."),
            (ans // 2, "You halved the gap. That's how far each contact is from the direction halfway between them.") if ans % 2 == 0 else None,
        ]),
        solution=[
            f"Subtract the bearings: |{a} − {b}| = {diff}.",
            f"That is more than 180°, so the short way around is 360 − {diff} = {ans}°." if diff > 180
            else f"That is 180° or less, so it is already the smaller angle: {ans}°.",
        ],
        hint="Subtract the two bearings. If you get more than 180, take 360 minus that instead.",
        fig=_fig("compass", course=0,
                 rays=[{"deg": a, "label": _pad3(a), "c": "given", "mark": "target"},
                       {"deg": b, "label": _pad3(b), "c": "given", "mark": "target"}],
                 arcs=[{"from": lo, "to": hi, "label": "?", "c": "ask"} if diff <= 180
                       else {"from": hi, "to": lo + 360, "label": "?", "c": "ask"}]),
    )


@gen("ang", 1)
def triangle_angle_sum(ctx: Context) -> Problem:
    me, en = ctx.my_name, ctx.enemy_name
    A = ctx.rand(20, 90)
    Bv = ctx.rand(20, 150 - A)
    C = 180 - A - Bv
    e = _escort(ctx)
    return _problem(
        help="trisum",
        story=f"{me}, the escort {e} and {en} make a triangle on the plot. The angle at {me} is {A}° and the angle at the escort is {Bv}°.",
        expr=f"{A}° + {Bv}° + x = 180°",
        ask=f"What is the angle at {en}?",
        choices=_numeric_choices(ctx, C, [
            (180 - A, f"That's 180 − {A}: you forgot to take away the {Bv}° angle too."),
            (180 - Bv, f"That's 180 − {Bv}: you forgot to take away the {A}° angle too."),
            (360 - A - Bv, "You used 360°, but the three angles of a triangle add to 180°."),
            (A + Bv, f"That's {A} + {Bv}, the two angles you know. Now take that away from 180."),
            (C // 2, f"You split 180 − {A + Bv} in half. Halving is only for the two equal angles of an isosceles triangle.") if C % 2 == 0 else None,
            (90 - A - Bv, "You used 90°, but the three angles of a triangle add to 180°.") if A + Bv < 90 else None,
            (Bv, f"That's the angle at the escort, which you were given. The angle at {en} is what's left of 180°."),
            (A, f"That's the angle at {me}, which you were given. The angle at {en} is what's left of 180°."),
        ]),
        solution=["The three angles of any triangle add to 180°.", f"{A} + {Bv} = {A + Bv}.", f"180 − {A + Bv} = {C}°."],
        hint="Add the two angles you know, then take that away from 180.",
        fig=_fig("triangle", apex=120 if A > Bv else 180, angles=[_gv(f"{A}°"), _gv(f"{Bv}°"), _ak("?")],
                 marks=[{"kind": "you", "label": "you"}, {"kind": "escort", "label": "escort"}, {"kind": "target"}]),
    )


@gen("ang", 1)
def supplementary_complementary(ctx: Context) -> Problem:
    me, en = ctx.my_name, ctx.enemy_name
    t = ctx.pick([k * 5 for k in range(2, 18) if k != 9])  # not 45°: 90 − 45 would be the angle you were given
    v = ctx.pick([
        {"s": f"The forward turret is trained {t}° off the bow toward {en}. The bow and the stern lie on one straight line through the turret, 180° apart.",
         "ask": "What angle does the gun make with the stern?", "ans": 180 - t, "expr": f"{t}° + x = 180°", "kind": "a straight line (180°)",
         "fig": _fig("angle_split", t=t, total=180, given="h", names=["stern", "bow"], rayLabel="gun")},
        {"s": f"{me}'s gun barrel is elevated {t}° above the flat deck. The mast stands straight up, at 90° to the deck.",
         "ask": "What is the angle between the barrel and the mast?", "ans": 90 - t, "expr": f"{t}° + x = 90°", "kind": "a right angle (90°)",
         "fig": _fig("angle_split", t=t, total=90, given="h", names=["deck", "", "mast"], rayLabel="barrel")},
        {"s": f"{en}'s periscope is tilted {t}° away from straight up.",
         "ask": "What angle does the periscope make with the flat sea surface?", "ans": 90 - t, "expr": f"{t}° + x = 90°", "kind": "a right angle (90°)",
         "fig": _fig("angle_split", t=t, total=90, given="v", names=["sea surface", "", "straight up"], rayLabel="periscope")},
        {"s": f"The searchlight on {me} is swung {t}° to port of the bow. The bow and stern are 180° apart.",
         "ask": "What angle does the beam make with the stern?", "ans": 180 - t, "expr": f"{t}° + x = 180°", "kind": "a straight line (180°)",
         "fig": _fig("angle_split", t=t, total=180, given="h", names=["stern", "bow"], rayLabel="beam")},
    ])
    ans = v["ans"]
    total = 180 if ans == 180 - t else 90
    other = 270 - total  # the total people mix it up with
    return _problem(
        help="supp", story=v["s"], expr=v["expr"], ask=v["ask"],
        choices=_numeric_choices(ctx, ans, [
            (other - t, f"You used {other}°, but the two angles make {v['kind']}."),
            (t, f"That's the {t}° angle you were given. You want the rest of the {total}°."),
            (360 - t, f"You used 360°, a full turn. The two angles make {v['kind']}."),
            (total + t, f"That's {total} + {t}. The two angles together make {total}°, so take {t} away instead."),
            (total // 2, f"You split the {total}° evenly, but the two angles aren't equal. The other one is {total} − {t}."),
        ]),
        solution=[f"The two angles together make {v['kind']}.", f"So x = {180 if '180' in v['kind'] else 90} − {t} = {ans}°."],
        hint="Ask: do the two angles make a straight line (180°) or a right angle (90°)? Then subtract.",
        fig=v["fig"],
    )


@gen("ang", 1)
def course_change(ctx: Context) -> Problem:
    me = ctx.my_name
    side = ctx.pick(["starboard", "port"])
    stbd = side == "starboard"
    # Never 000° then starboard: the right answer would be the turn itself, measured from north.
    H = ctx.rand(1 if stbd else 0, 35) * 10
    # No 180° turn: port and starboard would land in the same place, so the side wouldn't matter.
    d = ctx.pick([10, 20, 30, 45, 60, 90, 120, 135, 150])
    ans = (H + d) % 360 if stbd else (H - d + 360) % 360
    wrong = (H - d + 360) % 360 if stbd else (H + d) % 360
    raw = H + d if stbd else H - d
    turn_way = "Starboard is a right turn, so add" if stbd else "Port is a left turn, so take away"
    choices = _string_choices(ctx, _pad3(ans), [
        (_pad3(wrong), f"You turned the wrong way. {turn_way} {d}°."),
        (f"{raw}°", f"That's {H} + {d} = {raw}, but courses stop at 359°. Take away 360.") if raw >= 360 else None,
        (f"−{-raw}°", f"That's {H} − {d} = −{-raw}. A course can't go below 000°, so add 360.") if raw < 0 else None,
        (_pad3(d - H), f"That's {d} − {H}: you swapped them to dodge a negative. Work out {H} − {d}, then add 360.") if raw < 0 else None,
        (f"{raw + 360}°", f"That's {H} − {d} + 360. Only add 360 when the answer drops below 000°.") if not stbd and raw >= 0 else None,
        (_pad3(raw - 180), f"That's {raw} − 180. When you pass 359°, take away 360, not 180.") if raw >= 360 else None,
        (_pad3(raw + 180), f"That's −{-raw} + 180. When you drop below 000°, add 360, not 180.") if raw < 0 else None,
        (f"−{360 - raw}°", f"That's {H} + {d} − 360. Only take away 360 when the answer reaches 360 or more.") if stbd and raw < 360 else None,
        (_pad3(d if stbd else -d), f"You turned {d}° from north (000°). Start from your course, {_pad3(H)}, instead."),
        (_pad3(d), f"That's just the size of the turn. Start from your course, {_pad3(H)}, and turn {d}° to port.") if not stbd else None,
        (_pad3(H + 90 if stbd else H - 90), f"You swung a full 90° to {side}. The order is to turn just {d}°.") if d != 90 else None,
        (_pad3(H + 180), f"That's the reverse course, {H} + 180. The order is a {d}° turn, not turning right around.") if d == 90 else None,
    ], lambda: _pad3(ans + ctx.pick([-90, -60, 60, 90])))  # filler: every course and turn has three mistakes without it
    if stbd and H + d >= 360:
        wrap = f"That is 360 or more, so subtract 360: {ans}."
    elif not stbd and H - d < 0:
        wrap = f"That is negative, so add 360: {ans}."
    else:
        wrap = "That is already between 000 and 359."
    return _problem(
        help="turn",
        story=f'"Helm, come {side} {d} degrees!" {me} is on course {_pad3(H)}. Starboard means turn right, clockwise around the compass; port means turn left.',
        expr=f"{_pad3(H)} {_pm(side)} {d}°",
        note="wrap around if you leave 000°–359°",
        ask="What is the new course?",
        choices=choices,
        solution=[
            f"{side.capitalize()} means {'add' if stbd else 'subtract'}: {H} {_pm(side)} {d} = {_signed(raw)}.",
            wrap,
            f"New course {_pad3(ans)}.",
        ],
        hint="Starboard adds, port subtracts. Fix the wrap-around at the end if you need to.",
        fig=_fig("compass", course=H,
                 rays=[{"deg": H, "label": f"course {_pad3(H)}", "dash": True, "c": "dim"},
                       {"deg": ans, "label": "new ?", "c": "ask"}],
                 arcs=[{"from": H if stbd else H - d, "to": H + d if stbd else H, "label": f"{d}° {side}", "c": "given"}]),
    )


@gen("ang", 2)
def turn_between_courses(ctx: Context) -> Problem:
    me = ctx.my_name
    across_north = ctx.rand(0, 2) > 0  # the case the note is about: the new course is the smaller number
    while True:  # not a new course of 000°: then the parts before and after north run into each other
        A = ctx.rand(0, 35) * 10
        d = ctx.pick([20, 30, 40, 50, 60, 70, 90, 110, 130, 150])
        Bc = (A + d) % 360
        if Bc and (Bc < A) == bool(across_north):
            break
    wrap = Bc < A
    return _problem(
        help="turn",
        story=f"{me} is on course {_pad3(A)}. The convoy commodore signals a new course of {_pad3(Bc)}.",
        expr=f"{_pad3(Bc)} − {_pad3(A)}",
        note="add 360 to the new course first if it is smaller",
        ask="How many degrees must she turn to starboard to get there?",
        choices=_numeric_choices(ctx, d, [
            (Bc - A, f"That's {Bc} − {A}, which is below zero. The new course is the smaller number, so add 360 to it first.") if wrap
            else (A - Bc, f"That's {A} − {Bc}: you took the new course away from the old one. The turn is new − old."),
            (360 - d, f"That's {A} − {Bc}: you took the new course away from the old one. Add 360 to {Bc} first, then take away {A}.")
            if wrap else (360 - d, f"That's the turn to port, the long way round. Starboard goes clockwise, from {_pad3(A)} up to {_pad3(Bc)}."),
            (d + 360, f"That's {Bc + 360} − {A}. Only add 360 when the new course is the smaller number.") if not wrap else None,
            (A + Bc, "You added the two courses. The turn is the new course − the old course."),
            (Bc, f"That's only the part of the turn past north (000°). Add the {360 - A}° from {_pad3(A)} up to north too.") if wrap
            else (Bc, f"That's the new course itself. The turn is how far it is from {_pad3(A)}: new − old."),
            (360 - A, f"That's only the turn from {_pad3(A)} up to north (360°). Add the {Bc}° past north too.") if wrap else None,
            (180 - d, f"That's 180 − {d}, the angle between the old track and the new one. The turn itself is new − old."),
        ], allow_neg=True),
        solution=[
            "Turning to starboard adds degrees, so find the difference going clockwise.",
            f"{Bc} is smaller than {A}, so add 360 first: {Bc + 360} − {A} = {d}°." if Bc < A else f"{Bc} − {A} = {d}°.",
        ],
        hint="Subtract the old course from the new one. If the new course is the smaller number, add 360 to it first.",
        fig=_fig("compass", course=A,
                 rays=[{"deg": A, "label": f"now {_pad3(A)}", "dash": True, "c": "dim"},
                       {"deg": Bc, "label": f"new {_pad3(Bc)}", "c": "given"}],
                 arcs=[{"from": A, "to": A + d, "label": "?", "c": "ask"}]),
    )


_POLY_NAMES = {3: "triangle", 4: "square", 5: "pentagon", 6: "hexagon", 8: "octagon", 10: "decagon", 12: "twelve-sided polygon"}


@gen("ang", 1)
def regular_polygon_angles(ctx: Context) -> Problem:
    me = ctx.my_name
    n = ctx.pick([3, 4, 5, 6, 8, 10, 12])
    ext = 360 / n
    int_ = (n - 2) * 180 / n
    mode = ctx.pick(["int", "ext"])
    if mode == "int":
        return _problem(
            help="poly",
            story=f"The anti-aircraft gun tub on {me}'s fantail is a regular {_POLY_NAMES[n]}: {n} equal sides and {n} equal corners.",
            expr=f"(n − 2) × 180° ÷ n, with n = {n}",
            ask="What is each interior angle (the angle inside each corner)?",
            choices=_numeric_choices(ctx, int_, [
                (ext, f"That's the exterior angle, 360 ÷ {n}, the turn at each corner. The inside angle is 180 − {_js(ext)}."),
                ((n - 2) * 180, f"That's the total of all {n} inside angles. Share it out: divide by {n}."),
                (180, f"You left out the − 2: {n} × 180 ÷ {n} is just 180. Use ({n} − 2) × 180 ÷ {n}."),
                ((n - 2) * 360 / n, f"You used 360 in the formula. It's ({n} − 2) × 180 ÷ {n}."),
                ((n - 1) * 180 / n, f"You took 1 away from {n} instead of 2. It's ({n} − 2) × 180 ÷ {n}."),
                ((n - 2) * 90 / n, f"You used 90 in the formula. It's ({n} − 2) × 180 ÷ {n}."),
                (180 / n, f"That's 180 ÷ {n}. The interior angle is 180 − 360 ÷ {n}, or ({n} − 2) × 180 ÷ {n}."),
                (360 - int_, f"That's 360 − {_js(int_)}, the angle outside the corner. The interior angle is the one inside the shape."),
            ]),
            solution=[
                f"({n} − 2) × 180 = {(n - 2) * 180}.",
                f"{(n - 2) * 180} ÷ {n} = {_js(int_)}°.",
                f"Check: the exterior angle is 360 ÷ {n} = {_js(ext)}, and 180 − {_js(ext)} = {_js(int_)} ✓",
            ],
            hint="Take two off the number of sides, multiply by 180, then divide by the number of sides.",
            fig=_fig("polygon", n=n, mode="int"),
        )
    return _problem(
        help="poly",
        story=f"The turret on {me} trains all the way around in {n} equal clicks — one click at each corner of a regular {_POLY_NAMES[n]}. Each click turns the turret through the polygon's exterior angle (the dashed line in the picture shows one side extended).",
        expr=f"360° ÷ {n}",
        ask="How many degrees is each click (the exterior angle)?",
        choices=_numeric_choices(ctx, ext, [
            (int_, f"That's the interior angle, the one inside the corner. Each click is the turn: 360 ÷ {n}."),
            (180 / n, "You shared out 180°, but going all the way round is a full turn, 360°."),
            (360 / (n - 2), f"You divided by {n} − 2. That's for the interior angle; here share 360° among the {n} corners."),
            (360 / (n + 2), f"You divided by {n} + 2. Share the 360° among the {n} corners: 360 ÷ {n}."),
            ((n - 2) * 180, f"That's the total of the interior angles. The clicks share out a full turn: 360 ÷ {n}."),
        ]),
        solution=["Going all the way around is 360°.", f"360 ÷ {n} = {_js(ext)}°."],
        hint=f"A full circle is 360°. Share it equally among the {n} corners.",
        fig=_fig("polygon", n=n, mode="ext"),
    )


@gen("ang", 1)
def isosceles_triangle(ctx: Context) -> Problem:
    me, en = ctx.my_name, ctx.enemy_name
    e = _escort(ctx)

    def marks() -> list[dict[str, str]]:
        return [{"kind": "you", "label": "you"}, {"kind": "escort", "label": "escort"}, {"kind": "target"}]

    if ctx.rand(0, 1):
        apex = ctx.rand(10, 70) * 2
        base = (180 - apex) / 2
        return _problem(
            help="isos",
            story=f"{en} is exactly the same distance from {me} as from the escort {e}, so the three ships make an isosceles triangle with its tip at {en}. The angle at the tip is {apex}°.",
            expr=f"{apex}° + x + x = 180°",
            ask="What is each of the two equal base angles?",
            choices=_numeric_choices(ctx, base, [
                (180 - apex, f"That's 180 − {apex}, what's left for both base angles together. Split it in half."),
                (apex, "That's the tip angle again. The base angles are the two equal ones at the bottom."),
                (180 - 2 * apex, f"You doubled the tip angle, as if it were one of the equal pair. Do (180 − {apex}) ÷ 2."),
                ((360 - apex) / 2, "You used 360°, but the three angles of a triangle add to 180°."),
                ((180 - apex) / 3, f"You split 180 − {apex} into three. Only the two base angles share it: divide by 2."),
                (apex / 2, f"You halved the tip angle. Halve what's left after you take {apex} from 180."),
                (60, "Only a triangle with three equal sides has three 60° angles. Here the tip is different: (180 − tip) ÷ 2."),
            ]),
            solution=[
                "The two base angles are equal because two sides are equal.",
                f"180 − {apex} = {180 - apex} is left for both of them.",
                f"{180 - apex} ÷ 2 = {_js(base)}° each.",
            ],
            hint="Take the tip angle away from 180, then split what's left in half.",
            fig=_fig("triangle", apex=150, angles=[_ak("?"), _ak("?"), _gv(f"{apex}°")], ticks=[False, True, True], marks=marks()),
        )
    base = ctx.pick([x for x in range(20, 81) if x != 60])  # 60° would make the tip 60° too, the angle you were given
    apex = 180 - 2 * base
    return _problem(
        help="isos",
        story=f"{me} and the escort {e} are both the same distance from {en}. The angle at {me} is {base}°, and the angle at the escort must match it.",
        expr=f"{base}° + {base}° + x = 180°",
        ask=f"What is the angle at the tip, at {en}?",
        choices=_numeric_choices(ctx, apex, [
            (180 - base, f"That's 180 − {base}: you only took away one base angle. There are two, so take away {base} twice."),
            (base, f"That's a base angle again. The tip is what's left: 180 − {base} − {base}."),
            ((180 - base) / 2, f"You halved 180 − {base}, as if {base}° were the tip. It's a base angle, and there are two of them."),
            (360 - 2 * base, "You used 360°, but the three angles of a triangle add to 180°."),
            (2 * base, f"That's {base} + {base}, the two base angles. Now take that away from 180."),
            (60, f"Only a triangle with three equal sides has three 60° angles. Here the tip is 180 − {base} − {base}."),
        ]),
        solution=[f"Both base angles are {base}°: {base} + {base} = {2 * base}.", f"180 − {2 * base} = {apex}°."],
        hint="Double the base angle, then subtract from 180.",
        fig=_fig("triangle", apex=150, angles=[_gv(f"{base}°"), _gv(f"{base}°"), _ak("?")], ticks=[False, True, True], marks=marks()),
    )


@gen("ang", 2)
def parallel_lines(ctx: Context) -> Problem:
    me = ctx.my_name
    t = ctx.rand(4, 16) * 5
    v = ([
        {"kind": "alt", "ask": 'The same leg crosses the second column. What is the alternate interior angle there (the "Z" shape)?', "ans": t, "why": "Alternate interior angles are equal."},
        {"kind": "corr", "ask": 'What is the corresponding angle where the leg crosses the second column (the "F" shape)?', "ans": t, "why": "Corresponding angles are equal."},
        {"kind": "coint", "ask": 'What is the co-interior angle at the second column (same side of the leg, between the two columns — the "C" shape)?', "ans": 180 - t, "why": "Co-interior angles add to 180°."},
    ][ctx.pick([0, 1, 2, 2])])  # the C shape half the time: it's the one that isn't "equal"
    ans = v["ans"]
    shape = {"alt": "Z", "corr": "F", "coint": "C"}[v["kind"]]
    if ans == t:
        pool = [
            (180 - t, f"You took {t} from 180, but a {shape} shape means the two angles are equal. Only the C shape adds to 180°."),
            (90 - t, f"You took {t} from 90, but there's no right angle here. A {shape} shape means the angles are equal."),
            (360 - t, f"You took {t} from 360. The two angles in a {shape} shape are simply equal."),
            (180 + t, f"That's 180 + {t}, the angle all the way round the outside. A {shape} shape means the two angles are equal."),
        ]
    else:
        pool = [
            (t, f"You kept it at {t}°, but that's for Z and F shapes. Co-interior angles (the C shape) add to 180°."),
            (90 - t, "You took it from 90. Co-interior angles (the C shape) add to 180°, not 90°."),
            (360 - t, "You took it from 360. Co-interior angles (the C shape) add to 180°."),
            (180 + t, f"That's 180 + {t}. Co-interior angles add to 180°, so take {t} away from 180."),
        ]
    return _problem(
        help="parallel",
        story=f"Two convoy columns steam on parallel tracks. {me} runs a zig-zag leg that cuts across the first column at {t}°, then carries on across the second column.",
        expr=f"two parallel lines, one crossing line, {t}°",
        ask=v["ask"],
        choices=_numeric_choices(ctx, ans, pool),
        solution=[v["why"], f"So the angle is {ans}°."],
        hint="Z and F shapes mean the angles are equal. A C shape means they add to 180.",
        fig=_fig("parallel", t=t, mode=v["kind"]),
    )


# ---------------- Plot · Triangles ----------------


@gen("tri", 1)
def pythagorean_range(ctx: Context) -> Problem:
    me, en = ctx.my_name, ctx.enemy_name
    a, b, c = _triple(ctx)
    return _problem(
        help="pyth",
        story=f"The radar plot puts {en} {a} nm east and {b} nm north of {me}. The gun director needs the straight-line range.",
        expr=f"{a}{sup(2)} + {b}{sup(2)} = r{sup(2)}",
        ask="What is the range in nautical miles?",
        choices=_numeric_choices(ctx, c, [
            (a + b, f"You added the two legs: {a} + {b}. Square them, add, then take the square root."),
            (c * c, f"That's {a}² + {b}² = {c * c}. You forgot the last step: take the square root."),
            (c * c / 2, f"You halved {c * c}. To undo the squaring, take the square root instead."),
            (abs(b - a), "You subtracted the legs. Square them, add, then take the square root."),
            (_jround(math.sqrt(abs(b * b - a * a))), f"You subtracted the squares: √({max(a, b) ** 2} − {min(a, b) ** 2}). For the longest side, add them."),
            (max(a, b), "That's just the longer leg. The range is the slanted side, which is longer than both legs."),
        ]),
        solution=[f"{a}² = {a * a} and {b}² = {b * b}.", f"{a * a} + {b * b} = {c * c}.", f"√{c * c} = {c} nm."],
        hint="Square both distances, add them, then find the square root.",
        fig=_fig("right_tri", ratio=b / a, adj=_gv(f"{a} nm east"), opp=_gv(f"{b} nm north"), hyp=_ak("range ?"), marks={"P": _you(), "Q": _tgt()}),
    )


@gen("tri", 1)
def pythagorean_leg(ctx: Context) -> Problem:
    me, en = ctx.my_name, ctx.enemy_name
    a, b, c = _triple(ctx)
    return _problem(
        help="pythleg",
        story=f"Range to {en} is {c} nm, and the plot shows she is {a} nm east of {me}.",
        expr=f"{a}{sup(2)} + n{sup(2)} = {c}{sup(2)}",
        ask="How far north of you is she?",
        choices=_numeric_choices(ctx, b, [
            (c - a, f"You subtracted the sides: {c} − {a}. Square them first, {c}² − {a}², then take the square root."),
            (_jround(math.sqrt(c * c + a * a)), f"You added the squares, but {c} nm is the longest side. Take {a}² away from {c}² instead."),
            (b * b, f"That's {c}² − {a}² = {b * b}. You forgot the last step: take the square root."),
            (b * b / 2, f"You halved {b * b}. To undo the squaring, take the square root instead."),
            (c + a, f"You added {c} and {a}. The range is the longest side: north² = {c}² − {a}²."),
            (a, f"That's the {a} nm east you were given. The question asks how far north she is."),
            (_jround(math.sqrt(c - a)), f"You took the square root of {c} − {a}. Square first, then subtract: √({c}² − {a}²).") if c - a > 3 else None,
        ]),
        solution=[f"{c}² = {c * c} and {a}² = {a * a}.", f"{c * c} − {a * a} = {b * b}.", f"√{b * b} = {b} nm."],
        hint="Square the range, subtract the square of the known leg, then square-root.",
        fig=_fig("right_tri", ratio=b / a, adj=_gv(f"{a} nm east"), opp=_ak("north ?"), hyp=_gv(f"range {c} nm"), marks={"P": _you(), "Q": _tgt()}),
    )


@gen("tri", 2)
def distance_formula(ctx: Context) -> Problem:
    me, en = ctx.my_name, ctx.enemy_name
    a, b, c = ctx.pick([t for t in TRIPLES if t[2] <= 20])
    x1 = ctx.rand(1, 9)
    down = ctx.rand(0, 1)
    y1 = ctx.rand(b + 1, b + 9) if down else ctx.rand(1, 9)
    x2 = x1 + a
    y2 = y1 - b if down else y1 + b
    dy = f"({_signed(y2 - y1)})" if y2 - y1 < 0 else str(y2 - y1)
    return _problem(
        help="dist",
        story=f"On the plotting grid {me} is at ({x1}, {y1}) and {en} is at ({x2}, {y2}). Each grid square is one nautical mile.",
        expr=f"√(({x2} − {x1}){sup(2)} + ({y2} − {y1}){sup(2)})",
        ask="How far apart are the two ships?",
        choices=_numeric_choices(ctx, c, [
            (a + b, f"You added Δx and Δy: {a} + {b}. Square them, add, then take the square root."),
            (c * c, f"That's {a}² + {b}² = {c * c}. You forgot the last step: take the square root."),
            (c * c / 2, f"You halved {c * c}. To undo the squaring, take the square root instead."),
            (abs(b - a), "You subtracted Δx and Δy. Square them, add, then take the square root."),
            (_jround(math.hypot(x1 + x2, y1 + y2)), "You added the x's and the y's. Subtract them to get Δx and Δy."),
            (_jround(math.sqrt(abs(b * b - a * a))), f"You subtracted the squares: √({max(a, b) ** 2} − {min(a, b) ** 2}). Add them instead."),
        ]),
        solution=[
            f"Δx = {x2} − {x1} = {x2 - x1}, Δy = {y2} − {y1} = {_signed(y2 - y1)}.",
            f"{x2 - x1}² + {dy}² = {a * a} + {b * b} = {c * c}.",
            f"√{c * c} = {c} nm.",
        ],
        hint="Find the change in x and the change in y, then use them as the two legs of a right triangle.",
        fig=_fig("grid", p1=[x1, y1], p2=[x2, y2], mode="dist"),
    )


@gen("tri", 2)
def chart_scale(ctx: Context) -> Problem:
    me, en = ctx.my_name, ctx.enemy_name
    k = ctx.pick([2, 4, 5, 8, 10])
    m = ctx.pick([1.5, 2, 2.5, 3, 3.5, 4, 6, 7.5])
    whole = _is_int(m)
    ms = _js(m)
    if ctx.rand(0, 1):
        ans = k * m
        ch = _numeric_choices(ctx, ans, [
            (m / k, f"You divided by the scale. Going from paper to sea, multiply: {ms} × {k}."),
            (m + k, f"You added {ms} and {k}. Every centimetre stands for {k} nm, so multiply."),
            (m, f"That's the length on paper, in cm. Multiply by {k} to get nautical miles."),
            (k, f"That's the scale, for 1 cm. The line is {ms} cm long, so multiply by {ms}."),
            (k * (m + 1), f"You counted the tick marks: a {ms} cm line has {_js(m + 1)} of them. Count the gaps between them.") if whole else None,
            (k * math.ceil(m), f"You rounded {ms} cm up to {math.ceil(m)} before multiplying. Use all {ms} cm.") if not whole else None,
            (k * math.floor(m), f"You dropped the half centimetre: {math.floor(m)} × {k}. Use all {ms} cm.") if not whole else None,
        ], dp="auto")
        return _problem(
            help="scale",
            story=f"The plotting sheet is drawn to scale: 1 cm on paper is {k} nm at sea. The line from {me} to {en} measures {ms} cm.",
            expr=f"{ms} cm × {k} nm per cm",
            ask="How far away is she, in nautical miles?",
            choices=ch,
            solution=[f"Every centimetre stands for {k} nm.", f"{ms} × {k} = {ch.texts[0]} nm."],
            hint="Multiply the paper length by the scale.",
            fig=_fig("scale_line", k=k, m=m, ask="nm"),
        )
    d = k * m
    ds = _js(d)
    rem = d % k if _is_int(d) else 0
    ch = _numeric_choices(ctx, m, [
        (d * k, f"You multiplied by the scale. Going from sea to paper, divide: {ds} ÷ {k}."),
        (d - k, f"You took {k} away from {ds}. Every {k} nm is 1 cm, so divide."),
        (d, f"That's the distance at sea, in nm. Divide by {k} to get centimetres on paper."),
        (k / d, f"You divided the wrong way round: {k} ÷ {ds}. Do {ds} ÷ {k}."),
        (math.floor(m), f"You dropped the remainder: {ds} ÷ {k} doesn't come out whole. Keep going past the decimal point.") if rem else None,
        (math.floor(m) + rem / 10, f"You wrote the remainder, {_js(rem)}, after the decimal point. It's {_js(rem)} out of {k}, which is {_js(rem / k)} of a cm.")
        if rem else None,
    ], dp="auto")
    return _problem(
        help="scale",
        story=f"The plotting sheet is drawn to scale: 1 cm on paper is {k} nm at sea. {en} is {ds} nm away.",
        expr=f"{ds} nm ÷ {k} nm per cm",
        ask="How many centimetres long should the line on the plot be?",
        choices=ch,
        solution=["Going from real distance to paper, divide by the scale.", f"{ds} ÷ {k} = {ch.texts[0]} cm."],
        hint="Real to paper means divide by the scale.",
        fig=_fig("scale_line", k=k, d=d, ask="cm"),
    )


@gen("tri", 2)
def similar_triangles(ctx: Context) -> Problem:
    a, b, c = ctx.pick([t for t in TRIPLES if t[2] <= 17])
    k = ctx.pick([2, 3, 4, 5])
    return _problem(
        help="scale",
        story=f"The plotting officer draws two similar triangles. The small one has sides {a}, {b} and {c} nm. The big one's shortest side is {a * k} nm.",
        expr=f"scale factor = {a * k} ÷ {a}",
        ask="What is the big triangle's longest side?",
        choices=_numeric_choices(ctx, c * k, [
            (c + (a * k - a), f"You added {a * k - a}, the gap between {a * k} and {a}. Similar shapes grow by multiplying: × {k}."),
            (b * k, f"That's {b} × {k}, the middle side scaled up. The longest side is {c} × {k}."),
            (c, f"That's the small triangle's longest side. Scale it up: × {k}."),
            (c + k, f"You added the scale factor, {k}. Multiply by it instead."),
            (c / k, "You divided by the scale factor. The big triangle is bigger, so multiply."),
            (c * a * k, f"You multiplied by {a * k}, the big side. Multiply by the scale factor, {a * k} ÷ {a} = {k}."),
            (c * k * k, f"You multiplied by {k} twice. Lengths grow by × {k} just once."),
        ]),
        solution=[f"Scale factor = {a * k} ÷ {a} = {k}.", f"Every side gets multiplied by {k}: {c} × {k} = {c * k} nm."],
        hint="Find how many times bigger the big triangle is, then multiply the longest side by that.",
        fig=_fig("similar", a=a, b=b, c=c, k=k),
    )


@gen("tri", 1)
def diagonal_45_45_90(ctx: Context) -> Problem:
    me, en = ctx.my_name, ctx.enemy_name
    s = ctx.pick([3, 4, 5, 6, 7, 8, 10, 12, 15, 20])
    v = ctx.pick([
        {"story": f"{en} is exactly 45° off {me}'s starboard bow, so she is just as far ahead as she is to the side: {s} nm each way. That's a 45-45-90 triangle.",
         "ask": "What is the range?", "hyp": "range ?", "marks": {"P": _you(), "Q": _tgt()}},
        {"story": f"{me} patrols a square box {s} nm on each side. The captain wants to cut straight across from one corner to the opposite corner.",
         "ask": "How long is the diagonal?", "hyp": "diagonal ?", "marks": {"P": _you()}},
    ])
    return _problem(
        help="sqdiag", story=v["story"],
        expr="hypotenuse = leg × √2",
        ask=v["ask"],
        choices=_string_choices(ctx, f"{s}√2 nm", [
            (f"{2 * s} nm", f"You added the two legs: {s} + {s}. The long side is a leg × √2."),
            (f"{s}√3 nm", "√3 is for the 30-60-90 triangle. With two 45° angles the long side is a leg × √2."),
            (f"{s * s} nm", f"That's {s} × {s}. The long side is {s} × √2, not {s} × {s}."),
            (f"{2 * s}√2 nm", f"You doubled it. One leg × √2 is enough: {s} × √2."),
            (f"{s} nm", "That's the length of a leg. The long side is longer: a leg × √2."),
            (f"{2 * s * s} nm", f"That's {s}² + {s}² = {2 * s * s}. Take the square root: √{2 * s * s} = {s}√2."),
            (f"{s // 2}√2 nm", f"That's {s} ÷ √2. The long side is longer than a leg, so multiply by √2.") if s % 2 == 0 else None,
            (f"{math.isqrt(2 * s)} nm" if math.isqrt(2 * s) ** 2 == 2 * s else f"√{2 * s} nm",
             f"That's √({s} + {s}). Square the legs before you add them: √({s}² + {s}²)."),
        ]),
        solution=[f"Both legs are {s} nm.", f"Hypotenuse = {s} × √2 = {s}√2 nm (about {_js(_round1(s * 1.414))} nm)."],
        hint="In a 45-45-90 triangle the long side is a leg times √2.",
        fig=_fig("right_tri", ratio=1, adj=_gv(f"{s} nm"), opp=_gv(f"{s} nm"), hyp=_ak(v["hyp"]), ang=_lab("45°"), ang2=_lab("45°"), marks=v["marks"]),
    )


@gen("tri", 1)
def midpoint(ctx: Context) -> Problem:
    me = ctx.my_name
    x1 = ctx.rand(0, 12)
    y1 = ctx.rand(0, 12)
    x2 = x1 + 2 * ctx.rand(1, 8)
    y2 = y1 + 2 * ctx.rand(1, 8)
    mx = (x1 + x2) // 2  # always whole: x2 - x1 is even
    my = (y1 + y2) // 2
    e1 = _escort(ctx)
    e2 = _other_escort(ctx, e1)
    return _problem(
        help="mid",
        story=f"Escort {e1} is at ({x1}, {y1}) and escort {e2} is at ({x2}, {y2}) on the plot. Orders: station {me} exactly halfway between them.",
        expr="((x₁ + x₂) ÷ 2, (y₁ + y₂) ÷ 2)",
        ask="Where does she go?",
        choices=_string_choices(ctx, f"({mx}, {my})", [
            (f"({x1 + x2}, {y1 + y2})", f"You added the coordinates but didn't halve them. Halfway is the average: ({x1} + {x2}) ÷ 2."),
            (f"({x2 - x1}, {y2 - y1})", "You subtracted the coordinates. That's how far apart they are, not the point halfway. Add and halve."),
            (f"({(x2 - x1) // 2}, {(y2 - y1) // 2})", f"That's half the gap between them. Add it to {e1}'s position to land halfway."),
            (f"({my}, {mx})", "You swapped x and y. The x-coordinate comes first."),
            (f"({(x1 + y1) // 2}, {(x2 + y2) // 2})", "You averaged each escort's own x and y. Average the two x's together, then the two y's.")
            if (x1 + y1) % 2 == 0 and (x2 + y2) % 2 == 0 else None,
            (f"({mx}, {y1 + y2})", f"You halved the x's but not the y's. The y is ({y1} + {y2}) ÷ 2 too."),
            (f"({x1 + x2}, {my})", f"You halved the y's but not the x's. The x is ({x1} + {x2}) ÷ 2 too."),
        ]),
        solution=[f"x: ({x1} + {x2}) ÷ 2 = {mx}.", f"y: ({y1} + {y2}) ÷ 2 = {my}.", f"Station: ({mx}, {my})."],
        hint="Average the two x's, then average the two y's.",
        fig=_fig("grid", p1=[x1, y1], p2=[x2, y2], mode="mid"),
    )


@gen("tri", 2)
def triangle_30_60_90(ctx: Context) -> Problem:
    en = ctx.enemy_name
    s = ctx.rand(2, 12)
    marks = {"P": _you(), "Q": _tgt()}
    if ctx.rand(0, 1):
        return _problem(
            help="tri30",
            story=f"{en} is 30° off the bow at a range of {2 * s} nm. In a 30-60-90 triangle the side across from the 30° angle is exactly half the hypotenuse.",
            expr="short leg = hypotenuse ÷ 2",
            ask="How far is she off your track (the side across from the 30° angle)?",
            choices=_numeric_choices(ctx, s, [
                (4 * s, f"You doubled the range. The side across from 30° is half of it: {2 * s} ÷ 2."),
                (_jround(s * 1.73), "That's about the side across from the 60° angle (short side × √3). Across from 30° is the short one."),
                (2 * s, "That's the range, the longest side. The side across from 30° is half of it."),
                (2 * s // 3, "Sides don't grow in step with the angles (30:60:90 isn't 1:2:3). Across from 30° is half the range.")
                if s % 3 == 0 else None,
                (2 * s * 3 // 10, "You used 0.3 for the 30°. The side across from 30° is exactly half the range.") if s % 5 == 0 else None,
            ]),
            solution=[f"The hypotenuse is the range, {2 * s} nm.", f"Across from 30° is half of that: {2 * s} ÷ 2 = {s} nm."],
            hint="Halve the range.",
            fig=_fig("right_tri", deg=30, hyp=_gv(f"range {2 * s} nm"), opp=_ak("?"), adj=_lab("your track", "dim"), ang=_lab("30°"), ang2=_lab("60°"), marks=marks),
        )
    return _problem(
        help="tri30",
        story=f"{en} is 30° off the bow and {s} nm off your track, the side across from the 30° angle. In a 30-60-90 triangle that side is exactly half the hypotenuse.",
        expr="hypotenuse = short leg × 2",
        ask="What is the range to her (the hypotenuse)?",
        choices=_numeric_choices(ctx, 2 * s, [
            (s / 2, f"You halved it. The range is the longest side, so double the {s} nm."),
            (s, "That's the side across from 30°, which you were given. The range is twice as long."),
            (_jround(s * 1.73), "That's about the side along your track (short side × √3). The range is the longest side: short side × 2."),
            (_jround(s * 1.41), "That's the 45-45-90 rule (× √2). With a 30° angle the range is the short side × 2."),
            (3 * s, "Sides don't grow in step with the angles (30:60:90 isn't 1:2:3). The range is twice the short side."),
        ]),
        solution=["The side across from 30° is half the hypotenuse, so the hypotenuse is twice that side.", f"{s} × 2 = {2 * s} nm."],
        hint="Double the short side.",
        fig=_fig("right_tri", deg=30, opp=_gv(f"{s} nm"), hyp=_ak("range ?"), adj=_lab("your track", "dim"), ang=_lab("30°"), ang2=_lab("60°"), marks=marks),
    )


@gen("tri", 2)
def patrol_perimeter(ctx: Context) -> Problem:
    me = ctx.my_name
    a, b, c = _triple(ctx)
    return _problem(
        help="perim",
        story=f"{me} runs a triangular patrol: {a} nm on the first leg, {b} nm on the second, then {c} nm straight back to the start.",
        expr=f"{a} + {b} + {c}",
        ask="How many nautical miles is the whole circuit?",
        choices=_numeric_choices(ctx, a + b + c, [
            (a + b, f"That's only the first two legs. Add the {c} nm back to the start too."),
            (b + c, f"You left out the first leg, {a} nm. Add all three legs."),
            (a + c, f"You left out the second leg, {b} nm. Add all three legs."),
            (a * b, f"You multiplied {a} × {b}. The distance round is all three legs added."),
            (a * b / 2, f"That's the area inside the patrol, ½ × {a} × {b}. The circuit is the distance round: add the legs."),
            (2 * (a + b), f"You doubled {a} + {b}, like a rectangle's perimeter. A triangle has just three sides."),
        ]),
        solution=["Perimeter is all the sides added together.", f"{a} + {b} + {c} = {a + b + c} nm."],
        hint="Add the three legs.",
        fig=_fig("triangle", apex=60, sides=[_gv(f"{a} nm"), _gv(f"{c} nm"), _gv(f"{b} nm")], marks=[{"kind": "you", "label": "start"}]),
    )


# ---------------- Gunnery · Trig ----------------

_TRIG_DEFS = {"sin": "opposite ÷ hypotenuse", "cos": "adjacent ÷ hypotenuse", "tan": "opposite ÷ adjacent"}
# Where an angle is asked, the triangle is drawn the same shape every time: drawn true, the angle
# could be judged by eye (37° or 53°?) without working anything out.
_NOT_TO_SCALE = "not to scale"


def _exact(fn: str, deg: float) -> float:
    """What a calculator gives for sin/cos/tan of ``deg`` degrees (the problems use the trig table instead)."""
    return {"sin": math.sin, "cos": math.cos, "tan": math.tan}[fn](math.radians(deg))


@gen("trig", 1)
def trig_find_side(ctx: Context) -> Problem:
    me, en = ctx.my_name, ctx.enemy_name
    th = ctx.pick(TRIG_ANGLES)
    R = ctx.pick([10, 12, 15, 18, 20, 24, 25, 30, 36, 40])
    A = ctx.pick([10, 12, 15, 20, 25, 30, 40, 50])
    h = ctx.pick([20, 25, 30, 40, 50])
    marks = {"P": _you(), "Q": _tgt()}
    angL = _lab(f"{th}°")
    S, C, T = _sin(th), _cos(th), _tan(th)
    up = "The side you want is on top of the ratio, so multiply."
    pct = th / 100

    def digits(fn: str, val: float) -> str:
        return f"You used {_js(pct)} for {fn} {th}°, but the angle isn't the ratio. The trig table gives {_js(val)}."

    def by_angle(g: int, fn: str, val: float) -> Mistake:
        return (_round1(g / th), f"You divided by the angle itself, {th}. Use {fn} {th}° from the trig table, {_js(val)}, instead.")

    def hyp_pool(g: int, fn: str, what: str) -> list[Mistake]:
        """Mistakes when the hypotenuse ``g`` is given and the side ``fn`` × g is wanted."""
        other, oval = ("cos", C) if fn == "sin" else ("sin", S)
        side = "opposite" if fn == "sin" else "next to"
        return [
            (_round1(g * oval), f"You used {other}, but the side you want is {side} the {th}° angle, so it's {fn}."),
            (_round1(g * T), f"You used tan. The {what} is the hypotenuse, so the ratio is {fn}: {_TRIG_DEFS[fn]}."),
            (_round1(g / (S if fn == "sin" else C)), f"You divided by {fn} {th}°. {up}"),
            (_round1(g / T), f"You divided by tan {th}°. The {what} is the hypotenuse, so multiply it by {fn} {th}°."),
            (g, f"That's the {what} itself. Multiply it by {fn} {th}° to get the side you want."),
            (_round1(g * pct), digits(fn, S if fn == "sin" else C)),
            by_angle(g, fn, S if fn == "sin" else C),
        ]

    v = ctx.pick([
        {"fn": "sin", "val": S, "given": R, "ans": _round1(R * S), "unit": "nm", "op": "×",
         "story": f"{en} bears {th}° off the bow at a range of {R} nm. The range is the hypotenuse; how far she sits off your track is the side opposite the {th}° angle.",
         "ask": "How far is she off your track (cross-range), in nm?", "wrong": hyp_pool(R, "sin", "range"),
         "fig": _fig("right_tri", deg=th, hyp=_gv(f"hyp {R} nm"), opp=_ak("opp ?"), adj=_lab("your track (adj)", "dim"), ang=angL, marks=marks)},
        {"fn": "cos", "val": C, "given": R, "ans": _round1(R * C), "unit": "nm", "op": "×",
         "story": f"{en} bears {th}° off the bow at a range of {R} nm. The range is the hypotenuse; how far ahead she is along your track is the side adjacent to the {th}° angle.",
         "ask": "How far ahead along your track is she, in nm?", "wrong": hyp_pool(R, "cos", "range"),
         "fig": _fig("right_tri", deg=th, hyp=_gv(f"hyp {R} nm"), adj=_ak("adj ?"), opp=_lab("opp", "dim"), ang=angL, marks=marks)},
        {"fn": "tan", "val": T, "given": A, "ans": _round1(A * T), "unit": "nm", "op": "×",
         "story": f"{en} is {th}° off the bow and {A} nm ahead of {me} along your track (the side adjacent to the angle). You want the side opposite the angle.",
         "ask": "How far off your track is she, in nm?",
         "wrong": [
             (_round1(A * S), f"You used sin. You know the side next to the angle, not the hypotenuse, so use tan: {_TRIG_DEFS['tan']}."),
             (_round1(A * C), "You used cos. You know the side next to the angle and want the side opposite, so use tan."),
             (_round1(A / T), f"You divided by tan {th}°. {up}"),
             (A, f"That's the distance ahead that you were given. Multiply it by tan {th}° to get the side opposite."),
             (_round1(A / C), "That's the straight-line range (adjacent ÷ cos). You want the side opposite: adjacent × tan."),
             (_round1(A * pct), digits("tan", T)),
             by_angle(A, "tan", T),
         ],
         "fig": _fig("right_tri", deg=th, adj=_gv(f"adj {A} nm"), opp=_ak("opp ?"), hyp=_lab("hyp", "dim"), ang=angL, marks=marks)},
        {"fn": "sin", "val": S, "given": R, "ans": _round1(R * S), "unit": "km", "op": "×",
         "story": f"A lookout on {me} spots a patrol plane {th}° above the horizon at a slant range of {R} km. The slant range is the hypotenuse; the plane's height is the side opposite the angle.",
         "ask": "How high is the plane flying, in km?", "wrong": hyp_pool(R, "sin", "slant range"),
         "fig": _fig("right_tri", deg=th, hyp=_gv(f"slant {R} km"), opp=_ak("height ?"), adj=_lab("horizon (adj)", "dim"), ang=angL,
                     marks={"P": _you(), "Q": {"kind": "plane", "dx": 16, "dy": -12}})},
        {"fn": "tan", "val": T, "given": h, "ans": _round1(h / T), "unit": "m", "op": "÷",
         "story": f"From the crow's nest {h} m above the sea, the lookout on {me} spots {en}'s periscope at an angle of depression of {th}°. The height is the side opposite that angle; the horizontal distance is adjacent, on the bottom of the tan ratio.",
         "ask": "How far away is the periscope horizontally, in metres?",
         "wrong": [
             (_round1(h * T), f"You multiplied by tan {th}°. The distance is on the bottom of the ratio, so divide: {h} ÷ {_js(T)}."),
             (_round1(h / S), "You used sin. That gives the line of sight (the slanted side), not the distance across the sea."),
             (_round1(h / C), "You used cos. The height is opposite the angle and the distance is next to it, so use tan."),
             (h, f"That's the height of the crow's nest. The distance across the sea is {h} ÷ tan {th}°."),
             (_round1(h * C), f"You multiplied by cos {th}°. The height is opposite the angle and the distance next to it, so divide by tan."),
             (_round1(h / pct), digits("tan", T)),
             by_angle(h, "tan", T),
         ],
         "fig": _fig("right_tri", orient="mast", deg=th, opp=_gv(f"mast {h} m"), adj=_ak("distance ?"), hyp=_lab("line of sight", "dim"), ang=angL,
                     marks={"R": {"kind": "you", "dx": -16, "dy": 12}, "Q": {"kind": "target", "dx": 12, "dy": 10}})},
    ])
    fn, val, given, ans, unit, op = v["fn"], _js(v["val"]), v["given"], v["ans"], v["unit"], v["op"]
    exact = given * _exact(fn, th) if op == "×" else given / _exact(fn, th)
    ch = _numeric_choices(ctx, ans, v["wrong"], dp="auto", avoid=[exact])
    if fn == "tan":
        known = "opposite side" if op == "÷" else "adjacent side"
    else:
        known = "hypotenuse"
    want = "opposite" if fn == "sin" else "adjacent" if fn == "cos" else "adjacent" if op == "÷" else "opposite"
    return _problem(
        help="trigside",
        story=v["story"],
        expr=f"x = {given} {op} {fn} {th}°",
        note=f"{fn} {th}° ≈ {val}",
        ask=v["ask"],
        choices=ch,
        solution=[
            f"{fn} = {_TRIG_DEFS[fn]}, so {fn} {th}° = {'x ÷ ' + str(given) if op == '×' else str(given) + ' ÷ x'}.",
            f"From the trig table, {fn} {th}° ≈ {val}.",
            f"x = {given} {op} {val} = {ch.texts[0]} {unit}.",
        ],
        hint=f"You know the {known} and want the {want} side, so use {fn}. Look up {fn} {th}° in the trig table, then {'multiply' if op == '×' else 'divide'}.",
        fig=v["fig"],
    )


_SIDE_NAMES = {"opp": "opposite side", "adj": "adjacent side", "hyp": "hypotenuse"}
_RATIO_SIDES = {"sin": ("opp", "hyp"), "cos": ("adj", "hyp"), "tan": ("opp", "adj")}
# Triples drawn as a right triangle at roughly their real shape (the figure clamps opp ÷ adj to 0.3..2.2).
_RATIO_TRIPLES = tuple(t for t in TRIPLES if 0.4 <= t[0] / t[1] <= 2.5)


@gen("trig", 1)
def trig_ratio(ctx: Context) -> Problem:
    """sin, cos or tan of θ as a fraction of two sides. Which side is opposite depends on where θ is."""
    me, en = ctx.my_name, ctx.enemy_name
    off, along, rng = ctx.pick(_RATIO_TRIPLES)  # off your track (R–Q), along it (P–R), the range (P–Q)
    if ctx.rand(0, 1):
        off, along = along, off
    fn = ctx.pick(["sin", "cos", "tan"])
    at_target = ctx.rand(0, 2) == 0  # θ at the target: then your track is the side opposite it
    sides = {"opp": along, "adj": off, "hyp": rng} if at_target else {"opp": off, "adj": along, "hyp": rng}
    top, bottom = _RATIO_SIDES[fn]

    def frac(pair: tuple[str, str], seen: dict[str, int] = sides) -> str:
        return f"{seen[pair[0]]}/{seen[pair[1]]}"

    ans = frac((top, bottom))
    wrong: list[Mistake] = []
    if at_target:  # first, so this reason is kept: the same fraction is also another ratio's
        from_you = {"opp": off, "adj": along, "hyp": rng}
        wrong.append((frac((top, bottom), from_you),
                      f"Those are the sides seen from {me}. θ is at {en}, and from there the side opposite is your track, {along} nm."))
    wrong += [
        (frac(pair), f"That's {other} θ, {_TRIG_DEFS[other]}. {fn} θ is {_TRIG_DEFS[fn]}.")
        for other, pair in _RATIO_SIDES.items() if other != fn
    ]
    wrong.append((frac((bottom, top)), f"Upside down: {fn} θ is {_TRIG_DEFS[fn]}, so the {_SIDE_NAMES[bottom]} goes on the bottom."))
    for pair in itertools.permutations(sides, 2):  # the other ratios upside down
        if pair not in _RATIO_SIDES.values() and pair != (bottom, top):
            wrong.append((frac(pair), f"That's the {_SIDE_NAMES[pair[0]]} ÷ the {_SIDE_NAMES[pair[1]]}. {fn} θ is {_TRIG_DEFS[fn]}."))
    if at_target:
        where = f"θ is the angle at {en}, between the line to {me} and the shortest line across to your track."
        sides_line = f"θ is at {en}, so the side opposite it is your track, {along} nm; the side next to it is {off} nm, and the hypotenuse {rng} nm."
    else:
        where = f"θ is the angle at {me}, between your track and the line to {en}."
        sides_line = f"From θ, the side opposite is {off} nm (off your track), the side next to it {along} nm (your track), and the hypotenuse {rng} nm."
    theta = {"ang2": _ak("θ")} if at_target else {"ang": _ak("θ")}
    return _problem(
        help="trigratio",
        story=f"{en} is {off} nm off your track and {along} nm ahead along it: {rng} nm away in a straight line. {where}",
        expr=f"{fn} θ = ? ÷ ?",
        ask=f"What is {fn} θ?",
        choices=_string_choices(ctx, ans, wrong),
        solution=[sides_line, f"{fn} θ = {_TRIG_DEFS[fn]} = {ans}."],
        hint=f"No trig table needed: from θ, find the {_SIDE_NAMES[top]} and the {_SIDE_NAMES[bottom]}, then write one over the other.",
        fig=_fig("right_tri", ratio=off / along, adj=_gv(f"{along} nm"), opp=_gv(f"{off} nm"), hyp=_gv(f"{rng} nm"),
                 marks={"P": _you(), "Q": _tgt()}, **theta),
    )


# (side you know, side you want, the ratio with both, and whether x is on top of it (×) or underneath (÷))
_TRIG_SETUPS = (
    ("hyp", "opp", "sin", "×"), ("hyp", "adj", "cos", "×"), ("adj", "opp", "tan", "×"),
    ("opp", "adj", "tan", "÷"), ("opp", "hyp", "sin", "÷"), ("adj", "hyp", "cos", "÷"),
)


@gen("trig", 1)
def trig_which_ratio(ctx: Context) -> Problem:
    """Which equation finds the side: the ratio that has the side you know and the side you want, then × or ÷."""
    en = ctx.enemy_name
    known, want, fn, op = ctx.pick(_TRIG_SETUPS)
    th = ctx.pick([a for a in TRIG_ANGLES if a != 45])  # at 45° sin and cos are the same, so two choices would be right
    g = ctx.pick([8, 10, 12, 15, 20, 24, 25, 30, 40])
    given = {"opp": f"{g} nm off your track", "adj": f"{g} nm ahead along your track", "hyp": f"at a range of {g} nm"}[known]
    asked = {"opp": "how far she is off your track", "adj": "how far ahead along your track she is", "hyp": "her range in a straight line"}[want]

    def eq(f: str, o: str) -> str:
        return f"x = {g} {o} {f} {th}°"

    ans = eq(fn, op)
    on_top = op == "×"
    wrong: list[Mistake] = [
        (eq(fn, "÷" if on_top else "×"),
         f"x, the {_SIDE_NAMES[want]}, is on {'top' if on_top else 'the bottom'} of {fn} = {_TRIG_DEFS[fn]}, "
         f"so {'multiply' if on_top else 'divide'}.")
    ]
    for other in ("sin", "cos", "tan"):
        if other != fn:
            for o in ("×", "÷"):
                wrong.append((eq(other, o), f"{other} is {_TRIG_DEFS[other]}, but you know the {_SIDE_NAMES[known]} and want the "
                                            f"{_SIDE_NAMES[want]}: the ratio with both is {fn}."))
    labels = {known: _gv(f"{g} nm"), want: _ak("x")}
    third = next(s for s in ("opp", "adj", "hyp") if s not in labels)
    labels[third] = _lab({"opp": "off track", "adj": "track", "hyp": "range"}[third], "dim")
    return _problem(
        help="trigsetup",
        story=f"{en} bears {th}° off the bow, {given}. You want x, {asked}.",
        expr=f"θ = {th}°,  {_SIDE_NAMES[known]} = {g} nm,  {_SIDE_NAMES[want]} = x",
        ask="Which equation gives x?",
        choices=_string_choices(ctx, ans, wrong),
        solution=[
            f"From the {th}° angle, you know the {_SIDE_NAMES[known]} and want the {_SIDE_NAMES[want]}.",
            f"The ratio with both of them is {fn} = {_TRIG_DEFS[fn]}.",
            f"x is on {'top' if on_top else 'the bottom'}, so {'multiply' if on_top else 'divide'}: {ans}.",
        ],
        hint="Label the sides from the angle, pick the ratio that has the side you know and the side you want, then decide: "
             "multiply or divide? No trig table needed until you work it out.",
        fig=_fig("right_tri", deg=th, ang=_lab(f"{th}°"), marks={"P": _you(), "Q": _tgt()}, **labels),
    )


def _nearest_angle(fn: str, x: float) -> int:
    """The table angle whose ``fn`` value is closest to ``x``."""
    col = _TRIG_COL[fn]
    return min(TRIG_ANGLES, key=lambda a: abs(TRIG[a][col] - x))


_TRIG_COL = {"sin": 0, "cos": 1, "tan": 2}


def _angle_mistakes(fn: str, r: float, top: str, bottom: str, flip: str) -> list[Mistake]:
    """Wrong angles for "find θ from the ratio ``r`` = top ÷ bottom in the ``fn`` column".

    ``flip`` says what dividing the wrong way round looks like ("20 ÷ 15").
    """
    rs = _js(r)
    out: list[Mistake] = []
    for other in ("sin", "cos", "tan"):
        if other != fn:
            out.append((f"{_nearest_angle(other, r)}°",
                        f"You looked in the {other} column. The {top} and the {bottom} go with {fn}, so use the {fn} column."))
    if fn == "tan":
        out.append((f"{_nearest_angle('tan', 1 / r)}°", f"You divided {flip}, upside down. tan θ = {top} ÷ {bottom}."))
    if r < 1 and _is_int(round(r * 100, 6)):
        out.append((f"{round(r * 100)}°", f"{rs} is the ratio, not the angle. Find {rs} in the {fn} column and read the angle beside it."))
    if r >= 1:
        out.append((f"{rs}°", f"{rs} is the ratio, not the angle. Find {rs} in the {fn} column and read the angle beside it."))
    if r < 1:
        out.append((f"{_jround(r * 90)}°", f"The angle doesn't grow in step with the ratio, so it isn't {rs} × 90°. Look {rs} up in the {fn} column."))
    if fn == "tan" and r == 1:
        out.append(("60°", "Two equal sides don't make 60° here (that's for a triangle with three equal sides). Find 1 in the tan column."))
    return out


@gen("trig", 2)
def trig_find_angle(ctx: Context) -> Problem:
    en = ctx.enemy_name
    k = ctx.pick([2, 3, 4, 5, 6])
    c = ctx.pick([
        {"th": 30, "fn": "sin", "a": k, "b": 2 * k, "r": 0.5, "lab": ("opposite", "hypotenuse")},
        {"th": 37, "fn": "sin", "a": 3 * k, "b": 5 * k, "r": 0.6, "lab": ("opposite", "hypotenuse")},
        {"th": 53, "fn": "sin", "a": 4 * k, "b": 5 * k, "r": 0.8, "lab": ("opposite", "hypotenuse")},
        {"th": 60, "fn": "cos", "a": k, "b": 2 * k, "r": 0.5, "lab": ("adjacent", "hypotenuse")},
        {"th": 37, "fn": "cos", "a": 4 * k, "b": 5 * k, "r": 0.8, "lab": ("adjacent", "hypotenuse")},
        {"th": 53, "fn": "cos", "a": 3 * k, "b": 5 * k, "r": 0.6, "lab": ("adjacent", "hypotenuse")},
        {"th": 45, "fn": "tan", "a": k, "b": k, "r": 1, "lab": ("opposite", "adjacent")},
        {"th": 37, "fn": "tan", "a": 3 * k, "b": 4 * k, "r": 0.75, "lab": ("opposite", "adjacent")},
        {"th": 53, "fn": "tan", "a": 4 * k, "b": 3 * k, "r": 1.33, "lab": ("opposite", "adjacent")},
    ])
    th, fn, a, b, r, lab = c["th"], c["fn"], c["a"], c["b"], _js(c["r"]), c["lab"]
    elev = fn == "tan" and bool(ctx.rand(0, 1))
    if fn == "sin":
        story = f"{en} is {a} nm off your track (the side opposite the angle at your ship) and {b} nm away in a straight line (the hypotenuse). The turrets need the angle off the bow."
    elif fn == "cos":
        story = f"{en} is {a} nm ahead along your track (the side adjacent to the angle at your ship) and {b} nm away in a straight line (the hypotenuse)."
    elif elev:
        story = f"To drop a shell onto {en} behind a headland, the shell must climb {a} m (opposite) over a horizontal run of {b} m (adjacent). The gun captain needs the elevation angle."
    else:
        story = f"{en} is {a} nm off your track (opposite) and {b} nm ahead along your track (adjacent)."
    u = "m" if elev else "nm"
    angL = _ak("θ = ?")
    marks = {"P": _you(), "Q": _tgt()}
    if fn == "sin":
        fg = _fig("right_tri", ratio=1, note=_NOT_TO_SCALE, opp=_gv(f"opp {a} {u}"), hyp=_gv(f"hyp {b} {u}"), ang=angL, marks=marks)
    elif fn == "cos":
        fg = _fig("right_tri", ratio=1, note=_NOT_TO_SCALE, adj=_gv(f"adj {a} {u}"), hyp=_gv(f"hyp {b} {u}"), ang=angL, marks=marks)
    else:
        fg = _fig("right_tri", ratio=1, note=_NOT_TO_SCALE, opp=_gv(f"opp {a} {u}"), adj=_gv(f"adj {b} {u}"), ang=angL,
                  marks={"P": _you(label="gun")} if elev else marks)
    return _problem(
        help="trigangle",
        story=story,
        expr=f"{fn} θ = {lab[0]} ÷ {lab[1]} = {a} ÷ {b} = {r}",
        ask="What is the angle θ? (Look the ratio up in the trig table.)",
        choices=_string_choices(ctx, f"{th}°", _angle_mistakes(fn, c["r"], lab[0], lab[1], f"{b} ÷ {a}")),
        solution=[f"{lab[0]} and {lab[1]} → use {fn}.", f"{a} ÷ {b} = {r}.", f"In the {fn} column of the trig table, {r} is {th}°."],
        hint=f"Divide, then find {r} in the {fn} column of the trig table.",
        fig=fg,
    )


@gen("trig", 2)
def stadimeter_range(ctx: Context) -> Problem:
    en = ctx.enemy_name
    H = _enemy_mast(ctx)
    th = ctx.pick([1, 2, 3, 4, 5])
    t = SMALL_TAN[th]
    ans = _jround(H / t)
    return _problem(
        help="stadimeter",
        story=f"Time for the stadimeter. The recognition manual lists {en}'s mast height as {H} m. In the rangefinder the mast fills an angle of just {th}°. Range = height ÷ tan(angle).",
        expr=f"range = {H} ÷ tan {th}°",
        note=f"tan {th}° ≈ {_js(t)}",
        ask="What is the range in metres? (Round to the nearest metre.)",
        choices=_numeric_choices(ctx, ans, [
            (_jround(H / SMALL_TAN[th + 1]), f"You used tan {th + 1}° ({_js(SMALL_TAN[th + 1])}). The mast fills {th}°, so divide by {_js(t)}.") if th < 5 else None,
            (_jround(H / SMALL_TAN[th - 1]), f"You used tan {th - 1}° ({_js(SMALL_TAN[th - 1])}). The mast fills {th}°, so divide by {_js(t)}.") if th > 1 else None,
            (_jround(H / th), f"You divided by {th}, the angle itself. Divide by its tangent, {_js(t)}, instead."),
            (_jround(H / (t * 10)), f"You used {_js(round(t * 10, 6))} for tan {th}°. Check the decimal point: it's {_js(t)}."),
            (_jround(H / (t / 10)), f"You used {_js(round(t / 10, 6))} for tan {th}°. Check the decimal point: it's {_js(t)}."),
            (_jround(H * t), f"You multiplied by tan {th}°. The range is on the bottom of the ratio, so divide: {H} ÷ {_js(t)}."),
        ]),
        solution=[f"From the trig table, tan {th}° ≈ {_js(t)} (a small angle has a small tangent).", f"{H} ÷ {_js(t)} ≈ {_fmt_n(ans, 0)} m."],
        hint="Divide the mast height by the tangent of the angle.",
        fig=_fig("right_tri", ratio=0.32, adj=_ak("range ?"), opp=_gv(f"mast {H} m"), ang=_lab(f"{th}°"), marks={"P": _you(), "Q": _tgt()},
                 note="not to scale — the real angle is tiny"),
    )


_LEAD_CASES = (
    {"v": 6, "t": 30, "R": 1000, "th": 10}, {"v": 12, "t": 30, "R": 1000, "th": 20}, {"v": 9, "t": 40, "R": 1000, "th": 20},
    {"v": 15, "t": 20, "R": 400, "th": 37}, {"v": 10, "t": 25, "R": 250, "th": 45}, {"v": 18, "t": 20, "R": 1000, "th": 20},
    {"v": 29, "t": 20, "R": 1000, "th": 30}, {"v": 20, "t": 15, "R": 400, "th": 37}, {"v": 12, "t": 25, "R": 400, "th": 37},
    {"v": 25, "t": 20, "R": 500, "th": 45}, {"v": 6, "t": 30, "R": 500, "th": 20},
)


def _lead_marks(t: Optional[int]) -> dict[str, dict[str, Any]]:
    """The target now (at R) and where she'll be when the shells land (at Q). ``t`` None: the time is asked."""
    later = f"in {t} s" if t is not None else "in ? s"
    return {"P": _you(), "R": {"kind": "target", "dx": 8, "dy": -12}, "Q": {"kind": "target", "label": later, "dx": 22, "dy": -14}}


@gen("trig", 2)
def lead_angle(ctx: Context) -> Problem:
    me, en = ctx.my_name, ctx.enemy_name
    c = ctx.pick(_LEAD_CASES + ({"v": 18, "t": 10, "R": 1000, "th": 10},))
    v, t, R, th = c["v"], c["t"], c["R"], c["th"]
    d = v * t
    r = math.floor(d / R * 100 + 0.5) / 100
    marks = _lead_marks(t)
    if ctx.rand(0, 2) == 0:
        return _problem(
            help="lead",
            story=f"{en} is crossing your bow at {v} m/s. {me}'s shells take {t} seconds to reach her, so you have to aim where she will be, not where she is.",
            expr=f"lead distance = {v} m/s × {t} s",
            ask="How far ahead of her should you aim, in metres?",
            choices=_numeric_choices(ctx, d, [
                (v + t, "You added the speed and the time. Distance = speed × time."),
                (v, f"That's how far she goes in 1 second. In {t} seconds she goes {t} times as far."),
                (R, f"That's the range to her. The lead is how far she moves while the shells fly: {v} × {t}."),
                (t, f"That's the flight time, in seconds. The lead is a distance: speed × time, {v} × {t}."),
            ]),
            solution=[f"In {t} seconds she moves {v} × {t} = {d} m."],
            hint="Distance = speed × time.",
            # (the range isn't needed here; it isn't shown when it happens to equal the answer)
            fig=_fig("right_tri", ratio=0.4, adj=_lab(f"range {_fmt_n(R, 0)} m", "dim") if R != d else None, opp=_ak("lead ?"), marks=marks,
                     note=f"she moves at {v} m/s for {t} s"),
        )
    return _problem(
        help="lead",
        story=f"{en} is crossing your bow at {v} m/s at a range of {_fmt_n(R, 0)} m. {me}'s shells take {t} seconds to get there. The gun director sets a lead angle so the shells and the target arrive together.",
        expr=f"lead = {v} × {t};   tan(lead angle) = lead ÷ {_fmt_n(R, 0)}",
        ask="What lead angle should the director set? (Use the trig table.)",
        choices=_string_choices(ctx, f"{th}°", _angle_mistakes("tan", r, "lead", "range", f"{_fmt_n(R, 0)} ÷ {d}") + [
            (f"{_nearest_angle('tan', v / R)}°", f"You used her speed, {v}, as the lead. The lead is speed × time: {v} × {t} = {d} m."),
        ]),
        solution=[f"Lead distance: {v} × {t} = {d} m.", f"tan(lead) = {d} ÷ {_fmt_n(R, 0)} = {_js(r)}.", f"In the tan column of the trig table, {_js(r)} is {th}°."],
        hint="Multiply speed by time, divide by the range, then find that number in the tan column.",
        fig=_fig("right_tri", ratio=1, adj=_gv(f"range {_fmt_n(R, 0)} m"), opp=_gv(f"lead {d} m"), ang=_ak("lead ?"), marks=marks,
                 note=f"{_NOT_TO_SCALE}: she moves {d} m in {t} s"),
    )


# ---------------- Engineering · Area & Volume ----------------


@gen("geo", 1)
def rectangle(ctx: Context) -> Problem:
    me = ctx.my_name
    Lv = ctx.pick([40, 50, 60, 80, 90, 120, 150, 200])
    Wv = ctx.pick([12, 15, 18, 20, 24, 30, 36])
    area = _fmt_n(Lv * Wv, 0)
    v = ctx.pick([
        {"story": f"The helicopter deck on {me} is a rectangle {Lv} ft long and {Wv} ft wide. The deck crew has to paint the whole thing with non-skid.",
         "ask": "What is its area in square feet?", "expr": f"A = {Lv} × {Wv}", "ans": Lv * Wv,
         "wrong": [(2 * Lv + 2 * Wv, "That's the perimeter (all four sides added). Area is length × width."),
                   (Lv + Wv, "You added the length and the width. Area is length × width."),
                   (Lv * Wv / 2, "You halved it. Halving is for a triangle; a rectangle's area is just length × width."),
                   (2 * Lv * Wv, "You doubled it, like in the perimeter rule. Area is just length × width."),
                   (Lv * Lv, f"You multiplied the length by itself. Area is length × width: {Lv} × {Wv}.")],
         "sol": ["Area = length × width.", f"{Lv} × {Wv} = {area} sq ft."], "mode": "area"},
        {"story": f"The crew is rigging a safety line all the way around the edge of {me}'s {Lv} ft × {Wv} ft flight deck.",
         "ask": "How many feet of line do they need (the perimeter)?", "expr": f"P = 2 × {Lv} + 2 × {Wv}", "ans": 2 * Lv + 2 * Wv,
         "wrong": [(Lv * Wv, "That's the area (length × width). The line goes round the edge: add all four sides."),
                   (Lv + Wv, "That's only halfway round: one length and one width. Double it."),
                   (2 * Lv + Wv, "You only counted one width. A rectangle has two lengths and two widths."),
                   (Lv + 2 * Wv, "You only counted one length. A rectangle has two lengths and two widths."),
                   (4 * Lv, f"You counted four lengths. Two of the sides are the {Wv} ft width."),
                   (2 * Lv * Wv, "You doubled the area. The line goes round the edge: 2 × length + 2 × width.")],
         "sol": ["Perimeter = 2 × length + 2 × width.", f"{2 * Lv} + {2 * Wv} = {2 * Lv + 2 * Wv} ft."], "mode": "perim"},
        {"story": f"A rectangular fuel-oil tank below decks has a floor area of {area} sq ft and is {Wv} ft wide.",
         "ask": "How long is the tank?", "expr": f"{area} = L × {Wv}", "ans": Lv,
         "wrong": [(Lv * Wv - Wv, f"You took {Wv} away from {area}. To undo × {Wv}, divide by {Wv}."),
                   (Lv * Wv / 2, "You halved the area. To undo × width, divide by the width."),
                   (Lv * Wv * Wv, f"You multiplied by {Wv}. To undo × {Wv}, divide by {Wv}."),
                   (Lv * Wv / 2 - Wv, f"You treated {area} as the perimeter: halved it and took off the width. It's the area, so divide by {Wv}."),
                   (2 * Lv, "You doubled the area first, as if the floor were a triangle. For a rectangle, length = area ÷ width."),
                   (Lv / 2, f"You divided by 2 × {Wv}, as if both widths counted. Length = area ÷ width, just once."),
                   (_jround(math.sqrt(Lv * Wv)), f"You took the square root, as if the floor were a square. It's {Wv} ft wide, so divide by {Wv}.")],
         "sol": ["Area = length × width, so length = area ÷ width.", f"{area} ÷ {Wv} = {Lv} ft."], "mode": "L"},
    ])
    return _problem(help="rect", story=v["story"], expr=v["expr"], ask=v["ask"], choices=_numeric_choices(ctx, v["ans"], v["wrong"]),
                    solution=v["sol"], hint="Area is length × width. Perimeter is all four sides added up.",
                    fig=_fig("rect", Lv=Lv, Wv=Wv, mode=v["mode"]))


@gen("geo", 1)
def triangle_area(ctx: Context) -> Problem:
    me = ctx.my_name
    b = ctx.pick([20, 24, 30, 36, 40, 50, 60])
    h = ctx.pick([10, 12, 15, 18, 20, 25, 30])
    return _problem(
        help="tri",
        story=f"The foredeck ahead of {me}'s anchor windlass is a triangle: {b} ft across at the back and {h} ft from there straight to the bow (its height). It needs a coat of non-skid.",
        expr=f"A = ½ × {b} × {h}",
        ask="What is the area in square feet?",
        choices=_numeric_choices(ctx, b * h / 2, [
            (b * h, f"You forgot the ½. A triangle is half a rectangle: ½ × {b} × {h}."),
            (b + h, "You added the base and the height. Multiply them, then halve."),
            (b * h / 4, "You halved both the base and the height. Halve just once."),
            (2 * b * h, "You doubled instead of halving. A triangle is half of base × height."),
            ((b + h) / 2, "You added the base and the height and halved that. Multiply them, then halve."),
            ((b + h) / 2 * h, f"You averaged {b} and {h}, then multiplied by {h}. That's for a trapezoid; a triangle is ½ × base × height."),
        ]),
        solution=[f"{b} × {h} = {b * h}.", f"Half of that: {b * h} ÷ 2 = {_js(b * h / 2)} sq ft."],
        hint="Multiply base by height, then halve it.",
        fig=_fig("tri_area", b=b, h=h),
    )


@gen("geo", 1)
def circle(ctx: Context) -> Problem:
    me = ctx.my_name
    mode = ctx.pick(["cpi", "api", "cnum", "anum"])
    if mode == "cpi":
        d = ctx.pick([8, 10, 12, 14, 16, 20, 24, 30])
        return _problem(
            help="circle",
            story=f"The barbette ring under {me}'s forward turret is a circle {d} ft across (its diameter). The shipwrights need enough steel to go all the way around it.",
            expr=f"C = π × d, with d = {d}",
            ask="What is the circumference? (Leave π in the answer.)",
            choices=_string_choices(ctx, f"{d}π ft", [
                (f"{_js(d / 2)}π ft", f"You used the radius, {_js(d / 2)}. Circumference is π × the diameter, {d}."),
                (f"{_js(d * d / 4)}π ft", "That's π × r², the area inside. Circumference is π × the diameter."),
                (f"{2 * d}π ft", f"You did 2 × π × {d}, but {d} ft is the diameter, not the radius. It's just π × {d}."),
                (f"{d * d}π ft", "You squared the diameter. Circumference is π × the diameter."),
            ]),
            solution=["Circumference = π × diameter.", f"π × {d} = {d}π ft (about {_js(_round1(3.14 * d))} ft)."],
            hint="Circumference is π times the diameter.",
            fig=_fig("circle", d=d, mode="circ", unit="ft"),
        )
    if mode == "api":
        r = ctx.pick([5, 8, 10, 12, 15, 20, 25, 30])
        return _problem(
            help="circle",
            story=f"{me}'s search radar reaches {r} nm in every direction, sweeping a full circle around the ship.",
            expr=f"A = π × r{sup(2)}, with r = {r}",
            ask="How many square nautical miles does the radar cover? (Leave π in the answer.)",
            choices=_string_choices(ctx, f"{r * r}π sq nm", [
                (f"{2 * r}π sq nm", f"That's 2 × π × {r}, the circumference. Area is π × r²."),
                (f"{r}π sq nm", f"You didn't square the radius. Area is π × {r}²."),
                (f"{4 * r * r}π sq nm", f"You squared the diameter, {2 * r}. Area uses the radius: π × {r}²."),
                (f"{_js(r * r / 4)}π sq nm", f"You halved {r} first, but {r} nm is already the radius. Area is π × {r}²."),
                (f"{2 * r * r}π sq nm", f"You doubled r², mixing it up with 2πr. Area is just π × {r}²."),
            ]),
            solution=["Area = π × radius².", f"{r}² = {r * r}, so the area is {r * r}π sq nm (about {_fmt_n(3.14 * r * r, 0)})."],
            hint="Square the radius and put π in front.",
            fig=_fig("circle", r=r, mode="area", unit="nm"),
        )
    if mode == "cnum":
        d = ctx.pick([5, 10, 20, 30, 50])
        ans = _round1(3.14 * d)
        ch = _numeric_choices(ctx, ans, [
            (_round1(3.14 * d / 2), f"You used the radius, {_js(d / 2)}. Circumference is 3.14 × the diameter, {d}."),
            (_round1(3.14 * d * d / 4), "That's the area inside (3.14 × r²). Circumference is 3.14 × the diameter."),
            (_round1(3.14 * d * 2), f"You did 2 × 3.14 × {d}, but {d} ft is the diameter, not the radius. It's just 3.14 × {d}."),
            (d * 3, "You used 3 for π. Use 3.14 to get a number the shipwrights can cut to."),
            (_round1(3.14 + d), f"You added 3.14 and {d}. Circumference is 3.14 × the diameter."),
            (_round1(3.14 * d * d), "You squared the diameter. Circumference is 3.14 × the diameter."),
        ], dp="auto")
        return _problem(
            help="circle",
            story=f"The turret ring on {me} is {d} ft across. Using π ≈ 3.14, the shipwrights want a number they can cut steel to.",
            expr=f"C = 3.14 × {d}",
            ask="What is the circumference in feet?",
            choices=ch,
            solution=["Circumference = π × diameter.", f"3.14 × {d} = {ch.texts[0]} ft."],
            hint="Multiply 3.14 by the diameter.",
            fig=_fig("circle", d=d, mode="circ", unit="ft"),
        )
    r = ctx.pick([5, 10, 20])
    ans = _round1(3.14 * r * r)
    ch = _numeric_choices(ctx, ans, [
        (_round1(3.14 * 2 * r), f"That's 2 × 3.14 × {r}, the circumference. Area is 3.14 × r²."),
        (_round1(3.14 * r), f"You didn't square the radius. Area is 3.14 × {r}²."),
        (_round1(3.14 * 4 * r * r), f"You squared the diameter, {2 * r}. Area uses the radius: 3.14 × {r}²."),
        (r * r, "You forgot to multiply by π. Area is 3.14 × r²."),
        (_round1((3.14 * r) ** 2), f"You squared 3.14 × {r}. Only the radius gets squared: 3.14 × {r}²."),
    ], dp="auto")
    return _problem(
        help="circle",
        story=f"{me}'s radar reaches {r} nm in every direction. Using π ≈ 3.14, the navigator wants the area it sweeps.",
        expr=f"A = 3.14 × {r}{sup(2)}",
        ask="What is the area in square nautical miles?",
        choices=ch,
        solution=["Area = π × radius².", f"{r}² = {r * r}. 3.14 × {r * r} = {ch.texts[0]} sq nm."],
        hint="Square the radius first, then multiply by 3.14.",
        fig=_fig("circle", r=r, mode="area", unit="nm"),
    )


@gen("geo", 1)
def arc_length(ctx: Context) -> Problem:
    me = ctx.my_name
    r = ctx.pick([120, 240, 360, 480, 600])
    th = ctx.pick([45, 60, 90, 120, 180, 270])
    c = th / 360 * 2 * r
    frac = _fraction(th, 360)
    choices = _string_choices(ctx, f"{_js(c)}π yd", [
        (f"{2 * r}π yd", f"That's the whole circle, 2π × {r}. She only turns {th}° of the 360°."),
        (f"{_js(c / 2)}π yd", f"You used π × {r} for the whole circle. The full circle is 2π × {r} = {2 * r}π."),
        (f"{_js(c * 2)}π yd", f"You used the diameter, {2 * r}, as the radius. The radius is {r} yd."),
        (f"{_js(th / 360 * r * r)}π yd", f"That's the area of the wedge ({frac} × π × {r}²). The arc is part of the edge: {frac} × 2π × {r}."),
        (f"{_js(360 / th * 2 * r)}π yd", f"You did 360 ÷ {th}, upside down. The fraction of the circle is {th} ÷ 360."),
        (f"{th * 2 * r}π yd", f"You forgot to divide by 360. The fraction of the circle is {th} ÷ 360 = {frac}."),
        (f"{_js((360 - th) / 360 * 2 * r)}π yd", f"That's the rest of the circle, the {360 - th}° she didn't turn. Take {frac} of 2π × {r}.") if th != 180 else None,
        (f"{2 * r // th}π yd", f"You divided the whole circle, {2 * r}π, by {th}. Take {frac} of it instead: {th} ÷ 360 × {2 * r}π.")
        if (2 * r) % th == 0 else None,
    ])
    return _problem(
        help="arc",
        story=f"{me}'s turning circle has a radius of {r} yards. The helm puts the rudder over and she swings through {th}°.",
        expr=f"arc = ({th} ÷ 360) × 2π × {r}",
        ask="How far does she travel along the arc? (Leave π in the answer.)",
        choices=choices,
        solution=[
            f"Full circumference: 2π × {r} = {2 * r}π.",
            f"Fraction of the circle: {th} ÷ 360 = {frac}.",
            f"{frac} × {2 * r}π = {_js(c)}π yd (about {_fmt_n(3.14 * c, 0)} yd).",
        ],
        hint=f"Find the full circumference, then take the fraction of it that {th}° is out of 360°.",
        fig=_fig("arc", r=r, th=th),
    )


@gen("geo", 1)
def box_volume(ctx: Context) -> Problem:
    me = ctx.my_name
    Lv = ctx.pick([8, 10, 12, 15, 20])
    Wv = ctx.pick([4, 5, 6, 8])
    Hv = ctx.pick([3, 4, 5, 6])
    V = Lv * Wv * Hv
    return _problem(
        help="vol",
        story=f"A fresh-water tank below decks on {me} is a box {Lv} ft long, {Wv} ft wide and {Hv} ft deep. The engineer needs its volume.",
        expr=f"V = {Lv} × {Wv} × {Hv}",
        ask="What is the volume in cubic feet?",
        choices=_numeric_choices(ctx, V, [
            (Lv * Wv, f"That's just the floor, {Lv} × {Wv}. Multiply by the depth, {Hv}, too."),
            (Lv + Wv + Hv, "You added the three sides. Volume is length × width × height."),
            (2 * (Lv * Wv + Lv * Hv + Wv * Hv), "That's the surface area (all six faces). Volume is length × width × height."),
            (4 * (Lv + Wv + Hv), "That's all 12 edges added up. Volume is length × width × height."),
            (Lv * Wv * Hv * 2, "You doubled it. Volume is just length × width × height."),
            (Lv * Wv + Hv, f"You added the depth to the floor area. Multiply by it instead: {Lv * Wv} × {Hv}."),
            ((Lv + Wv) * Hv, f"You added the length and the width. Multiply all three: {Lv} × {Wv} × {Hv}."),
            (Lv * Wv + Lv * Hv + Wv * Hv, "You added the areas of three faces. Volume multiplies the three sides together."),
        ]),
        solution=[f"{Lv} × {Wv} = {Lv * Wv} (the floor).", f"{Lv * Wv} × {Hv} = {V} cubic ft."],
        hint="Multiply all three: length × width × height.",
        fig=_fig("box", Lv=Lv, Wv=Wv, Hv=Hv, mode="vol"),
    )


@gen("geo", 1)
def cylinder_volume(ctx: Context) -> Problem:
    me = ctx.my_name
    r = ctx.pick([2, 3, 4, 5, 6])
    h = ctx.pick([5, 8, 10, 12])
    return _problem(
        help="cyl",
        story=f"The boiler feed tank on {me} is a cylinder: radius {r} ft, height {h} ft.",
        expr=f"V = π × r{sup(2)} × h",
        ask="What is the volume? (Leave π in the answer.)",
        choices=_string_choices(ctx, f"{r * r * h}π cubic ft", [
            (f"{2 * r * h}π cubic ft", f"That's 2 × π × {r} × {h}, the area of the curved side. Volume is π × r² × h."),
            (f"{r * h}π cubic ft", f"You didn't square the radius: π × {r}² × {h}."),
            (f"{r * r}π cubic ft", f"That's just the circle on the end, π × {r}². Multiply by the height, {h}, too."),
            (f"{4 * r * r * h}π cubic ft", f"You used the diameter, {2 * r}, as the radius. Square the radius: {r}² = {r * r}."),
            (f"{r * h * h}π cubic ft", f"You squared the height instead of the radius: π × {r}² × {h}."),
        ]),
        solution=[f"{r}² = {r * r}.", f"{r * r} × {h} = {r * r * h}.", f"Volume = {r * r * h}π cubic ft."],
        hint="Square the radius, multiply by the height, keep the π.",
        fig=_fig("cyl", r=r, h=h),
    )


@gen("geo", 2)
def trapezoid_area(ctx: Context) -> Problem:
    me = ctx.my_name
    a = ctx.pick([10, 12, 16, 20])
    b = a + ctx.pick([4, 6, 8, 10])
    h = ctx.pick([4, 6, 8, 10])
    ans = (a + b) / 2 * h
    return _problem(
        help="trap",
        story=f"The splinter shield around the gun on {me}'s fantail is a trapezoid: {a} ft along the top, {b} ft along the bottom and {h} ft tall.",
        expr=f"A = ({a} + {b}) ÷ 2 × {h}",
        ask="How many square feet of steel plate is that?",
        choices=_numeric_choices(ctx, ans, [
            ((a + b) * h, f"You forgot to halve. Average the two parallel sides first: ({a} + {b}) ÷ 2."),
            (a * h, f"You only used the top, {a} ft. Use the average of the top and the bottom."),
            (b * h, f"You only used the bottom, {b} ft. Use the average of the top and the bottom."),
            ((a + b) / 2 + h, "You added the height. Multiply the average width by the height instead."),
            (b * h / 2, f"That's ½ × {b} × {h}, the triangle rule. A trapezoid uses the average of both parallel sides."),
            (a * b * h / 2, f"You multiplied the two parallel sides. Add them and halve: ({a} + {b}) ÷ 2."),
        ]),
        solution=[f"Average the parallel sides: ({a} + {b}) ÷ 2 = {_js((a + b) / 2)}.", f"{_js((a + b) / 2)} × {h} = {_js(ans)} sq ft."],
        hint="Average the top and bottom, then multiply by the height.",
        fig=_fig("trap", a=a, b=b, h=h),
    )


@gen("geo", 2)
def surface_area(ctx: Context) -> Problem:
    me = ctx.my_name
    l = ctx.pick([4, 5, 6, 8])  # noqa: E741 (the original's names)
    w = ctx.pick([2, 3, 4])
    h = ctx.pick([2, 3, 5])
    ans = 2 * (l * w + l * h + w * h)
    return _problem(
        help="surf",
        story=f"A watertight ready-ammunition locker on {me} is {l} ft long, {w} ft wide and {h} ft tall. The bosun paints all six faces.",
        expr=f"SA = 2({l}×{w} + {l}×{h} + {w}×{h})",
        ask="How many square feet get painted?",
        choices=_numeric_choices(ctx, ans, [
            (l * w + l * h + w * h, "You added the three different faces but forgot their twins. Double it."),
            (l * w * h, "That's the volume. Paint covers the faces: add up the six face areas."),
            (2 * (l * w + l * h), f"You left out the two {w} × {h} end faces."),
            (2 * (l * w + w * h), f"You left out the two {l} × {h} side faces."),
            (2 * (l * h + w * h), f"You left out the top and the bottom, {l} × {w} each."),
            (6 * l * w, f"You counted six faces all {l} × {w}. Only a cube has six matching faces; here there are three pairs."),
            (2 * l * w + l * h + w * h, "You doubled the top and bottom but not the sides. Every face has a twin."),
            (4 * (l * w + l * h + w * h), "You doubled twice. Add the three different faces, then double just once."),
        ]),
        solution=[
            f"Three different faces: {l}×{w} = {l * w}, {l}×{h} = {l * h}, {w}×{h} = {w * h}.",
            f"Add: {l * w + l * h + w * h}. Each face has a twin, so double it: {ans} sq ft.",
        ],
        hint="Find the three different face areas, add them, then double.",
        fig=_fig("box", Lv=l, Wv=w, Hv=h, mode="surf"),
    )


@gen("geo", 2)
def composite_area(ctx: Context) -> Problem:
    me = ctx.my_name
    Lv = ctx.pick([200, 240, 300])
    Wv = ctx.pick([30, 40, 50, 60])
    b = ctx.pick([20, 30, 40, 50])
    ans = Lv * Wv + Wv * b / 2
    return _problem(
        help="composite",
        story=f"Seen from above, {me}'s main deck is a rectangle {Lv} ft long and {Wv} ft wide, with a triangular bow {b} ft long on the front. The whole deck is being re-planked.",
        expr=f"A = {Lv} × {Wv} + ½ × {Wv} × {b}",
        ask="What is the total deck area in square feet?",
        choices=_numeric_choices(ctx, ans, [
            (Lv * Wv, f"That's just the rectangle. Add the triangular bow, ½ × {Wv} × {b}, too."),
            (Lv * Wv + Wv * b, f"You forgot the ½ for the triangle: ½ × {Wv} × {b}."),
            (Lv * Wv + b, f"You added the bow's length, {b}, not its area. The bow is ½ × {Wv} × {b}."),
            (Lv * Wv - Wv * b / 2, "You took the bow away. It's part of the deck, so add it."),
            (Lv * Wv + Lv * b / 2, f"The bow's base is the deck's width, {Wv} ft, not its length. Bow = ½ × {Wv} × {b}."),
            (Wv * b / 2, f"That's only the bow. Add the rectangle, {Lv} × {Wv}, too."),
        ]),
        solution=[
            f"Rectangle: {Lv} × {Wv} = {_fmt_n(Lv * Wv, 0)}.",
            f"Bow triangle: ½ × {Wv} × {b} = {_js(Wv * b / 2)}.",
            f"Total: {_fmt_n(Lv * Wv, 0)} + {_js(Wv * b / 2)} = {_fmt_n(ans, 0)} sq ft.",
        ],
        hint="Do the rectangle and the triangle separately, then add.",
        fig=_fig("composite", Lv=Lv, Wv=Wv, b=b),
    )


# ---------------- Shields · Circles ----------------
# Not in the original game: the fleet's new force fields are circles. Circle theorems, and
# circles on the plotting grid. Every number works out by hand (perfect squares, Pythagorean
# triples); the figures are sketches in a fixed layout, so nothing can be measured off them.


def _pt(x: int, y: int) -> str:
    """A grid point with proper minus signs: (3, −2)."""
    return f"({_signed(x)}, {_signed(y)})"


def _paren(n: int) -> str:
    """A number as it goes after a minus sign: 3, or (−3)."""
    return f"({_signed(n)})" if n < 0 else str(n)


def _sq(n: int) -> str:
    """n², bracketed if negative: 3², (−3)²."""
    return f"{_paren(n)}²"


def _brk(var: str, c: int) -> str:
    """The bracket that takes the centre coordinate ``c`` away: (x − 3), (y + 2), or just x for 0."""
    return f"({var} − {c})" if c > 0 else f"({var} + {-c})" if c < 0 else var


def _circle_eq(h: int, k: int, rhs: int) -> str:
    """(x − h)² + (y − k)² = rhs, signs worked out: _circle_eq(3, -2, 49) -> "(x − 3)² + (y + 2)² = 49"."""
    return f"{_brk('x', h)}² + {_brk('y', k)}² = {rhs}"


def _take(var: str, c: int) -> str:
    """How a bracket takes the centre away: "x − 3", or "y − (−2) = y + 2"."""
    return f"{var} − {c}" if c >= 0 else f"{var} − (−{-c}) = {var} + {-c}"


def _reads(var: str, c: int) -> str:
    """What a bracket says about the centre: "(x − 3) → x = 3", "(y + 2) → y = −2"."""
    return f"{_brk(var, c)} → {var} = {_signed(c)}"


def _centre_r(h: int, k: int, r: int) -> str:
    """A centre and radius as a choice: "(3, −2), r = 7"."""
    return f"{_pt(h, k)}, r = {r}"


def _lin(a: int, b: int) -> str:
    """ax + b written out: _lin(3, 2) -> "3x + 2", _lin(1, -6) -> "x − 6"."""
    ax = "x" if a == 1 else f"{a}x"
    return f"{ax} + {b}" if b > 0 else f"{ax} − {-b}" if b < 0 else ax


def _off_centre(ctx: Context, lo: int, hi: int) -> tuple[int, int]:
    """A centre (h, k) with neither coordinate 0 and |h| ≠ |k|, so a sign or a swap is always its own mistake."""
    while True:
        h = ctx.pick([-1, 1]) * ctx.rand(lo, hi)
        k = ctx.pick([-1, 1]) * ctx.rand(lo, hi)
        if abs(h) != abs(k):
            return h, k


_YOU_AT_C = {"C": {"kind": "you"}}
_YOU_AT_P = {"P": {"kind": "you"}}


@gen("circ", 1)
def shield_centre_radius(ctx: Context) -> Problem:
    me, en = ctx.my_name, ctx.enemy_name
    h, k = _off_centre(ctx, 1, 9)
    r = ctx.rand(3, 12)
    rr = r * r
    eq = _circle_eq(h, k, rr)
    ans = _centre_r(h, k, r)
    reads = f"{_reads('x', h)}, {_reads('y', k)}"
    return _problem(
        help="circeq",
        story=f"{en} has raised a force field: a circular shield all round her. {me}'s plotting computer draws its edge as {eq}, where each grid square is 1 nm.",
        expr=eq,
        note="(x − h)² + (y − k)² = r²: centre (h, k), radius r",
        ask="Where is the shield's centre, and what is its radius?",
        choices=_string_choices(ctx, ans, [
            (_centre_r(-h, -k, r), f"You copied the signs in the brackets. The centre's signs are the opposite: {reads}."),
            (_centre_r(h, k, rr), f"{rr} is r², not r. The radius is √{rr} = {r}."),
            (_centre_r(-h, -k, rr), f"Two slips: the centre's signs are the opposite of the brackets', and {rr} is r², so r = √{rr} = {r}."),
            (_centre_r(k, h, r), "You swapped x and y. The number in the x bracket gives the x-coordinate, which comes first."),
            (_centre_r(-h, k, r), f"The y is right, but you copied the sign in the x bracket: {_reads('x', h)}."),
            (_centre_r(h, -k, r), f"The x is right, but you copied the sign in the y bracket: {_reads('y', k)}."),
            (_centre_r(h, k, rr // 2), f"You halved {rr}. The radius is its square root: √{rr} = {r}.") if rr % 2 == 0 else None,
        ]),
        solution=[
            f"Each bracket takes the centre away, so the centre's signs are the opposite: {reads}.",
            f"The right side is r² = {rr}, so r = √{rr} = {r}.",
            f"Centre and radius: {ans}.",
        ],
        hint="For the centre, flip the sign of the number in each bracket. The number on the right is r²: take its square root.",
        fig=_fig("shield", centre=_ak("(?, ?)"), radius=_ak("r = ?"), ship="target"),
    )


@gen("circ", 1)
def inscribed_angle(ctx: Context) -> Problem:
    me, en = ctx.my_name, ctx.enemy_name
    mode = ctx.pick(["rim", "centre", "semi"])
    if mode == "semi":
        x = ctx.rand(12, 42)  # so the answer, 90 − x, is the bigger of the two angles
        ans = 90 - x
        return _problem(
            help="inscribed",
            story=f"Two of {en}'s shield pylons, A and B, stand at opposite ends of a diameter, straight across her circular shield through its centre. {me} has closed right up to the edge of the shield and sights both pylons. At A, the line to {me} makes {x}° with the diameter.",
            expr=f"{x}° + 90° + b = 180°",
            note="an angle in a semicircle is 90°",
            ask=f"At B, what angle does the line to {me} make with the diameter?",
            choices=_numeric_choices(ctx, ans, [
                (180 - x, "You left out the right angle at the ship. An angle facing a diameter is 90°, so take 90 away too."),
                (x, "That's the angle at A again. The angles at A and B share the 90° left over after the right angle."),
                (45, f"You split the leftover 90° evenly between A and B. They aren't equal: B gets 90 − {x}."),
                (90, "That's the angle at the ship: an angle in a semicircle is 90°. B gets what's left of 180°."),
                ((180 - x) // 2, f"You halved 180 − {x}, as if two angles were equal. The angle at the ship is 90°: 180 − 90 − {x}.")
                if x % 2 == 0 else None,
                (90 + x, f"You added {x} to 90. All three angles add to 180, so take both away: 180 − 90 − {x}."),
                (270 - x, "You used 360°, but the three angles of a triangle add to 180°."),
            ]),
            solution=[
                f"AB is a diameter, so the angle at {me}, facing it, is 90° (an angle in a semicircle).",
                f"The three angles of the triangle add to 180°: 180 − 90 − {x} = {ans}°.",
            ],
            hint="The angle at the ship, facing a diameter, is 90°. Then the three angles of the triangle add to 180.",
            fig=_fig("inscribed", mode="semi", angA=_gv(f"{x}°"), angB=_ak("?"), marks=_YOU_AT_C, note=_NOT_TO_SCALE),
        )
    rim = ctx.rand(20, 85)
    C = 2 * rim
    if mode == "rim":
        return _problem(
            help="inscribed",
            story=f"Two emitter pylons stand on the edge of {en}'s circular shield. Seen from the shield's centre, they are {C}° apart. {me} has closed right up to the edge on the far side of the shield and sights both pylons.",
            expr=f"angle at the rim = {C}° ÷ 2",
            ask=f"What angle does {me} see between the two pylons?",
            choices=_numeric_choices(ctx, rim, [
                (C, "That's the angle at the centre. From the rim, the same two pylons fill half that angle."),
                (2 * C, "You doubled it. The angle at the rim is half the angle at the centre, not twice it."),
                (180 - C, f"You took {C} from 180. There's no straight line here: the angle at the rim is {C} ÷ 2."),
                (180 - rim, f"That's the angle from the short stretch of edge between the pylons. The ship is on the far side: {C} ÷ 2."),
                (360 - C, f"That's the reflex angle at the centre, the long way round. Halve the {C}° angle instead."),
                (90 - rim, f"That's (180 − {C}) ÷ 2, the angle at a pylon between the radius and the line to the other pylon. Halve {C}."),
                (rim // 2, f"You halved twice. The angle at the rim is {C} ÷ 2, just once.") if rim % 2 == 0 else None,
            ]),
            solution=["An angle at the rim is half the angle at the centre facing the same two points.", f"{C} ÷ 2 = {rim}°."],
            hint="Halve the angle at the centre.",
            fig=_fig("inscribed", mode="arc", central=_gv(f"{C}°"), rim=_ak("?"), marks=_YOU_AT_C, note=_NOT_TO_SCALE),
        )
    return _problem(
        help="inscribed",
        story=f"{me} has closed right up to the edge of {en}'s circular shield. From there she sights two emitter pylons, also on the edge, {rim}° apart. The shield's generator sits at its centre.",
        expr=f"angle at the centre = {rim}° × 2",
        ask="What angle do the two pylons make at the centre of the shield?",
        choices=_numeric_choices(ctx, C, [
            (rim, "That's the angle at the rim again. The angle at the centre is twice the angle at the rim."),
            (rim // 2, "You halved it. The angle at the centre is double the angle at the rim, not half.") if rim % 2 == 0 else None,
            (360 - C, f"That's the reflex angle, the long way round the centre. The angle facing the pylons is {rim} × 2."),
            (180 - rim, f"You took {rim} from 180. There's no straight line here: the angle at the centre is {rim} × 2."),
            (4 * rim, f"You doubled twice. The angle at the centre is {rim} × 2, just once."),
        ]),
        solution=["The angle at the centre is twice the angle at the rim facing the same two points.", f"{rim} × 2 = {C}°."],
        hint="Double the angle at the rim.",
        fig=_fig("inscribed", mode="arc", central=_ak("?"), rim=_gv(f"{rim}°"), marks=_YOU_AT_C, note=_NOT_TO_SCALE),
    )


@gen("circ", 1)
def tangent_radius_angle(ctx: Context) -> Problem:
    me, en = ctx.my_name, ctx.enemy_name
    x = ctx.rand(12, 42)  # so the answer, 90 − x, is the bigger of the two angles
    ans = 90 - x
    at_ship = ctx.rand(0, 1)
    story = (f"{me}'s course just grazes the edge of {en}'s circular shield, touching it at one point, T: the course is a tangent. "
             "The radius from the shield's centre to T meets the course at 90°. ")
    if at_ship:
        known, other = "the ship", "the centre"
        story += f"At {me}, the line to the shield's centre makes {x}° with her course."
        ask = f"At the centre, what angle is there between the radius to T and the line to {me}?"
        fig = _fig("tangents", oline=True, right=True, angP=_gv(f"{x}°"), angO=_ak("?"), marks=_YOU_AT_P, note=_NOT_TO_SCALE)
    else:
        known, other = "the centre", "the ship"
        story += f"At the centre, the radius to T and the line to {me} make {x}°."
        ask = f"At {me}, what angle does the line to the centre make with her course?"
        fig = _fig("tangents", oline=True, right=True, angP=_ak("?"), angO=_gv(f"{x}°"), marks=_YOU_AT_P, note=_NOT_TO_SCALE)
    return _problem(
        help="tangent",
        story=story,
        expr=f"{x}° + 90° + a = 180°",
        note="a tangent meets the radius at 90°",
        ask=ask,
        choices=_numeric_choices(ctx, ans, [
            (180 - x, "You left out the right angle at T. The radius meets the tangent at 90°, so take 90 away too."),
            (x, f"That's the angle at {known}, which you were given. The angle at {other} is what's left."),
            (45, f"You split the 90° left over evenly, but the two angles aren't equal: it's 90 − {x}."),
            (90, f"That's the angle at T, where the radius meets the tangent. The angle at {other} is what's left of 180°."),
            ((180 - x) // 2, f"You halved 180 − {x}, as if two angles were equal. The angle at T is 90°.") if x % 2 == 0 else None,
            (90 + x, f"You added {x} to 90. All three angles add to 180, so take both away: 180 − 90 − {x}."),
            (270 - x, "You used 360°, but the three angles of a triangle add to 180°."),
        ]),
        solution=[
            "The radius meets the tangent at 90°, so the triangle has a right angle at T.",
            f"The three angles add to 180°: 180 − 90 − {x} = {ans}°.",
        ],
        hint="Put in the 90° where the tangent touches the shield. Then the triangle's three angles add to 180.",
        fig=fig,
    )


@gen("circ", 1)
def cyclic_quadrilateral(ctx: Context) -> Problem:
    me, en = ctx.my_name, ctx.enemy_name
    x = ctx.pick([v for v in range(50, 131) if v != 90])  # at 90° the opposite corner would be 90° too
    ans = 180 - x
    g, a = ctx.pick([("A", "C"), ("C", "A"), ("B", "D"), ("D", "B")])
    return _problem(
        help="cyclic",
        story=f"{en}'s shield is held up by four pylons, A, B, C and D, standing in that order round the edge of the circular field. Joined up, they make a quadrilateral, and {me}'s sensors measure its angle at {g}: {x}°.",
        expr=f"{x}° + {a} = 180°",
        note="opposite angles of a quadrilateral on a circle add to 180°",
        ask=f"What is the angle at {a}, the corner opposite {g}?",
        choices=_numeric_choices(ctx, ans, [
            (x, f"That's the angle at {g} again. Opposite corners of a quadrilateral on a circle aren't equal; they add to 180°."),
            (360 - x, "You took it from 360°. All four corners add to 360, but one pair of opposite corners adds to 180°."),
            ((360 - x) // 3, "You shared what's left of 360° equally among the other three corners. They aren't equal; opposite corners add to 180°.")
            if (360 - x) % 3 == 0 else None,
            (abs(90 - x), "You used 90°. Opposite corners of a quadrilateral on a circle add to 180°."),
            (x // 2, f"You halved {x}, as for an angle at the rim from one at the centre. {a} is on the rim too: 180 − {x}.") if x % 2 == 0 else None,
            (2 * x, f"You doubled {x}, as for an angle at the centre. {a} is on the rim too, and opposite corners add to 180°."),
        ]),
        solution=[f"{g} and {a} are opposite corners of a quadrilateral on a circle, so they add to 180°.", f"180 − {x} = {ans}°."],
        hint="Opposite corners of a quadrilateral on a circle add to 180. Subtract.",
        fig=_fig("inscribed", mode="quad", note=_NOT_TO_SCALE, **{f"ang{g}": _gv(f"{x}°"), f"ang{a}": _ak("?")}),
    )


@gen("circ", 2)
def shield_equation(ctx: Context) -> Problem:
    me = ctx.my_name
    h, k = _off_centre(ctx, 1, 9)
    r = ctx.rand(3, 12)
    rr = r * r
    ans = _circle_eq(h, k, rr)
    takes = f"{_take('x', h)} and {_take('y', k)}"
    return _problem(
        help="circeq",
        story=f"{me}'s engineers are loading her new shield into the plotting computer. Its emitter sits at {_pt(h, k)} on the grid, and the force field reaches {r} nm out in every direction.",
        expr=f"centre {_pt(h, k)}, radius {r}",
        note="(x − h)² + (y − k)² = r²",
        ask="What equation describes the edge of the shield?",
        choices=_string_choices(ctx, ans, [
            (_circle_eq(-h, -k, rr), f"You put the centre's own signs in the brackets. Each bracket takes the centre away: {takes}."),
            (_circle_eq(h, k, r), f"The right side is r², not r: {r}² = {rr}."),
            (_circle_eq(-h, -k, r), f"Two slips: each bracket takes the centre away (flip its signs), and the right side is r² = {rr}."),
            (_circle_eq(h, k, 2 * r), f"You doubled the radius. The right side is r² = {r} × {r} = {rr}."),
            (_circle_eq(-h, k, rr), f"The y bracket is right, but the x bracket takes the centre away too: {_take('x', h)}."),
            (_circle_eq(h, -k, rr), f"The x bracket is right, but the y bracket takes the centre away too: {_take('y', k)}."),
            (_circle_eq(k, h, rr), "You swapped x and y. The centre's x-coordinate goes in the x bracket."),
        ]),
        solution=[f"Each bracket takes the centre away: {takes}.", f"The right side is r² = {r}² = {rr}.", f"The edge: {ans}."],
        hint="Put the centre into (x − h)² + (y − k)²: the signs flip inside the brackets. Then square the radius.",
        fig=_fig("shield", centre=_gv(_pt(h, k)), radius=_gv(f"r = {r} nm"), edge=_ak("equation ?"), ship="you"),
    )


@gen("circ", 2)
def torpedo_clearance(ctx: Context) -> Problem:
    me, en = ctx.my_name, ctx.enemy_name
    a, b, c = ctx.pick([t for t in TRIPLES if t[2] <= 26])
    if ctx.rand(0, 1):
        a, b = b, a
    sx, sy = ctx.pick([-1, 1]), ctx.pick([-1, 1])
    h = ctx.rand(0, 6) + (a if sx < 0 else 0)  # every coordinate stays 0 or more
    k = ctx.rand(0, 6) + (b if sy < 0 else 0)
    x, y = h + sx * a, k + sy * b
    # Shorter than the longer leg, so "only used Δx" (or Δy) is a smaller wrong answer: otherwise the
    # answer would nearly always be the smallest choice.
    r = ctx.rand(2, max(a, b) - 1)
    ans = c - r
    tangent = c * c - r * r
    return _problem(
        help="circdist",
        story=f"{en} has raised a circular shield {r} nm in radius, centred on {_pt(h, k)} on the plot. A torpedo from {me} is running at {_pt(x, y)}, outside the field. Each grid square is one nautical mile.",
        expr=f"√(({x} − {h})² + ({y} − {k})²) − {r}",
        note="distance to the centre − the radius",
        ask="How far is the torpedo from the edge of the shield?",
        choices=_numeric_choices(ctx, ans, [
            (c, f"That's how far the torpedo is from the centre. The edge is {r} nm nearer: take away the radius."),
            (c + r, "You added the radius. The edge lies between the torpedo and the centre, so take the radius away."),
            (a + b - r, f"You added Δx and Δy: {a} + {b}. Use Pythagoras for the distance to the centre, then take away {r}."),
            (c * c - r, f"You forgot the square root: √{c * c} = {c}. Then take away the radius."),
            (c - 2 * r, f"You took away the diameter, {2 * r}. The edge is one radius, {r} nm, from the centre."),
            (a - r, f"You only used Δx = {a}. The distance to the centre is √({a}² + {b}²) = {c}."),
            (b - r, f"You only used Δy = {b}. The distance to the centre is √({a}² + {b}²) = {c}."),
            (math.isqrt(tangent), f"That's √({c}² − {r}²), a tangent's length. Straight to the edge is the distance to the centre − {r}.")
            if math.isqrt(tangent) ** 2 == tangent else None,
            (_jround(math.hypot(x + h, y + k)) - r, "You added the coordinates. Subtract them to get Δx and Δy.") if h or k else None,
        ]),
        solution=[
            f"Δx = {x} − {h} = {_signed(x - h)}, Δy = {y} − {k} = {_signed(y - k)}.",
            f"{_sq(x - h)} + {_sq(y - k)} = {a * a} + {b * b} = {c * c}, so the torpedo is √{c * c} = {c} nm from the centre.",
            f"The edge is one radius nearer: {c} − {r} = {ans} nm.",
        ],
        hint="Use the distance formula to get from the torpedo to the centre of the shield, then take away the radius.",
        fig=_fig("shield", centre=_gv(_pt(h, k)), radius=_gv(f"r = {r} nm"), gap=_ak("?"), ship="target",
                 point={"label": _pt(x, y), "c": "given", "mark": "torpedo", "dir": [sx, sy]}),
    )


@gen("circ", 2)
def tangent_length(ctx: Context) -> Problem:
    me, en = ctx.my_name, ctx.enemy_name
    r, t, d = _triple(ctx)
    return _problem(
        help="tanlen",
        story=f"{me} is {d} nm from the centre of {en}'s circular shield, which reaches {r} nm out. To slip past, the helmsman lays a course that just grazes the edge: a tangent. The radius to the touching point meets that course at 90°.",
        expr=f"t² + {r}² = {d}²",
        ask="How far must she steam along the tangent to reach the touching point?",
        choices=_numeric_choices(ctx, t, [
            (d - r, f"You took the radius straight off the distance. The tangent is a side of a right triangle: √({d}² − {r}²)."),
            (_jround(math.sqrt(d * d + r * r)), f"You added the squares, but the line to the centre is the longest side. Take {r}² away from {d}²."),
            (t * t, f"That's {d}² − {r}² = {t * t}. You forgot the last step: take the square root."),
            (t * t / 2, f"You halved {t * t}. To undo the squaring, take the square root instead."),
            (d + r, f"You added {d} and {r}. The tangent is a side of a right triangle: √({d}² − {r}²)."),
            (d, f"That's the distance to the centre, the longest side. The tangent is shorter: √({d}² − {r}²)."),
            (r, "That's the radius, from the centre to the touching point. The tangent runs from the ship to that point."),
        ]),
        solution=[
            f"The radius meets the tangent at 90°, so the {d} nm line to the centre is the hypotenuse.",
            f"{d}² − {r}² = {d * d} − {r * r} = {t * t}.",
            f"√{t * t} = {t} nm.",
        ],
        hint="The line to the centre is the hypotenuse. Square it, take away the radius squared, then take the square root.",
        fig=_fig("tangents", op=_gv(f"{d} nm"), ot=_gv(f"r = {r} nm"), pt=_ak("?"), right=True, marks=_YOU_AT_P),
    )


@gen("circ", 2)
def tangent_segments(ctx: Context) -> Problem:
    me, en = ctx.my_name, ctx.enemy_name
    while True:
        a1, k, x, b1 = ctx.rand(1, 4), ctx.rand(1, 3), ctx.rand(2, 9), ctx.rand(1, 15)
        c = k * x - b1  # PB = (a1 + k)x − c
        if c > 0:
            break
    a2 = a1 + k
    L = a1 * x + b1
    pa, pb = _lin(a1, b1), _lin(a2, -c)
    swapped = b1 - c  # moving the − c across without flipping its sign: kx = b1 − c
    added = b1 + c  # a1 + a2 would divide this if the x terms were added
    solve = f"{added} = {_lin(k, 0)}" + (f", so x = {added} ÷ {k} = {x}." if k > 1 else ".")
    return _problem(
        help="tanseg",
        story=f"Two courses from {me} (call her P) just graze {en}'s circular shield, one on each side, touching it at A and at B. The fire-control computer gives the two tangent runs as PA = {pa} nm and PB = {pb} nm.",
        expr=f"{pa} = {pb}",
        note="two tangents from the same point are equal",
        ask="How long is each tangent run, in nm?",
        choices=_numeric_choices(ctx, L, [
            (x, f"That's x = {x}. Put it back into PA = {pa} to get the length."),
            (2 * L, "You added PA and PB. The two runs are equal, so each one is just PA."),
            (a1 * swapped // k + b1, f"You moved the {c} across without changing its sign. {pa} = {pb} gives {_lin(k, 0)} = {b1} + {c}.")
            if swapped > 0 and swapped % k == 0 else None,
            (a1 * added // (a1 + a2) + b1, f"You added the x terms. Take {_lin(a1, 0)} from both sides: {_lin(k, 0)} = {added}.")
            if added % (a1 + a2) == 0 else None,
            (a1 * added + b1, f"You forgot to divide by {k}: {_lin(k, 0)} = {added}, so x = {x}.") if k > 1 else None,
            (a2 * x + c, f"You dropped the minus sign in PB: {a2} × {x} − {c} = {L}."),
            (a1 * x, f"You left off the + {b1} in PA = {pa}."),
            (a2 * x, f"You left off the − {c} in PB = {pb}."),
        ]),
        solution=[
            f"Two tangents from the same point are equal: {pa} = {pb}.",
            f"Take {_lin(a1, 0)} from both sides and add {c} to both: {solve}",
            f"PA = {a1} × {x} + {b1} = {L} nm. Check: PB = {a2} × {x} − {c} = {L} ✓",
        ],
        hint="Two tangents from the same ship are the same length. Set PA = PB, solve for x, then put x back in.",
        fig=_fig("tangents", two=True, radii=False, pt=_gv(f"PA = {pa}"), pt2=_gv(f"PB = {pb}"), marks={"P": {"kind": "you", "label": "P"}}),
    )


# ===========================================================================
# Missile problems (hard mode, tier 3). Multi-step, or the formula is not
# spelled out. Diagrams only where they don't give the intermediate step away.
# ===========================================================================

# ---------------- Lookout · Angles (missiles) ----------------


@gen("ang", 3)
def hard_relative_bearing_after_turn(ctx: Context) -> Problem:
    me, en = ctx.my_name, ctx.enemy_name
    H = ctx.rand(0, 35) * 10
    R = ctx.pick([20, 30, 45, 60, 90, 120, 135, 150, 210, 225, 240, 270, 300, 315, 330])
    T = _deg360(H + R)
    d = ctx.pick([10, 20, 30, 45, 60, 90])
    side = ctx.pick(["starboard", "port"])
    stbd = side == "starboard"
    H2 = _deg360(H + d if stbd else H - d)
    ans = _deg360(T - H2)
    return _problem(
        help="bearing",
        story=f'{me} is on course {_pad3(H)} when the lookout reports {en} bearing {R}° relative. The captain orders "come {side} {d} degrees". {en} holds her position while you turn. Relative bearings are measured clockwise from your own bow.',
        expr=f"true = {_pad3(H)} + {R}°",
        note=f"new course = {_pad3(H)} {_pm(side)} {d}° · new relative = true − new course",
        ask="After the turn, what is her new relative bearing?",
        choices=_string_choices(ctx, f"{ans}°", [
            (f"{_deg360(R + d if stbd else R - d)}°",
             f"You {'added' if stbd else 'took away'} the turn. Turning {side} swings your bow toward {'higher' if stbd else 'lower'} bearings, "
             f"so her relative bearing goes {'down' if stbd else 'up'} by {d}°."),
            (f"{T}°", f"That's her true bearing. Relative bearing = true bearing − your new course, {_pad3(H2)}."),
            (f"{H2}°", "That's your new course. Her relative bearing = her true bearing − your new course."),
            (f"{R}°", "That's her old relative bearing. When you turn, your bow moves, so her relative bearing changes."),
            (f"−{H2 - T}°", f"That's {T} − {H2}, which is below zero. Add 360 to get a bearing.") if T < H2 else None,
            (f"{T - H2 + 360}°", f"That's {T} − {H2} + 360. Only add 360 when the answer goes below zero.") if T >= H2 else None,
            (f"{_deg360(H2 - T)}°", f"That's {H2} − {T}{' + 360' if H2 < T else ''}: you took the true bearing away from the course. Relative = true − course."),
            (f"{_deg360(T + H2)}°", "You added her true bearing and your course. Relative bearing = true bearing − course."),
        ]),
        solution=[
            f"Her true bearing is {H} + {R} = {_pad3(T)}, and your turn does not change that.",
            f"Your new course is {H} {_pm(side)} {d} = {_pad3(H2)}.",
            f"Relative = true − course = {T} − {H2}{' + 360' if T - H2 < 0 else ''} = {ans}°.",
        ],
        hint="Find her true bearing first (it doesn't change when you turn). Then find your new course. Relative = true − course; add 360 if that goes negative.",
        fig=_fig("compass", course=H2,
                 rays=[{"deg": H, "label": f"old {_pad3(H)}", "dash": True, "c": "dim"},
                       {"deg": H2, "label": f"new {_pad3(H2)}", "c": "given"},
                       {"deg": T, "label": "contact", "c": "ask", "mark": "target"}],
                 arcs=[{"from": H2, "to": H2 + ans, "label": "?", "c": "ask"}]),
    )


@gen("ang", 3)
def hard_related_triangle_angles(ctx: Context) -> Problem:
    me, en = ctx.my_name, ctx.enemy_name
    e = _escort(ctx)
    marks = [{"kind": "you", "label": "you"}, {"kind": "escort", "label": "escort"}, {"kind": "target"}]
    if ctx.rand(0, 1):
        while True:
            C = ctx.rand(30, 120)
            if (180 - C) % 3 == 0:
                break
        x = (180 - C) // 3
        return _problem(
            help="trisum",
            story=f"On the plot {me}, the escort {e} and {en} make a triangle. The angle at {en} is {C}°, and the angle at {me} is exactly twice the angle at the escort.",
            expr=f"2x + x + {C}° = 180°",
            ask=f"What is the angle at {me}?",
            choices=_numeric_choices(ctx, 2 * x, [
                (x, f"That's x, the escort's angle. Yours is twice that: 2 × {x}."),
                (180 - C, f"That's 180 − {C}, what the other two angles share. They're x and 2x, so split it into 3 parts."),
                ((180 - C) / 2, f"You split {180 - C} in half, but the two angles are x and 2x, not equal. 3x = {180 - C}."),
                (120, f"You forgot the {C}° angle: 2x + x + {C} = 180, not 2x + x = 180."),
                (2 * (360 - C) / 3, "You used 360°, but the three angles of a triangle add to 180°."),
                (4 * x, f"You doubled twice. x = {x}, and your angle is 2x."),
            ]),
            solution=["Call the escort's angle x. Then yours is 2x.", f"x + 2x + {C} = 180, so 3x = {180 - C} and x = {x}.", f"Your angle is 2 × {x} = {2 * x}°."],
            hint="Call the small angle x and the big one 2x. All three add to 180. Solve for x, then double it.",
            fig=_fig("triangle", apex=120, angles=[_ak("2x"), _ak("x"), _gv(f"{C}°")], marks=marks),
        )
    while True:
        C = ctx.rand(30, 110)
        k = ctx.pick([10, 20, 30, 40])
        if (180 - C - k) % 2 == 0:
            break
    x = (180 - C - k) // 2
    if ctx.rand(0, 1):
        return _problem(
            help="trisum",
            story=f"{me}, the escort {e} and {en} make a triangle on the plot. The angle at {en} is {C}°, and the angle at {me} is {k}° bigger than the angle at the escort.",
            expr=f"(x + {k}°) + x + {C}° = 180°",
            ask=f"What is the angle at {me}?",
            choices=_numeric_choices(ctx, x + k, [
                (x, f"That's x, the escort's angle. Yours is {k}° bigger: x + {k}."),
                ((180 - C) / 2, f"You split {180 - C} in half, but the two angles aren't equal: yours is {k}° bigger."),
                ((180 - C) / 2 + k, f"You halved {180 - C}, then added {k}. Take the {k} away first: 2x = {180 - C} − {k}."),
                (180 - C - k, f"That's 2x = {180 - C - k}. Halve it for x, then add {k} for your angle."),
                ((180 - k) / 2 + k, f"You forgot the {C}° angle. All three angles add to 180: x + (x + {k}) + {C}."),
                (180 - C, f"That's 180 − {C}, what your angle and the escort's share. Split it: x + (x + {k}) = {180 - C}."),
            ]),
            solution=[f"Call the escort's angle x. Yours is x + {k}.", f"x + (x + {k}) + {C} = 180, so 2x = {180 - C - k} and x = {x}.",
                      f"Your angle is {x} + {k} = {x + k}°."],
            hint=f"Call the escort's angle x, so yours is x + {k}. Add all three to 180, solve for x, then add {k}.",
            fig=_fig("triangle", apex=120, angles=[_ak(f"x + {k}°"), _ak("x"), _gv(f"{C}°")], marks=marks),
        )
    return _problem(
        help="trisum",
        story=f"{me}, the escort {e} and {en} make a triangle on the plot. The angle at {en} is {C}°, and the angle at {me} is {k}° bigger than the angle at the escort.",
        expr=f"(x + {k}°) + x + {C}° = 180°",
        ask="What is the angle at the escort?",
        choices=_numeric_choices(ctx, x, [
            (x + k, f"That's your angle, x + {k}. The escort's is {k}° less."),
            ((180 - C) / 2, f"You split {180 - C} in half, but you're {k}° bigger than the escort. Take the {k} away first."),
            (180 - C - k, "That's 2x. Halve it to get x."),
            ((180 - C) // 2 - k, f"You halved {180 - C}, then took away all {k}. Take the {k} away before you halve.") if (180 - C) % 2 == 0 else None,
            ((180 - k) / 2, f"You forgot the {C}° angle. All three angles add to 180: x + (x + {k}) + {C}."),
            ((180 - C - k) / 3, f"You divided by 3, but there are only two x's: x + (x + {k}). Divide {180 - C - k} by 2."),
        ]),
        solution=[f"Call the escort's angle x. Yours is x + {k}.", f"x + (x + {k}) + {C} = 180, so 2x = {180 - C - k}.", f"x = {x}°."],
        hint=f"Call the escort's angle x, so yours is x + {k}. Add all three to 180 and solve.",
        fig=_fig("triangle", apex=120, angles=[_ak(f"x + {k}°"), _ak("x"), _gv(f"{C}°")], marks=marks),
    )


@gen("ang", 3)
def hard_polygons(ctx: Context) -> Problem:
    me = ctx.my_name
    if ctx.rand(0, 1):
        n = ctx.pick([5, 6, 8, 9, 10, 12, 15, 18, 20])
        int_ = (n - 2) * 180 / n
        ext = 360 / n
        return _problem(
            help="poly",
            story=f"The armoured conning tower on {me} is a regular polygon, but the drawing is torn and you can't count the sides. The shipwright measures every interior corner at {_js(int_)}°.",
            expr=f"exterior = 180° − {_js(int_)}°",
            note="n = 360° ÷ exterior",
            ask="How many sides does the tower have?",
            choices=_numeric_choices(ctx, n, [
                (ext, f"That's the exterior angle. The number of sides is 360 ÷ {_js(ext)}."),
                (n / 2, f"You divided 180 by the exterior angle. The exterior angles go all the way round: 360 ÷ {_js(ext)}."),
                (n - 2, f"You took 2 away, like in the (n − 2) × 180 rule. Here n is just 360 ÷ {_js(ext)}."),
                (360 - int_, f"That's 360 − {_js(int_)}. The exterior angle is 180 − {_js(int_)}; then divide 360 by it."),
                (_jround(360 / int_), f"You divided 360 by the interior angle. Use the exterior angle: 360 ÷ {_js(ext)}.") if _is_int(360 / int_) else None,
            ]),
            solution=[f"Each exterior angle is 180 − {_js(int_)} = {_js(ext)}°.", f"The exterior angles of any polygon add to 360°, so n = 360 ÷ {_js(ext)} = {n}."],
            hint="Find the exterior angle (180 minus the interior). Exterior angles always add to 360, so divide.",
        )
    n = ctx.pick([4, 5, 6])
    total = (n - 2) * 180
    names = {4: "four", 5: "five", 6: "six"}
    while True:
        angs = [ctx.rand(6, 15) * 10 for _ in range(n - 1)]
        s = sum(angs)
        ans = total - s
        if not (ans < 40 or ans > 170):
            break
    return _problem(
        help="poly",
        story=f"The splinter shield around a gun tub on {me} is a {names[n]}-sided plate, and not a regular one. The shipwright measured {n - 1} of its corners: {', '.join(f'{a}°' for a in angs)}. The last corner is smudged on the drawing.",
        expr=f"({n} − 2) × 180° = {total}°",
        note=f"{' + '.join(str(a) for a in angs)} + x = {total}",
        ask="What is the missing corner angle?",
        choices=_numeric_choices(ctx, ans, [
            (180 - ans, f"That's 180 − {ans}, the turn outside that corner. The corner itself is {total} − {s}."),
            (n * 180 - s, f"You used {n} × 180 for the total. It's ({n} − 2) × 180 = {total}."),
            ((n - 1) * 180 - s, f"You took 1 from {n} instead of 2. The total is ({n} − 2) × 180 = {total}."),
            (total // n, f"That's {total} ÷ {n}, a corner of a regular shape. This plate isn't regular, so subtract the known corners."),
            ((n - 3) * 180 - s, f"You took 3 from {n} instead of 2. The total is ({n} − 2) × 180 = {total}."),
            (360 - s, f"You used 360°, but that's only for four-sided shapes. A {n}-sided shape's corners add to {total}°.") if n != 4 else None,
            (s, f"That's the corners you know, added up. Take them away from {total}."),
            (ans + angs[0], f"You left out the {angs[0]}° corner when you added up the ones you know."),
            (ans - angs[-1], f"You counted the {angs[-1]}° corner twice when you added up the ones you know."),
        ]),
        solution=[f"A {names[n]}-sided shape's angles add to ({n} − 2) × 180 = {total}°.", f"The known corners add to {s}.", f"{total} − {s} = {ans}°."],
        hint="Angles inside an n-sided shape add to (n − 2) × 180. Add the corners you know and subtract.",
    )


@gen("ang", 3)
def hard_zigzag_parallel(ctx: Context) -> Problem:
    me = ctx.my_name
    t1 = ctx.rand(4, 12) * 5
    t2 = ctx.pick([x * 5 for x in range(4, 13) if x * 5 != t1])  # two different angles, so each mistake shows as its own number
    inner = 180 - t1 - t2
    turn = t1 + t2
    story = f"Two convoy columns steam on parallel tracks. {me} leaves the first column on a zig leg that cuts across it at {t1}°, reaches the second column, and comes straight back on a zag leg that meets the first column again at {t2}°."
    if ctx.rand(0, 1):
        return _problem(
            help="parallel", story=story,
            expr=f"alternate angles at the second column: {t1}° and {t2}°",
            note="the two legs and the column make a straight line",
            ask="At the turning point on the second column, what is the angle between the two legs?",
            choices=_numeric_choices(ctx, inner, [
                (turn, f"That's {t1} + {t2}, the turn the ship makes. The angle between the legs is what's left of 180°."),
                (180 - t1, f"That's 180 − {t1}: you forgot to take away the {t2}° too."),
                (180 - t2, f"That's 180 − {t2}: you forgot to take away the {t1}° too."),
                (360 - turn, "You used 360°. The three angles along the column make a straight line, 180°."),
                (90 - turn, "You used 90°. The three angles along the column make a straight line, 180°.") if turn < 90 else None,
                (abs(t1 - t2), f"You subtracted {min(t1, t2)} from {max(t1, t2)}. Take both angles away from 180.") if t1 != t2 else None,
            ]),
            solution=[
                f"Where the legs meet the second column, the alternate (Z-shape) angles are {t1}° and {t2}°.",
                f"Those two plus the angle between the legs make a straight line: 180 − {t1} − {t2} = {inner}°.",
                "Check: it is also the third angle of the triangle the legs make with the first column.",
            ],
            hint="Copy the two angles across to the second column using Z shapes. The three angles along that column add to 180.",
            fig=_fig("triangle", apex=150, angles=[_gv(f"{t1}°"), _gv(f"{t2}°"), _ak("?")],
                     marks=[{"kind": "you", "label": "leave"}, {"kind": "you", "label": "return"}]),
        )
    return _problem(
        help="parallel", story=story,
        expr=f"angle between the legs = 180° − {t1}° − {t2}°",
        note="turn = 180° − that",
        ask="How many degrees does the helm turn the ship through at the second column to come back?",
        choices=_numeric_choices(ctx, turn, [
            (inner, "That's the angle between the two legs. The turn swings the ship round the outside: 180 minus that."),
            (t1, f"You only counted the {t1}°. The turn is 180 − the angle between the legs, which is {t1} + {t2}."),
            (t2, f"You only counted the {t2}°. The turn is 180 − the angle between the legs, which is {t1} + {t2}."),
            (360 - turn, "That's 360 − the turn, all the way round the other way. The turn is 180 − the angle between the legs."),
            (180 + inner, "You added 180 instead of taking the angle away from it. The turn is 180 − the angle between the legs."),
            (abs(t1 - t2), f"You subtracted {min(t1, t2)} from {max(t1, t2)}. The turn is {t1} + {t2}.") if t1 != t2 else None,
        ]),
        solution=[
            f"The angle between the two legs is 180 − {t1} − {t2} = {inner}°.",
            f"Swinging from one leg onto the other is the outside of that angle: 180 − {inner} = {turn}°.",
        ],
        hint="First find the angle between the legs (180 minus both given angles). The turn is 180 minus that.",
    )


# ---------------- Plot · Triangles (missiles) ----------------


@gen("tri", 3)
def hard_pythagoras_after_move(ctx: Context) -> Problem:
    me, en = ctx.my_name, ctx.enemy_name
    a, b, c = _triple(ctx)
    x = ctx.pick([2, 3, 4, 5, 6, 8, 10])
    east = ctx.rand(0, 1)
    e0 = a + x if east else a
    n0 = b if east else b + x
    way = "east" if east else "north"
    return _problem(
        help="pyth",
        story=f"The plot puts {en} {e0} nm east and {n0} nm north of {me}. Before the turrets are ready, {me} steams {x} nm due {'east' if east else 'north'} and stops. {en} has not moved.",
        expr=f"({e0}{' − ' + str(x) if east else ''}){sup(2)} + ({n0}{'' if east else ' − ' + str(x)}){sup(2)} = r{sup(2)}",
        ask="What is the range after the move?",
        choices=_numeric_choices(ctx, c, [
            (_jround(math.hypot(e0, n0)), f"That's about the range before you moved. Take the {x} nm off the {way} distance first."),
            (a + b, f"You added the new distances, {a} + {b}. Square them, add, then take the square root."),
            (c + x, f"You added the {x} nm you steamed to the range. Moving {way} changes one leg; redo Pythagoras with it."),
            (_jround(math.hypot(e0, n0)) - x, f"You took the {x} nm straight off the old range. It only shortens the {way} leg, so redo Pythagoras."),
            (_jround(math.hypot(e0 + x, n0) if east else math.hypot(e0, n0 + x)),
             f"You added the {x} nm, but steaming toward her makes the {way} distance shorter: take it away."),
            (a if east else b, f"That's only the new {way} distance. The range is the slanted side: use Pythagoras."),
            (c * c, f"That's {a}² + {b}² = {c * c}. You forgot the last step: take the square root."),
        ]),
        solution=[
            f"After the move she is {a} nm east and {b} nm north ({f'{e0} − {x}' if east else f'{n0} − {x}'} = {a if east else b}).",
            f"{a}² + {b}² = {a * a} + {b * b} = {c * c}.",
            f"√{c * c} = {c} nm.",
        ],
        hint="Work out the new east and north distances first, then use Pythagoras on those.",
        fig=_fig("right_tri", ratio=b / a, adj=_lab("east, after the move", "dim"), opp=_lab("north, after", "dim"), hyp=_ak("range ?"), marks={"P": _you(), "Q": _tgt()}),
    )


@gen("tri", 3)
def hard_nearer_escort(ctx: Context) -> Problem:
    me = ctx.my_name
    a1, b1, c1 = ctx.pick([t for t in TRIPLES if t[2] <= 20])
    while True:
        t2 = ctx.pick([t for t in TRIPLES if t[2] <= 26])
        if t2[2] != c1:
            break
    a2, b2, c2 = t2
    x0 = ctx.rand(10, 15)
    y0 = ctx.rand(10, 15)
    e1 = _escort(ctx)
    e2 = _other_escort(ctx, e1)
    p1 = [x0 + ctx.pick([-1, 1]) * a1, y0 + ctx.pick([-1, 1]) * b1]
    p2 = [x0 + ctx.pick([-1, 1]) * a2, y0 + ctx.pick([-1, 1]) * b2]
    near = e1 if c1 < c2 else e2
    ans = abs(c1 - c2)
    return _problem(
        help="dist",
        story=f"{me} is at ({x0}, {y0}) on the plot. Escort {e1} is at ({_signed(p1[0])}, {_signed(p1[1])}) and escort {e2} is at ({_signed(p2[0])}, {_signed(p2[1])}). Each grid square is one nautical mile. The commodore wants the nearer escort to close with you.",
        expr=f"d = √((Δx){sup(2)} + (Δy){sup(2)}) for each escort",
        note="then subtract the two distances",
        ask=f"{near} is the nearer one. How many nautical miles nearer is she than the other escort?",
        choices=_numeric_choices(ctx, ans, [
            (min(c1, c2), f"That's how far {near} is from you. The question asks how much nearer she is: subtract the two distances."),
            (max(c1, c2), f"That's how far the other escort is from you. The question asks how much nearer {near} is: subtract."),
            (c1 + c2, "You added the two distances. \"How much nearer\" means take one from the other."),
            (abs((a1 + b1) - (a2 + b2)), "You added Δx and Δy for each escort instead of using Pythagoras.") if a1 + b1 != a2 + b2 else None,
            (abs(c1 * c1 - c2 * c2), "You subtracted the squared distances. Take each square root first, then subtract."),
            (_jround(math.hypot(p1[0] - p2[0], p1[1] - p2[1])), "That's about how far apart the two escorts are. You want the difference of their distances from you."),
            (abs(a1 - a2), "You only compared the east-west gaps (Δx). Use Pythagoras for each escort's full distance first.") if a1 != a2 else None,
            (abs(b1 - b2), "You only compared the north-south gaps (Δy). Use Pythagoras for each escort's full distance first.") if b1 != b2 else None,
        ]),
        solution=[
            f"{e1}: Δx = {a1}, Δy = {b1}. √({a1 * a1} + {b1 * b1}) = √{c1 * c1} = {c1} nm.",
            f"{e2}: Δx = {a2}, Δy = {b2}. √({a2 * a2} + {b2 * b2}) = √{c2 * c2} = {c2} nm.",
            f"{max(c1, c2)} − {min(c1, c2)} = {ans} nm.",
        ],
        hint="Use the distance formula twice, once for each escort, then subtract the two distances.",
    )


@gen("tri", 3)
def hard_scale_then_pythagoras(ctx: Context) -> Problem:
    me, en = ctx.my_name, ctx.enemy_name
    k = ctx.pick([2, 4, 5, 10])
    a, b, c = ctx.pick([t for t in TRIPLES if t[2] <= 13])
    return _problem(
        help="scale",
        story=f"The plotting sheet is drawn at 1 cm = {k} nm. On paper, {en} is {a} cm east and {b} cm north of {me}.",
        expr=f"paper range = √({a}{sup(2)} + {b}{sup(2)})",
        note=f"real range = paper × {k}",
        ask="What is the real range in nautical miles?",
        choices=_numeric_choices(ctx, c * k, [
            (c, f"That's the length on paper, {c} cm. Multiply by {k} to get nautical miles."),
            ((a + b) * k, f"You added the two sides, {a} + {b}. Use Pythagoras on paper first, then scale."),
            (c + k, f"You added the scale. Every centimetre is {k} nm, so multiply."),
            (c * c * k, f"You forgot the square root: √{c * c} = {c} cm on paper, then × {k}."),
            (c / k, f"You divided by the scale. Paper to sea means multiply: {c} × {k}."),
            (a * k + b, f"You only scaled one side. Find the paper length first ({c} cm), then multiply it by {k}."),
        ]),
        solution=[f"On paper: {a}² + {b}² = {a * a} + {b * b} = {c * c}, so the line is √{c * c} = {c} cm.", f"Every centimetre is {k} nm: {c} × {k} = {c * k} nm."],
        hint="Find the length of the line on paper with Pythagoras, then multiply by the scale.",
        fig=_fig("right_tri", ratio=b / a, adj=_gv(f"{a} cm east"), opp=_gv(f"{b} cm north"), hyp=_ak("range ? nm"), marks={"P": _you(), "Q": _tgt()},
                 note=f"1 cm on the plot = {k} nm"),
    )


@gen("tri", 3)
def hard_similar_backwards(ctx: Context) -> Problem:
    a, b, c = ctx.pick([t for t in TRIPLES if t[2] <= 17])
    k = ctx.pick([2, 3, 4, 5])
    which, want, other = ("shortest", a, b) if ctx.rand(0, 1) else ("middle", b, a)
    big = want * k
    return _problem(
        help="scale",
        story=f"The plotting officer draws two similar triangles. The big one has sides {a * k}, {b * k} and {c * k} nm. The small one's longest side is {c} nm.",
        expr=f"scale factor = {c * k} ÷ {c}",
        note="small side = big side ÷ factor",
        ask=f"What is the small triangle's {which} side?",
        choices=_numeric_choices(ctx, want, [
            (other, f"That's the small triangle's {'middle' if which == 'shortest' else 'shortest'} side. Scale down the {which} one: {big} ÷ {k}."),
            (big - (c * k - c), f"You took away {c * k - c}, the gap between {c * k} and {c}. Similar shapes shrink by dividing: ÷ {k}."),
            (big / c, f"You divided by {c}. Divide by the scale factor instead: {c * k} ÷ {c} = {k}."),
            (big * k, "You multiplied by the scale factor. The small triangle is smaller, so divide."),
            (big, f"That's the big triangle's {which} side. Divide it by the scale factor, {k}."),
            (big - k, f"You took {k} away. Divide by the scale factor, {k}, instead."),
            (k, f"That's the scale factor. Now divide the big triangle's {which} side by it: {big} ÷ {k}."),
            (c, f"That's the small triangle's longest side, which you were given. You want the {which} side."),
        ]),
        solution=[f"Match the longest sides: {c * k} ÷ {c} = {k}, so the big triangle is {k} times the small one.", f"{which.capitalize()} side: {big} ÷ {k} = {want} nm."],
        hint=f"Compare the two longest sides to get the scale factor, then divide the big triangle's {which} side by it.",
    )


@gen("tri", 3)
def hard_special_right_backwards(ctx: Context) -> Problem:
    me, en = ctx.my_name, ctx.enemy_name
    s = ctx.pick([2, 3, 4, 5, 6, 8, 10, 12])
    if ctx.rand(0, 1):
        return _problem(
            help="sqdiag",
            story=f"{me} patrols a square box. Cutting straight across from corner to corner is {2 * s} nm. The captain wants to know how long each side of the box is.",
            expr=f"leg × √2 = {2 * s}",
            note=f"leg = {2 * s} ÷ √2",
            ask="How long is each side of the box?",
            choices=_string_choices(ctx, f"{s}√2 nm", [
                (f"{s} nm", "You halved the diagonal. The diagonal is a side × √2, so divide by √2 instead."),
                (f"{2 * s}√2 nm", "You multiplied by √2. To go from the diagonal back to a side, divide by √2."),
                (f"{s}√3 nm", "√3 is for 30-60-90 triangles. A square's diagonal is a side × √2."),
                (f"{2 * s * s} nm", f"That's {2 * s}² ÷ 2 = {2 * s * s}, which is side². Take the square root."),
                (f"{2 * s} nm", "That's the diagonal itself. Each side is shorter: the diagonal ÷ √2."),
                (f"{4 * s * s} nm", f"You squared the diagonal: {2 * s}² = {4 * s * s}. Halve that for side², then take the square root."),
                (f"{math.isqrt(2 * s)} nm" if math.isqrt(2 * s) ** 2 == 2 * s else f"√{2 * s} nm",
                 f"You took the square root of the diagonal. Divide it by √2 instead: {2 * s} ÷ √2."),
            ]),
            solution=[
                "In a 45-45-90 triangle, hypotenuse = leg × √2.",
                f"leg = {2 * s} ÷ √2. Multiply top and bottom by √2: {2 * s}√2 ÷ 2 = {s}√2 nm (about {_js(_round1(s * 1.414))} nm).",
            ],
            hint="Divide the diagonal by √2, then tidy up: dividing by √2 is the same as multiplying by √2 and halving.",
            fig=_fig("right_tri", ratio=1, adj=_ak("side ?"), opp=_ak("side ?"), hyp=_gv(f"{2 * s} nm"), ang=_lab("45°"), ang2=_lab("45°"), marks={"P": _you()}),
        )
    return _problem(
        help="tri30",
        story=f"{en} is 30° off the bow at a range of {2 * s} nm. You need the distance ahead along your track: the side across from the 60° angle, which is not half the range.",
        expr=f"short leg = {2 * s} ÷ 2",
        note="long leg = short leg × √3",
        ask="How far ahead along your track is she?",
        choices=_string_choices(ctx, f"{s}√3 nm", [
            (f"{s} nm", "That's the short side, across from 30°. The side across from 60° is the short side × √3."),
            (f"{2 * s}√3 nm", "You multiplied the range by √3. Start from the short side, half the range, then × √3."),
            (f"{s}√2 nm", "√2 is for 45-45-90 triangles. Across from 60° it's the short side × √3."),
            (f"{3 * s * s} nm", f"That's {2 * s}² − {s}² = {3 * s * s}. Take the square root: √{3 * s * s} = {s}√3."),
            (f"{s}√5 nm", f"You added the squares, but the range is the longest side. Take them away: {2 * s}² − {s}²."),
            (f"{2 * s} nm", "That's the range, the longest side. The side across from 60° is shorter: half the range × √3."),
        ]),
        solution=[
            f"Across from 30° is half the hypotenuse: {2 * s} ÷ 2 = {s} nm.",
            f"Across from 60° is the short leg × √3: {s}√3 nm (about {_js(_round1(s * 1.732))} nm).",
        ],
        hint="Find the short leg first (half the range). The long leg is the short leg times √3.",
        fig=_fig("right_tri", deg=30, hyp=_gv(f"range {2 * s} nm"), adj=_ak("?"), opp=_lab("short leg", "dim"), ang=_lab("30°"), ang2=_lab("60°"), marks={"P": _you(), "Q": _tgt()}),
    )


@gen("tri", 3)
def hard_midpoint_backwards(ctx: Context) -> Problem:
    me = ctx.my_name
    x1 = ctx.rand(0, 10)
    y1 = ctx.rand(0, 10)
    mx = x1 + ctx.rand(1, 6)
    my = y1 + ctx.rand(1, 6)
    x2 = 2 * mx - x1
    y2 = 2 * my - y1
    e1 = _escort(ctx)
    e2 = _other_escort(ctx, e1)
    return _problem(
        help="mid",
        story=f"{me} is stationed at ({mx}, {my}), exactly halfway between two escorts. Escort {e1} is at ({x1}, {y1}). The other escort, {e2}, has gone silent and the plot has lost her.",
        expr=f"({x1} + x) ÷ 2 = {mx}",
        note=f"({y1} + y) ÷ 2 = {my}",
        ask=f"Where is {e2}?",
        choices=_string_choices(ctx, f"({x2}, {y2})", [
            (f"({2 * mx}, {2 * my})", f"You doubled your position but forgot to take away {e1}'s: 2 × {mx} − {x1}."),
            (f"({mx + x1}, {my + y1})", f"You added {e1}'s position to yours. Double yours, then take hers away: 2 × {mx} − {x1}."),
            (f"({mx - x1}, {my - y1})", f"That's the step from {e1} to you. Add it on to your position to reach {e2}."),
            (f"({_js((x1 + mx) / 2)}, {_js((y1 + my) / 2)})", f"That's halfway between {e1} and you. {e2} is as far past you as {e1} is before you."),
            (f"({y2}, {x2})", "You swapped x and y. The x-coordinate comes first."),
            (f"({2 * mx + x1}, {2 * my + y1})", f"You added {e1}'s position instead of taking it away: 2 × {mx} − {x1}."),
            (f"({_signed(2 * x1 - mx)}, {_signed(2 * y1 - my)})", f"You stepped the wrong way, back past {e1}. Go from {e1} through you, then the same distance on."),
            (f"({_js(mx + (mx - x1) / 2)}, {_js(my + (my - y1) / 2)})", f"You went only half as far again. From {e1} to you is ({mx - x1}, {my - y1}); go that far again past you."),
        ]),
        solution=[
            "The midpoint is the average, so double it and take away the escort you know.",
            f"x: 2 × {mx} − {x1} = {x2}. y: 2 × {my} − {y1} = {y2}.",
            f"She is at ({x2}, {y2}).",
        ],
        hint="Going from the known escort to the midpoint, keep going the same distance again.",
    )


@gen("tri", 3)
def hard_right_patrol_perimeter(ctx: Context) -> Problem:
    me = ctx.my_name
    a, b, c = _triple(ctx)
    return _problem(
        help="perim",
        story=f"{me} runs a right-angled patrol: {a} nm due east, a sharp turn, {b} nm due north, then straight back to the start along the diagonal.",
        expr=f"diagonal = √({a}{sup(2)} + {b}{sup(2)})",
        note=f"circuit = {a} + {b} + diagonal",
        ask="How long is the whole circuit?",
        choices=_numeric_choices(ctx, a + b + c, [
            (a + b, f"That's only the two legs you know. Add the way back too: √({a}² + {b}²) = {c}."),
            (2 * (a + b), f"You used {a} + {b} for the diagonal. It's √({a}² + {b}²), which is shorter."),
            (a + b + c * c, f"You forgot the square root on the diagonal: √{c * c} = {c}."),
            (a * b / 2, f"That's the area inside, ½ × {a} × {b}. The circuit is the distance round: add the three legs."),
            (c, f"That's just the way back. Add the {a} nm and {b} nm legs to it."),
            (a + b + abs(b - a), f"You used {max(a, b)} − {min(a, b)} for the diagonal. It's √({a}² + {b}²)."),
        ]),
        solution=[f"The last leg is the hypotenuse: {a}² + {b}² = {a * a + b * b}, and √{c * c} = {c} nm.", f"{a} + {b} + {c} = {a + b + c} nm."],
        hint="You only know two legs. Use Pythagoras for the third, then add all three.",
        fig=_fig("right_tri", ratio=b / a, adj=_gv(f"{a} nm east"), opp=_gv(f"{b} nm north"), hyp=_ak("back ?"), marks={"P": _you()}),
    )


# ---------------- Gunnery · Trig (missiles) ----------------


@gen("trig", 3)
def hard_trig_find_hypotenuse(ctx: Context) -> Problem:
    me, en = ctx.my_name, ctx.enemy_name
    th = ctx.pick([a for a in TRIG_ANGLES if 20 <= a <= 70])
    g = ctx.pick([5, 8, 10, 12, 15, 20, 24])
    marks = {"P": _you(), "Q": _tgt()}
    angL = _lab(f"{th}°")
    v = ctx.pick([
        {"fn": "sin", "known": "the side opposite the angle", "unit": "nm", "long": "range", "along": "the side along your track",
         "story": f"{en} is {g} nm off {me}'s track and bears {th}° off the bow. The fire-control table needs the straight-line range.",
         "ask": "What is the range, in nm? (Use the trig table.)",
         "fig": _fig("right_tri", deg=th, opp=_gv(f"{g} nm off track"), hyp=_ak("range ?"), adj=_lab("your track", "dim"), ang=angL, marks=marks)},
        {"fn": "cos", "known": "the side adjacent to the angle", "unit": "nm", "long": "range", "across": "the side off your track",
         "story": f"{en} is {g} nm ahead of {me} along the track and bears {th}° off the bow. The fire-control table needs the straight-line range.",
         "ask": "What is the range, in nm? (Use the trig table.)",
         "fig": _fig("right_tri", deg=th, adj=_gv(f"{g} nm ahead"), hyp=_ak("range ?"), opp=_lab("off track", "dim"), ang=angL, marks=marks)},
        {"fn": "sin", "known": "the side opposite the angle", "unit": "km", "long": "slant range", "along": "the distance along the horizon",
         "story": f"A patrol plane is flying {g} km up, and the lookout on {me} sees it {th}° above the horizon.",
         "ask": "What is the slant range to the plane, in km? (Use the trig table.)",
         "fig": _fig("right_tri", deg=th, opp=_gv(f"height {g} km"), hyp=_ak("slant ?"), adj=_lab("horizon", "dim"), ang=angL,
                     marks={"P": _you(), "Q": {"kind": "plane", "dx": 16, "dy": -12}})},
    ])
    fn, u, long_ = v["fn"], v["unit"], v["long"]
    val = _sin(th) if fn == "sin" else _cos(th)
    T = _tan(th)
    ans = _round1(g / val)
    divide = f"The {long_} is on the bottom of the ratio, so divide: {g} ÷ {_js(val)}."
    digits = (_round1(g / (th / 100)), f"You used {_js(th / 100)} for {fn} {th}°, but the angle isn't the ratio. The trig table gives {_js(val)}.")
    by_angle = (_round1(g / th), f"You divided by the angle itself, {th}. Divide by {fn} {th}° from the trig table, {_js(val)}.")
    if fn == "sin":
        pool: list[Mistake] = [
            (_round1(g * val), f"You multiplied by sin {th}°. {divide}"),
            (_round1(g / _cos(th)), f"You used cos, but the {g} {u} side is opposite the angle, so it's sin."),
            (_round1(g / T), f"That's {v['along']} (opposite ÷ tan). The {long_} is the slanted side: opposite ÷ sin."),
            (_round1(g * T), f"You multiplied by tan. The {long_} is the hypotenuse: opposite ÷ sin."),
            digits,
            by_angle,
        ]
    else:
        pool = [
            (_round1(g * val), f"You multiplied by cos {th}°. {divide}"),
            (_round1(g / _sin(th)), f"You used sin, but the {g} {u} side is next to the angle, so it's cos."),
            (_round1(g * T), f"That's {v['across']} (adjacent × tan). The {long_} is the slanted side: adjacent ÷ cos."),
            (_round1(g / T), f"You divided by tan. The {long_} is the hypotenuse: adjacent ÷ cos."),
            digits,
            by_angle,
        ]
    ch = _numeric_choices(ctx, ans, pool, dp="auto", avoid=[g / _exact(fn, th)])
    return _problem(
        help="trigside",
        story=v["story"],
        expr=f"{fn} {th}° = {g} ÷ hyp",
        note=f"so hyp = {g} ÷ {fn} {th}°",
        ask=v["ask"],
        choices=ch,
        solution=[
            f"You know {v['known']} and want the hypotenuse, so use {fn}: {fn} {th}° = {g} ÷ hyp.",
            f"From the trig table, {fn} {th}° ≈ {_js(val)}.",
            f"hyp = {g} ÷ {_js(val)} = {ch.texts[0]} {u}.",
        ],
        hint="Decide which side you know (opposite or adjacent) and look up the ratio in the trig table. The hypotenuse is on the bottom of the ratio, so you have to divide by the trig value, not multiply.",
        fig=v["fig"],
    )


@gen("trig", 3)
def hard_opposite_bows(ctx: Context) -> Problem:
    en = ctx.enemy_name
    th1 = ctx.pick([a for a in TRIG_ANGLES if a <= 60])
    th2 = ctx.pick([a for a in TRIG_ANGLES if a <= 60])
    R1 = ctx.pick([10, 15, 20, 25, 30])
    R2 = ctx.pick([10, 15, 20, 25, 30])
    e = _escort(ctx)
    S1, S2 = _sin(th1), _sin(th2)
    o1 = _round1(R1 * S1)
    o2 = _round1(R2 * S2)
    ans = _round1(o1 + o2)
    ch = _numeric_choices(ctx, ans, [
        (o1, f"That's only {en}'s distance off your track. Add the escort's too: they're on opposite sides."),
        (o2, f"That's only the escort's distance off your track. Add {en}'s too: they're on opposite sides."),
        (_round1(abs(o1 - o2)), "You subtracted, but one ship is to port and one to starboard, so add."),
        (_round1(R1 * _cos(th1) + R2 * _cos(th2)), "You used cos. The distance across your track is opposite each angle: range × sin."),
        (_round1(R1 * _tan(th1) + R2 * _tan(th2)), "You used tan. Each range is a hypotenuse, so use sin: opposite ÷ hypotenuse."),
        (R1 + R2, "You added the ranges. First find each ship's distance off your track (range × sin), then add."),
        (_round1(R1 / S1 + R2 / S2), "You divided by sin. The side across your track is on top of the ratio, so multiply."),
        (_round1(R1 * S2 + R2 * S1), "You paired each range with the other ship's angle. Use each ship's own range and angle.")
        if th1 != th2 and R1 != R2 else None,
    ], dp="auto", avoid=[R1 * _exact("sin", th1) + R2 * _exact("sin", th2)])
    return _problem(
        help="trigside",
        story=f"{en} bears {th1}° off the starboard bow at {R1} nm. The escort {e} bears {th2}° off the port bow at {R2} nm. The gunnery officer wants to know how far apart the two ships are, measured straight across your track from port to starboard.",
        expr=f"{R1} × sin {th1}° + {R2} × sin {th2}°",
        ask="How far apart are they across your track, in nm? (Use the trig table.)",
        choices=ch,
        solution=[
            "Each ship's distance off your track is the side opposite her angle: range × sin.",
            f"From the trig table, sin {th1}° ≈ {_js(S1)}" + (f" and sin {th2}° ≈ {_js(S2)}." if th2 != th1 else "."),
            f"{en}: {R1} × {_js(S1)} = {_js(o1)} nm to starboard. {e}: {R2} × {_js(S2)} = {_js(o2)} nm to port.",
            f"They are on opposite sides, so add: {_js(o1)} + {_js(o2)} = {ch.texts[0]} nm.",
        ],
        hint="Find how far each ship is off your track (range × sin of her angle, from the trig table). One is to port and one to starboard, so add the two.",
    )


@gen("trig", 3)
def hard_which_ratio(ctx: Context) -> Problem:
    me, en = ctx.my_name, ctx.enemy_name
    ok = False
    guard = 0
    th, fn, col, a, b, r = 37, "tan", 2, 15, 20, 0.75
    while not ok and guard < 80:
        guard += 1
        th = ctx.pick(TRIG_ANGLES)
        fn = ctx.pick(["sin", "cos", "tan"])
        col = 0 if fn == "sin" else 1 if fn == "cos" else 2
        b = ctx.pick([10, 20, 25, 40, 50])
        a = _jround(b * TRIG[th][col])
        r = math.floor(a / b * 100 + 0.5) / 100
        by_dist = sorted(TRIG_ANGLES, key=lambda p: abs(TRIG[p][col] - r))
        # (tan 80° = 5.67 is left out: every column you could misread lands on 10° or 80°.)
        ok = (a > 0 and by_dist[0] == th and abs(TRIG[th][col] - r) <= 0.015 and not (fn == "tan" and th == 80)
              and abs(TRIG[by_dist[1]][col] - r) - abs(TRIG[th][col] - r) >= 0.03)
    if not ok:
        th, fn, col, a, b, r = 37, "tan", 2, 15, 20, 0.75
    elev = fn == "tan" and bool(ctx.rand(0, 1))
    u = "m" if elev else "nm"
    marks = {"P": _you(), "Q": _tgt()}
    angL = _ak("θ = ?")
    if fn == "sin":
        story = f"{en} is {a} nm off your track and {b} nm away in a straight line. The turrets need her angle off the bow."
    elif fn == "cos":
        story = f"{en} is {a} nm ahead of {me} along the track and {b} nm away in a straight line. The turrets need her angle off the bow."
    elif elev:
        story = f"To lob a shell over a headland onto {en}, the shell has to climb {a} m over a horizontal run of {b} m. The gun captain needs the elevation angle."
    else:
        story = f"{en} is {a} nm off your track and {b} nm ahead along it. The turrets need her angle off the bow."
    lab = {"sin": ("opposite", "hypotenuse"), "cos": ("adjacent", "hypotenuse"), "tan": ("opposite", "adjacent")}[fn]
    if fn == "sin":
        fg = _fig("right_tri", ratio=1, note=_NOT_TO_SCALE, opp=_gv(f"{a} {u}"), hyp=_gv(f"{b} {u}"), ang=angL, marks=marks)
    elif fn == "cos":
        fg = _fig("right_tri", ratio=1, note=_NOT_TO_SCALE, adj=_gv(f"{a} {u}"), hyp=_gv(f"{b} {u}"), ang=angL, marks=marks)
    else:
        fg = _fig("right_tri", ratio=1, note=_NOT_TO_SCALE, opp=_gv(f"{a} {u}"), adj=_gv(f"{b} {u}"), ang=angL, marks={"P": _you(label="gun")} if elev else marks)
    return _problem(
        help="trigangle",
        story=story,
        expr=f"{fn} θ = {lab[0]} ÷ {lab[1]} = {a} ÷ {b}",
        ask="What is the angle θ, to the nearest angle in the trig table?",
        choices=_string_choices(ctx, f"{th}°", _angle_mistakes(fn, r, lab[0], lab[1], f"{b} ÷ {a}")),
        solution=[
            f'"{lab[0]}" and "{lab[1]}" are the two sides you were given, so this is {fn}.',
            f"{a} ÷ {b} ≈ {_js(r)}.",
            f"The closest value in the {fn} column of the trig table is {_js(TRIG[th][col])}, which is {th}°.",
        ],
        hint="Nobody told you which sides these are. Off the track = opposite, along the track = adjacent, straight-line = hypotenuse. Pick the ratio, divide, then find the nearest value in that column of the trig table.",
        fig=fg,
    )


@gen("trig", 3)
def hard_stadimeter_angle(ctx: Context) -> Problem:
    en = ctx.enemy_name
    H = _enemy_mast(ctx)
    th0 = ctx.pick([1, 2, 3, 4, 5])
    R = _jround(H / SMALL_TAN[th0] / 10) * 10
    r = math.floor(H / R * 1000 + 0.5) / 1000
    th = 1
    for q in (2, 3, 4, 5):
        if abs(SMALL_TAN[q] - r) < abs(SMALL_TAN[th] - r):
            th = q
    rng_ = _fmt_n(R, 0)
    closer = f"{_js(r)} is closest to tan {th}° = {_js(SMALL_TAN[th])}."
    return _problem(
        help="stadimeter",
        story=f"The rangefinder optics are fogged, but radar has {en} at {rng_} m and the manual lists her mast at {H} m. The stadimeter officer wants to know what angle the mast should fill, so he can check his instrument. Small-angle tangents: tan 1° ≈ 0.017, tan 2° ≈ 0.035, tan 3° ≈ 0.052, tan 4° ≈ 0.07, tan 5° ≈ 0.087.",
        expr=f"tan(angle) = {H} ÷ {rng_}",
        ask="What angle should the mast fill, to the nearest degree?",
        choices=_string_choices(ctx, f"{th}°", [
            (f"{th - 1}°", f"tan {th - 1}° is {_js(SMALL_TAN[th - 1])}, but {closer}") if th > 1 else None,
            (f"{th + 1}°", f"tan {th + 1}° is {_js(SMALL_TAN[th + 1])}, but {closer}") if th < 5 else None,
            (f"{th - 2}°", f"tan {th - 2}° is {_js(SMALL_TAN[th - 2])}, but {closer}") if th > 2 else None,
            (f"{th + 2}°", f"tan {th + 2}° is {_js(SMALL_TAN[th + 2])}, but {closer}") if th < 4 else None,
            (f"{90 - th}°", f"That's 90 − {th}, the angle up at the top of the mast. The stadimeter angle is the tiny one at your ship."),
            (f"{_js(round(r * 100, 1))}°", f"{_js(r)} is the tangent, not the angle. Find the small-angle tangent closest to {_js(r)}."),
            (f"{_js(r)}°", f"That's the tangent, {_js(r)}, not the angle. Find the small-angle tangent closest to it."),
        ]),
        solution=[
            f"tan(angle) = opposite ÷ adjacent = mast ÷ range = {H} ÷ {rng_} ≈ {_js(r)}.",
            f"The closest small-angle tangent is {_js(SMALL_TAN[th])}, so the mast fills {th}°.",
        ],
        hint="Divide the mast height by the range to get the tangent, then find the nearest small-angle tangent in the list.",
        fig=_fig("right_tri", ratio=0.32, adj=_gv(f"range {rng_} m"), opp=_gv(f"mast {H} m"), ang=_ak("?"), marks={"P": _you(), "Q": _tgt()},
                 note="not to scale — the real angle is tiny"),
    )


@gen("trig", 3)
def hard_lead_backwards(ctx: Context) -> Problem:
    """Every entry here has lead = range × tan exactly."""
    me, en = ctx.my_name, ctx.enemy_name
    c = ctx.pick(_LEAD_CASES)
    v, t, R, th = c["v"], c["t"], c["R"], c["th"]
    d = v * t
    rng_ = _fmt_n(R, 0)
    tan = _js(_tan(th))
    lead = f"The trig table gives tan {th}° ≈ {tan}, so the lead distance is {rng_} × {tan} = {d} m."
    exact_lead = R * _exact("tan", th)
    asks_time = bool(ctx.rand(0, 1))
    fig = _fig("right_tri", ratio=_tan(th), adj=_gv(f"range {rng_} m"), opp=_ak("lead ?"), ang=_gv(f"{th}°"),
               marks=_lead_marks(None if asks_time else t), note="lead distance first, then the time or speed")
    if asks_time:
        return _problem(
            help="lead",
            story=f"{en} is crossing your bow at {v} m/s at a range of {rng_} m. The gun director has set a lead angle of {th}° and reports the shells will land right on her.",
            expr=f"lead = {rng_} × tan {th}°",
            note=f"time = lead ÷ {v}",
            ask="How long are the shells in the air, in seconds? (Use the trig table.)",
            choices=_numeric_choices(ctx, t, [
                (d, f"That's the lead distance in metres. Time = distance ÷ speed: {d} ÷ {v}."),
                (_jround(R / v), f"You divided the range by her speed. Use the lead distance: {rng_} × tan {th}° = {d} m."),
                (d * v, f"You multiplied the lead by her speed. Time = distance ÷ speed: {d} ÷ {v}."),
                (_jround(R * _sin(th) / v), f"You used sin {th}° for the lead. The lead is range × tan: {rng_} × {tan}."),
                (_jround(R * _cos(th) / v), f"You used cos {th}° for the lead. The lead is range × tan: {rng_} × {tan}."),
                (_jround(R * th / 100 / v), f"You used {_js(th / 100)} for tan {th}°. Look it up in the trig table: it's {tan}."),
            ], avoid=[exact_lead / v]),
            solution=[lead, f"She covers {d} m at {v} m/s: {d} ÷ {v} = {t} s."],
            hint="Turn the lead angle back into a lead distance (range × tan, from the trig table), then time = distance ÷ speed.",
            fig=fig,
        )
    return _problem(
        help="lead",
        story=f"{en} is crossing your bow at a range of {rng_} m. {me}'s shells take {t} seconds to get there, and the director has set a lead angle of {th}° for a perfect hit.",
        expr=f"lead = {rng_} × tan {th}°",
        note=f"speed = lead ÷ {t}",
        ask="How fast is she moving, in m/s? (Use the trig table.)",
        choices=_numeric_choices(ctx, v, [
            (d, f"That's the lead distance in metres. Speed = distance ÷ time: {d} ÷ {t}."),
            (_jround(R / t), f"You divided the range by the time. Use the lead distance: {rng_} × tan {th}° = {d} m."),
            (d * t, f"You multiplied the lead by the time. Speed = distance ÷ time: {d} ÷ {t}."),
            (_jround(R * _sin(th) / t), f"You used sin {th}° for the lead. The lead is range × tan: {rng_} × {tan}."),
            (_jround(R * _cos(th) / t), f"You used cos {th}° for the lead. The lead is range × tan: {rng_} × {tan}."),
            (_jround(R * th / 100 / t), f"You used {_js(th / 100)} for tan {th}°. Look it up in the trig table: it's {tan}."),
        ], avoid=[exact_lead / t]),
        solution=[lead, f"She covers {d} m in {t} s: {d} ÷ {t} = {v} m/s."],
        hint="Turn the lead angle back into a lead distance (range × tan, from the trig table), then speed = distance ÷ time.",
        fig=fig,
    )


# ---------------- Engineering · Area & Volume (missiles) ----------------


@gen("geo", 3)
def hard_rectangle_missing_side(ctx: Context) -> Problem:
    me = ctx.my_name
    Lv = ctx.pick([40, 50, 60, 80, 90, 120, 150, 200])
    Wv = ctx.pick([12, 15, 18, 20, 24, 30, 36])
    P = 2 * Lv + 2 * Wv
    A = Lv * Wv
    area = _fmt_n(A, 0)
    v = ctx.pick([
        {"story": f"The safety line rigged all the way around {me}'s flight deck is {P} ft long, and the deck is {Wv} ft wide. The deck crew needs to know how much non-skid to order.",
         "ask": "What is the deck's area in square feet?", "expr": f"{P} = 2L + 2 × {Wv}", "note": f"A = L × {Wv}", "ans": A,
         "wrong": [((P - Wv) * Wv, f"You took only one width off the perimeter. Halve it first: {P} ÷ 2 − {Wv} is the length."),
                   (P * Wv, f"You multiplied the perimeter by the width. Find the length first: {P} ÷ 2 − {Wv}."),
                   ((P / 2) * Wv, f"You used half the perimeter as the length. Take the width off it too: {P // 2} − {Wv}."),
                   (P - 2 * Wv, f"That's {P} − 2 × {Wv}, which is both lengths. Halve it for the length, then multiply by {Wv} for the area."),
                   (Lv, "That's the length. The question asks for the area: length × width."),
                   ((P - 2 * Wv) * Wv, f"You forgot to halve {P} − {2 * Wv}: that's both lengths together. One length × {Wv} is the area.")],
         "sol": [f"Half the perimeter is length + width: {P} ÷ 2 = {Lv + Wv}.", f"Length = {Lv + Wv} − {Wv} = {Lv} ft.", f"Area = {Lv} × {Wv} = {area} sq ft."],
         # The original drew figRect(Lv, Wv, 'L') here too, but that picture prints "A = <the answer>".
         "fig": None},
        {"story": f"A rectangular fuel tank's floor is {area} sq ft and it is {Wv} ft wide. The shipwrights are welding a lip all the way around the edge of the floor.",
         "ask": "How many feet of lip (the perimeter) do they weld?", "expr": f"{area} = L × {Wv}", "note": f"P = 2L + 2 × {Wv}", "ans": P,
         "wrong": [(Lv + Wv, "That's one length and one width, only half the way round. Double it."),
                   (2 * Lv + Wv, "You only counted one width. The lip goes along two lengths and two widths."),
                   (Lv, f"That's the length ({area} ÷ {Wv}). Now add up all four sides."),
                   (2 * A + 2 * Wv, f"You used the area, {area}, as the length. Find the length first: {area} ÷ {Wv}."),
                   (2 * (A - Wv), f"You took the width away from the area. The length is {area} ÷ {Wv}."),
                   (4 * Lv, f"You counted four lengths. Two of the sides are the {Wv} ft width.")],
         "sol": [f"Length = area ÷ width = {area} ÷ {Wv} = {Lv} ft.", f"Perimeter = 2 × {Lv} + 2 × {Wv} = {2 * Lv} + {2 * Wv} = {P} ft."],
         "fig": _fig("rect", Lv=Lv, Wv=Wv, mode="L")},
    ])
    return _problem(help="rect", story=v["story"], expr=v["expr"], note=v["note"], ask=v["ask"], choices=_numeric_choices(ctx, v["ans"], v["wrong"]),
                    solution=v["sol"], hint="Find the missing side first, from the perimeter or the area you were given. Then work out what was asked.",
                    fig=v["fig"])


@gen("geo", 3)
def hard_triangle_height(ctx: Context) -> Problem:
    me = ctx.my_name
    b = ctx.pick([20, 24, 30, 36, 40, 50, 60])
    h = ctx.pick([10, 12, 15, 18, 20, 25, 30])
    A = b * h / 2
    return _problem(
        help="tri",
        story=f"The triangular foredeck on {me} takes {_fmt_n(A, 0)} sq ft of non-skid, and it is {b} ft across at the back. The bosun wants to know how far it is from the back edge straight to the bow (the triangle's height).",
        expr=f"{_fmt_n(A, 0)} = ½ × {b} × h",
        ask="What is the height in feet?",
        choices=(ch := _numeric_choices(ctx, h, [
            (A / b, f"You divided the area by the base but forgot the ½. Double the area first: 2 × {_fmt_n(A, 0)} ÷ {b}."),
            (A / b / 2, "You halved instead of doubling. Height = 2 × area ÷ base."),
            (2 * A, f"That's 2 × the area. Now divide by the base, {b}."),
            (A / 2, "You halved the area. Height = 2 × area ÷ base."),
            (A - b, f"You took the base away from the area. Divide instead: 2 × {_fmt_n(A, 0)} ÷ {b}."),
            (2 * A / b * 2, "You doubled twice. Double the area once, then divide by the base."),
        ], dp="auto")),
        solution=["Area = ½ × base × height, so height = 2 × area ÷ base.", f"2 × {_fmt_n(A, 0)} = {_fmt_n(2 * A, 0)}, and {_fmt_n(2 * A, 0)} ÷ {b} = {ch.texts[0]} ft."],
        hint="Double the area, then divide by the base.",
    )


@gen("geo", 3)
def hard_circle_conversions(ctx: Context) -> Problem:
    me = ctx.my_name
    if ctx.rand(0, 1):
        d = ctx.pick([8, 10, 12, 16, 20, 24])
        r = d / 2
        return _problem(
            help="circle",
            story=f"The steel ring around {me}'s forward barbette measures {d}π ft all the way around. The shipwrights need the area of the deck plate inside it.",
            expr=f"C = π × d = {d}π, so d = {d}",
            note="r = d ÷ 2, then A = π × r²",
            ask="What is the area inside the ring? (Leave π in the answer.)",
            choices=_string_choices(ctx, f"{_js(r * r)}π sq ft", [
                (f"{d * d}π sq ft", f"You squared the diameter, {d}. Halve it first to get the radius, {_js(r)}."),
                (f"{_js(r)}π sq ft", f"You found the radius but didn't square it: π × {_js(r)}²."),
                (f"{_js(2 * r * r)}π sq ft", f"You doubled r², mixing it up with 2πr. Area is just π × {_js(r)}²."),
                (f"{d}π sq ft", "That's the circumference you were given. The area is π × r²."),
                (f"{_js(r * r / 4)}π sq ft", f"You halved {_js(r)} again, but {_js(r)} ft is already the radius. Area is π × {_js(r)}²."),
                (f"{_js(d * r)}π sq ft", f"You multiplied the diameter by the radius. Area is π × r × r: π × {_js(r)} × {_js(r)}."),
                (f"{_js(r)} ft", f"That's the radius, {_js(r)} ft. Keep going: the area is π × {_js(r)}²."),
            ]),
            solution=[f"Circumference = π × diameter, so the diameter is {d} ft and the radius is {_js(r)} ft.", f"Area = π × {_js(r)}² = {_js(r * r)}π sq ft."],
            hint="The number in front of π in the circumference is the diameter. Halve it for the radius, then square it.",
        )
    r = ctx.pick([3, 4, 5, 6, 7, 8, 9, 10, 12])
    return _problem(
        help="circle",
        story=f"{me}'s sonar sweeps {r * r}π square nautical miles of sea. The navigator wants to draw the edge of that circle on the chart.",
        expr=f"A = π × r² = {r * r}π, so r = √{r * r}",
        note="C = 2 × π × r",
        ask="What is the circumference of the sonar circle? (Leave π in the answer.)",
        choices=_string_choices(ctx, f"{2 * r}π nm", [
            (f"{r}π nm", f"You forgot to double. Circumference = 2 × π × {r}."),
            (f"{r * r}π nm", "That's the area you were given. Take its square root for the radius, then C = 2πr."),
            (f"{4 * r}π nm", f"You used the diameter, {2 * r}, in 2πr. The radius is {r}: C = 2 × π × {r}."),
            (f"{2 * r * r}π nm", f"You used {r * r} as the radius. Take the square root first: √{r * r} = {r}."),
            (f"{_js(r * r / 2)}π nm", f"You halved {r * r} instead of taking its square root: √{r * r} = {r}."),
            (f"{r} nm", f"That's the radius, √{r * r} = {r} nm. Keep going: the distance round is 2 × π × {r}."),
        ]),
        solution=[f"Area = π × r², so r² = {r * r} and r = {r} nm.", f"Circumference = 2 × π × {r} = {2 * r}π nm."],
        hint="The number in front of π in the area is the radius squared. Square-root it, then double it for the circumference.",
    )


@gen("geo", 3)
def hard_sector_area(ctx: Context) -> Problem:
    me = ctx.my_name
    while True:
        r = ctx.pick([6, 12, 18, 24, 30, 36])
        th = ctx.pick([30, 45, 60, 90, 120, 180, 270])
        ans = th / 360 * r * r
        if _is_int(ans):
            break
    frac = _fraction(th, 360)
    return _problem(
        help="arc",
        story=f"{me}'s forward radar only looks ahead: it sweeps a {th}° wedge out to {r} nm. The captain wants to know how much sea that wedge covers.",
        expr=f"A = ({th} ÷ 360) × π × {r}{sup(2)}",
        ask="What area does the wedge cover? (Leave π in the answer.)",
        choices=_string_choices(ctx, f"{_js(ans)}π sq nm", [
            (f"{r * r}π sq nm", f"That's the whole circle, π × {r}². The wedge is only {frac} of it."),
            (f"{_js(ans * 2)}π sq nm", f"You divided by 180 instead of 360. The wedge is {th} ÷ 360 = {frac} of the circle."),
            (f"{_js(th / 360 * 2 * r)}π sq nm", f"That's the arc along the curved edge ({frac} × 2π × {r}). The area uses π × r²."),
            (f"{_js(th / 360 * r)}π sq nm", f"You didn't square the radius: {frac} × π × {r}²."),
            (f"{_js(360 / th * r * r)}π sq nm", f"You did 360 ÷ {th}, upside down. The wedge is {th} ÷ 360 = {frac} of the circle."),
            (f"{th * r * r}π sq nm", f"You forgot to divide by 360. The wedge is {th} ÷ 360 = {frac} of the circle."),
        ]),
        solution=[f"The full circle would be π × {r}² = {r * r}π.", f"The wedge is {th} ÷ 360 = {frac} of it.", f"{frac} × {r * r}π = {_js(ans)}π sq nm."],
        hint=f"Find the whole circle's area, then take the fraction of it that {th}° is out of 360°.",
    )


@gen("geo", 3)
def hard_box_depth(ctx: Context) -> Problem:
    me = ctx.my_name
    Lv = ctx.pick([8, 10, 12, 15, 20])
    Wv = ctx.pick([4, 5, 6, 8])
    Hv = ctx.pick([3, 4, 5, 6])
    V = Lv * Wv * Hv
    floor = Lv * Wv
    return _problem(
        help="vol",
        story=f"A fresh-water tank on {me} holds {_fmt_n(V, 0)} cubic feet. Its floor is {Lv} ft long and {Wv} ft wide. The engineer's sounding rod is marked in inches, so he needs the depth in inches (12 inches to a foot).",
        expr=f"{_fmt_n(V, 0)} = {Lv} × {Wv} × h",
        note="find h in feet, then × 12 for inches",
        ask="How deep is the tank, in inches?",
        choices=_numeric_choices(ctx, 12 * Hv, [
            (Hv, f"That's the depth in feet. The rod is marked in inches: {Hv} × 12."),
            (10 * Hv, f"There are 12 inches in a foot, not 10: {Hv} × 12."),
            (Hv + 12, f"You added 12. Each foot is 12 inches, so multiply: {Hv} × 12."),
            (12 * Wv * Hv, f"You divided by the length only. Divide by the floor area, {Lv} × {Wv} = {floor}, then × 12."),
            (12 * Lv * Hv, f"You divided by the width only. Divide by the floor area, {Lv} × {Wv} = {floor}, then × 12."),
            (V, "That's the volume in cubic feet. Divide it by the floor area to get the depth, then change it to inches."),
            (12 * floor, "That's the floor area × 12. Depth = volume ÷ floor area, then × 12 for inches."),
        ]),
        solution=[f"Floor area: {Lv} × {Wv} = {floor} sq ft.", f"Depth = volume ÷ floor area = {_fmt_n(V, 0)} ÷ {floor} = {Hv} ft.",
                  f"In inches: {Hv} × 12 = {12 * Hv} in."],
        hint="Multiply the two floor sides, divide the volume by that, then turn feet into inches (× 12).",
    )


@gen("geo", 3)
def hard_cylinder_diameter(ctx: Context) -> Problem:
    me = ctx.my_name
    d = ctx.pick([4, 6, 8, 10, 12])
    r = d // 2  # d is even
    h = ctx.pick([5, 8, 10, 12])
    return _problem(
        help="cyl",
        story=f"The boiler feed tank on {me} is a cylinder {d} ft across and {h} ft tall.",
        expr=f"r = {d} ÷ 2",
        note=f"V = π × r² × {h}",
        ask="What is its volume? (Leave π in the answer.)",
        choices=_string_choices(ctx, f"{r * r * h}π cubic ft", [
            (f"{d * d * h}π cubic ft", f"You used the diameter, {d}, as the radius. Halve it first: {r}."),
            (f"{d * h}π cubic ft", f"You used the diameter and didn't square it. Halve {d} to get {r}, then square: {r}² = {r * r}."),
            (f"{r * h}π cubic ft", f"You didn't square the radius: π × {r}² × {h}."),
            (f"{r * r}π cubic ft", f"That's just the circle on the end, π × {r}². Multiply by the height, {h}, too."),
            (f"{d * d * h // 2}π cubic ft", f"You halved {d}² instead of halving {d} before squaring. It's ({d} ÷ 2)² = {r * r}."),
            (f"{2 * r * h}π cubic ft", f"That's 2 × π × {r} × {h}, the curved side's area. Volume is π × r² × h."),
            (f"{r * h * h}π cubic ft", f"You squared the height instead of the radius: π × {r}² × {h}."),
        ]),
        solution=[f"{d} ft across is the diameter, so the radius is {r} ft.", f"{r}² = {r * r}, and {r * r} × {h} = {r * r * h}.", f"Volume = {r * r * h}π cubic ft."],
        hint='"Across" means the diameter. Halve it before you square it.',
    )


@gen("geo", 3)
def hard_trapezoid_height(ctx: Context) -> Problem:
    me = ctx.my_name
    a = ctx.pick([10, 12, 16, 20])
    b = a + ctx.pick([4, 6, 8, 10])
    h = ctx.pick([4, 6, 8, 10])
    A = (a + b) / 2 * h
    return _problem(
        help="trap",
        story=f"The trapezoid splinter shield on {me}'s fantail uses {_js(A)} sq ft of plate. It is {a} ft along the top and {b} ft along the bottom.",
        expr=f"{_js(A)} = ({a} + {b}) ÷ 2 × h",
        ask="How tall is the shield, in feet?",
        choices=(ch := _numeric_choices(ctx, h, [
            (A / (a + b), f"You divided by {a} + {b} but forgot to halve it. Divide by the average: ({a} + {b}) ÷ 2."),
            (A / a, "You divided by the top only. Divide by the average of the top and the bottom."),
            (A / b, "You divided by the bottom only. Divide by the average of the top and the bottom."),
            (A - (a + b) / 2, "You took the average away from the area. Divide by it instead."),
            (2 * A / (a + b) * 2, f"You doubled twice. Area ÷ the average, ({a} + {b}) ÷ 2, is the height."),
            (A / (b - a), f"You divided by the difference, {b} − {a}. Divide by the average: ({a} + {b}) ÷ 2."),
        ], dp="auto")),
        solution=[f"Average the parallel sides: ({a} + {b}) ÷ 2 = {_js((a + b) / 2)}.", f"Height = area ÷ that average = {_js(A)} ÷ {_js((a + b) / 2)} = {ch.texts[0]} ft."],
        hint="Average the top and bottom first, then divide the area by that average.",
    )


@gen("geo", 3)
def hard_open_locker(ctx: Context) -> Problem:
    me = ctx.my_name
    l = ctx.pick([4, 5, 6, 8])  # noqa: E741 (the original's names)
    w = ctx.pick([2, 3, 4])
    h = ctx.pick([2, 3, 5])
    ans = l * w + 2 * l * h + 2 * w * h
    return _problem(
        help="surf",
        story=f"A ready-ammunition locker on {me} is {l} ft long, {w} ft wide and {h} ft tall, and it has no lid: the top is open. The bosun paints the outside of every face there is.",
        expr=f"SA = {l}×{w} + 2 × {l}×{h} + 2 × {w}×{h}",
        ask="How many square feet get painted?",
        choices=_numeric_choices(ctx, ans, [
            (2 * (l * w + l * h + w * h), "That counts a top too, but the locker has no lid. Leave the top out."),
            (2 * l * h + 2 * w * h, f"You left out the bottom as well. Only the top is missing: add the {l} × {w} bottom."),
            (l * w * h, "That's the volume. Paint covers faces: add up their areas."),
            (l * w + l * h + w * h, "You counted each side once. There are two long sides and two short sides."),
            (l * w + 2 * l * h + w * h, f"You only counted one short side. There are two, {w} × {h} each."),
            (l * w + l * h + 2 * w * h, f"You only counted one long side. There are two, {l} × {h} each."),
            (2 * ans, "You painted the inside too. The bosun only paints the outside of each face."),
            (l * w + 4 * l * h, f"You made all four sides {l} × {h}. Two of them are the short ends, {w} × {h}.") if l != w else None,
        ]),
        solution=[
            f"Bottom: {l} × {w} = {l * w}. There is no top.",
            f"Two long sides: 2 × {l} × {h} = {2 * l * h}. Two short sides: 2 × {w} × {h} = {2 * w * h}.",
            f"{l * w} + {2 * l * h} + {2 * w * h} = {ans} sq ft.",
        ],
        hint="Count the faces: one bottom, two long sides, two short sides. No top.",
        fig=_fig("box", Lv=l, Wv=w, Hv=h, mode="surf"),
    )


@gen("geo", 3)
def hard_deck_cutout(ctx: Context) -> Problem:
    me = ctx.my_name
    Lv = ctx.pick([200, 240, 300])
    Wv = ctx.pick([40, 50, 60])
    a = ctx.pick([30, 40, 50, 60])
    b = ctx.pick([20, 24, 30])
    ans = Lv * Wv - a * b
    return _problem(
        help="composite",
        story=f"{me}'s hangar deck is a rectangle {Lv} ft long and {Wv} ft wide, with a rectangular aircraft-elevator opening {a} ft by {b} ft cut out of it. The crew is painting every square foot of deck that is actually there.",
        expr=f"A = {Lv} × {Wv} − {a} × {b}",
        ask="How many square feet get painted?",
        choices=_numeric_choices(ctx, ans, [
            (Lv * Wv, f"That's the whole deck. Take away the elevator opening, {a} × {b}."),
            (Lv * Wv + a * b, "You added the opening. It's a hole, so take it away."),
            (Lv * Wv - a - b, f"You took away {a} + {b}. The hole's area is {a} × {b}."),
            ((Lv - a) * (Wv - b), "You took the hole's sides off the deck's sides. Find the two areas, then subtract."),
            (a * b, "That's the area of the opening. Take it away from the whole deck."),
            (Lv * Wv - 2 * a * b, "You took the opening away twice. Once is enough."),
        ]),
        solution=[
            f"Whole deck: {Lv} × {Wv} = {_fmt_n(Lv * Wv, 0)}.",
            f"Opening: {a} × {b} = {_fmt_n(a * b, 0)}.",
            f"{_fmt_n(Lv * Wv, 0)} − {_fmt_n(a * b, 0)} = {_fmt_n(ans, 0)} sq ft.",
        ],
        hint="Find the whole rectangle, find the hole, and take the hole away.",
    )


@gen("geo", 3)
def hard_triangular_prism(ctx: Context) -> Problem:
    me = ctx.my_name
    b = ctx.pick([6, 8, 10, 12])
    h = ctx.pick([3, 4, 5, 6])
    L = ctx.pick([10, 15, 20, 30])
    ans = b * h / 2 * L
    return _problem(
        help="vol",
        story=f"The forward bilge tank on {me} is a triangular prism: its end is a triangle {b} ft across and {h} ft tall, and the tank runs {L} ft along the keel.",
        expr=f"V = (½ × {b} × {h}) × {L}",
        ask="What is its volume in cubic feet?",
        choices=_numeric_choices(ctx, ans, [
            (b * h * L, f"You forgot the ½ in the triangle's area: ½ × {b} × {h}."),
            (b * h * L / 4, "You halved both the base and the height. Halve just once."),
            (b * h / 2 + L, f"You added the length. Multiply the end's area by it: {_js(b * h / 2)} × {L}."),
            ((b + h) * L, f"You added {b} + {h}. The end's area is ½ × {b} × {h}."),
            (b * h / 2, f"That's the area of the triangle end. Multiply by the length, {L}."),
            (b * h * L * 2, "You doubled instead of halving. The end is half of base × height."),
        ]),
        solution=[f"End area: ½ × {b} × {h} = {_js(b * h / 2)} sq ft.", f"Volume = end area × length = {_js(b * h / 2)} × {L} = {_fmt_n(ans, 0)} cubic ft."],
        hint="Volume of any prism = area of the end × length. Here the end is a triangle.",
    )


# ---------------- Shields · Circles (missiles) ----------------


@gen("circ", 3)
def hard_chord_length(ctx: Context) -> Problem:
    me, en = ctx.my_name, ctx.enemy_name
    d, h, r = ctx.pick([t for t in TRIPLES if t[2] <= 26])  # d: centre to course, h: half the run inside
    if ctx.rand(0, 1):
        d, h = h, d
    if ctx.rand(0, 2):
        ans = 2 * h
        return _problem(
            help="chord",
            story=f"{me}'s course will take her straight through {en}'s circular shield. The shield's radius is {r} nm, and at the closest point her course passes {d} nm from its centre.",
            expr=f"(half the run)² + {d}² = {r}²",
            note="the line from the centre meets the course at 90° and cuts the run in half",
            ask=f"How far will {me} travel inside the shield?",
            choices=_numeric_choices(ctx, ans, [
                (h, "That's half the run. The line from the centre cuts the run in half, so double it."),
                (2 * (r - d), f"You took {d} straight off {r}. Half the run is a side of a right triangle: √({r}² − {d}²)."),
                (r - d, f"You took {d} from {r}. Use Pythagoras for half the run, √({r}² − {d}²), then double it."),
                (2 * r, f"That's the diameter, a run straight through the centre. Her course passes {d} nm off centre, so the run is shorter."),
                (2 * h * h, f"You forgot the square root: √{h * h} = {h}. Then double it."),
                (2 * _jround(math.sqrt(r * r + d * d)), f"You added the squares, but the radius is the longest side. Take {d}² away from {r}²."),
                (4 * h, f"You doubled twice. Half the run is {h} nm, so the whole run is 2 × {h}."),
            ]),
            solution=[
                "The line from the centre meets the course at 90° and cuts the run inside the shield in half.",
                f"The radius to where the course crosses the edge is the hypotenuse: half² = {r}² − {d}² = {r * r} − {d * d} = {h * h}, so half the run is {h} nm.",
                f"The whole run: 2 × {h} = {ans} nm.",
            ],
            hint="Draw the radius to where the course crosses the edge: it makes a right triangle with half the run. Find that half with Pythagoras, then double it.",
            fig=_fig("chord", r=_gv(f"r = {r} nm"), d=_gv(f"{d} nm"), chord=_ak("inside ?")),
        )
    return _problem(
        help="chord",
        story=f"{en}'s circular shield has a radius of {r} nm. {me} crossed it on a straight course and spent {2 * h} nm inside the field.",
        expr=f"half the run = {2 * h} ÷ 2",
        note=f"(distance to the centre)² + (half the run)² = {r}²",
        ask=f"How close to the centre of the shield did {me}'s course pass?",
        choices=_numeric_choices(ctx, d, [
            (r - h, f"You took half the run straight off {r}. The distance is a side of a right triangle: √({r}² − {h}²)."),
            (math.isqrt(r * r - 4 * h * h), f"You used the whole run, {2 * h}, in Pythagoras. The right triangle has half of it: {h}.")
            if r > 2 * h and math.isqrt(r * r - 4 * h * h) ** 2 == r * r - 4 * h * h else None,
            (d * d, f"That's {r}² − {h}² = {d * d}. You forgot the square root."),
            (_jround(math.sqrt(r * r + h * h)), f"You added the squares. The radius is the longest side: √({r}² − {h}²)."),
            (2 * d, f"You doubled it. Only the run is cut in half; the distance to the centre is just √({r}² − {h}²)."),
            (h, f"That's half the run. The distance to the centre is the other short side: √({r}² − {h}²)."),
            (r - 2 * h, f"You took the whole run from the radius. Use Pythagoras with half the run: √({r}² − {h}²)."),
            (r, "That's the radius, how far the edge is from the centre. The course passed closer in than that."),
        ]),
        solution=[
            f"The line from the centre meets the course at 90° and cuts the {2 * h} nm run in half: {h} nm each side.",
            f"The radius is the hypotenuse: distance² = {r}² − {h}² = {r * r} − {h * h} = {d * d}.",
            f"√{d * d} = {d} nm.",
        ],
        hint="Halve the run first. The radius, half the run and the distance to the centre make a right triangle, with the radius as the hypotenuse.",
        fig=_fig("chord", r=_gv(f"r = {r} nm"), d=_ak("?"), chord=_gv(f"{2 * h} nm inside")),
    )


@gen("circ", 3)
def hard_tangent_arc(ctx: Context) -> Problem:
    me, en = ctx.my_name, ctx.enemy_name
    mode = ctx.pick(["short", "long", "angle"])
    story = f"Two courses from {me} just graze {en}'s circular shield, one on each side, touching it at A and at B."
    right = "Each course meets the radius to its touching point at 90°."
    hint = "Put in the right angles where the courses touch the shield. The four angles of centre, A, ship and B add to 360°, and an arc is its angle at the centre."
    if mode == "angle":
        a = ctx.rand(4, 32) * 5
        ans = 180 - a
        return _problem(
            help="tanarc",
            story=story + f" On the side facing {me}, the shield's edge from A round to B is an arc of {a}°.",
            expr=f"90° + 90° + {a}° + P = 360°",
            note="an arc measures the same as its angle at the centre",
            ask=f"At what angle do the two courses meet at {me}?",
            choices=_numeric_choices(ctx, ans, [
                (a, "That's the arc, the angle at the centre. The angle at the ship is what's left of 360° after it and the two right angles."),
                (a // 2, f"You halved the arc, as for an angle on the rim. The ship is outside the shield: 360 − 90 − 90 − {a}.") if a % 2 == 0 else None,
                (360 - a, "You left out the two right angles at A and B, where each course meets a radius. Take 90 + 90 away as well."),
                (270 - a, f"You only took away one right angle. There's one at A and one at B: 360 − 90 − 90 − {a}."),
                ((360 - a) // 2, f"You halved the far arc. The angle at the ship is half the difference of the two arcs: ({360 - a} − {a}) ÷ 2.")
                if a % 2 == 0 else None,
                (180 + a, "You added the arc to 180. The angle at the centre and the angle at the ship add to 180°, so take it away."),
            ]),
            solution=[right, f"The four angles of centre, A, {me} and B add to 360°, and the angle at the centre is the arc, {a}°.", f"360 − 90 − 90 − {a} = {ans}°."],
            hint=hint,
            fig=_fig("tangents", two=True, radii=False, angP=_ak("?"), arc=_gv(f"{a}°"), marks=_YOU_AT_P, note=_NOT_TO_SCALE),
        )
    x = ctx.rand(4, 28) * 5
    short = 180 - x
    centre = f"The four angles of centre, A, {me} and B add to 360°: 360 − 90 − 90 − {x} = {short}° at the centre, so the short arc is {short}°."
    if mode == "short":
        ans = short
        ask = f"How many degrees is the short arc AB, on the side facing {me}?"
        note = "O is the angle at the centre: the short arc AB is O degrees"
        pool: list[Mistake] = [
            (x, f"That's the angle between the courses at the ship. The arc is the angle at the centre: 360 − 90 − 90 − {x}."),
            (360 - x, "You left out the two right angles at A and B, where each course meets a radius. Take 90 + 90 away as well."),
            (270 - x, f"You only took away one right angle. There's one at A and one at B: 360 − 90 − 90 − {x}."),
            (180 + x, f"That's the long arc, round the far side. The arc facing the ship is the short one: 180 − {x}."),
            (short // 2, "You halved the angle at the centre. An arc measures the same as its angle at the centre; halving is for angles on the rim.")
            if short % 2 == 0 else None,
            (2 * x, "You doubled the angle at the ship. Doubling goes from the rim to the centre, and the ship is outside the shield."),
        ]
        solution = [right, centre]
        fig = _fig("tangents", two=True, radii=False, angP=_gv(f"{x}°"), arc=_ak("?"), marks=_YOU_AT_P, note=_NOT_TO_SCALE)
    else:
        ans = 180 + x
        ask = f"How many degrees is the long arc AB, round the far side of the shield from {me}?"
        note = "O is the angle at the centre, the short arc; the long arc is the rest of 360°"
        pool = [
            (short, "That's the short arc, on the side facing the ship. The long arc is 360° minus it."),
            (360 - x, f"You took {x} straight off 360. Find the short arc first, 180 − {x}; the long arc is 360 minus that."),
            (90 + x, f"You only took one right angle away for the short arc. It's 360 − 90 − 90 − {x} = {short}; the long arc is 360 minus that."),
            (x, "That's the angle between the courses at the ship. The arcs are measured by the angle at the centre."),
            ((180 + x) // 2, "You halved it. An arc measures the same as its angle at the centre; halving is for angles on the rim.") if x % 2 == 0 else None,
            (360 - 2 * x, f"You doubled the angle at the ship and took it from 360. Find the short arc, 180 − {x}, then take it from 360."),
        ]
        solution = [right, centre, f"The long arc is the rest of the circle: 360 − {short} = {ans}°."]
        fig = _fig("tangents", two=True, radii=False, angP=_gv(f"{x}°"), far=_ak("?"), marks=_YOU_AT_P, note=_NOT_TO_SCALE)
    return _problem(
        help="tanarc",
        story=story + f" The two courses meet at {me} at an angle of {x}°.",
        expr=f"90° + 90° + {x}° + O = 360°",
        note=note,
        ask=ask,
        choices=_numeric_choices(ctx, ans, pool),
        solution=solution,
        hint=hint,
        fig=fig,
    )


@gen("circ", 3)
def hard_intersecting_chords(ctx: Context) -> Problem:
    me, en = ctx.my_name, ctx.enemy_name
    while True:
        a, b = ctx.rand(2, 12), ctx.rand(2, 12)
        p = a * b
        cs = [c for c in range(2, 17) if p % c == 0 and c not in (a, b) and 2 <= p // c <= 20 and p // c not in (a, b, c)]
        if cs:
            break
    c = ctx.pick(cs)
    x = p // c
    whole = bool(ctx.rand(0, 1))
    ans = c + x if whole else x
    paired = f"You paired the parts the wrong way. The two parts of one run multiply together: {a} × {b} = {c} × x."
    wrong_way = [a * c // b if a * c % b == 0 else None, b * c // a if b * c % a == 0 else None]
    if whole:
        pool: list[Mistake] = [
            (x, f"That's only the part beyond the crossing. Add the {c} nm on this side too."),
            (a + b, f"That's the first run. The runs needn't match: find the missing part from {a} × {b} = {c} × x, then add {c}."),
            (p + c, f"You didn't divide: {a} × {b} = {p} is {c} × x, so x = {p} ÷ {c}. Then add {c}."),
            (p, f"You took {c} from {p} for the missing part. Divide instead: x = {p} ÷ {c}. Then add {c}."),
            (2 * x, f"You doubled the missing part. The whole run is the {c} nm part plus the missing one."),
        ] + [(c + w, paired) if w is not None else None for w in wrong_way]
    else:
        pool = [
            (a + b - c, f"You made the two runs the same length: {a} + {b} − {c}. It's the products of the parts that match: {a} × {b} = {c} × x."),
            (p, f"That's {a} × {b}. Divide it by {c} to get the missing part."),
            (p - c, f"You took {c} away from {p}. It's {c} × x, so divide by {c}."),
            (c + x, "That's the whole second run. The question asks only for the part on the other side of the crossing."),
        ] + [(w, paired) if w is not None else None for w in wrong_way]
    return _problem(
        help="chords",
        story=f"Two of {me}'s torpedo runs cut straight across {en}'s circular shield, each from edge to edge, and they cross inside the field. The crossing point splits the first run into {a} nm and {b} nm. On the second run, {c} nm lies on one side of the crossing.",
        expr=f"{a} × {b} = {c} × x",
        note=f"whole second run = {c} + x" if whole else "",
        ask="How long is the second run, from edge to edge?" if whole else "How long is the second run on the other side of the crossing?",
        choices=_numeric_choices(ctx, ans, pool),
        solution=[
            f"When two chords cross, the parts of one multiply to the same as the parts of the other: {a} × {b} = {c} × x.",
            f"{p} = {c} × x, so x = {p} ÷ {c} = {x} nm.",
        ] + ([f"The whole second run: {c} + {x} = {ans} nm."] if whole else []),
        hint="Multiply the two parts of the first run. That equals the known part of the second run times its missing part.",
        fig=_fig("chords", a=_gv(f"{a} nm"), b=_gv(f"{b} nm"), c=_gv(f"{c} nm"), d=_ak("?")),
    )


@gen("circ", 3)
def hard_equation_from_point(ctx: Context) -> Problem:
    me, en = ctx.my_name, ctx.enemy_name
    while True:
        h, k = _off_centre(ctx, 1, 6)
        dx, dy = ctx.pick([-1, 1]) * ctx.rand(1, 8), ctx.pick([-1, 1]) * ctx.rand(1, 8)
        if abs(dx) != abs(dy):
            break
    px, py = h + dx, k + dy
    rr = dx * dx + dy * dy
    r = math.isqrt(rr)
    ans = _circle_eq(h, k, rr)
    added = (px + h) ** 2 + (py + k) ** 2
    return _problem(
        help="circeq",
        story=f"{en}'s shield generator sits at {_pt(h, k)} on the plot. {me} has crept right up to the edge of the force field: she is at {_pt(px, py)}, just touching it. Each grid square is 1 nm.",
        expr="r² = (Δx)² + (Δy)²",
        note="then (x − h)² + (y − k)² = r²",
        ask="What equation describes the edge of the shield?",
        choices=_string_choices(ctx, ans, [
            (_circle_eq(h, k, r), f"The right side is r², and Δx² + Δy² = {rr} is r² already. Don't take the square root.") if r * r == rr else None,
            (_circle_eq(h, k, (abs(dx) + abs(dy)) ** 2), f"You added Δx and Δy before squaring. Square each one first: {dx * dx} + {dy * dy} = {rr}."),
            (_circle_eq(h, k, abs(dx) + abs(dy)), f"You added Δx and Δy. r² = Δx² + Δy² = {dx * dx} + {dy * dy} = {rr}."),
            (_circle_eq(-h, -k, rr), f"You put the centre's own signs in the brackets. Each takes the centre away: {_take('x', h)} and {_take('y', k)}."),
            (_circle_eq(px, py, rr), f"You used the ship's position as the centre. She is on the edge; the generator at {_pt(h, k)} is the centre."),
            (_circle_eq(h, k, added), f"You added the coordinates to get Δx and Δy. Subtract them: Δx = {_signed(px)} − {_paren(h)} = {_signed(dx)}.")
            if added != rr else None,
            (_circle_eq(h, k, px * px + py * py), f"You measured r² from (0, 0). Measure Δx and Δy from the generator at {_pt(h, k)}.")
            if px * px + py * py != rr else None,
        ]),
        solution=[
            f"The radius runs from the centre {_pt(h, k)} to {me} at {_pt(px, py)}: Δx = {_signed(px)} − {_paren(h)} = {_signed(dx)}, Δy = {_signed(py)} − {_paren(k)} = {_signed(dy)}.",
            f"r² = {_sq(dx)} + {_sq(dy)} = {dx * dx} + {dy * dy} = {rr}. No square root: the equation needs r².",
            f"Each bracket takes the centre away: {ans}.",
        ],
        hint="Find Δx and Δy from the centre to the ship on the edge: their squares add up to r². Then write (x − h)² + (y − k)² = r².",
        fig=_fig("shield", centre=_gv(_pt(h, k)), radius=_ak("r = ?"), edge=_ak("equation ?"), ship="target",
                 point={"label": _pt(px, py), "c": "given", "mark": "you", "on": True, "dir": [1 if dx > 0 else -1, 1 if dy > 0 else -1]}),
    )
