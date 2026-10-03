"""Drive the real game window with a dummy video driver to catch crashes."""

import os

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
pygame = pytest.importorskip("pygame")

from seabattle import campaign as cm  # noqa: E402
from seabattle.battle import Move  # noqa: E402
from seabattle.ui.app import App  # noqa: E402
from seabattle.ui.battle_scene import CHANCE_SECONDS, BattleScene, tile_to_screen  # noqa: E402
from seabattle.ui.menu_scene import QuickBattleScene, SlotScene, TitleScene  # noqa: E402
from seabattle.ui.workshop_scene import WorkshopScene  # noqa: E402


def run(app, seconds, events=()):
    for i in range(max(1, int(seconds * 60))):
        app.frame(1 / 60, list(events) if i == 0 else [])


def click(pos):
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1)


def key(k, unicode=""):
    return pygame.event.Event(pygame.KEYDOWN, key=k, mod=0, unicode=unicode)


def finish_battle(app, scene):
    scene.toggle_fleet_auto()
    scene.speed = 3
    for _ in range(800):
        run(app, 0.5)
        if scene.show_result:
            return
    raise AssertionError("battle did not finish")


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("SEABATTLE_SAVE_DIR", str(tmp_path))
    app = App(window_flags=0)
    yield app
    pygame.quit()


def test_title_to_quick_battle_and_back(app):
    assert isinstance(app.scene, TitleScene)
    run(app, 0.2, [key(pygame.K_b)])
    assert isinstance(app.scene, QuickBattleScene)
    run(app, 0.2, [key(pygame.K_RETURN)])
    scene = app.scene
    assert isinstance(scene, BattleScene) and scene.human_sides == {0}
    finish_battle(app, scene)
    run(app, 0.1, [key(pygame.K_ESCAPE)])
    assert isinstance(app.scene, TitleScene)


def test_player_can_move_fire_and_end_turn(app):
    app.start_battle("skirmish", 3)
    scene = app.scene
    run(app, 3)
    stack = scene.human_turn()
    assert stack is not None and stack.side == 0

    # one tile forward, so the stack still has moves left and its turn doesn't end on its own
    dest = max((p for p, path in scene.battle.reachable(stack).items() if len(path) == 1), key=lambda p: p[0])
    run(app, 1.5, [click(tuple(map(int, tile_to_screen(*dest))))])
    assert stack.pos == dest

    run(app, 0.1, [key(pygame.K_h)])
    assert scene.show_help
    run(app, 0.1, [key(pygame.K_SPACE)])  # closes help only
    assert not scene.show_help and scene.battle.active is stack

    run(app, 0.1, [key(pygame.K_SPACE)])
    assert scene.battle.active is not stack or scene.battle.round > 1

    for _ in range(400):
        if scene.show_result:
            break
        s = scene.human_turn()
        if s is None:
            run(app, 0.5)
            continue
        targets = [e for e in scene.battle.enemies_of(s) if scene.fireable(s, e)]
        if targets:
            run(app, 0.2, [click(tuple(map(int, tile_to_screen(*targets[0].pos))))])
        else:
            reach = [p for p in scene.battle.reachable(s) if p != s.pos]
            enemy = scene.battle.enemies_of(s)[0]
            if reach and s.moves_left == s.design.speed:
                best = min(reach, key=lambda p: abs(p[0] - enemy.pos[0]) + abs(p[1] - enemy.pos[1]))
                scene.act(Move(best))
            run(app, 0.2, [key(pygame.K_SPACE)])
    assert scene.battle.over


def test_won_missions_can_be_replayed_as_skirmishes(app):
    c = cm.Campaign(slot=1, mission_number=3, fleet={"destroyer": 8, "picket": 8})
    cm.save(c)
    app.open_workshop(c)
    ws = app.scene
    ws.tab = "fleet"
    run(app, 0.1)
    assert set(ws.mission_rows) == {1, 2}  # only missions already won
    run(app, 0.1, [click(ws.mission_rows[2].center)])
    assert ws.show_briefing and ws.skirmish == 2
    run(app, 0.1, [key(pygame.K_ESCAPE)])
    assert not ws.show_briefing and ws.skirmish is None

    run(app, 0.1, [click(ws.mission_rows[1].center)])
    run(app, 0.1, [key(pygame.K_RETURN)])
    battle = app.scene
    assert isinstance(battle, BattleScene) and battle.skirmish == 1
    finish_battle(app, battle)
    assert battle.report.skirmish
    run(app, 0.1, [key(pygame.K_RETURN)])
    assert isinstance(app.scene, WorkshopScene)
    saved = cm.load(1)
    assert saved.mission_number == 3 and saved.fleet == {"destroyer": 8, "picket": 8} and not saved.wrecks


