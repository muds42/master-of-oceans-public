# North star

**A student who solves about 15 problems between missions meets a steadily rising, always-real
challenge from Harbor Patrol to the Maelstrom and on into the patrols: no walkover stretches, no
walls, every act finale a hard but beatable fight, and the things on sale all worth buying at
some point.**

## How it is measured

`python tools/north_star.py` runs the game's own modeled player (`python -m seabattle.balance`,
see the README's *Balancing the campaign*) for seeds 1-4, 16 players each, through mission 33
(the first three patrols), and pools all 64 players. (Iterations 1-6 were scored on seeds 1 and 2;
the first review, on seeds 3 and 4, showed late Act III fitted to them, so from iteration 7 on
every score is on all four.) For every mission it reports:

* **first**: the chance of winning at the first try;
* **tries**: tries needed on average;
* **lost**: the share of the fleet's hull sunk in a first-try battle (0% is a walkover; this is
  what tells a real fight from a parade when first-try wins are at 100%).

Each mission scores 0-10 against its bands, as good as its worst part: 10 inside every band,
minus 1 point for every 2 percentage points outside a band, or every 0.15 tries outside a tries
band. (The tries band catches a death spiral: a player who loses, can't pay for the wrecks, and
loses again.)

| Kind | Missions | First try | Fleet lost | Tries |
| --- | --- | --- | --- | --- |
| Intro | 1-3 | 85-100% | 0-35% | 1.0-1.2 |
| Regular | the rest | 78-95% | 8-50% | 1.0-1.5 |
| Set piece | 9, 13, 16, 26, 29 | 62-88% | 12-60% | 1.0-1.8 |
| Super | 10, 20 | 30-50% | | 1.8-3.0 |
| Super | 30 | 20-45% | | 2.2-3.8 |
| Patrol | 31-33 | 50-90% | 12-60% | 1.0-1.8 |

The first-try bands come from the README's targets (about 85% for most missions, 75% for the set
pieces, 40% for super missions). The fleet-lost bands were set from the baseline: Act I's corvette
fleets lose a lot of hull even in wins (a 9-hp boat sinks to one torpedo), so the upper limit is
generous; the lower limit is there to catch walkovers.

## Rubric

| # | Criterion | Weight | 10/10 looks like | Measured by |
| --- | --- | --- | --- | --- |
| 1 | **Act I curve** | 2 | Missions 1-9 rise from walkovers to real fights, all in band | mean mission score, 1-9 |
| 2 | **Act II curve** | 2 | Missions 11-19 stay a fight after the cruiser squadron: no 100%-and-nothing-lost stretch | mean mission score, 11-19 |
| 3 | **Act III curve** | 3 | Missions 21-29 make Red's future tech bite: you win, but you pay for it | mean mission score, 21-29 |
| 4 | **Act finales** | 3 | Super missions 10, 20, 30 are hard and beatable: ~40% first try, 2-3 tries; the Maelstrom a little harder, never a wall | mean of the three super scores |
| 5 | **Choices and economy** | 1 | Nearly every upgrade, class and retrofit is bought by at least a quarter of players by the end; no currency piles up unspent | 5 x share of options bought by 25%+ of players, + 5 x (no currency more than 5% unspent, -0.5 per point over) |
| 6 | **Endgame scaling** | 1 | The patrols after the Maelstrom are winnable and get harder smoothly | mean mission score, 31-33 |

**Target:** every criterion at 8 or higher (weighted total 8.5+), on the pooled four-seed run.

## Guardrails

* **Don't touch the instrument.** The modeled player's decisions (`balance.py`'s workshop,
  spending and fighting) and the AI are how this is measured; changing them to raise a score is
  gaming the rubric. Instrumentation that only records more is fine. If the model seems wrong,
  note it under *Rubric concerns* in PROGRESS.md.
* **Leave the learning design alone:** the math problems, their pay, streaks and penalties
  (`problems/`), and Math Boost's numbers (`boost.py`). The campaign is balanced without Math Boost.
* **Keep the campaign's shape:** thirty missions in three acts, super missions at 10, 20 and 30
  that are bigger than the missions either side of them, Red's Act I upgrades at level 2 or
  below, no first-turn torpedoes or lasers, and save files that still load (`SAVE_VERSION`).
* **Tests and lint stay green** at every commit (`python -m pytest -q`, `ruff check .`). A test
  that pins a number this loop deliberately changes is updated to the new number, never deleted
  or loosened.
* **The README stays true:** mission tables, prices and the balance numbers it quotes are
  updated with the change that moves them.
* Iteration cap: **20**. Nothing irreversible (no pushes to `main`, no PRs) without asking.
