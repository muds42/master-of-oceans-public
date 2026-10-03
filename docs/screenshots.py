"""Take the README's screenshots: ``python docs/screenshots.py``.

Drives the real game window off-screen (SDL's dummy video driver) through
seeded campaigns and battles, and saves each screen as a PNG next to this
file. Nothing here touches your own saves. Run it again after changing how the
game looks; ``python docs/screenshots.py retrofits battle`` retakes just those.
"""

from __future__ import annotations

import copy
import os
import random
import sys
import tempfile
from pathlib import Path
from typing import Callable

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ["SEABATTLE_SAVE_DIR"] = tempfile.mkdtemp(prefix="seabattle-shots-")  # leave the real saves alone
DOCS = Path(__file__).resolve().parent
sys.path.insert(0, str(DOCS.parent))

import pygame  # noqa: E402

from seabattle import campaign as cm  # noqa: E402
from seabattle.ai import SimpleAI  # noqa: E402
from seabattle.debrief import debrief  # noqa: E402
from seabattle.headless import run_battle  # noqa: E402
from seabattle.ui.app import App  # noqa: E402
from seabattle.ui.battle_scene import BattleScene, tile_to_screen  # noqa: E402
from seabattle.ui.workshop_scene import WorkshopScene  # noqa: E402

DT = 1 / 60


def run(app: App, seconds: float, events: tuple = ()) -> None:
    for i in range(max(1, round(seconds / DT))):
        app.frame(DT, list(events) if i == 0 else [])


def hover(app: App, pos: tuple[int, int]) -> None:
    run(app, DT, (pygame.event.Event(pygame.MOUSEMOTION, pos=pos, rel=(0, 0), buttons=(0, 0, 0)),))


def save(app: App, name: str) -> None:
    pygame.image.save(app.screen, str(DOCS / f"{name}.png"))
    print(f"docs/{name}.png")


# --------------------------------------------------------------------------- campaigns


def act_one() -> cm.Campaign:
    """Mission 9, Battleship!: a fleet of Act I ships and a few upgrades."""
    return cm.Campaign(
        slot=1, mission_number=9, fleet={"picket": 6, "torpedo_boat": 8, "destroyer": 6, "light_cruiser": 2},
        wrecks={"destroyer": 1}, unlocked=["picket", "torpedo_boat", "destroyer", "light_cruiser"],
        upgrades={"caliber": 2, "turrets": 1, "fire_control": 2, "warheads": 1, "armor": 1, "belt": 1, "engines": 1},
        currency={"steel": 240, "powder": 185, "fuel": 120, "blueprints": 95},
        stats={"solved": {"linear": 31, "systems": 18, "angles": 22, "triangles": 15},
               "attempted": {"linear": 36, "systems": 22, "angles": 25, "triangles": 19},
               "records": {"best_streak": 14}},
    )


def act_three() -> cm.Campaign:
    """Mission 26, The Tempest: future tech, retrofits and the Plasma classes."""
    c = cm.Campaign(
        slot=2, mission_number=26,
        fleet={"destroyer": 10, "light_cruiser": 5, "battleship": 2, "missile_cruiser": 3, "aegis_cruiser": 2,
               "hydrofoil": 8},
        unlocked=["picket", "torpedo_boat", "destroyer", "light_cruiser", "battleship", "missile_cruiser",
                  "hydrofoil", "aegis_cruiser"],
        upgrades={"caliber": 4, "turrets": 2, "rangefinders": 2, "fire_control": 3, "warheads": 3, "tubes": 1,
                  "torp_speed": 2, "engines": 1, "armor": 3, "belt": 3, "damage_control": 3, "interdiction": 4,
                  "lasers": 2, "fields": 2, "railguns": 1, "point_defense": 1, "nanite": 1, "decoys": 1},
        currency={"steel": 620, "powder": 410, "fuel": 260, "blueprints": 330, "plasma": 385},
        retrofits={"battleship": ["laser_battery", "field_generator"], "light_cruiser": ["laser_battery"],
                   "destroyer": ["field_generator"]},
        in_port=["missile_cruiser"],
    )
    c.boost = True
    return c


# --------------------------------------------------------------------------- the shots


def workshop(app: App, c: cm.Campaign, school: str = "algebra", seed: int = 1) -> WorkshopScene:
    cm.save(c)
    app.open_workshop(c)
    ws = app.scene
    assert isinstance(ws, WorkshopScene)
    ws.toast_time = 0
    ws.set_school(school)
    ws.rng = random.Random(seed)
    ws.new_problem()
    return ws


