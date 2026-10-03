"""Math Boost: a 7th-grade math problem on the big hits of a battle.

With Math Boost on (a switch on the mission briefing), the battle freezes just
as a big hit is about to land, the shells in the air or the torpedoes at the
ship, and a MATH BOOST box comes up beside the ship about to be hit. Clicking
it puts a Dino Math problem (``problems/dinomath.py``) to the player; left
alone, the hit lands as it was rolled after a few seconds. A right answer makes
the player's own hit do 30% more damage, or an enemy hit on the player's ships
do 30% less. A wrong answer costs a little: the player's hit does 15% less
damage, or the enemy's 15% more, and the working is shown. With four choices a
blind guess is right one time in four; in simulated battles, guessing every
answer comes out slightly behind not answering at all (about 1 damage lost per
boost), while a player who gets 80% right keeps nearly all of the benefit
(about 8 damage gained per boost, against 9.5 with no penalty). So only
solving the problems pays, as in the workshop. The player can switch the boost
off at any time, and it stays off for the rest of the battle.

The problems come from all five of Dino Math's levels, mostly the middle one:
each problem's level is drawn afresh, level 3 four times in ten, levels 2 and 4
twice in ten each, and levels 1 and 5 once in ten each (``LEVEL_ODDS``).

What counts as a big hit. Battles differ a lot: a first mission is two or
three rounds and a handful of hits, a late one against a super ship dozens of
hits of every size. So "big" is measured against the battle itself. A hit is
big when

* its hull damage is at least 5% of the smaller fleet's hull at the start of
  the battle, so small change never counts, and
* it is at least as big as the middle one of all the hits so far in the
  battle, both sides' (the first three hits only need the 5%).

Then, to keep it to a handful: at most one boost for each ship's turn (and
one at the start of each round, when torpedoes and missiles arrive), and at
most 10 a battle. In campaign battles fought by the modeled player (see
``balance.py``) this comes to 5-10 boosts in most battles from mission 5 on,
split about evenly between offense and defense. The short early missions,
with a handful of hits in all, get fewer. The campaign's super missions (10, 20
and 30) are longer battles with more math in them: a hit is big from 2.5% of the
smaller fleet's hull if it is at least as big as the quarter-way hit so far
(instead of the middle one), and there are up to 25 boosts.

Everything here is plain logic, no pygame: the battle screen previews each
action (:meth:`Battle.preview`), asks :meth:`MathBoost.big_hit` whether it
brings a big hit, and once the player has answered applies the action with
:meth:`MathBoost.boosts`.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Optional, Union

from .battle import Battle, Event, GunsFired, HitKey, RoundStarted, SalvoHit, SalvoLaunched, StackActivated
from .problems.dinomath import DinoProblem, make_problem

BOOST = 0.3  # a right answer: 30% more damage dealt, or 30% less taken
PENALTY = 0.15  # a wrong one: 15% less damage dealt, or 15% more taken, so guessing doesn't pay
FLOOR = 0.05  # a big hit is at least this share of the smaller fleet's starting hull...
WARMUP = 3  # ...and, after this many hits, at least as big as the middle hit so far
MAX_PER_BATTLE = 10  # big hits offered a battle, taken or not
# A super mission is a longer battle with more math in it: more hits count as big, and more of them are offered.
SUPER_FLOOR = 0.025
SUPER_BAR = 0.25  # after the warm-up, a big hit is at least as big as the hit this far up the hits so far
MAX_PER_SUPER_MISSION = 25
LEVEL_ODDS = (0.1, 0.2, 0.4, 0.2, 0.1)  # how often each level (0-4, shown as 1-5) comes up

Hit = Union[GunsFired, SalvoHit]


@dataclass(frozen=True)
class BigHit:
    """A hit worth a boost, as the preview rolled it."""

    event: Hit
    offense: bool  # the player's hit (True), or one on the player's ships
    attacker: str  # who fires: "your Destroyer x4", "Red Battleship x1"; for a salvo, "your torpedoes", "Red missiles"
    target: str
    weapon: str = ""  # guns only, e.g. '12" Guns'
    ships: int = 1  # how many ships fire (guns)

    @property
    def key(self) -> HitKey:
        return self.event.key

    @property
    def damage(self) -> int:
        return self.event.damage

    @property
    def scale(self) -> float:
        """The damage multiplier for a right answer."""
        return 1 + BOOST if self.offense else 1 - BOOST

    @property
    def miss_scale(self) -> float:
        """The damage multiplier for a wrong answer."""
        return 1 - PENALTY if self.offense else 1 + PENALTY

    def headline(self) -> str:
        return "BIG HIT!" if self.offense else "INCOMING!"

    def story(self) -> str:
        """What is about to happen, e.g. 'Your Destroyer x4 are about to fire 4" Guns at Red Cruiser x2: 38 damage, 1 sunk.'"""
        sunk = f", {self.event.kills} sunk" if self.event.kills else ""
        if isinstance(self.event, SalvoHit):
            what = f"{self.attacker} are about to reach {self.target}"
        else:
            what = f"{self.attacker} {'is' if self.ships == 1 else 'are'} about to fire {self.weapon} at {self.target}"
        return f"{what[0].upper() + what[1:]}: {self.damage} damage{sunk}."

    def stakes(self) -> str:
        pct, miss = f"{BOOST:.0%}", f"{PENALTY:.0%}"
        if self.offense:
            return f"Solve it for {pct} more damage. A wrong answer: {miss} less."
        return f"Solve it to take {pct} less damage. A wrong answer: {miss} more."

    def outcome(self, correct: bool) -> str:
        pct = f"{(BOOST if correct else PENALTY):.0%}"
        if correct:
            return f"Right! Your hit does {pct} more damage." if self.offense else f"Right! You take {pct} less damage."
        return f"Not this time: your hit does {pct} less damage." if self.offense else f"Not this time: you take {pct} more damage."


@dataclass
class MathBoost:
    """One battle's Math Boost: spots the big hits, poses the problems and keeps the score."""

    side: int = 0  # the player's side
    rng: random.Random = None  # type: ignore[assignment]
    on: bool = True
    scale: int = 0  # the smaller fleet's hull at the start: what "big" is measured against
    sizes: list = None  # type: ignore[assignment]  # every hit so far, smallest first
    turns: set = None  # type: ignore[assignment]  # the turns that have had a boost
    offered: int = 0  # big hits offered for a boost
    posed: int = 0  # problems put to the player (the offers taken)
    answered: int = 0
    right: int = 0
    dealt: int = 0  # extra damage the boosts added to the player's hits
    saved: int = 0  # damage the boosts kept off the player's ships
    cost: int = 0  # what wrong answers cost: damage the player's hits lost, and extra damage taken
    last_topic: Optional[str] = None
    limit: int = MAX_PER_BATTLE  # most big hits offered this battle
    floor: float = FLOOR  # a big hit is at least this share of ``scale``...
    bar: float = 0.5  # ...and at least as big as the hit this far up the hits so far (0.5: the middle one)

    def __post_init__(self) -> None:
        self.rng = self.rng or random.Random()
        self.sizes = self.sizes if self.sizes is not None else []
        self.turns = self.turns if self.turns is not None else set()

    @classmethod
    def for_battle(cls, battle: Battle, side: int = 0, rng: Optional[random.Random] = None,
                   super_mission: bool = False) -> "MathBoost":
        """The battle's Math Boost; a super mission's offers more of them."""
        hull = [sum(s.total_hp for s in battle.stacks.values() if s.side == k) for k in (0, 1)]
        boost = cls(side=side, rng=rng or random.Random(), scale=min(hull))
        if super_mission:
            boost.limit, boost.floor, boost.bar = MAX_PER_SUPER_MISSION, SUPER_FLOOR, SUPER_BAR
        return boost

    @property
    def active(self) -> bool:
        return self.on and self.offered < self.limit

    def turn_off(self) -> None:
        """Off for the rest of the battle."""
        self.on = False

    def big_hit(self, battle: Battle, events: list[Event]) -> Optional[BigHit]:
        """The biggest hit among ``events`` (what an action is about to bring, from
        :meth:`Battle.preview`) if it is big enough for a boost. Every hit, boosted or
        not, joins the record of hits that "big" is measured against."""
        best: Optional[tuple[int, Hit, tuple]] = None
        turn: tuple = (battle.round, battle.active_id)
        hits: list[int] = []
        for e in events:
            if isinstance(e, RoundStarted):
                turn = (e.round, None)
            elif isinstance(e, StackActivated):
                turn = (turn[0], e.stack_id)
            elif isinstance(e, (GunsFired, SalvoHit)) and e.damage > 0:
                hits.append(e.damage)
                if self.active and turn not in self.turns and self._big(e.damage) and (best is None or e.damage > best[0]):
                    best = (e.damage, e, turn)
        found = None
        if best is not None:
            found = self._describe(battle, events, best[1])
            self.turns.add(best[2])
            self.offered += 1
        for size in hits:
            self._record(size)
        return found

    def _big(self, size: int) -> bool:
        if size < self.floor * self.scale:
            return False
        return len(self.sizes) < WARMUP or size >= self.sizes[int(len(self.sizes) * self.bar)]

    def _record(self, size: int) -> None:
        i = len(self.sizes)
        while i and self.sizes[i - 1] > size:
            i -= 1
        self.sizes.insert(i, size)

    def _describe(self, battle: Battle, events: list[Event], e: Hit) -> BigHit:
        target = self._name(battle, battle.stacks[e.target_id])
        if isinstance(e, GunsFired):
            shooter = battle.stacks[e.attacker_id]
            weapon = shooter.design.mounts[e.mount].weapon.name + "s"
            return BigHit(e, shooter.side == self.side, self._name(battle, shooter), target, weapon, shooter.count)
        side = 1 - battle.stacks[e.target_id].side
        salvo = battle.salvos.get(e.salvo_id)
        kind = salvo.weapon.kind if salvo else next(
            (x.kind for x in events if isinstance(x, SalvoLaunched) and x.salvo_id == e.salvo_id), "torpedo")
        owner = "your" if side == self.side else battle.side_names[side]
        return BigHit(e, side == self.side, f"{owner} {'missiles' if kind == 'missile' else 'torpedoes'}", target)

    def _name(self, battle: Battle, stack) -> str:
        owner = "your" if stack.side == self.side else battle.side_names[stack.side]
        return f"{owner} {stack.design.name} x{stack.count}"

    # ---- the problem ------------------------------------------------------------

    def pose(self) -> DinoProblem:
        """A problem for a boost the player took: its level drawn by ``LEVEL_ODDS``, and never
        the same topic twice in a row."""
        level = self.rng.choices(range(len(LEVEL_ODDS)), weights=LEVEL_ODDS)[0]
        problem = make_problem(self.rng, level, avoid=self.last_topic)
        self.last_topic = problem.topic
        self.posed += 1
        return problem

    def boosts(self, hit: BigHit, correct: bool) -> dict[HitKey, float]:
        """Record an answer; what to pass to :meth:`Battle.apply` for the action."""
        self.answered += 1
        if not correct:
            return {hit.key: hit.miss_scale}
        self.right += 1
        return {hit.key: hit.scale}

    def landed(self, hit: BigHit, events: list[Event]) -> int:
        """After the answered action: how much damage the answer changed (added or kept off
        for a right one, lost or let through for a wrong one), counted in the score. Returns it."""
        real = next((e for e in events if isinstance(e, type(hit.event)) and e.key == hit.key), None)
        if real is None or real.boost == 1.0:
            return 0
        gain = real.damage - hit.damage if hit.offense else hit.damage - real.damage  # in the player's favor
        if real.boost == hit.miss_scale:
            self.cost += max(0, -gain)
            return max(0, -gain)
        if hit.offense:
            self.dealt += max(0, gain)
        else:
            self.saved += max(0, gain)
        return max(0, gain)

    def summary(self) -> str:
        """The battle's boosts in a line, e.g.
        "Math Boost: 6 of 8 right, +54 damage dealt, 31 damage stopped, 7 lost to wrong answers."."""
        if not self.answered:
            if self.offered:
                return "Math Boost: no boosts taken."
            return "Math Boost: no big hits came up." if self.on else ""
        parts = [f"Math Boost: {self.right} of {self.answered} right"]
        if self.dealt:
            parts.append(f"+{self.dealt} damage dealt")
        if self.saved:
            parts.append(f"{self.saved} damage stopped")
        if self.cost:
            parts.append(f"{self.cost} lost to wrong answers")
        return ", ".join(parts) + "."


def play(battle: Battle, controllers, boost: MathBoost, accuracy: float, rng: random.Random,
         max_actions: int = 20_000) -> Battle:
    """Play a battle to the end without a window, the way the battle screen runs Math Boost:
    each action is previewed, every big hit's boost is taken, and its problem is answered
    right with probability ``accuracy``. For balancing and tests."""
    battle.start()
    for _ in range(max_actions):
        if battle.over:
            return battle
        stack = battle.active
        assert stack is not None
        action = controllers[stack.side].choose_action(battle, stack)
        hit = boost.big_hit(battle, battle.preview(action)) if boost.active else None
        if hit is None:
            battle.apply(action)
            continue
        boost.pose()
        boost.landed(hit, battle.apply(action, boost.boosts(hit, rng.random() < accuracy)))
    raise RuntimeError("battle did not finish; a controller is probably stuck")
