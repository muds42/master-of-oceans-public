"""Ready-made battles. Each scenario builds a fresh :class:`Battle` from a seed."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Callable

from .battle import MAX_STACKS_PER_SIDE, Battle, Fleet, Pos
from .designs import ALL_DESIGNS, BATTLESHIP, DESTROYER, LIGHT_CRUISER, PICKET, TORPEDO_BOAT

# Wide enough that fleets start beyond one move plus a torpedo's range of each other,
# so only ships with upgraded engines can close in and launch on the first turn.
WIDTH, HEIGHT = 14, 9
ISLANDS = (2, 5)  # islands per map, fewest to most


@dataclass(frozen=True)
class Scenario:
    id: str
    name: str
    description: str
    fleets: Callable[[random.Random], tuple[Fleet, Fleet]]

    def build(self, seed: int, side_names: tuple[str, str] = ("Blue", "Red")) -> Battle:
        rng = random.Random(seed)
        fleets = self.fleets(rng)
        islands = generate_islands(rng, WIDTH, HEIGHT, rng.randint(*ISLANDS))
        return Battle(fleets, width=WIDTH, height=HEIGHT, islands=islands, seed=seed, side_names=side_names)


def generate_islands(rng: random.Random, width: int, height: int, count: int) -> set[Pos]:
    """Scatter islands in the middle of the map, never cutting it in two."""
    islands: set[Pos] = set()
    candidates = [(x, y) for x in range(3, width - 3) for y in range(height)]
    rng.shuffle(candidates)
    for pos in candidates:
        if len(islands) >= count:
            break
        near = any(abs(pos[0] - i[0]) <= 1 and abs(pos[1] - i[1]) <= 1 for i in islands)
        if not near and _connected(islands | {pos}, width, height):
            islands.add(pos)
    return islands


def _connected(islands: set[Pos], width: int, height: int) -> bool:
    open_tiles = {(x, y) for x in range(width) for y in range(height)} - islands
    start = next(iter(open_tiles))
    seen, frontier = {start}, [start]
    while frontier:
        x, y = frontier.pop()
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                p = (x + dx, y + dy)
                if p in open_tiles and p not in seen:
                    seen.add(p)
                    frontier.append(p)
    return len(seen) == len(open_tiles)


def _mirror(fleet: Fleet) -> Callable[[random.Random], tuple[Fleet, Fleet]]:
    return lambda rng: (list(fleet), list(fleet))


def random_fleet(rng: random.Random, budget: int) -> Fleet:
    """Spend roughly ``budget`` on up to six stacks of the preset designs."""
    designs = list(ALL_DESIGNS.values())
    picks = rng.sample(designs, k=rng.randint(2, 4))
    counts = {d.name: 0 for d in picks}
    by_name = {d.name: d for d in picks}
    spent = 0
    cheapest = min(d.cost for d in picks)
    while spent + cheapest <= budget:
        affordable = [d for d in picks if spent + d.cost <= budget]
        d = rng.choice(affordable)
        counts[d.name] += 1
        spent += d.cost
    fleet: Fleet = []
    for name, n in counts.items():
        if n == 0:
            continue
        # Split big groups into two stacks while there is room, like a real fleet would.
        if n >= 6 and len(fleet) < MAX_STACKS_PER_SIDE - 1:
            fleet += [(by_name[name], n // 2), (by_name[name], n - n // 2)]
        else:
            fleet.append((by_name[name], n))
    return fleet[:MAX_STACKS_PER_SIDE]


SCENARIOS: dict[str, Scenario] = {
    s.id: s
    for s in [
        Scenario(
            "skirmish",
            "Destroyer Skirmish",
            "Two evenly matched flotillas of destroyers, picket boats and torpedo boats.",
            _mirror([(DESTROYER, 3), (PICKET, 4), (TORPEDO_BOAT, 4), (DESTROYER, 3)]),
        ),
        Scenario(
            "battle_line",
            "Battle Line",
            "Full fleets: a battleship, cruisers, destroyers and escorts on each side.",
            _mirror([(PICKET, 6), (DESTROYER, 4), (LIGHT_CRUISER, 2), (BATTLESHIP, 1), (DESTROYER, 4)]),
        ),
        Scenario(
            "mosquito",
            "Mosquito Fleet",
            "Challenge: your swarm of torpedo boats and pickets against a battleship and two cruisers.",
            lambda rng: (
                [(PICKET, 8), (TORPEDO_BOAT, 12), (TORPEDO_BOAT, 12), (PICKET, 8)],
                [(LIGHT_CRUISER, 1), (BATTLESHIP, 1), (LIGHT_CRUISER, 1)],
            ),
        ),
        Scenario(
            "random",
            "Random Encounter",
            "Two random fleets of equal cost. Different every time.",
            lambda rng: (random_fleet(rng, 1500), random_fleet(rng, 1500)),
        ),
    ]
}