def math_station(app: App) -> None:
    """A Broadside problem answered wrong: the mistake explained, the working and the figure."""
    for seed in range(200):
        ws = workshop(app, act_one(), "broadside", seed)
        p = ws.posed
        if p.problem.fig and p.topic.id == "triangles" and p.tier == 2 and len(p.problem.solution) <= 4:
            break
    ws.answer((p.answer + 1) % 4)
    ws.show_equation = True
    hover(app, (0, 0))
    save(app, "workshop")


def future_tech(app: App) -> None:
    ws = workshop(app, act_three())
    ws.tab, ws.upgrade_view = "upgrades", "future"
    hover(app, (0, 0))
    save(app, "future-tech")


def retrofits(app: App) -> None:
    ws = workshop(app, act_three())
    ws.tab, ws.shipyard_view = "shipyard", "retrofits"
    hover(app, (0, 0))
    save(app, "retrofits")


def briefing(app: App) -> None:
    c = act_three()
    last = run_battle(c.build_battle(skirmish=c.mission_number - 1), (SimpleAI(), SimpleAI(retreat_ratio=0)))
    c.lessons = debrief(last, 0, campaign=True).lessons  # what the briefing remembers from the last battle
    ws = workshop(app, c)
    ws.tab = "fleet"
    ws.show_briefing = True
    hover(app, (0, 0))
    save(app, "briefing")


def mission(app: App, c: cm.Campaign) -> BattleScene:
    cm.save(c)
    app.start_mission(c)
    scene = app.scene
    assert isinstance(scene, BattleScene)
    return scene


def play_until(app: App, scene: BattleScene, done: Callable[[], bool], limit: float = 600) -> None:
    t = 0.0
    while not done():
        run(app, 0.1)
        t += 0.1
        if t > limit:
            raise RuntimeError("the battle never got there")


def battle(app: App) -> None:
    """Act III, your turn: a big ship picked out, where it can move, and the odds against the ship under the mouse.
    The computer plays your other stacks until a cruiser or battleship has something in reach."""
    c = act_three()
    c.boost = False
    c.fleet = {"destroyer": 4, "light_cruiser": 2, "battleship": 1, "hydrofoil": 4}  # a fair fight: Red stays afloat
    scene = mission(app, c)

    def aiming() -> bool:
        s = scene.human_turn()
        if s is None:
            return False
        if s.design.hull.id in ("cruiser", "battleship") and any(scene.fireable(s, e) for e in scene.battle.enemies_of(s)):
            return True
        scene.auto_ship()
        return False

    play_until(app, scene, aiming)
    s = scene.human_turn()
    target = max((e for e in scene.battle.enemies_of(s) if scene.fireable(s, e)), key=lambda e: e.design.max_hp)
    hover(app, tuple(map(int, tile_to_screen(*target.pos))))
    save(app, "battle")


def torpedoes(app: App) -> None:
    """Act I, the computer playing both fleets: the first torpedo salvos cross."""
    scene = mission(app, act_one())
    scene.toggle_fleet_auto()
    play_until(app, scene, lambda: len(scene.torps) >= 2)
    hover(app, (0, 0))
    save(app, "torpedoes")


def math_boost(app: App) -> None:
    """A big hit frozen with the MATH BOOST box beside it, then the problem it opens."""
    scene = mission(app, act_three())
    scene.toggle_fleet_auto()
    scene.speed = 3
    play_until(app, scene, lambda: scene.box_open and scene.chance.hit.offense)
    run(app, 0.6)
    hover(app, (0, 0))
    save(app, "math-boost")
    for seed in range(1000):  # a word problem with a sketch
        trial = copy.deepcopy(scene.boost)
        trial.rng = random.Random(seed)
        if (p := trial.pose()).fig and p.words:
            break
    scene.boost.rng = random.Random(seed)
    scene.take_boost()
    hover(app, (0, 0))
    save(app, "boost-problem")


def result(app: App) -> None:
    c = act_one()
    scene = mission(app, c)
    scene.toggle_fleet_auto()
    scene.speed = 3
    play_until(app, scene, lambda: scene.show_result, limit=1200)
    run(app, 1.0)
    hover(app, (0, 0))
    save(app, "debrief")


SHOTS = {
    "workshop": math_station, "future-tech": future_tech, "retrofits": retrofits,
    "briefing": briefing, "battle": battle, "torpedoes": torpedoes, "math-boost": math_boost, "debrief": result,
}


def main(names: list[str]) -> int:
    unknown = [n for n in names if n not in SHOTS]
    if unknown:
        print(f"unknown shots: {', '.join(unknown)} (choose from {', '.join(SHOTS)})")
        return 2
    app = App(window_flags=0)
    for name in names or SHOTS:
        SHOTS[name](app)
    pygame.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
