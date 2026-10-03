"""Procedural drawing: ocean, islands, ships, torpedoes, text and buttons.

Everything is drawn with shapes so the game needs no image assets.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Callable, Optional

import pygame

from . import theme as T

# --------------------------------------------------------------------------- text & widgets


def text(surf: pygame.Surface, s: str, pos, size: int = 20, color=T.TEXT, anchor: str = "topleft") -> pygame.Rect:
    img = T.render(s, size, color)
    rect = img.get_rect(**{anchor: (round(pos[0]), round(pos[1]))})
    surf.blit(img, rect)
    return rect


def wrap(s: str, size: int, width: int, font: Optional[pygame.font.Font] = None) -> list[str]:
    f = font or T.font(size)
    lines, line = [], ""
    for word in s.split():
        trial = f"{line} {word}".strip()
        if line and f.size(trial)[0] > width:
            lines.append(line)
            line = word
        else:
            line = trial
    if line:
        lines.append(line)
    return lines or [""]


def mtext(surf: pygame.Surface, s: str, pos, size: int = 20, color=T.TEXT, anchor: str = "topleft", bold: bool = False) -> pygame.Rect:
    """Text in the math font (for problems, which use symbols the UI font lacks)."""
    img = T.render_math(s, size, color, bold)
    rect = img.get_rect(**{anchor: (round(pos[0]), round(pos[1]))})
    surf.blit(img, rect)
    return rect


def mwrap(s: str, size: int, width: int, bold: bool = False) -> list[str]:
    """Word-wrap text for the math font; keeps explicit line breaks."""
    out: list[str] = []
    for para in s.split("\n"):
        out += wrap(para, size, width, T.math_font(size, bold))
    return out


def panel(surf: pygame.Surface, rect: pygame.Rect, color=T.PANEL_BG, border=T.PANEL_EDGE, radius: int = 8) -> None:
    pygame.draw.rect(surf, color, rect, border_radius=radius)
    pygame.draw.rect(surf, border, rect, 1, border_radius=radius)


def hp_color(frac: float):
    if frac > 0.6:
        return T.GOOD
    if frac > 0.3:
        return T.ACCENT
    return T.BAD


def bar(surf: pygame.Surface, rect: pygame.Rect, frac: float, color=None) -> None:
    pygame.draw.rect(surf, (8, 12, 18), rect, border_radius=2)
    inner = rect.inflate(-2, -2)
    inner.width = max(0, round(inner.width * max(0.0, min(1.0, frac))))
    if inner.width:
        pygame.draw.rect(surf, color or hp_color(frac), inner, border_radius=2)


def currency_icon(surf: pygame.Surface, center, currency: str, r: int = 9) -> None:
    """Small emblem for each currency: an ingot, a powder keg, a fuel drop, a blueprint roll and a plasma orb."""
    x, y = center
    c = T.CURRENCY_COLORS[currency]
    dark = tuple(v // 3 for v in c)
    if currency == "steel":
        pts = [(x - r, y + r * 0.6), (x + r, y + r * 0.6), (x + r * 0.6, y - r * 0.6), (x - r * 0.6, y - r * 0.6)]
        pygame.draw.polygon(surf, c, pts)
        pygame.draw.polygon(surf, dark, pts, 1)
        pygame.draw.line(surf, (235, 240, 246), (x - r * 0.4, y - r * 0.3), (x + r * 0.4, y - r * 0.3), 2)
    elif currency == "powder":
        rect = pygame.Rect(0, 0, r * 1.7, r * 2)
        rect.center = (x, y)
        pygame.draw.ellipse(surf, c, rect)
        pygame.draw.ellipse(surf, dark, rect, 1)
        for dy in (-r * 0.45, r * 0.45):
            pygame.draw.line(surf, dark, (x - r * 0.8, y + dy), (x + r * 0.8, y + dy), 2)
    elif currency == "fuel":
        pts = [(x, y - r)] + [(x + math.cos(a) * r * 0.75, y + r * 0.25 + math.sin(a) * r * 0.75) for a in [i * math.pi / 6 for i in range(-1, 8)]]
        pygame.draw.polygon(surf, c, pts)
        pygame.draw.polygon(surf, dark, pts, 1)
    elif currency == "plasma":
        pygame.draw.circle(surf, c, (x, y), r * 0.7)
        pygame.draw.circle(surf, (248, 230, 255), (x - r * 0.15, y - r * 0.15), r * 0.3)
        orbit = pygame.Rect(0, 0, r * 2, r * 0.9)
        orbit.center = (x, y)
        pygame.draw.ellipse(surf, c, orbit, 1)
    else:
        rect = pygame.Rect(0, 0, r * 2, r * 1.6)
        rect.center = (x, y)
        pygame.draw.rect(surf, c, rect, border_radius=3)
        for dy in (-r * 0.35, 0, r * 0.35):
            pygame.draw.line(surf, (230, 242, 255), (x - r * 0.65, y + dy), (x + r * 0.65, y + dy), 1)


def money(surf: pygame.Surface, pos, currency: str, amount: int, size: int = 20, color=T.TEXT) -> int:
    """Currency icon followed by an amount; returns the width drawn."""
    currency_icon(surf, (pos[0] + 8, pos[1]), currency, 8)
    return 20 + text(surf, str(amount), (pos[0] + 20, pos[1]), size, color, "midleft").width


def cost_row(surf: pygame.Surface, pos, cost: dict, balance: Optional[dict] = None, size: int = 19, anchor: str = "left") -> int:
    """Draw a price as icons and amounts; amounts you can't afford are red. Returns the width."""
    parts = [(c, v) for c, v in cost.items() if v]
    widths = [22 + T.font(size).size(str(v))[0] + 10 for c, v in parts]
    total = sum(widths) - 10 if parts else 0
    x = pos[0] - (total if anchor == "right" else 0)
    for (c, v), w in zip(parts, widths):
        currency_icon(surf, (x + 8, pos[1]), c, 8)
        ok = balance is None or balance.get(c, 0) >= v
        text(surf, str(v), (x + 20, pos[1]), size, T.TEXT if ok else T.BAD, "midleft")
        x += w
    return total


