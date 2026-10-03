"""Diagrams for Broadside problems (and Math Boost's Dino Math ones), ported from the games' SVG figures.

Each problem's ``fig`` is a dict like ``{"kind": "compass", ...}`` whose keys
are the arguments of the original ``fig*`` JavaScript function. Figures are
laid out in the original SVG coordinates and scaled to fit the box, so the
shapes and label positions match the browser game.

Colours: cream = lines, gold = given, mint = what you're asked for, blue = angles.
"""

from __future__ import annotations

import math
from typing import Any, Optional

import pygame

from . import theme as T

FC = {
    "line": (242, 239, 230),
    "given": (255, 201, 74),
    "ask": (95, 227, 192),
    "arc": (78, 203, 238),
    "dim": (143, 169, 189),
    "red": (244, 105, 78),
    "lav": (138, 168, 255),
    "fill": (78, 203, 238, 33),
}


def _color(c: Any, default: str = "line"):
    if isinstance(c, (tuple, list)):
        return tuple(c)
    return FC.get(c or default, FC[default])


def _rad(d: float) -> float:
    return d * math.pi / 180


def _pol(cx: float, cy: float, r: float, a: float) -> tuple[float, float]:
    """Point at screen angle ``a`` degrees (0 = right, clockwise positive), as in the game."""
    return cx + r * math.cos(_rad(a)), cy + r * math.sin(_rad(a))


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _label(v: Any) -> tuple[Optional[str], Any]:
    """Labels come as {"t": text, "c": colour} or plain strings."""
    if v is None:
        return None, None
    if isinstance(v, dict):
        return (str(v["t"]) if v.get("t") not in (None, "") else None), v.get("c")
    return str(v), None


