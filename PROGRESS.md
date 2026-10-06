# Progress

Scores from `python tools/north_star.py` (seeds 1 and 2, 32 modeled players, missions 1-33).
Order: act1 / act2 / act3 / finales / choices / endgame → weighted.

## Baseline

| Mission range | What the modeled player sees |
| --- | --- |
| 1-9 | In band, but Wolf Pack (8) and the Iron Wall (7) cost 58-66% of the fleet's hull even when won |
| 10 | 38% first try, 2.2 tries: on target (seed 1 alone: 20%) |
| 11-19 | 15-19 all won at the first try, 100% |
| 20 | 42%, 2.3 tries: on target |
| 21-29 | Every one won at the first try, 100%, losing 9-23% of the fleet |
| 30 | 31% first try but **5.2 tries**: a wall |
| 31-33 | Patrol 3 is 15% first try, 7.8 tries: the patrols hit a wall too |
| Shop | Never bought by the modeled players: Destroyer, Light Cruiser, Missile Cruiser, all three Plasma classes, More Torpedo Tubes, Graviton Beams, Plasma Torpedoes, Point-Defense Lasers, Nanite Repair. 26% of blueprints and 18% of plasma go unspent |

Baseline: **8.3 / 7.8 / 6.7 / 6.9 / 3.3 / 1.9 → 6.5**

## Iterations

| # | Change | Scores before → after | Kept? | Next idea |
| --- | --- | --- | --- | --- |

## Rubric concerns

* The modeled player judges purchases with a Lanchester estimate (damage x hull per stack), which
  favours deepening a stack it already has over starting a new class. "Never bought" is partly
  that bias, not only bad value. The choices criterion is weighted 1 for that reason.
* The fleet-lost bands were set from the baseline (setup, before iteration 1): Act I's corvette
  swarms lose much more hull per win than later fleets of big ships, whose damage that doesn't
  sink a ship costs nothing.
