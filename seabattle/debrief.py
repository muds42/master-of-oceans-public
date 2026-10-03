"""After-action debrief: what happened in a battle, and what to take from it.

Built from the battle's event history (``Battle.events``), so it works the same
in the game window, the headless runner and the tests. It compares the hits
each kind of weapon scored with what the odds predicted (the expected number,
and the range it usually lands in), and picks out the two or three things that
cost the player most: armor belts soaking up gun damage, damage wasted on ships
that were already sinking, torpedoes that ran dry or were shot down, where the
enemy's damage came from, and enemy ships repairing themselves. Act II adds
force fields soaking up damage, shots lost to holograms and graviton beams
carrying overkill through a stack.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .battle import Battle, GunsFired, Repaired, SalvoHit, SalvoLaunched, SalvoLost

KINDS = ("gun", "laser", "torpedo", "missile")
PLURAL = {"gun": "guns", "laser": "lasers", "torpedo": "torpedoes", "missile": "missiles"}
MAX_LESSONS = 3


@dataclass
class Tally:
    """How one side used one kind of weapon."""

    shots: int = 0  # shells fired, or torpedoes/missiles launched
    rolled: int = 0  # shots that got a roll to hit (the target was afloat; not shot down)
    expected: float = 0.0  # hits the odds predicted
    variance: float = 0.0
    hits: int = 0
    damage: int = 0
    blocked: int = 0  # stopped by armor belts
    wasted: int = 0  # past what sank the ship
    intercepted: int = 0
    lost: dict[str, int] = field(default_factory=dict)  # "range" / "target" -> torpedoes or missiles that never hit
    kills: int = 0
    absorbed: int = 0  # soaked up by force fields
    decoyed: int = 0  # went for a hologram
    carried: int = 0  # overkill a graviton beam carried into the next ship

    def roll(self, n: int, chance: float) -> None:
        """``n`` shots, each with ``chance`` to hit: add to the expected hits and their spread."""
        self.rolled += n
        self.expected += n * chance
        self.variance += n * chance * (1 - chance)

    @property
    def usual(self) -> tuple[int, int]:
        """The range the number of hits lands in about 19 battles out of 20 (two standard deviations)."""
        sd = math.sqrt(self.variance)
        return max(0, math.floor(self.expected - 2 * sd + 0.5)), math.floor(self.expected + 2 * sd + 0.5)


@dataclass
class Debrief:
    side: int  # the player's side
    names: tuple[str, str]
    tally: dict[tuple[int, str], Tally]
    repaired: dict[int, int]
    lessons: list[str]

    def of(self, side: int, kind: str) -> Tally:
        return self.tally.get((side, kind), Tally())

    def odds(self) -> list[tuple[str, str]]:
        """For each weapon the player used: (what happened against the odds, how lucky that was)."""
        out = []
        for kind in KINDS:
            t = self.of(self.side, kind)
            if not t.rolled:
                continue
            low, high = t.usual
            fired = f"{t.rolled} shots" if kind in ("gun", "laser") else f"{t.rolled} that reached their target"
            line = f"{PLURAL[kind].capitalize()}: {t.hits} hits from {fired}. The odds said about {t.expected:.0f}"
            line += f" (usually {low} to {high})." if high > low else "."
            if t.hits > high:
                verdict = "Luckier than usual!"
            elif t.hits < low:
                verdict = "Unluckier than usual."
            else:
                verdict = "Right in line with the odds."
            out.append((line, verdict))
        return out


def debrief(battle: Battle, side: int = 0, campaign: bool = False) -> Debrief:
    """Sum up ``battle`` from ``side``'s point of view. ``campaign`` allows advice about upgrades."""
    tally: dict[tuple[int, str], Tally] = {}
    salvos: dict[int, tuple[int, str]] = {}
    repaired = {0: 0, 1: 0}

    def t(s: int, kind: str) -> Tally:
        return tally.setdefault((s, kind), Tally())

    for e in battle.events:
        if isinstance(e, GunsFired):
            g = t(battle.stacks[e.attacker_id].side, e.kind)
            g.shots += e.shots
            g.roll(e.fired, e.chance)
            g.hits, g.damage, g.kills = g.hits + e.hits, g.damage + e.damage, g.kills + e.kills
            g.blocked, g.wasted = g.blocked + e.blocked, g.wasted + e.wasted
            g.absorbed, g.decoyed, g.carried = g.absorbed + e.absorbed, g.decoyed + e.decoyed, g.carried + e.carried
        elif isinstance(e, SalvoLaunched):
            salvos[e.salvo_id] = (battle.stacks[e.attacker_id].side, e.kind)
            t(*salvos[e.salvo_id]).shots += e.count
        elif isinstance(e, SalvoHit) and e.salvo_id in salvos:
            p = t(*salvos[e.salvo_id])
            p.roll(e.rolled, e.chance)
            p.hits, p.damage, p.kills = p.hits + e.hits, p.damage + e.damage, p.kills + e.kills
            p.blocked, p.wasted, p.intercepted = p.blocked + e.blocked, p.wasted + e.wasted, p.intercepted + e.intercepted
            p.absorbed, p.decoyed = p.absorbed + e.absorbed, p.decoyed + e.decoyed
        elif isinstance(e, SalvoLost) and e.salvo_id in salvos:
            p = t(*salvos[e.salvo_id])
            p.lost[e.reason] = p.lost.get(e.reason, 0) + e.count
        elif isinstance(e, Repaired):
            repaired[battle.stacks[e.stack_id].side] += e.amount
    d = Debrief(side, battle.side_names, tally, repaired, [])
    d.lessons = _lessons(d, battle, campaign)
    return d