def test_slots_that_cant_be_played_are_kept_safe(app, tmp_path):
    newer = dict(cm.Campaign(slot=1).to_dict(), version=cm.SAVE_VERSION + 1)
    cm.slot_path(1).write_text(cm.json.dumps(newer))
    cm.slot_path(2).write_text("{damaged")
    run(app, 0.2, [key(pygame.K_c)])
    slots = app.scene
    assert isinstance(slots, SlotScene) and set(slots.problems) == {1, 2}
    run(app, 0.2, [key(pygame.K_1)])  # "Try Again", not a new campaign over the newer save
    assert app.scene is slots and cm.json.loads(cm.slot_path(1).read_text())["version"] == cm.SAVE_VERSION + 1
    run(app, 0.2, [key(pygame.K_2)])  # the damaged one was set aside: the slot is free
    assert isinstance(app.scene, WorkshopScene) and cm.load(2).mission_number == 1


def test_a_failed_save_is_shown_not_a_crash(app, tmp_path, monkeypatch):
    run(app, 0.2, [key(pygame.K_c)])
    run(app, 0.2, [key(pygame.K_1)])
    ws = app.scene
    assert isinstance(ws, WorkshopScene)

    def full(campaign):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(cm, "save", full)
    run(app, 0.1, [key(pygame.K_1 + ws.posed.answer)])
    assert "No space left on device" in ws.toast


def test_campaign_workshop_to_mission_and_back(app, tmp_path):
    run(app, 0.2, [key(pygame.K_c)])
    assert isinstance(app.scene, SlotScene)
    run(app, 0.2, [key(pygame.K_1)])
    ws = app.scene
    assert isinstance(ws, WorkshopScene)
    assert cm.slot_path(1).exists()

    # Answer problems from both schools; right answers pay, wrong ones show the working.
    for school in ("algebra", "broadside"):
        ws.set_school(school)
        for _ in range(4):
            posed = ws.posed
            before = ws.c.balance(posed.topic.currency)
            run(app, 0.1, [key(pygame.K_1 + posed.answer)])
            assert ws.c.balance(posed.topic.currency) > before
            run(app, 0.1, [key(pygame.K_RETURN)])
        wrong = (ws.posed.answer + 1) % 4
        run(app, 0.1, [key(pygame.K_1 + wrong)])
        assert ws.c.streak == 0
        run(app, 0.1, [key(pygame.K_w)])
        assert ws.show_working
        run(app, 0.1, [key(pygame.K_h)])
        assert ws.show_help
        run(app, 0.1, [key(pygame.K_ESCAPE)])
        run(app, 0.1, [key(pygame.K_RETURN)])

    # Spend some of it, visit every page, then set sail.
    ws.c.currency.update(steel=400, powder=400, fuel=400, blueprints=400)
    ws.buy_upgrade("caliber")
    ws.buy_ship("picket")
    assert ws.c.level("caliber") == 1 and ws.c.fleet["picket"] == cm.STARTING_FLEET["picket"] + 1
    for tab in ("upgrades", "shipyard", "fleet", "log", "math"):
        ws.tab = tab
        run(app, 0.1)
    ws.tab, ws.shipyard_view = "shipyard", "retrofits"  # before Plasma: what's coming
    run(app, 0.1)
    ws.tab, ws.shipyard_view = "math", "act1"
    ws.show_briefing = True
    run(app, 0.1)
    run(app, 0.1, [key(pygame.K_RETURN)])
    battle = app.scene
    assert isinstance(battle, BattleScene) and battle.campaign is ws.c
    assert battle.ai[1].retreat_ratio == 0  # Red never retreats from a mission
    finish_battle(app, battle)
    assert battle.report is not None and battle.debrief is not None
    run(app, 0.1, [key(pygame.K_RETURN)])
    assert isinstance(app.scene, WorkshopScene)

    saved = cm.load(1)
    assert saved.level("caliber") == 1 and saved.lessons == battle.debrief.lessons
    assert saved.mission_number == 2 if battle.report.won else saved.attempts == 1