class Slider:
    """A horizontal slider over a list of values, dragged or clicked with the mouse."""

    def __init__(self, rect: pygame.Rect, values: list, index: int, on_change: Callable[[object], None]) -> None:
        self.rect = rect
        self.values = values
        self.index = index
        self.on_change = on_change
        self.dragging = False

    def _x(self, i: int) -> float:
        return self.rect.x + 10 + (self.rect.width - 20) * i / max(1, len(self.values) - 1)

    def _set_from(self, px: float) -> None:
        i = min(range(len(self.values)), key=lambda k: abs(self._x(k) - px))
        if i != self.index:
            self.index = i
            self.on_change(self.values[i])

    def handle(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.rect.inflate(0, 16).collidepoint(event.pos):
            self.dragging = True
            self._set_from(event.pos[0])
            return True
        if event.type == pygame.MOUSEMOTION and self.dragging:
            self._set_from(event.pos[0])
            return True
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.dragging = False
        return False

    def draw(self, surf: pygame.Surface, labels: Optional[list[str]] = None) -> None:
        y = self.rect.centery
        pygame.draw.line(surf, T.PANEL_EDGE, (self._x(0), y), (self._x(len(self.values) - 1), y), 4)
        pygame.draw.line(surf, T.ACCENT, (self._x(0), y), (self._x(self.index), y), 4)
        for i in range(len(self.values)):
            pygame.draw.circle(surf, T.ACCENT if i <= self.index else T.PANEL_EDGE, (self._x(i), y), 5)
            if labels:
                text(surf, labels[i], (self._x(i), y + 12), 15, T.TEXT if i == self.index else T.FAINT, "midtop")
        pygame.draw.circle(surf, T.TEXT, (self._x(self.index), y), 10)
        pygame.draw.circle(surf, T.ACCENT, (self._x(self.index), y), 10, 3)


@dataclass
class Button:
    rect: pygame.Rect
    label: str
    on_click: Callable[[], None]
    hint: str = ""
    enabled: bool = True
    toggled: bool = False
    size: int = 20

    def draw(self, surf: pygame.Surface, mouse) -> None:
        hover = self.enabled and self.rect.collidepoint(mouse)
        color = T.BUTTON_HOVER if hover else T.BUTTON
        if self.toggled:
            color = (86, 72, 30)
        pygame.draw.rect(surf, color, self.rect, border_radius=6)
        pygame.draw.rect(surf, T.ACCENT if self.toggled else T.PANEL_EDGE, self.rect, 1, border_radius=6)
        fg = T.TEXT if self.enabled else T.FAINT
        if self.hint:
            gap = self.size // 2 - 3
            text(surf, self.label, (self.rect.centerx, self.rect.centery - gap), self.size, fg, "center")
            text(surf, self.hint, (self.rect.centerx, self.rect.centery + 9 + gap - 7), 15, T.DIM if self.enabled else T.FAINT, "center")
        else:
            text(surf, self.label, self.rect.center, self.size, fg, "center")

    def click(self, pos) -> bool:
        if self.enabled and self.rect.collidepoint(pos):
            self.on_click()
            return True
        return False


# --------------------------------------------------------------------------- ocean


def ocean_surface(width: int, height: int, grid: Optional[int] = None, seed: int = 0) -> pygame.Surface:
    surf = pygame.Surface((width, height))
    for y in range(height):
        f = y / max(1, height - 1)
        c = [round(a + (b - a) * f) for a, b in zip(T.OCEAN_TOP, T.OCEAN_BOTTOM)]
        pygame.draw.line(surf, c, (0, y), (width, y))
    rng = random.Random(seed)
    speckle = pygame.Surface((width, height), pygame.SRCALPHA)
    for _ in range(width * height // 180):
        x, y = rng.randrange(width), rng.randrange(height)
        r = rng.randint(6, 22)
        shade = rng.choice([(255, 255, 255, 5), (0, 20, 40, 10)])
        pygame.draw.ellipse(speckle, shade, (x - r, y - r // 3, 2 * r, r))
    surf.blit(speckle, (0, 0))
    if grid:
        lines = pygame.Surface((width, height), pygame.SRCALPHA)
        for x in range(0, width + 1, grid):
            pygame.draw.line(lines, (255, 255, 255, 26), (x, 0), (x, height))
        for y in range(0, height + 1, grid):
            pygame.draw.line(lines, (255, 255, 255, 26), (0, y), (width, y))
        surf.blit(lines, (0, 0))
    return surf


class Waves:
    """Little glinting wave crests drifting across an area."""

    def __init__(self, rect: pygame.Rect, count: int, seed: int = 1) -> None:
        rng = random.Random(seed)
        self.rect = rect
        self.waves = [
            (rng.uniform(0, rect.width), rng.uniform(0, rect.height), rng.uniform(0, math.tau), rng.uniform(6, 14))
            for _ in range(count)
        ]

        self.layer = pygame.Surface(rect.size, pygame.SRCALPHA)

    def draw(self, surf: pygame.Surface, t: float) -> None:
        layer = self.layer
        layer.fill((0, 0, 0, 0))
        for x, y, phase, size in self.waves:
            a = math.sin(t * 0.9 + phase)
            if a <= 0:
                continue
            xx = (x + t * 6) % self.rect.width
            alpha = round(70 * a)
            pygame.draw.arc(layer, (220, 240, 255, alpha), (xx, y, size * 2, size * 0.8), 0.4, math.pi - 0.4, 2)
        surf.blit(layer, self.rect.topleft)


# --------------------------------------------------------------------------- islands


def island_shape(center, radius: float, seed: int) -> tuple[list, list, list]:
    """Irregular polygons for the shallows, beach and vegetation of an island."""
    rng = random.Random(seed)
    n = 11
    radii = [radius * rng.uniform(0.72, 1.0) for _ in range(n)]

    def poly(scale: float):
        pts = []
        for i, r in enumerate(radii):
            a = i / n * math.tau
            pts.append((center[0] + math.cos(a) * r * scale, center[1] + math.sin(a) * r * scale * 0.9))
        return pts

    return poly(1.25), poly(1.0), poly(0.62)


def draw_island(surf: pygame.Surface, shape) -> None:
    shallows, beach, green = shape
    layer = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
    pygame.draw.polygon(layer, (*T.SHALLOW, 150), shallows)
    surf.blit(layer, (0, 0))
    pygame.draw.polygon(surf, T.SAND, beach)
    pygame.draw.polygon(surf, T.SAND_DARK, beach, 2)
    pygame.draw.polygon(surf, T.GRASS, green)
    pygame.draw.polygon(surf, T.GRASS_DARK, green, 2)


# --------------------------------------------------------------------------- ships

# hull id -> (length, beam) as a fraction of a tile, and turret positions along the keel.
HULL_SHAPES = {
    "corvette": (0.56, 0.17, [0.45]),
    "destroyer": (0.72, 0.19, [0.5, -0.55]),
    "cruiser": (0.84, 0.23, [0.55, 0.32, -0.55]),
    "battleship": (0.96, 0.28, [0.58, 0.36, -0.42, -0.64]),
    # Red's super ships are drawn bigger than a tile
    "dreadnought": (1.12, 0.34, [0.66, 0.48, 0.3, -0.38, -0.56, -0.72]),
    "fortress": (1.26, 0.48, [0.7, 0.56, 0.42, 0.26, -0.3, -0.46, -0.62, -0.76]),
}
# Missile ships swap some turrets for launch cells: hull -> (turrets kept, cell positions)
MISSILE_LAYOUT = {
    "dreadnought": ([0.66, -0.38, -0.56, -0.72], (0.48, 0.3)),
    "fortress": ([0.7, 0.56, -0.3, -0.46, -0.62, -0.76], (0.42, 0.26)),
}


def lerp_pt(a, b, f: float):
    return (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)


def _rotated(points, angle: float, center):
    c, s = math.cos(angle), math.sin(angle)
    return [(center[0] + x * c - y * s, center[1] + x * s + y * c) for x, y in points]


def draw_ship(
    surf: pygame.Surface, center, hull_id: str, side: int, angle: float, alpha: float = 255, scale: float = 1.0,
    missiles: bool = False,
) -> None:
    style = T.SIDE_STYLE[side]
    length, beam, turrets = HULL_SHAPES.get(hull_id, HULL_SHAPES["destroyer"])
    cells: tuple[float, ...] = ()
    if missiles:  # launch cells forward instead of (some of) the turrets
        turrets, cells = MISSILE_LAYOUT.get(hull_id, ([t for t in turrets if t < 0], (0.52, 0.3)))
    L, W = length * T.TILE * scale / 2, beam * T.TILE * scale / 2
    size = round(max(T.TILE * 1.2, 2 * L + 12))
    layer = pygame.Surface((size, size), pygame.SRCALPHA)
    mid = (size / 2, size / 2)

    hull = [(L, 0), (L * 0.45, W), (-L * 0.85, W), (-L, W * 0.55), (-L, -W * 0.55), (-L * 0.85, -W), (L * 0.45, -W)]
    deck = [(x * 0.86, y * 0.7) for x, y in hull]
    pygame.draw.polygon(layer, style["hull"], _rotated(hull, angle, mid))
    pygame.draw.polygon(layer, style["deck"], _rotated(deck, angle, mid))
    pygame.draw.aalines(layer, style["dark"], True, _rotated(hull, angle, mid))
    # superstructure and funnel
    bridge = [(L * 0.2, W * 0.5), (-L * 0.2, W * 0.5), (-L * 0.2, -W * 0.5), (L * 0.2, -W * 0.5)]
    pygame.draw.polygon(layer, style["hull"], _rotated(bridge, angle, mid))
    pygame.draw.polygon(layer, style["dark"], _rotated(bridge, angle, mid), 1)
    fx, fy = _rotated([(-L * 0.08, 0)], angle, mid)[0]
    pygame.draw.circle(layer, style["dark"], (fx, fy), max(2, W * 0.35))
    # gun turrets, barrels pointing away from the bridge
    if missiles:
        for pos in cells:
            cell = [(L * (pos + 0.09), W * 0.55), (L * (pos - 0.09), W * 0.55), (L * (pos - 0.09), -W * 0.55), (L * (pos + 0.09), -W * 0.55)]
            pygame.draw.polygon(layer, style["trim"], _rotated(cell, angle, mid))
            pygame.draw.polygon(layer, style["dark"], _rotated(cell, angle, mid), 1)
            a, b = _rotated([(L * pos, W * 0.55), (L * pos, -W * 0.55)], angle, mid)
            pygame.draw.line(layer, style["dark"], a, b, 1)
    for pos in turrets:
        tx, ty = _rotated([(L * pos, 0)], angle, mid)[0]
        direction = 1 if pos > 0 else -1
        bx, by = _rotated([(L * pos + direction * W * 1.1, 0)], angle, mid)[0]
        pygame.draw.line(layer, style["dark"], (tx, ty), (bx, by), max(1, round(W * 0.3)))
        pygame.draw.circle(layer, style["trim"], (tx, ty), max(2, W * 0.55))
        pygame.draw.circle(layer, style["dark"], (tx, ty), max(2, W * 0.55), 1)

    if alpha < 255:
        layer.set_alpha(max(0, round(alpha)))
    surf.blit(layer, (center[0] - size / 2, center[1] - size / 2))


def draw_torpedo(surf: pygame.Surface, center, angle: float, side: int, alpha: float = 255, kind: str = "torpedo") -> None:
    size = 80  # room for the wake, whatever the tile size
    layer = pygame.Surface((size, size), pygame.SRCALPHA)
    mid = (size / 2, size / 2)
    a = max(0, min(255, round(alpha)))
    if kind == "missile":
        nose, tail = _rotated([(10, 0), (-9, 0)], angle, mid)
        flame = _rotated([(-9, 0), (-17, 0)], angle, mid)
        pygame.draw.line(layer, (255, 170, 60, a), flame[0], flame[1], 5)
        pygame.draw.line(layer, (255, 240, 170, a), flame[0], lerp_pt(flame[0], flame[1], 0.5), 3)
        pygame.draw.line(layer, (225, 228, 232, a), nose, tail, 4)
        fins = _rotated([(-8, -4), (-8, 4)], angle, mid)
        pygame.draw.line(layer, (225, 228, 232, a), fins[0], fins[1], 2)
        pygame.draw.circle(layer, (*T.SIDE_STYLE[side]["trim"], a), nose, 2)
        surf.blit(layer, (center[0] - size / 2, center[1] - size / 2))
        return
    # foam wake trailing behind
    for i in range(1, 6):
        wx, wy = _rotated([(-6 - i * 5, 0)], angle, mid)[0]
        pygame.draw.circle(layer, (*T.FOAM, max(0, a - 40 * i)), (wx, wy), 3 + i * 0.6)
    nose, tail = _rotated([(8, 0), (-8, 0)], angle, mid)
    pygame.draw.line(layer, (30, 34, 40, a), nose, tail, 4)
    pygame.draw.circle(layer, (*T.SIDE_STYLE[side]["trim"], a), nose, 2)
    surf.blit(layer, (center[0] - size / 2, center[1] - size / 2))
