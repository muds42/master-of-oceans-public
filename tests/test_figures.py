"""Every figure a Broadside or Math Boost problem can produce must draw without errors."""

import os
import random

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
pygame = pytest.importorskip("pygame")

from seabattle.problems import broadside, dinomath  # noqa: E402
from seabattle.problems.common import Context  # noqa: E402
from seabattle.ui import theme as T  # noqa: E402
from seabattle.ui.figures import FIGURES, draw_number_line, render_figure  # noqa: E402


@pytest.fixture(scope="module")
def surface():
    pygame.init()
    T.reset()
    yield pygame.Surface((400, 360))
    pygame.quit()


@pytest.mark.parametrize("key", sorted(broadside.HELP_FIGURES))
def test_help_figures_render(key, surface):
    box = pygame.Rect(10, 10, 340, 320)
    for fig in broadside.HELP_FIGURES[key]:
        assert fig["kind"] in FIGURES, fig["kind"]
        surface.fill((0, 0, 0))
        render_figure(surface, box, fig)


@pytest.mark.parametrize("gen", broadside.GENERATORS, ids=lambda g: g.name)
def test_figures_render(gen, surface):
    box = pygame.Rect(10, 10, 340, 320)
    for seed in range(60):
        p = gen.fn(Context(random.Random(seed), my_name="USS Kestrel", enemy_name="RNS Kraken"))
        if p.fig is None:
            continue
        assert p.fig["kind"] in FIGURES, p.fig["kind"]
        surface.fill((0, 0, 0))
        render_figure(surface, box, p.fig)


@pytest.mark.parametrize("topic", ["Circles & area", "Surface area & volume", "Inequalities"])
def test_math_boost_figures_render(topic, surface):
    rng = random.Random(topic)
    drawn = set()
    for _ in range(300):
        p = dinomath.make_problem(rng, 4, topic)
        if p.fig is not None:
            assert p.fig["kind"] in FIGURES, p.fig["kind"]
            surface.fill((0, 0, 0))
            render_figure(surface, pygame.Rect(10, 10, 250, 150), p.fig)
            drawn.add(p.fig["kind"])
        for choice in p.choices:
            if choice.graph:
                at, rel, lo, hi = choice.graph
                draw_number_line(surface, pygame.Rect(10, 10, 300, 48), at, rel, lo, hi, (255, 255, 255), (0, 0, 0))
                drawn.add("number line")
    expected = {
        "Circles & area": {"dm_circle", "dm_triangle", "dm_para", "dm_trap", "dm_house", "dm_L", "dm_round"},
        "Surface area & volume": {"dm_box", "dm_prism"},
        "Inequalities": {"number line"},
    }[topic]
    assert drawn == expected