def test_the_shipyard_retrofits_a_class(app):
    c = cm.Campaign(slot=1, mission_number=21, fleet={"destroyer": 4, "picket": 3},
                    unlocked=["picket", "torpedo_boat", "destroyer"], upgrades={"lasers": 1},
                    currency={"plasma": 200, "powder": 200, "steel": 50})
    cm.save(c)
    app.open_workshop(c)
    ws = app.scene
    ws.tab, ws.shipyard_view = "shipyard", "retrofits"
    run(app, 0.1)

    def fit_button(class_id, retrofit_id):
        return next((rect for rect, fn in ws.hits if getattr(fn, "__defaults__", None) == (class_id, retrofit_id)), None)

    assert fit_button("destroyer", "field_generator") is None  # Force Fields not researched yet
    assert fit_button("battleship", "laser_battery") is None  # class still locked
    rect = fit_button("destroyer", "laser_battery")
    assert rect is not None
    run(app, 0.1, [click(rect.center)])
    assert ws.c.has_retrofit("destroyer", "laser_battery") and cm.load(1).retrofits == {"destroyer": ["laser_battery"]}
    assert fit_button("destroyer", "laser_battery") is None  # fitted
    ws.mouse = rect.center
    run(app, 0.1)  # the tooltip
    for view in ("act1", "future"):
        ws.shipyard_view = view
        run(app, 0.1)


def test_mistakes_are_explained_and_come_back_for_review(app):
    c = cm.Campaign(slot=1)
    cm.save(c)
    app.open_workshop(c)
    ws = app.scene
    run(app, 0.1, [key(pygame.K_w)])
    assert not ws.show_working  # the working is the answer: no peeking before you pick

    missed = ws.posed.generator.key
    wrong = (ws.posed.answer + 1) % 4
    run(app, 0.1, [key(pygame.K_1 + wrong)])
    assert ws.show_working and ws.c.review == {missed: cm.REVIEW_GAP}
    assert ws.posed.reason(wrong) == ws.posed.why[wrong] and ws.posed.reason(ws.posed.answer) == ""
    for _ in range(cm.REVIEW_GAP):
        run(app, 0.1, [key(pygame.K_RETURN)])
        assert not ws.reviewing
        run(app, 0.1, [key(pygame.K_1 + ws.posed.answer)])
    run(app, 2.0)  # a right answer moves on by itself
    assert ws.reviewing and ws.posed.generator.key == missed
    run(app, 0.1, [key(pygame.K_1 + ws.posed.answer)])
    assert missed not in ws.c.review and cm.load(1).skills[missed].endswith("1")

    ws.set_school("broadside")
    run(app, 0.1, [key(pygame.K_t)])
    assert ws.show_trig
    run(app, 0.1, [key(pygame.K_1)])  # the table is open: answer keys do nothing
    assert ws.picked is None
    run(app, 0.1, [key(pygame.K_ESCAPE)])
    assert not ws.show_trig and isinstance(app.scene, WorkshopScene)


def test_the_briefing_sets_math_boost(app):
    c = cm.Campaign(slot=1, mission_number=2, fleet={"destroyer": 4, "picket": 4})
    cm.save(c)
    app.open_workshop(c)
    ws = app.scene
    ws.show_briefing = True
    run(app, 0.1)
    assert not ws.c.boost
    run(app, 0.1, [key(pygame.K_b)])
    assert ws.c.boost and cm.load(1).boost
    run(app, 0.1, [key(pygame.K_b)])
    assert not ws.c.boost and ws.show_briefing
    run(app, 0.1, [key(pygame.K_b)])
    run(app, 0.1, [key(pygame.K_RETURN)])
    assert isinstance(app.scene, BattleScene) and app.scene.boost is not None


def test_a_super_mission_is_briefed_as_one_and_offers_more_boosts(app):
    c = cm.Campaign(slot=1, mission_number=10, fleet={"destroyer": 6, "light_cruiser": 3}, boost=True)
    cm.save(c)
    app.open_workshop(c)
    ws = app.scene
    ws.tab = "fleet"
    run(app, 0.1)
    ws.show_briefing = True
    run(app, 0.1)
    run(app, 0.1, [key(pygame.K_RETURN)])
    scene = app.scene
    assert isinstance(scene, BattleScene) and scene.boost is not None and scene.boost.limit == 25
    finish_battle(app, scene)
    assert scene.report.lines()[0].startswith("Super Mission 10 ")


def boosted_mission(app):
    c = cm.Campaign(slot=1, mission_number=9, fleet={"destroyer": 6, "light_cruiser": 3, "torpedo_boat": 4},
                    boost=True)
    cm.save(c)
    app.start_mission(c)
    scene = app.scene
    scene.toggle_fleet_auto()
    scene.speed = 3
    return scene


def next_box(app, scene):
    """Play on until a MATH BOOST box comes up; it, or None if the battle ended first."""
    for _ in range(3000):
        run(app, 0.1)
        if scene.box_open or scene.show_result:
            return scene.chance if scene.box_open else None
    raise AssertionError("no Math Boost came up")


