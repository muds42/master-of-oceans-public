"""Layout constants, colors and fonts."""

from __future__ import annotations

from pathlib import Path

import pygame

FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
ICON = Path(__file__).resolve().parent.parent / "assets" / "icon.png"

WINDOW = (1280, 720)
TILE = 58
MAP_X, MAP_Y = 16, 56  # the 14 x 9 map is 812 x 522 pixels
PANEL_X, PANEL_Y, PANEL_W, PANEL_H = 848, 56, 416, 656
LOG_RECT = (16, 586, 816, 126)

BG = (10, 18, 30)
PANEL_BG = (18, 28, 42)
PANEL_EDGE = (46, 64, 86)
BUTTON = (34, 50, 70)
BUTTON_HOVER = (48, 70, 96)
TEXT = (228, 234, 240)
DIM = (146, 162, 180)
FAINT = (92, 108, 126)
ACCENT = (242, 196, 84)
GOOD = (112, 206, 122)
BAD = (236, 96, 80)
WARN = (240, 160, 70)

OCEAN_TOP = (28, 82, 122)
OCEAN_BOTTOM = (14, 48, 84)
SHALLOW = (58, 132, 150)
SAND = (214, 196, 140)
SAND_DARK = (168, 148, 100)
GRASS = (80, 126, 64)
GRASS_DARK = (58, 96, 48)
FOAM = (236, 246, 250)
REACH = (140, 225, 255)

CURRENCY_COLORS = {
    "steel": (180, 192, 206),
    "powder": (238, 114, 80),
    "fuel": (244, 192, 74),
    "blueprints": (106, 174, 246),
    "plasma": (206, 128, 255),
}

SIDE_STYLE = [
    {"hull": (170, 188, 206), "deck": (120, 136, 154), "trim": (84, 156, 240), "dark": (44, 58, 74)},
    {"hull": (200, 164, 148), "deck": (150, 112, 100), "trim": (236, 92, 72), "dark": (72, 46, 40)},
]

_fonts: dict[int, pygame.font.Font] = {}
_math_fonts: dict[tuple[int, bool], pygame.font.Font] = {}
_text_cache: dict[tuple, pygame.Surface] = {}


def reset() -> None:
    """Forget cached fonts and text (needed if pygame is re-initialised)."""
    _fonts.clear()
    _math_fonts.clear()
    _text_cache.clear()


def math_font(size: int, bold: bool = False) -> pygame.font.Font:
    """DejaVu Sans: covers the math symbols (superscripts, √, ±, π, ≤ ...) the problems use."""
    key = (size, bold)
    if key not in _math_fonts:
        name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
        _math_fonts[key] = pygame.font.Font(str(FONT_DIR / name), size)
    return _math_fonts[key]


OVERLINE = "\u0305"  # a combining bar over the character before it (repeating decimals: 0.83̅)


def render_math(text: str, size: int, color, bold: bool = False) -> pygame.Surface:
    key = ("math", text, size, tuple(color), bold)
    surf = _text_cache.get(key)
    if surf is None:
        if len(_text_cache) > 2000:
            _text_cache.clear()
        f = math_font(size, bold)
        surf = _text_cache[key] = _render_overlined(f, text, color) if OVERLINE in text else f.render(text, True, color)
    return surf


def _render_overlined(f: pygame.font.Font, text: str, color) -> pygame.Surface:
    """Text with bars drawn over the characters marked with OVERLINE: the font's own
    combining bar lands beside the digit, not over it."""
    plain, barred = "", []
    for ch in text:
        if ch == OVERLINE:
            if plain:
                barred.append(len(plain) - 1)
        else:
            plain += ch
    surf = f.render(plain, True, color)
    top = max(1, f.get_ascent() - round(f.get_height() * 0.76))
    thick = max(1, f.get_height() // 16)
    for i in barred:
        x0, x1 = f.size(plain[:i])[0], f.size(plain[:i + 1])[0]
        pygame.draw.line(surf, color, (x0 + 1, top), (x1 - 1 if i + 1 not in barred else x1, top), thick)
    return surf


def font(size: int) -> pygame.font.Font:
    if size not in _fonts:
        _fonts[size] = pygame.font.Font(None, size)
    return _fonts[size]


def render(text: str, size: int, color) -> pygame.Surface:
    key = (text, size, tuple(color))
    surf = _text_cache.get(key)
    if surf is None:
        if len(_text_cache) > 2000:
            _text_cache.clear()
        surf = _text_cache[key] = font(size).render(text, True, color)
    return surf