def _lessons(d: Debrief, battle: Battle, campaign: bool) -> list[str]:
    """The few things that mattered most, biggest first. Each is (weight in hull points, advice)."""
    me, foe = d.side, 1 - d.side
    enemy = d.names[foe]
    mine = [d.of(me, k) for k in KINDS]
    found: list[tuple[float, str]] = []

    blocked = d.of(me, "gun").blocked + d.of(me, "missile").blocked
    got_through = d.of(me, "gun").damage + d.of(me, "missile").damage
    if blocked >= 10 and blocked >= 0.15 * (blocked + got_through):
        share = round(100 * blocked / (blocked + got_through))
        weapons = " and ".join(PLURAL[k] for k in ("gun", "missile") if d.of(me, k).blocked)
        tip = ("Torpedoes strike below the belt and ignore it, and each level of Heavier Shells adds 1 to every hit."
               if campaign else "Torpedoes strike below the belt and ignore it, and big guns lose less to it than small ones.")
        found.append((blocked, f"{enemy}'s armor belts stopped {blocked} damage from your {weapons} "
                               f"({share}% of what hit). {tip}"))

    absorbed = sum(t.absorbed for t in mine)
    dealt = sum(t.damage for t in mine)
    if absorbed >= 20 and absorbed >= 0.15 * (absorbed + dealt):
        share = round(100 * absorbed / (absorbed + dealt))
        tip = "hit one ship with everything at once, or send torpedoes under them"
        tip += ". Ion Beams drain fields faster." if campaign else "."
        found.append((absorbed, f"{enemy}'s force fields soaked up {absorbed} damage ({share}% of what got through "
                                f"the belts). Fields refill every turn: {tip}"))

    decoyed = sum(t.decoyed for t in mine)
    if decoyed >= 6:
        found.append((3 * decoyed, f"{decoyed} of your shots, torpedoes and missiles went for {enemy}'s holograms. "
                                   "Decoys can't be outaimed: only more shots get through."))

    carried = d.of(foe, "laser").carried
    if carried >= 15:
        found.append((carried, f"{enemy}'s graviton beams carried {carried} damage from ship to ship through your "
                               "stacks. Big stacks of small boats suffer most: lean on bigger ships."))

    wasted = sum(t.wasted for t in mine)
    if wasted >= 10 and wasted >= 0.2 * (wasted + dealt):
        found.append((wasted, f"{wasted} damage was wasted on ships that were already sinking. Save heavy guns and "
                              "torpedoes for big ships, and use lots of light guns on swarms of small boats."))

    def fired(counts: dict[str, int]) -> str:
        """ "torpedoes", "missiles" or "torpedoes and missiles": whichever it was."""
        return " and ".join(PLURAL[k] for k in ("torpedo", "missile") if counts.get(k))

    lost_range = {k: d.of(me, k).lost.get("range", 0) for k in ("torpedo", "missile")}
    lost_target = {k: d.of(me, k).lost.get("target", 0) for k in ("torpedo", "missile")}
    ran_dry, too_late = sum(lost_range.values()), sum(lost_target.values())
    if ran_dry + too_late >= 4:
        lost = {k: lost_range[k] + lost_target[k] for k in lost_range}
        if ran_dry >= too_late:
            tip = "Launch from closer, at ships too slow to outrun them"
            tip += ", or buy Longer-Range Torpedoes." if campaign and lost["torpedo"] else "."
            found.append((8 * ran_dry, f"{ran_dry + too_late} of your {fired(lost)} ran out of range "
                                       f"before they reached anything. {tip}"))
        else:
            found.append((8 * too_late, f"{ran_dry + too_late} of your {fired(lost)} lost their target: it sank "
                                        "before they arrived. Don't send a salvo after a ship that's already going down."))

    shot = {k: d.of(me, k).intercepted for k in ("torpedo", "missile")}
    if sum(shot.values()) >= 4:
        found.append((8 * sum(shot.values()), f"{enemy} shot down {sum(shot.values())} of your {fired(shot)}. "
                                              "Fire them in big salvos so more get through."))

    taken = {k: d.of(foe, k).damage for k in KINDS}
    total = sum(taken.values())
    if total >= 20:
        kind = max(taken, key=lambda k: taken[k])
        if taken[kind] >= 0.5 * total:
            tips = {
                "gun": ("An Armor Belt takes 1 off every gun hit, and Armor Plate adds hull." if campaign
                        else "Stay out of reach of the biggest guns until you can hit back."),
                "laser": ("Lasers burn straight through armor belts. Force Fields soak them up (a Field Generator "
                          "retrofit adds more to one class), and Holographic Decoys draw them off." if campaign
                          else "Lasers burn straight through armor belts: close in fast "
                          "and sink the laser ships first."),
                "torpedo": ("Torpedoes are slow: keep your distance and sink the torpedo boats first"
                            + (". Torpedo Interdiction shoots them down." if campaign else ".")),
                "missile": ("Missiles fly far and fast. Close in on the missile ships quickly"
                            + (", and Torpedo Interdiction shoots missiles down too." if campaign else ".")),
            }
            found.append((0.6 * taken[kind], f"{enemy}'s {PLURAL[kind]} did {taken[kind]} of the {total} damage your "
                                             f"fleet took. {tips[kind]}"))

    if d.repaired[foe] >= 15:
        found.append((d.repaired[foe], f"{enemy}'s damage control repaired {d.repaired[foe]} hull. Focus your fire on "
                                       "one ship at a time so it sinks before it can patch itself up."))

    found.sort(key=lambda f: -f[0])
    lessons = [text for _, text in found[:MAX_LESSONS]]
    if not lessons:
        if battle.winner == me:
            lessons = ["Nothing went badly wrong. Well fought!"]
        else:
            lessons = [f"{enemy} simply had more firepower this time. More ships and upgrades will turn it around."
                       if campaign else f"{enemy} simply had more firepower this time. Try focusing fire on its most "
                                        "dangerous ships first."]
    return lessons