def test_a_big_hit_freezes_with_the_box_beside_it(app):
    scene = boosted_mission(app)
    c = next_box(app, scene)
    assert c is not None and scene.human_turn() is None and not scene.prompt_open
    assert scene.current is c.anim and c.anim.frozen and c.anim.ev is c.hit.event  # the hit itself, held just before it lands
    seen = len(scene.battle.events)
    run(app, 1.0)  # the battle waits (and the box counts down)
    assert scene.chance is c and len(scene.battle.events) == seen and 0 < c.wait < CHANCE_SECONDS
    assert scene.box_rect is not None and scene.map_rect.contains(scene.box_rect)
    x, y = scene.visuals[c.hit.event.target_id].screen
    assert scene.box_rect.inflate(160, 160).collidepoint(x, y)  # right by the ship about to be hit, within a tile or so
    assert "MATH BOOST" in scene.log[-1][0] and c.hit.story() in scene.log[-1][0]
    left = c.wait
    run(app, left - 0.2)
    assert scene.chance is c
    run(app, 0.4)  # left alone, the hit lands as rolled
    assert scene.chance is not c and scene.boost.offered >= 1 and scene.boost.posed == scene.boost.answered == 0
    landed = next(e for e in scene.battle.events if getattr(e, "key", None) == c.hit.key and type(e) is type(c.hit.event))
    assert landed.boost == 1.0 and landed.damage == c.hit.damage

    c = next_box(app, scene)
    if c is not None:
        run(app, 0.05, [key(pygame.K_SPACE)])  # Space lets it land at once
        assert scene.chance is not c and scene.boost.posed == 0


def test_the_same_battle_offers_the_same_boosts(app):
    """A battle's seed replays its Math Boost too: the hits that offer one and the problems."""
    def first_problem():
        scene = boosted_mission(app)
        box = next_box(app, scene)
        run(app, 0.05, [key(pygame.K_b)])
        return box.hit.key, scene.prompt.problem.question

    assert first_problem() == first_problem()


def test_math_boost_problems_in_battle(app):
    scene = boosted_mission(app)
    for n in range(3):
        c = next_box(app, scene)
        assert c is not None
        if n == 0:
            run(app, 0.05, [click(scene.box_rect.center)])  # take it with a click...
        else:
            run(app, 0.05, [key(pygame.K_b)])  # ...or with B
        p = scene.prompt
        assert p is c and scene.prompt_open and p.problem is not None and scene.boost.posed == n + 1
        run(app, 0.05, [key(pygame.K_RETURN)])  # no answer yet: the battle waits
        run(app, CHANCE_SECONDS + 1)  # and doesn't run out of time
        assert scene.prompt is p
        run(app, 0.05, [key(pygame.K_h)])
        assert p.show_hint
        pick = p.problem.answer if n != 1 else (p.problem.answer + 1) % 4
        run(app, 0.05, [key(pygame.K_1 + pick)])
        assert p.picked == pick and p.boosts == {p.hit.key: p.hit.scale if n != 1 else p.hit.miss_scale}
        run(app, 0.05, [key(pygame.K_RETURN)])
        assert scene.chance is None
        landed = next(e for e in reversed(scene.battle.events) if getattr(e, "key", None) == p.hit.key)
        assert landed.boost == pytest.approx(p.hit.scale if n != 1 else p.hit.miss_scale)
    assert (scene.boost.answered, scene.boost.right) == (3, 2)

    c = next_box(app, scene)  # the popup's own button turns it off for the rest of the mission
    run(app, 0.05, [key(pygame.K_b)])
    assert scene.prompt is c
    turn_off = next(fn for _, fn in scene.prompt_hits if getattr(fn, "__name__", "") == "turn_boost_off")
    turn_off()
    assert scene.chance is None and not scene.boost.on and scene.boost.answered == 3
    for _ in range(3000):
        run(app, 0.5)
        assert scene.chance is None
        if scene.show_result:
            break
    assert scene.show_result and scene.boost.summary().startswith("Math Boost: 2 of 3 right")
    assert cm.load(1).stats["boost"] == {"attempted": 3, "solved": 2}


def test_math_boost_can_be_turned_off_from_the_battle(app):
    scene = boosted_mission(app)
    run(app, 0.1)
    button = scene.boost_button
    assert button is not None
    run(app, 0.1, [key(pygame.K_b)])  # B on its own does nothing without a box
    assert scene.boost.on and scene.boost_confirm == 0
    run(app, 0.1, [click(button.rect.center)])
    assert scene.boost.on and scene.boost_confirm > 0  # once asks, twice turns it off
    run(app, 0.1, [click(button.rect.center)])
    assert not scene.boost.on
    for _ in range(3000):
        run(app, 0.5)
        assert scene.chance is None
        if scene.show_result:
            break
    assert scene.show_result and scene.boost.posed == 0