class Canvas:
    """Draws in figure coordinates, scaled and offset into a screen rectangle."""

    def __init__(self, surf: pygame.Surface, box: pygame.Rect, w: float, h: float) -> None:
        self.surf = surf
        self.box = box
        self.k = min(box.width / w, box.height / h, 1.6)
        self.ox = (box.width - w * self.k) / 2
        self.oy = (box.height - h * self.k) / 2
        self.layer = pygame.Surface(box.size, pygame.SRCALPHA)

    def p(self, x: float, y: float) -> tuple[float, float]:
        return self.ox + x * self.k, self.oy + y * self.k

    def w(self, width: float) -> int:
        return max(1, round(width * self.k))

    def line(self, x1, y1, x2, y2, c="line", width=2.0, dash=False) -> None:
        a, b = self.p(x1, y1), self.p(x2, y2)
        col = _color(c)
        if not dash:
            pygame.draw.line(self.layer, col, a, b, self.w(width))
            return
        length = math.dist(a, b)
        if length == 0:
            return
        step = 5 * self.k
        n = int(length // step)
        for i in range(0, n, 2):
            f0, f1 = i * step / length, min(1.0, (i + 1) * step / length)
            pygame.draw.line(self.layer, col, (a[0] + (b[0] - a[0]) * f0, a[1] + (b[1] - a[1]) * f0),
                             (a[0] + (b[0] - a[0]) * f1, a[1] + (b[1] - a[1]) * f1), self.w(width))

    def poly(self, pts, fill="fill", stroke="line", width=2.0) -> None:
        sp = [self.p(*q) for q in pts]
        if fill:
            pygame.draw.polygon(self.layer, _color(fill), sp)
        pygame.draw.polygon(self.layer, _color(stroke), sp, self.w(width))

    def arc(self, cx, cy, r, a0, a1, c="arc", width=2.0) -> None:
        if a1 < a0:
            a0, a1 = a1, a0
        n = max(4, int((a1 - a0) / 4))
        pts = [self.p(*_pol(cx, cy, r, a0 + (a1 - a0) * i / n)) for i in range(n + 1)]
        pygame.draw.lines(self.layer, _color(c), False, pts, self.w(width))

    def circle(self, cx, cy, r, stroke="line", width=2.0, fill=None, dash=False) -> None:
        center = self.p(cx, cy)
        if fill:
            pygame.draw.circle(self.layer, _color(fill), center, r * self.k)
        if dash:
            for a in range(0, 360, 18):
                self.arc(cx, cy, r, a, a + 9, stroke, width)
        else:
            pygame.draw.circle(self.layer, _color(stroke), center, r * self.k, self.w(width))

    def text(self, x, y, s, c="line", size=13, anchor="middle") -> None:
        img = T.render_math(str(s), max(9, round(size * 0.92 * self.k)), _color(c)[:3], bold=True)
        px, py = self.p(x, y)
        rect = img.get_rect()
        rect.centery = round(py)
        if anchor == "start":
            rect.left = round(px)
        elif anchor == "end":
            rect.right = round(px)
        else:
            rect.centerx = round(px)
        self.layer.blit(img, rect)

    def ang_arc(self, V, A, B, r, label, c="arc", lr=None, lc=None, size=None) -> None:
        """Arc of the angle at V between the rays toward A and B (the short way), labelled on the bisector."""
        a0 = math.degrees(math.atan2(A[1] - V[1], A[0] - V[0]))
        a1 = math.degrees(math.atan2(B[1] - V[1], B[0] - V[0]))
        d = a1 - a0
        if d > 180:
            d -= 360
        if d < -180:
            d += 360
        s, e = min(a0, a0 + d), max(a0, a0 + d)
        lr = lr or (26 if abs(d) < 32 else 15)
        self.arc(V[0], V[1], r, s, e, c)
        if label is not None:
            lx, ly = _pol(V[0], V[1], r + lr, (s + e) / 2)
            self.text(lx, ly, label, lc or c, size or 13)

    def right_mark(self, C, u, v, s=9) -> None:
        pts = [(C[0] + u[0] * s, C[1] + u[1] * s), (C[0] + (u[0] + v[0]) * s, C[1] + (u[1] + v[1]) * s),
               (C[0] + v[0] * s, C[1] + v[1] * s)]
        pygame.draw.lines(self.layer, FC["dim"], False, [self.p(*q) for q in pts], self.w(1.6))

    def mark(self, x, y, kind, label=None) -> None:
        if kind in ("you", "escort"):
            col = FC["line"] if kind == "you" else FC["lav"]
            hull = [(x - 8, y + 2), (x + 8, y + 2), (x + 5, y + 7), (x - 5, y + 7)]
            pygame.draw.polygon(self.layer, col, [self.p(*q) for q in hull])
            top = pygame.Rect(0, 0, 5 * self.k, 7 * self.k)
            top.bottomleft = self.p(x - 2, y + 2)
            pygame.draw.rect(self.layer, col, top)
        elif kind == "target":
            self.circle(x, y, 5, "red", 2)
            pygame.draw.circle(self.layer, FC["red"], self.p(x, y), max(1, 1.6 * self.k))
        elif kind == "plane":
            self.line(x - 9, y, x + 9, y, "red", 2)
            self.line(x - 2, y - 5, x + 2, y, "red", 2)
            self.line(x + 2, y, x - 2, y + 5, "red", 2)
            self.line(x - 7, y - 3, x - 7, y + 3, "red", 2)
        elif kind == "torpedo":
            self.line(x - 7, y, x + 5, y, "red", 4)
            pygame.draw.circle(self.layer, FC["red"], self.p(x + 5, y), max(1, 2 * self.k))
            self.line(x - 8, y - 4, x - 8, y + 4, "red", 2)
        if label:
            self.text(x, y + 17, label, "dim", 10)

    def blit(self) -> None:
        self.surf.blit(self.layer, self.box.topleft)


# --------------------------------------------------------------------------- figures


def _right_tri(surf, box, o) -> None:
    deg = o.get("deg")
    ratio = o.get("ratio")
    ratio = _clamp(ratio if ratio is not None else math.tan(_rad(deg if deg is not None else 37)), 0.3, 2.2)
    if ratio <= 1:
        W, H = 190, 190 * ratio
    else:
        H, W = 160, 160 / ratio
    mast = o.get("orient") == "mast"
    ang = math.degrees(math.atan2(H, W))
    x0, y0 = (116 if mast else 64), H + 48
    w, h, length = W + (210 if mast else 178), H + 88, math.hypot(W, H)
    P = (x0, y0 - H) if mast else (x0, y0)
    R = (x0, y0) if mast else (x0 + W, y0)
    Q = (x0 + W, y0) if mast else (x0 + W, y0 - H)
    cv = Canvas(surf, box, w, h)

    def lab(v, x, y, anchor):
        t, c = _label(v)
        if t:
            cv.text(x, y, t, c or "line", 13, anchor)

    cv.poly([P, R, Q])
    if mast:
        cv.right_mark(R, (1, 0), (0, -1))
        cv.line(P[0], P[1], P[0] + 90, P[1], "dim", 1.5, True)
        t, c = _label(o.get("ang"))
        if o.get("ang"):
            cv.ang_arc(P, (P[0] + 90, P[1]), Q, 26, t, c or "arc", lr=28 if ang < 30 else 16)
        lab(o.get("opp"), x0 - 12, y0 - H / 2, "end")
        lab(o.get("adj"), x0 + W / 2, y0 + 18, "middle")
        lab(o.get("hyp"), x0 + W / 2 + 15 * H / length + 4, y0 - H / 2 + 15 * W / length, "start")
    else:
        cv.right_mark(R, (-1, 0), (0, -1))
        if o.get("ang"):
            t, c = _label(o.get("ang"))
            cv.ang_arc(P, R, Q, 26, t, c or "arc", lr=28 if ang < 30 else 16)
        if o.get("ang2"):
            t, c = _label(o.get("ang2"))
            cv.ang_arc(Q, P, R, 22, t, c or "arc")
        lab(o.get("adj"), x0 + W / 2, y0 + 18, "middle")
        lab(o.get("opp"), x0 + W + 12, y0 - H / 2, "start")
        lab(o.get("hyp"), x0 + W / 2 - 15 * H / length - 4, y0 - H / 2 - 15 * W / length, "end")
    for k, m in (o.get("marks") or {}).items():
        pt = {"P": P, "R": R, "Q": Q}.get(k)
        if pt and m:
            cv.mark(pt[0] + m.get("dx", 0), pt[1] + m.get("dy", 0), m.get("kind"), m.get("label"))
    if o.get("note"):
        cv.text(w / 2, 14, o["note"], "dim", 11)
    cv.blit()


def _compass(surf, box, o) -> None:
    cx, cy, r = 130, 116, 72
    cv = Canvas(surf, box, 260, 232)
    cv.circle(cx, cy, r, "dim", 1.5)
    for a in range(0, 360, 30):
        x1, y1 = _pol(cx, cy, r, a - 90)
        x2, y2 = _pol(cx, cy, r - (5 if a % 90 else 9), a - 90)
        cv.line(x1, y1, x2, y2, "dim", 1.5)
    for n, a in (("N", 0), ("E", 90), ("S", 180), ("W", 270)):
        cv.text(*_pol(cx, cy, r + 12, a - 90), n, "dim", 11)
    for a in o.get("arcs") or []:
        rr = a.get("r", 40)
        cv.arc(cx, cy, rr, a["from"] - 90, a["to"] - 90, a.get("c") or "arc", 2.5)
        cv.text(*_pol(cx, cy, rr + 15, (a["from"] + a["to"]) / 2 - 90), a.get("label", ""), a.get("c") or "arc", 12)
    rays = o.get("rays") or []
    for i, ry in enumerate(rays):
        x, y = _pol(cx, cy, r - 4, ry["deg"] - 90)
        cv.line(cx, cy, x, y, ry.get("c") or "line", 2.4, ry.get("dash", False))
        close = any(abs(((o2["deg"] - ry["deg"]) % 360 + 540) % 360 - 180) > 155 for o2 in rays[:i])
        if ry.get("label"):
            cv.text(*_pol(cx, cy, r + (44 if close else 27), ry["deg"] - 90), ry["label"], ry.get("c") or "line", 12)
        if ry.get("mark"):
            cv.mark(x, y, ry["mark"])
    course = _rad(o.get("course", 0) or 0)
    arrow = [(0, -12), (6, 5), (0, 1), (-6, 5)]
    pts = [(cx + px * math.cos(course) - py * math.sin(course), cy + px * math.sin(course) + py * math.cos(course)) for px, py in arrow]
    pygame.draw.polygon(cv.layer, FC["line"], [cv.p(*q) for q in pts])
    cv.blit()


def _triangle(surf, box, o) -> None:
    apex = o.get("apex")
    A, B, C = (40, 172), (260, 172), (150 if apex is None else apex, 42)
    V = [A, B, C]
    cv = Canvas(surf, box, 300, 214)
    cv.poly(V)
    for i, a in enumerate(o.get("angles") or []):
        if a:
            t, c = _label(a)
            cv.ang_arc(V[i], V[(i + 1) % 3], V[(i + 2) % 3], 22, t, c or "arc")
    cen = ((A[0] + B[0] + C[0]) / 3, (A[1] + B[1] + C[1]) / 3)
    for i, sd in enumerate(o.get("sides") or []):
        if not sd:
            continue
        t, c = _label(sd)
        P1, P2 = V[i], V[(i + 1) % 3]
        mx, my = (P1[0] + P2[0]) / 2, (P1[1] + P2[1]) / 2
        dx, dy = mx - cen[0], my - cen[1]
        d = math.hypot(dx, dy) or 1
        cv.text(mx + dx / d * 18, my + dy / d * 18, t, c or "given")
    for i, tick in enumerate(o.get("ticks") or []):
        if not tick:
            continue
        P1, P2 = V[i], V[(i + 1) % 3]
        mx, my = (P1[0] + P2[0]) / 2, (P1[1] + P2[1]) / 2
        dx, dy = P2[0] - P1[0], P2[1] - P1[1]
        d = math.hypot(dx, dy)
        cv.line(mx - dy / d * 6, my + dx / d * 6, mx + dy / d * 6, my - dx / d * 6, "given", 2.5)
    for i, m in enumerate(o.get("marks") or []):
        if m:
            off = [(-6, 18), (6, 18), (0, -18)][i]
            cv.mark(V[i][0] + off[0], V[i][1] + off[1], m.get("kind"), m.get("label"))
    cv.blit()


def _angle_split(surf, box, o) -> None:
    full = o.get("total") == 180
    V = (160, 122) if full else (70, 150)
    names = o.get("names") or ["", "", ""]
    t = o["t"]
    cv = Canvas(surf, box, 320 if full else 280, 150 if full else 180)
    if full:
        cv.line(30, V[1], 290, V[1])
        cv.text(30, V[1] + 15, names[0], "dim", 11, "start")
        cv.text(290, V[1] + 15, names[1] if len(names) > 1 else "", "dim", 11, "end")
    else:
        cv.line(V[0], V[1], 262, V[1])
        cv.line(V[0], V[1], V[0], 28)
        cv.text(262, V[1] + 14, names[0], "dim", 11, "end")
        cv.text(V[0] + 7, 26, names[2] if len(names) > 2 else "", "dim", 11, "start")
        cv.right_mark(V, (1, 0), (0, -1))
    ray = -(90 - t) if o.get("given") == "v" else -t
    rx, ry = _pol(V[0], V[1], 112, ray)
    cv.line(V[0], V[1], rx, ry, "given", 2.5)
    if o.get("given") == "v":
        cv.arc(V[0], V[1], 34, -90, ray, "given")
        cv.text(*_pol(V[0], V[1], 52, (-90 + ray) / 2), f"{t}°", "given")
        cv.arc(V[0], V[1], 48, ray, 0, "ask")
        cv.text(*_pol(V[0], V[1], 66, ray / 2), "?", "ask")
    else:
        cv.arc(V[0], V[1], 34, ray, 0, "given")
        cv.text(*_pol(V[0], V[1], 52, ray / 2), f"{t}°", "given")
        cv.arc(V[0], V[1], 48, -o["total"], ray, "ask")
        cv.text(*_pol(V[0], V[1], 66, (-o["total"] + ray) / 2), "?", "ask")
    if o.get("rayLabel"):
        cv.text(rx + 6, ry - 9, o["rayLabel"], "given", 11, "start" if rx > V[0] + 40 else "middle")
    cv.blit()


def _polygon(surf, box, o) -> None:
    n, mode = o["n"], o.get("mode", "int")
    cx, cy, r = 122, 118, 78
    V = [_pol(cx, cy, r, -90 + i * 360 / n) for i in range(n)]
    cv = Canvas(surf, box, 256, 236)
    cv.poly(V)
    i0 = max(1, int(n / 4 + 0.5))
    v, prev, nxt = V[i0], V[(i0 - 1 + n) % n], V[(i0 + 1) % n]
    if mode == "int":
        cv.ang_arc(v, prev, nxt, 18, "?", "ask", lr=22)
    else:
        ex = (v[0] + (v[0] - prev[0]) * 0.75, v[1] + (v[1] - prev[1]) * 0.75)
        cv.line(v[0], v[1], ex[0], ex[1], "dim", 1.5, True)
        cv.ang_arc(v, ex, nxt, 18, "?", "ask", lr=24)
        cv.ang_arc(v, prev, nxt, 11, None, "dim")
    cv.text(cx, cy, f"{n} equal sides", "dim", 11)
    cv.blit()


def _parallel(surf, box, o) -> None:
    t, kind = o["t"], o.get("mode", "alt")  # the game's `kind` argument, stored as "mode"
    y1, y2, cx = 66, 152, 160
    k = 43 / math.tan(_rad(t))
    u = (math.cos(_rad(t)), -math.sin(_rad(t)))
    X1, X2 = (cx + k, y1), (cx - k, y2)
    cv = Canvas(surf, box, 320, 190)
    cv.line(30, y1, 290, y1)
    cv.line(30, y2, 290, y2)
    cv.text(32, y1 - 11, "column 1", "dim", 10, "start")
    cv.text(288, y2 + 13, "column 2", "dim", 10, "end")
    cv.line(X2[0] - u[0] * 36, X2[1] - u[1] * 36, X1[0] + u[0] * 36, X1[1] + u[1] * 36, "given", 2.4)
    cv.ang_arc(X1, (X1[0] - 40, X1[1]), (X1[0] - u[0] * 40, X1[1] - u[1] * 40), 20, f"{t}°", "given")
    if kind == "alt":
        cv.ang_arc(X2, (X2[0] + 40, X2[1]), (X2[0] + u[0] * 40, X2[1] + u[1] * 40), 20, "?", "ask")
    elif kind == "corr":
        cv.ang_arc(X2, (X2[0] - 40, X2[1]), (X2[0] - u[0] * 40, X2[1] - u[1] * 40), 20, "?", "ask")
    else:
        cv.ang_arc(X2, (X2[0] - 40, X2[1]), (X2[0] + u[0] * 40, X2[1] + u[1] * 40), 20, "?", "ask")
    cv.blit()


def _scale_line(surf, box, o) -> None:
    k, ask = o["k"], o.get("ask")
    cv = Canvas(surf, box, 320, 150)
    cv.text(160, 20, f"Scale: 1 cm on the plot = {k} nm at sea", "dim", 12)
    x0, y = 40, 100
    if ask == "cm":
        # The paper length is the answer, so the line is not drawn to scale and has no
        # centimetre ticks to count: just a tick at each end.
        x1 = x0 + 230
        cv.line(x0, y, x1, y, "line", 3)
        for x in (x0, x1):
            cv.line(x, y - 6, x, y + 6, "dim", 1.5)
        cv.text((x0 + x1) / 2, y - 20, "? cm", "ask")
        cv.text((x0 + x1) / 2, y + 28, f"{_num(o['d'])} nm", "given")
        cv.text(160, 140, "not to scale", "dim", 10)
    else:
        m = o["m"]
        ppc = min(34, 230 / m)
        x1 = x0 + m * ppc
        cv.line(x0, y, x1, y, "line", 3)
        for i in range(int(m) + 1):
            cv.line(x0 + i * ppc, y - 6, x0 + i * ppc, y + 6, "dim", 1.5)
        cv.text((x0 + x1) / 2, y - 20, f"{_num(m)} cm", "given")
        cv.text((x0 + x1) / 2, y + 28, "? nm", "ask")
    cv.mark(x0, y, "you")
    cv.mark(x1, y, "target")
    cv.blit()


def _num(v: float) -> str:
    return str(int(v)) if float(v).is_integer() else f"{v:g}"


def _similar(surf, box, o) -> None:
    a, b, c, k = o["a"], o["b"], o["c"], o["k"]
    u = min(140 / (a * k), 120 / (b * k))
    W1, H1, W2, H2 = a * u, b * u, a * k * u, b * k * u
    y0 = 34 + H2
    cv = Canvas(surf, box, 30 + W1 + 76 + W2 + 50, y0 + 34)

    def tri(x, W, H, la, lb, lc):
        P, R, Q = (x, y0), (x + W, y0), (x + W, y0 - H)
        cv.poly([P, R, Q])
        cv.right_mark(R, (-1, 0), (0, -1))
        cv.text(x + W / 2, y0 + 16, la[0], la[1])
        if lb[0]:
            cv.text(x + W + 8, y0 - H / 2, lb[0], lb[1], 12, "start")
        cv.text(x + W / 2 - 8, y0 - H / 2 - 10, lc[0], lc[1], 13, "end")

    tri(30, W1, H1, (_num(a), "given"), (_num(b), "given"), (_num(c), "given"))
    tri(30 + W1 + 76, W2, H2, (_num(a * k), "given"), ("", "dim"), ("?", "ask"))
    cv.text(30 + W1 + 38, y0 - 10, f"×{_num(k)}", "arc", 14)
    cv.blit()


def _grid(surf, box, o) -> None:
    p1, p2, kind = o["p1"], o["p2"], o.get("mode", "dist")  # the game's `kind` argument, stored as "mode"
    if kind == "mid":
        _grid_mid(surf, box, p1, p2)
        return
    maxX, maxY = max(p1[0], p2[0]) + 1, max(p1[1], p2[1]) + 1
    cell = min(230 / maxX, 170 / maxY, 26)
    ox, oy = 42, 24 + maxY * cell
    cv = Canvas(surf, box, ox + maxX * cell + 70, oy + 40)

    def X(x):
        return ox + x * cell

    def Y(y):
        return oy - y * cell

    for i in range(int(maxX) + 1):
        cv.line(X(i), Y(0), X(i), Y(maxY), (255, 255, 255, 30), 1)
    for j in range(int(maxY) + 1):
        cv.line(X(0), Y(j), X(maxX), Y(j), (255, 255, 255, 30), 1)
    cv.line(X(0), Y(0), X(maxX), Y(0), "dim", 1.5)
    cv.line(X(0), Y(0), X(0), Y(maxY), "dim", 1.5)
    cv.text(X(0) - 8, Y(0) + 8, "0", "dim", 10)
    A, B = (X(p1[0]), Y(p1[1])), (X(p2[0]), Y(p2[1]))
    up = B[1] < A[1]
    C = (B[0], A[1])
    cv.line(A[0], A[1], C[0], C[1], "given", 2, True)
    cv.line(C[0], C[1], B[0], B[1], "given", 2, True)
    cv.line(A[0], A[1], B[0], B[1], "ask", 2.5)
    cv.text((A[0] + C[0]) / 2, A[1] + (14 if up else -12), f"Δx = {abs(p2[0] - p1[0])}", "given", 11)
    cv.text(C[0] + 8, (C[1] + B[1]) / 2, f"Δy = {abs(p2[1] - p1[1])}", "given", 11, "start")
    cv.text((A[0] + B[0]) / 2 - 12, (A[1] + B[1]) / 2 + (-10 if up else 10), "?", "ask", 16)
    cv.mark(A[0], A[1], "you")
    cv.mark(B[0], B[1], "target")
    cv.text(A[0], A[1] + (-16 if up else 26), f"({p1[0]}, {p1[1]})", "given", 11)
    cv.text(B[0], B[1] + (26 if up else -14), f"({p2[0]}, {p2[1]})", "given", 11)
    cv.blit()


def _grid_mid(surf, box, p1, p2) -> None:
    """The midpoint picture: a sketch, not a grid. Drawn to scale, the "?" could be read off by counting squares."""
    cv = Canvas(surf, box, 320, 200)
    left = p1[0] <= p2[0]
    low = p1[1] <= p2[1]
    A = (60 if left else 260, 150 if low else 50)
    B = (260 if left else 60, 50 if low else 150)
    M = ((A[0] + B[0]) / 2, (A[1] + B[1]) / 2)
    cv.line(A[0], A[1], B[0], B[1], "dim", 2, True)
    cv.circle(M[0], M[1], 6, "ask", 2)
    cv.text(M[0] + 14, M[1] + 16, "(?, ?)", "ask", 13, "start")
    cv.text(M[0] - 12, M[1] - 12, "halfway", "dim", 10, "end")
    cv.mark(A[0], A[1], "escort")
    cv.mark(B[0], B[1], "escort")
    cv.text(A[0], A[1] + (26 if low else -14), f"({p1[0]}, {p1[1]})", "given", 11)
    cv.text(B[0], B[1] + (-14 if low else 26), f"({p2[0]}, {p2[1]})", "given", 11)
    cv.text(160, 192, "sketch, not to scale", "dim", 10)
    cv.blit()


def _rect(surf, box, o) -> None:
    Lv, Wv, mode = o["Lv"], o["Wv"], o.get("mode", "area")
    w, h, x, y = 220, _clamp(220 * Wv / Lv, 60, 150), 50, 30
    cv = Canvas(surf, box, 320, y + h + 40)
    corners = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
    pygame.draw.polygon(cv.layer, FC["fill"], [cv.p(*q) for q in corners])
    for i in range(4):
        a, b = corners[i], corners[(i + 1) % 4]
        cv.line(a[0], a[1], b[0], b[1], "ask" if mode == "perim" else "line", 3.5 if mode == "perim" else 2, mode == "perim")
    cv.text(x + w / 2, y + h + 18, "? ft" if mode == "L" else f"{_num(Lv)} ft", "ask" if mode == "L" else "given")
    cv.text(x + w + 12, y + h / 2, f"{_num(Wv)} ft", "given", 13, "start")
    inside = {"area": "A = ?", "L": f"A = {Lv * Wv:,.0f}"}.get(mode, "P = ?")
    cv.text(x + w / 2, y + h / 2, inside, "given" if mode == "L" else "ask", 16)
    cv.blit()


def _tri_area(surf, box, o) -> None:
    b, h = o["b"], o["h"]
    W, H, x = 220, _clamp(220 * h / b, 60, 150), 40
    y0, ax = 30 + H, x + W * 0.62
    cv = Canvas(surf, box, 320, y0 + 36)
    cv.poly([(x, y0), (x + W, y0), (ax, 30)])
    cv.line(ax, 30, ax, y0, "given", 2, True)
    cv.right_mark((ax, y0), (1, 0), (0, -1))
    cv.text(x + W / 2, y0 + 18, f"b = {_num(b)} ft", "given")
    cv.text(ax - 8, 30 + H / 2, f"h = {_num(h)} ft", "given", 12, "end")
    cv.text(x + W * 0.36, y0 - H * 0.22, "A = ?", "ask", 15)
    cv.blit()


def _circle(surf, box, o) -> None:
    cx, cy, R = 120, 110, 76
    mode, unit = o.get("mode", "area"), o.get("unit", "")
    cv = Canvas(surf, box, 300, 220)
    cv.circle(cx, cy, R, "ask" if mode == "circ" else "line", 4 if mode == "circ" else 2, fill="fill" if mode == "area" else None)
    pygame.draw.circle(cv.layer, FC["line"], cv.p(cx, cy), 3 * cv.k)
    if o.get("d") is not None:
        cv.line(cx - R, cy, cx + R, cy, "given", 2.5)
        cv.text(cx, cy - 12, f"d = {_num(o['d'])} {unit}", "given")
    else:
        x, y = _pol(cx, cy, R, -35)
        cv.line(cx, cy, x, y, "given", 2.5)
        cv.text(cx + 22, cy - 36, f"r = {_num(o['r'])} {unit}", "given", 12)
    if mode == "circ":
        cv.text(cx + R + 14, cy + 62, "C = ?", "ask", 15, "start")
    else:
        cv.text(cx, cy + 34, "A = ?", "ask", 15)
    cv.blit()


def _arc(surf, box, o) -> None:
    r, th = o["r"], o["th"]
    cx, cy, R = 150, 118, 84
    a0, a1 = -90, -90 + th
    cv = Canvas(surf, box, 300, 240)
    cv.circle(cx, cy, R, "dim", 1.5, dash=True)
    pygame.draw.circle(cv.layer, FC["line"], cv.p(cx, cy), 3 * cv.k)
    cv.arc(cx, cy, R, a0, a1, "ask", 4.5)
    sx, sy = _pol(cx, cy, R, a0)
    ex, ey = _pol(cx, cy, R, a1)
    cv.line(cx, cy, sx, sy, "given", 2)
    cv.line(cx, cy, ex, ey, "line", 1.5, True)
    cv.text(cx - 8, cy - R / 2, f"r = {_num(r)} yd", "given", 12, "end")
    cv.arc(cx, cy, 24, a0, a1, "arc")
    cv.text(*_pol(cx, cy, 40, (a0 + a1) / 2), f"{th}°", "arc", 12)
    cv.mark(sx, sy, "you")
    cv.text(*_pol(cx, cy, R + 20, (a0 + a1) / 2), "arc = ?", "ask", 14)
    cv.blit()


def _box(surf, box, o) -> None:
    Lv, Wv, Hv, mode = o["Lv"], o["Wv"], o["Hv"], o.get("mode", "vol")
    m = max(Lv, Wv, Hv)
    s1, s2, s3 = _clamp(150 * Lv / m, 50, 150), _clamp(150 * Hv / m, 40, 150), _clamp(80 * Wv / m, 26, 80)
    x, dx, dy = 40, s3 * 0.9, -s3 * 0.6
    y = 30 - dy
    surf_mode = mode == "surf"
    F = [(x, y), (x + s1, y), (x + s1, y + s2), (x, y + s2)]
    Tp = [(x, y), (x + dx, y + dy), (x + s1 + dx, y + dy), (x + s1, y)]
    Sd = [(x + s1, y), (x + s1 + dx, y + dy), (x + s1 + dx, y + s2 + dy), (x + s1, y + s2)]
    cv = Canvas(surf, box, x + s1 + dx + 84, y + s2 + 36)
    cv.poly(F, (78, 203, 238, 56) if surf_mode else "fill")
    cv.poly(Tp, (95, 227, 192, 61) if surf_mode else (255, 255, 255, 15))
    cv.poly(Sd, (255, 201, 74, 56) if surf_mode else (0, 0, 0, 46))
    cv.text(x + s1 / 2, y + s2 + 18, f"{_num(Lv)} ft", "given")
    cv.text(x + s1 + dx + 10, y + s2 / 2 + dy / 2, f"{_num(Hv)} ft", "given", 13, "start")
    cv.text(x + s1 + dx / 2 + 12, y + s2 + dy / 2 + 12, f"{_num(Wv)} ft", "given", 12, "start")
    cv.text(x + s1 / 2, y + s2 / 2, "6 faces = ?" if surf_mode else "V = ?", "ask", 15)
    cv.blit()


def _cyl(surf, box, o) -> None:
    r, h = o["r"], o["h"]
    m = max(2 * r, h)
    R = _clamp(120 * r / m, 34, 100)
    ry, H, cx = R * 0.32, _clamp(150 * h / m, 50, 150), 140
    top = 40 + ry
    cv = Canvas(surf, box, cx + R + 90, top + H + ry + 18)
    body = [(cx - R, top), (cx - R, top + H)] + [
        (cx + R * math.cos(math.pi - a), top + H + ry * math.sin(math.pi - a)) for a in [i * math.pi / 24 for i in range(25)]
    ] + [(cx + R, top)]
    pygame.draw.polygon(cv.layer, FC["fill"], [cv.p(*q) for q in body])
    pygame.draw.lines(cv.layer, FC["line"], False, [cv.p(*q) for q in body], cv.w(2))
    ell = pygame.Rect(0, 0, 2 * R * cv.k, 2 * ry * cv.k)
    ell.center = cv.p(cx, top)
    pygame.draw.ellipse(cv.layer, (255, 255, 255, 20), ell)
    pygame.draw.ellipse(cv.layer, FC["line"], ell, cv.w(2))
    back = [(cx + R * math.cos(math.pi + a), top + H + ry * math.sin(math.pi + a)) for a in [i * math.pi / 12 for i in range(13)]]
    for i in range(0, len(back) - 1, 2):
        cv.line(*back[i], *back[i + 1], "dim", 1.5)
    cv.line(cx, top, cx + R, top, "given", 2.5)
    cv.text(cx + R / 2, top - ry - 11, f"r = {_num(r)} ft", "given", 12)
    cv.text(cx + R + 12, top + H / 2, f"h = {_num(h)} ft", "given", 13, "start")
    cv.text(cx, top + H / 2 + 4, "V = ?", "ask", 15)
    cv.blit()


def _trap(surf, box, o) -> None:
    a, b, h = o["a"], o["b"], o["h"]
    W = 230
    tw, H, x, y = W * a / b, _clamp(230 * h / b, 60, 140), 40, 30
    off = (W - tw) / 2
    hx = x + off + tw - 24
    cv = Canvas(surf, box, 320, y + H + 40)
    cv.poly([(x + off, y), (x + off + tw, y), (x + W, y + H), (x, y + H)])
    cv.line(hx, y, hx, y + H, "given", 2, True)
    cv.right_mark((hx, y + H), (1, 0), (0, -1))
    cv.text(x + W / 2, y - 12, f"{_num(a)} ft", "given")
    cv.text(x + W / 2, y + H + 18, f"{_num(b)} ft", "given")
    cv.text(hx + 8, y + H / 2, f"h = {_num(h)} ft", "given", 12, "start")
    cv.text(x + W * 0.33, y + H / 2, "A = ?", "ask", 15)
    cv.blit()


def _composite(surf, box, o) -> None:
    Lv, Wv, b = o["Lv"], o["Wv"], o["b"]
    sc = 210 / (Lv + b)
    Lw, bw, Hh, x, y = Lv * sc, max(b * sc, 22), _clamp(Wv * sc, 40, 120), 70, 40
    cv = Canvas(surf, box, x + Lw + bw + 30, y + Hh + 40)
    cv.poly([(x, y), (x + Lw, y), (x + Lw, y + Hh), (x, y + Hh)])
    cv.poly([(x + Lw, y), (x + Lw + bw, y + Hh / 2), (x + Lw, y + Hh)], (95, 227, 192, 46))
    cv.text(x + Lw / 2, y + Hh + 18, f"{_num(Lv)} ft", "given")
    cv.text(x - 8, y + Hh / 2, f"{_num(Wv)} ft", "given", 12, "end")
    cv.text(x + Lw + bw / 2, y - 12, f"{_num(b)} ft", "given", 12)
    cv.text(x + Lw / 2, y + Hh / 2, "A = ?", "ask", 15)
    cv.blit()


# --------------------------------------------------------------------------- shields (circles)
# Shield figures are sketches in a fixed layout: nothing about them is to scale, so no length,
# angle or centre can be read off the drawing.


def _unit(a: float) -> tuple[float, float]:
    return math.cos(_rad(a)), math.sin(_rad(a))


def _side_label(cv: Canvas, P1, P2, v, default: str, off: float = 14, up: bool = True, f: float = 0.5) -> None:
    """Label ``v`` beside the segment P1-P2, ``f`` of the way along, on its upper (or lower) side."""
    t, c = _label(v)
    if not t:
        return
    dx, dy = P2[0] - P1[0], P2[1] - P1[1]
    d = math.hypot(dx, dy) or 1
    nx, ny = dy / d, -dx / d
    if (ny > 0 or (ny == 0 and nx < 0)) == up:
        nx, ny = -nx, -ny
    x, y = P1[0] + dx * f + nx * off, P1[1] + dy * f + ny * off
    anchor = "start" if nx > 0.5 else "end" if nx < -0.5 else "middle"
    cv.text(x, y, t, c or default, 13, anchor)


def _shield_disc(cv: Canvas, O, R, dot: bool = True) -> None:
    cv.circle(O[0], O[1], R, "lav", 2.5, fill="fill")
    if dot:
        pygame.draw.circle(cv.layer, FC["line"], cv.p(*O), 3 * cv.k)


def _letters(cv: Canvas, O, R, pts, names) -> None:
    for P, n in zip(pts, names or []):
        if n:
            ux, uy = (P[0] - O[0]) / R, (P[1] - O[1]) / R
            cv.text(P[0] + ux * 14, P[1] + uy * 14, n, "dim", 11)


def _shield(surf, box, o) -> None:
    O, R = (170, 128), 62
    cv = Canvas(surf, box, 340, 262)
    _shield_disc(cv, O, R)
    pt = o.get("point")
    sx, sy = (pt.get("dir") or [1, 1]) if pt else (1, 1)
    ship = o.get("ship")
    if ship == "target":
        cv.mark(O[0], O[1], "target")
    elif ship:
        cv.mark(O[0], O[1] - 14, ship)
    t, c = _label(o.get("centre"))
    if t:
        cv.text(O[0], O[1] + (-20 if pt and sy < 0 else 20), t, c or "given", 13)
    if pt:
        a = (-40 if sy > 0 else 40) if sx > 0 else (-140 if sy > 0 else 140)
        u = _unit(a)
        on = bool(pt.get("on"))
        dist = R if on else R * 1.75
        P = (O[0] + u[0] * dist, O[1] + u[1] * dist)
        E = (O[0] + u[0] * R, O[1] + u[1] * R)
        cv.line(O[0], O[1], P[0], P[1], "dim", 1.5, True)
        if not on:
            gt, gc = _label(o.get("gap"))
            cv.line(E[0], E[1], P[0], P[1], gc or "ask", 3)
            if gt:
                mx, my = (E[0] + P[0]) / 2, (E[1] + P[1]) / 2
                cv.text(mx - u[1] * 14, my + u[0] * 14, gt, gc or "ask", 14)
        if pt.get("mark"):
            cv.mark(P[0], P[1], pt["mark"])
        lt, lc = _label({"t": pt.get("label"), "c": pt.get("c")})
        if lt:
            cv.text(P[0] + u[0] * 22, P[1] + u[1] * 22, lt, lc or "given", 12, "start" if u[0] > 0 else "end")
        ra = a if on else 180 - a
    else:
        ra = -35
    if o.get("radius") is not None:
        u = _unit(ra)
        end = (O[0] + u[0] * R, O[1] + u[1] * R)
        if pt and pt.get("on"):  # the dashed line to the point is the radius; its label goes beside it
            _side_label(cv, O, end, o["radius"], "given", 16, f=0.55)
        else:  # a radius of its own, labelled just past its end, outside the shield
            t, c = _label(o["radius"])
            cv.line(O[0], O[1], end[0], end[1], c or "given", 2.5)
            if t:
                cv.text(O[0] + u[0] * (R + 12), O[1] + u[1] * (R + 12), t, c or "given", 13, "start" if u[0] > 0 else "end")
    t, c = _label(o.get("edge"))
    if t:
        cv.text(O[0], O[1] + R + 18, t, c or "ask", 13)
    cv.text(O[0], 252, o.get("note", "sketch, not to scale"), "dim", 10)
    cv.blit()


def _tangents(surf, box, o) -> None:
    O, R, P = (118, 122), 64, (290, 122)
    cv = Canvas(surf, box, 340, 244)
    phi = math.degrees(math.acos(R / (P[0] - O[0])))
    T, T2 = _pol(O[0], O[1], R, -phi), _pol(O[0], O[1], R, phi)
    two = bool(o.get("two"))
    _shield_disc(cv, O, R)
    for key, a0, a1, mid in (("arc", -phi, phi, 0), ("far", phi, 360 - phi, 180)):
        t, c = _label(o.get(key))
        if t:
            cv.arc(O[0], O[1], R, a0, a1, c or "ask", 4.5)
            cv.text(*_pol(O[0], O[1], R + 20, mid), t, c or "ask", 14)
    if o.get("op") is not None or o.get("oline"):
        cv.line(O[0], O[1], P[0], P[1], "dim", 1.5, True)
    cv.line(P[0], P[1], T[0], T[1], "line", 2.2)
    if two:
        cv.line(P[0], P[1], T2[0], T2[1], "line", 2.2)
    if o.get("radii", True):
        for Q in (T, T2) if two else (T,):
            cv.line(O[0], O[1], Q[0], Q[1], "line", 1.8)
            if o.get("right"):
                u = ((O[0] - Q[0]) / R, (O[1] - Q[1]) / R)
                d = math.dist(P, Q)
                cv.right_mark(Q, u, ((P[0] - Q[0]) / d, (P[1] - Q[1]) / d))
    if o.get("angP"):
        t, c = _label(o["angP"])
        cv.ang_arc(P, T2 if two else O, T, 30, t, c or "arc")
    if o.get("angO"):
        t, c = _label(o["angO"])
        cv.ang_arc(O, T, T2 if two else P, 18, t, c or "arc")
    _side_label(cv, O, P, o.get("op"), "given", 13, up=False)
    _side_label(cv, O, T, o.get("ot"), "given", 10, up=False)  # inside the triangle, clear of the outline
    _side_label(cv, T, P, o.get("pt"), "given", 13)
    _side_label(cv, T2, P, o.get("pt2"), "given", 13, up=False)
    _letters(cv, O, R, (T, T2), o.get("names") or (["A", "B"] if two else ["T"]))
    for k, m in (o.get("marks") or {}).items():
        if k == "P" and m:
            cv.mark(P[0] + 14, P[1], m.get("kind"), m.get("label"))
    if o.get("note"):
        cv.text(170, 12, o["note"], "dim", 11)
    cv.blit()


def _chord(surf, box, o) -> None:
    O, R, dd = (150, 108), 78, 44  # the course passes a little over half a radius from the centre
    y = O[1] + dd
    hw = math.sqrt(R * R - dd * dd)
    A, B, M = (O[0] - hw, y), (O[0] + hw, y), (O[0], y)
    cv = Canvas(surf, box, 300, 228)
    _shield_disc(cv, O, R)
    ct, cc = _label(o.get("chord"))
    cv.line(18, y, A[0], y, "dim", 1.5, True)
    cv.line(B[0], y, 282, y, "dim", 1.5, True)
    cv.line(A[0], y, B[0], y, cc or "line", 3)
    cv.mark(26, y, "you")
    dt, dc = _label(o.get("d"))
    cv.line(O[0], O[1], M[0], M[1], dc or "given", 2, True)
    cv.right_mark(M, (0, -1), (1, 0))
    if dt:
        cv.text(O[0] - 8, O[1] + dd / 2, dt, dc or "given", 13, "end")
    end = B if o.get("radius_to") == "end" else _pol(O[0], O[1], R, -130)
    rt, rc = _label(o.get("r"))
    if rt:
        cv.line(O[0], O[1], end[0], end[1], rc or "given", 2)
        _side_label(cv, O, end, o["r"], "given", 12)
    ht, hc = _label(o.get("half"))
    if ht:
        cv.text((M[0] + B[0]) / 2, y - 11, ht, hc or "given", 12)
    if ct:
        cv.text(O[0], y + 16, ct, cc or "ask", 13)
    cv.text(150, 222, o.get("note", "sketch, not to scale"), "dim", 10)
    cv.blit()


def _chords(surf, box, o) -> None:
    O, R, X = (150, 112), 84, (132, 126)
    cv = Canvas(surf, box, 300, 230)
    _shield_disc(cv, O, R, dot=False)
    w = (X[0] - O[0], X[1] - O[1])
    for deg, (k1, k2) in ((18, ("a", "b")), (118, ("c", "d"))):
        u = _unit(deg)
        uw = u[0] * w[0] + u[1] * w[1]
        root = math.sqrt(uw * uw - (w[0] ** 2 + w[1] ** 2 - R * R))
        ends = [(X[0] + u[0] * t, X[1] + u[1] * t) for t in (-uw - root, -uw + root)]
        cv.line(ends[0][0], ends[0][1], ends[1][0], ends[1][1], "line", 2.2)
        n = (u[1], -u[0]) if deg < 90 else (-u[1], u[0])  # the first chord's labels go above it, the second's to its left
        anchor = "end" if n[0] < -0.4 else "middle"
        for key, E in zip((k1, k2), ends):
            pygame.draw.circle(cv.layer, FC["line"], cv.p(*E), 2.5 * cv.k)
            t, c = _label(o.get(key))
            if t:
                off = 12 if anchor == "middle" else 8
                cv.text((X[0] + E[0]) / 2 + n[0] * off, (X[1] + E[1]) / 2 + n[1] * off, t, c or "given", 13, anchor)
    pygame.draw.circle(cv.layer, FC["given"], cv.p(*X), 3.5 * cv.k)
    cv.text(150, 222, o.get("note", "sketch, not to scale"), "dim", 10)
    cv.blit()


def _inscribed(surf, box, o) -> None:
    O, R = (150, 112), 80
    mode = o.get("mode", "arc")
    cv = Canvas(surf, box, 300, 232)

    def at(a: float) -> tuple[float, float]:
        return _pol(O[0], O[1], R, a)

    def ang(V, P1, P2, key, r=20):
        if o.get(key):
            t, c = _label(o[key])
            cv.ang_arc(V, P1, P2, r, t, c or "arc")

    _shield_disc(cv, O, R, dot=mode != "quad")
    if mode == "quad":
        pts = [at(a) for a in (160, 250, 340, 70)]
        for i in range(4):
            cv.line(*pts[i], *pts[(i + 1) % 4], "line", 2.2)
        for i, key in enumerate(("angA", "angB", "angC", "angD")):
            ang(pts[i], pts[i - 1], pts[(i + 1) % 4], key)
        _letters(cv, O, R, pts, o.get("names") or ["A", "B", "C", "D"])
    else:
        semi = mode == "semi"
        A, B, C = (at(180), at(0), at(235)) if semi else (at(145), at(35), at(262))
        if semi:
            cv.line(A[0], A[1], B[0], B[1], "line", 2.2)
            ang(A, B, C, "angA")
            ang(B, A, C, "angB")
        else:
            cv.line(O[0], O[1], A[0], A[1], "line", 1.8)
            cv.line(O[0], O[1], B[0], B[1], "line", 1.8)
            ang(O, A, B, "central", 18)
        cv.line(C[0], C[1], A[0], A[1], "line", 2.2)
        cv.line(C[0], C[1], B[0], B[1], "line", 2.2)
        ang(C, A, B, "angC" if semi else "rim", 18 if semi else 22)
        _letters(cv, O, R, (A, B), o.get("names") or ["A", "B"])
        m = (o.get("marks") or {}).get("C")
        if m:
            cv.mark(C[0], C[1] - 12, m.get("kind"), m.get("label"))
    if o.get("note"):
        cv.text(150, 226, o["note"], "dim", 10)
    cv.blit()


# --------------------------------------------------------------------------- Dino Math (Math Boost)
# The sketches of problems/dinomath.py's geometry problems, ported from its SVG: drawn
# to scale in a 200 x 106 box with the base line at y = 88, so a side labeled twice as
# long looks twice as long. A dashed red line is a height, with its right-angle mark;
# dashed grey lines are hidden edges.


def _dm_canvas(surf, box) -> Canvas:
    return Canvas(surf, box, 200, 110)


def _dm_lab(cv: Canvas, x, y, s, cls: str = "") -> None:
    """An SVG label: (x, y) is the baseline; class s anchors the start, e the end, hl colors it as a height."""
    classes = cls.split()
    anchor = "start" if "s" in classes else "end" if "e" in classes else "middle"
    cv.text(x, y - 4.5, s, "red" if "hl" in classes else "given", 13, anchor)


def _dm_path(cv: Canvas, pts, cls: str = "shape", close: bool = True) -> None:
    if cls == "cut":  # a hidden edge
        for a, b in zip(pts, pts[1:] + (pts[:1] if close else [])):
            cv.line(*a, *b, "dim", 1.5, True)
        return
    fill = {"shape": "fill", "top": (78, 203, 238, 64), "side": (78, 203, 238, 14)}[cls]
    cv.poly(pts, fill, "line", 2.5)


def _dm_height(cv: Canvas, x, y1, y2, corner_dx) -> None:
    """A dashed height from (x, y1) down to the base at y2, with its right-angle mark on the side of corner_dx."""
    cv.line(x, y1, x, y2, "red", 2, True)
    pts = [(x + corner_dx, y2), (x + corner_dx, y2 - 8), (x, y2 - 8)]
    pygame.draw.lines(cv.layer, FC["red"], False, [cv.p(*q) for q in pts], cv.w(1.5))


def _dm_side(cv: Canvas, P, Q, s) -> None:
    """A label beside the side from P to Q, on the left going from P to Q."""
    dx, dy = Q[0] - P[0], Q[1] - P[1]
    length = math.hypot(dx, dy)
    nx, ny = dy / length, -dx / length
    _dm_lab(cv, (P[0] + Q[0]) / 2 + nx * 10, (P[1] + Q[1]) / 2 + ny * 10 + 4, s, "e" if nx < -0.3 else "s" if nx > 0.3 else "")


def _dm_circle(surf, box, o) -> None:
    across, u = o["across"], o["u"]
    cv = _dm_canvas(surf, box)
    cv.circle(100, 52, 46, "line", 2.5, fill="fill")
    pygame.draw.circle(cv.layer, FC["line"], cv.p(100, 52), 3 * cv.k)
    cv.line(54 if across else 100, 52, 146, 52, "line", 2.5)
    _dm_lab(cv, 100 if across else 123, 45, f"{o['len']} {u}")
    cv.blit()


def _dm_triangle(surf, box, o) -> None:
    b, h, run, s, u = o["b"], o["h"], o["run"], o["s"], o["u"]
    k = min(150 / b, 72 / h)
    x0 = 100 - b * k / 2
    xf, top = x0 + run * k, 88 - h * k
    room_left = run > b - run  # the height label goes on the wider side of the dashed line
    cv = _dm_canvas(surf, box)
    _dm_path(cv, [(x0, 88), (x0 + b * k, 88), (xf, top)])
    _dm_height(cv, xf, top, 88, -8 if room_left else 8)
    _dm_lab(cv, x0 + b * k / 2, 102, f"{b} {u}")
    _dm_lab(cv, xf + (-5 if room_left else 5), 88 - h * k / 2 + 5, f"{h} {u}", "hl e" if room_left else "hl s")
    if s:
        _dm_side(cv, (x0, 88), (xf, top), f"{s} {u}")
    cv.blit()


def _dm_para(surf, box, o) -> None:
    b, h, off, s, u = o["b"], o["h"], o["off"], o["s"], o["u"]
    k = min(160 / (b + off), 72 / h)
    x0 = 100 - (b + off) * k / 2
    top, xt = 88 - h * k, x0 + off * k
    cv = _dm_canvas(surf, box)
    _dm_path(cv, [(x0, 88), (x0 + b * k, 88), (xt + b * k, top), (xt, top)])
    _dm_height(cv, xt, top, 88, 8)
    _dm_lab(cv, x0 + b * k / 2, 102, f"{b} {u}")
    _dm_lab(cv, xt + 5, 88 - h * k / 2 + 5, f"{h} {u}", "hl s")
    _dm_side(cv, (xt + b * k, top), (x0 + b * k, 88), f"{s} {u}")
    cv.blit()


def _dm_trap(surf, box, o) -> None:
    b1, b2, h, u = o["b1"], o["b2"], o["h"], o["u"]
    k = min(176 / b2, 68 / h)
    x0, top, xt = 100 - b2 * k / 2, 88 - h * k, 100 - b1 * k / 2
    cv = _dm_canvas(surf, box)
    _dm_path(cv, [(x0, 88), (x0 + b2 * k, 88), (xt + b1 * k, top), (xt, top)])
    _dm_height(cv, xt, top, 88, 8)
    _dm_lab(cv, 100, top - 5, f"{b1} {u}")
    _dm_lab(cv, 100, 102, f"{b2} {u}")
    _dm_lab(cv, xt + 5, 88 - h * k / 2 + 5, f"{h} {u}", "hl s")
    cv.blit()


def _dm_house(surf, box, o) -> None:
    w, h1, h2, u = o["w"], o["h1"], o["h2"], o["u"]
    k = min(130 / w, 78 / (h1 + h2))
    x0 = 100 - w * k / 2
    eave = 88 - h1 * k
    peak = eave - h2 * k
    low = h2 * k < 24  # a low roof has no room inside for its label: it goes above the peak
    cv = _dm_canvas(surf, box)
    _dm_path(cv, [(x0, 88), (x0, eave), (100, peak), (x0 + w * k, eave), (x0 + w * k, 88)])
    _dm_path(cv, [(x0, eave), (x0 + w * k, eave)], "cut", False)
    _dm_height(cv, 100, peak, eave, 8)
    _dm_lab(cv, 100, 102, f"{w} {u}")
    _dm_lab(cv, x0 + w * k + 5, 88 - h1 * k / 2 + 5, f"{h1} {u}", "s")
    _dm_lab(cv, 106 if low else 105, peak - 3 if low else eave - 5, f"{h2} {u}", "hl s")
    cv.blit()


def _dm_l(surf, box, o) -> None:
    W, H, a, b, u = o["W"], o["H"], o["a"], o["b"], o["u"]
    k = min(140 / W, 74 / H)
    x0, top, step = 100 - W * k / 2, 88 - H * k, 88 - b * k
    cv = _dm_canvas(surf, box)
    _dm_path(cv, [(x0, top), (x0 + a * k, top), (x0 + a * k, step), (x0 + W * k, step), (x0 + W * k, 88), (x0, 88)])
    _dm_lab(cv, 100, 102, f"{W} {u}")
    _dm_lab(cv, x0 - 5, 88 - H * k / 2 + 5, f"{H} {u}", "e")
    _dm_lab(cv, x0 + a * k / 2, top - 5, f"{a} {u}")
    _dm_lab(cv, x0 + W * k + 5, 88 - b * k / 2 + 5, f"{b} {u}", "s")
    cv.blit()


def _dm_round(surf, box, o) -> None:
    w, h, u = o["w"], o["h"], o["u"]
    k = min(150 / (w + h / 2), 72 / h)
    x0 = 100 - (w + h / 2) * k / 2 + 6
    top, r = 88 - h * k, h * k / 2
    xe = x0 + w * k
    arc = [(xe + r * math.cos(a), top + r + r * math.sin(a)) for a in [-math.pi / 2 + math.pi * i / 24 for i in range(25)]]
    cv = _dm_canvas(surf, box)
    _dm_path(cv, [(x0, top), *arc, (x0, 88)])
    _dm_path(cv, [(xe, top), (xe, 88)], "cut", False)
    _dm_lab(cv, x0 + w * k / 2, top - 5, f"{w} {u}")
    _dm_lab(cv, x0 - 5, 88 - h * k / 2 + 5, f"{h} {u}", "e")
    cv.blit()


def _dm_box(surf, box, o) -> None:
    l, w, h, u, cube = o["l"], o["w"], o["h"], o["u"], o.get("cube")
    hh = l * 0.6 if h == "?" else h  # an unknown height still needs drawing
    k = min(130 / (l + 0.45 * w), 76 / (hh + 0.3 * w))
    dx, dy = 0.45 * w * k, 0.3 * w * k
    x0 = 100 - (l * k + dx) / 2 + 6
    x1, bot, top = x0 + l * k, 88, 88 - hh * k
    cv = _dm_canvas(surf, box)
    _dm_path(cv, [(x0, bot), (x1, bot), (x1, top), (x0, top)])
    _dm_path(cv, [(x0, top), (x0 + dx, top - dy), (x1 + dx, top - dy), (x1, top)], "top")
    _dm_path(cv, [(x1, top), (x1 + dx, top - dy), (x1 + dx, bot - dy), (x1, bot)], "side")
    _dm_path(cv, [(x0, bot), (x0 + dx, bot - dy), (x1 + dx, bot - dy)], "cut", False)  # seen through the faces
    _dm_path(cv, [(x0 + dx, bot - dy), (x0 + dx, top - dy)], "cut", False)
    _dm_lab(cv, (x0 + x1) / 2, 102, f"{l} {u}")
    if not cube:
        _dm_lab(cv, x0 - 5, (top + bot) / 2 + 5, f"{h} {u}", "e")
        _dm_lab(cv, x1 + dx / 2 + 6, bot - dy / 2 + 9, f"{w} {u}", "s")
    cv.blit()


def _dm_prism(surf, box, o) -> None:
    b, h, L, u = o["b"], o["h"], o["L"], o["u"]
    k = min(130 / (b + 0.45 * L), 76 / (h + 0.3 * L))
    dx, dy = 0.45 * L * k, 0.3 * L * k
    x0 = 100 - (b * k + dx) / 2 + 6
    xb, top = x0 + b * k, 88 - h * k
    cv = _dm_canvas(surf, box)
    _dm_path(cv, [(x0, top), (x0 + dx, top - dy), (xb + dx, 88 - dy), (xb, 88)], "side")
    _dm_path(cv, [(x0, 88), (xb, 88), (x0, top)])
    _dm_path(cv, [(x0, 88), (x0 + dx, 88 - dy), (xb + dx, 88 - dy)], "cut", False)  # seen through the faces
    _dm_path(cv, [(x0 + dx, 88 - dy), (x0 + dx, top - dy)], "cut", False)
    pts = [(x0 + 8, 88), (x0 + 8, 80), (x0, 80)]
    pygame.draw.lines(cv.layer, FC["line"], False, [cv.p(*q) for q in pts], cv.w(1.5))
    _dm_lab(cv, (x0 + xb) / 2, 102, f"{b} {u}")
    _dm_lab(cv, x0 - 5, 88 - h * k / 2 + 5, f"{h} {u}", "e")
    _dm_lab(cv, xb + dx / 2 + 6, 88 - dy / 2 + 9, f"{L} {u}", "s")
    cv.blit()


def draw_number_line(surf: pygame.Surface, rect: pygame.Rect, at: float, rel: str, lo: int, hi: int, color, dot_fill) -> None:
    """A small number line graph of x ``rel`` ``at`` from ``lo`` to ``hi``: the answer choices of a
    graphing problem. A filled dot for ≤ and ≥, an open one (filled with ``dot_fill``) for < and >."""
    W, P, Y = 160, 12, 15
    k = min(rect.width / W, rect.height / 40)
    ox, oy = rect.x + (rect.width - W * k) / 2, rect.y + (rect.height - 40 * k) / 2

    def pt(x, y):
        return ox + x * k, oy + y * k

    def X(n):
        return P + (n - lo) * (W - 2 * P) / (hi - lo)

    right = rel in (">", "≥")
    rail = tuple(round(c * 0.55 + b * 0.45) for c, b in zip(color, dot_fill))
    pygame.draw.line(surf, rail, pt(3, Y), pt(W - 3, Y), max(1, round(2 * k)))
    for n in range(lo, hi + 1):
        pygame.draw.line(surf, rail, pt(X(n), Y - 4), pt(X(n), Y + 4), max(1, round(2 * k)))
    shade = FC["red"]
    pygame.draw.line(surf, shade, pt(X(at), Y), pt(W - 10 if right else 10, Y), max(2, round(5 * k)))
    head = [(W - 12, Y - 6), (W - 1, Y), (W - 12, Y + 6)] if right else [(12, Y - 6), (1, Y), (12, Y + 6)]
    pygame.draw.polygon(surf, shade, [pt(*q) for q in head])
    center, r = pt(X(at), Y), 5 * k
    pygame.draw.circle(surf, shade, center, r)
    if rel in ("<", ">"):
        pygame.draw.circle(surf, dot_fill, center, max(1, r - 2.5 * k))
    size = max(11, round(13 * k))
    for n in dict.fromkeys([0, at]):
        label = ("−" if n < 0 else "") + f"{abs(n):g}"
        img = T.render_math(label, size, color, True)
        surf.blit(img, img.get_rect(midtop=(round(pt(X(n), 0)[0]), round(pt(0, Y + 7)[1]))))


FIGURES = {
    "right_tri": _right_tri,
    "compass": _compass,
    "triangle": _triangle,
    "angle_split": _angle_split,
    "polygon": _polygon,
    "parallel": _parallel,
    "scale_line": _scale_line,
    "similar": _similar,
    "grid": _grid,
    "rect": _rect,
    "tri_area": _tri_area,
    "circle": _circle,
    "arc": _arc,
    "box": _box,
    "cyl": _cyl,
    "trap": _trap,
    "composite": _composite,
    "shield": _shield,
    "tangents": _tangents,
    "chord": _chord,
    "chords": _chords,
    "inscribed": _inscribed,
    "dm_circle": _dm_circle,
    "dm_triangle": _dm_triangle,
    "dm_para": _dm_para,
    "dm_trap": _dm_trap,
    "dm_house": _dm_house,
    "dm_L": _dm_l,
    "dm_round": _dm_round,
    "dm_box": _dm_box,
    "dm_prism": _dm_prism,
}


def render_figure(surf: pygame.Surface, box: pygame.Rect, fig: dict) -> None:
    """Draw ``fig`` inside ``box``; raises on unknown kinds or bad data (used by the tests)."""
    FIGURES[fig["kind"]](surf, box, fig)


def draw_figure(surf: pygame.Surface, box: pygame.Rect, fig: dict) -> bool:
    """Draw ``fig`` inside ``box``. Returns False (and draws nothing) if it can't."""
    try:
        render_figure(surf, box, fig)
    except (KeyError, TypeError, ValueError, ZeroDivisionError, IndexError):
        return False
    return True
