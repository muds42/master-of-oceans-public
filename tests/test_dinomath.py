"""The Dino Math port (Math Boost's problems): the same problems as the original engine, and
every problem well formed at every level."""

import hashlib
import json
import random
from pathlib import Path

import pytest

from seabattle.problems import dinomath as dm

TOPICS = [t.name for t in dm.TOPICS]


class Mulberry32:
    """The small seeded generator the original engine was run with for the fingerprints."""

    def __init__(self, seed: int) -> None:
        self.a = seed & 0xFFFFFFFF

    def random(self) -> float:
        m = 0xFFFFFFFF
        self.a = a = (self.a + 0x6D2B79F5) & m
        t = ((a ^ (a >> 15)) * (a | 1)) & m
        t = ((t + (((t ^ (t >> 7)) * (t | 61)) & m)) & m) ^ t
        return ((t ^ (t >> 14)) & m) / 4294967296


ORIGINAL = json.loads((Path(__file__).parent / "dinomath_original.json").read_text(encoding="utf-8"))["problems"]


@pytest.mark.parametrize("topic, level, seed, fingerprint", ORIGINAL, ids=lambda v: str(v))
def test_same_problems_as_the_original_engine(topic, level, seed, fingerprint):
    """Fed the same random numbers, the port writes what the JavaScript engine wrote, character for character
    (with the original's way of picking wrong choices: the game balances them, see test_problem_guessing)."""
    text = dm.to_text(dm.make_problem(Mulberry32(seed), level, topic, faithful=True))
    assert hashlib.sha256(text.encode()).hexdigest()[:16] == fingerprint, text


@pytest.mark.parametrize("topic", TOPICS)
def test_every_problem_is_well_formed(topic):
    rng = random.Random(topic)
    for level in dm.LEVELS:
        for _ in range(150):
            p = dm.make_problem(rng, level, topic)
            texts = [c.text for c in p.choices]
            assert len(texts) == 4 and len(set(texts)) == 4, dm.to_text(p)
            assert 0 <= p.answer < 4 and p.reason(p.answer) == ""
            assert p.question and p.ask and "?" in p.ask and p.hint and p.steps
            for s in [p.question, p.ask, p.hint, *texts, *(c.why for c in p.choices), *(x for step in p.steps for x in step)]:
                assert "<span" not in s and "<sup" not in s and "&" not in s, s  # no markup left over
            graphs = [c.graph for c in p.choices]
            assert all(graphs) or not any(graphs)  # a graphing problem's choices are all number lines
            if graphs[0]:
                at, rel, lo, hi = graphs[p.answer]
                assert (at, rel) == p.ray and lo < at < hi


def test_levels_open_topics():
    rng = random.Random(3)
    seen = {level: {dm.make_problem(rng, level).topic for _ in range(400)} for level in dm.LEVELS}
    assert seen[0] == {"Integers", "One-step equations", "Proportions", "Percents"}
    assert seen[4] == set(TOPICS)
    assert all(seen[a] <= seen[a + 1] for a in range(4))


def test_never_the_same_topic_twice_in_a_row_when_asked():
    rng = random.Random(5)
    last = None
    for _ in range(200):
        p = dm.make_problem(rng, 2, avoid=last)
        assert p.topic != last
        last = p.topic


def test_text_as_the_game_shows_it():
    assert dm.plain('<span class="frac"><span>2</span><span>3</span></span>x = 4') == "(2⁄3)x = 4"
    assert dm.plain('−<span class="frac"><span>1</span><span>2</span></span>(4x − 6)') == "−(1⁄2)(4x − 6)"
    assert dm.plain('<span class="frac"><span>3</span><span>4</span></span> + 1') == "3⁄4 + 1"
    assert dm.plain('0.8<span class="rep">3</span>') == "0.83̅"
    assert dm.plain("cm<sup>2</sup> and x &lt; 4&nbsp;ok") == "cm² and x < 4 ok"


def test_numbers_are_written_as_javascript_writes_them():
    assert [dm.js_str(v) for v in (3.0, 0.1 + 0.2, 5e-05, 1e-7, 100.0, -0.0, 1e21)] == [
        "3", "0.30000000000000004", "0.00005", "1e-7", "100", "0", "1e+21"]
    assert (dm.js_round(2.5), dm.js_round(-2.5), dm.js_round(0.49)) == (3, -2, 0)
    assert dm.js_fixed(0.125, 2) == "0.13" and dm.money(12.5) == "$12.50" and dm.money(-3) == "−$3"
    assert dm.num(-0.1 - 0.2) == "−0.3"


def test_figures_say_what_they_show():
    p = dm.make_problem(random.Random(1), 4, "Surface area & volume")
    assert p.fig is not None and p.fig["kind"] in ("dm_box", "dm_prism")
    assert p.figure_text.startswith(("A box", "A cube", "A triangular prism"))
