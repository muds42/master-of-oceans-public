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

Baseline: **8.3 / 7.8 / 6.7 / 6.9 / 3.3 / 1.9 → 6.5** (seeds 1-2; iterations 1-6 are scored on these)

Baseline on all four seeds (from iteration 7 on): **8.1 / 7.9 / 6.7 / 6.7 / 3.2 / 1.6 → 6.4**.
Iteration 6 on all four seeds: **8.1 / 8.7 / 7.7 / 6.7 / 3.5 / 6.1 → 7.2**.

## Iterations

| # | Change | Scores before → after | Kept? | Next idea |
| --- | --- | --- | --- | --- |
| 1 | Act II tail: escorts for missions 15-19 (Leviathan + 2 light cruisers + 4 destroyers; twin dreadnoughts + 5 destroyers; a bigger swarm; + 4 destroyers in the straits; 2 battleships, 2 cruisers, 4 destroyers at the harbor). The Kraken loses its 2 destroyers so the act finale stays ~40% | 8.3/7.8/6.7/6.9/3.3/1.9 → 8.3/**8.8**/6.7/6.7/3.2/0.0 (6.5 → 6.5) | kept | Endgame's drop is the Maelstrom wall's knock-on (players stuck at 30 reach the patrols crippled). Next: shipyard prices before Act III, since they move the player's strength |
| 2 | Shipyard prices, from equal-cost battles against real Red fleets: Missile Cruiser 900 → 430 (unlock 500 → 300 blueprints), Light Cruiser 360 → 290, Aegis Cruiser 580 → 360 (unlock 300 → 200 plasma), Hydrofoil Raider 100 → 75 (unlock 150 → 100). Before, the Missile Cruiser won 8% where the same money in destroyers won 95% (mission 11), and the Aegis 0-7% | 8.3/8.8/6.7/6.7/3.2/0.0 → same, bit for bit (6.5 → 6.5) | kept | The modeled player never considers these classes (see Rubric concerns), so the rubric can't see it; the duels can: Missile Cruiser 8% → 100% at mission 11, Light Cruiser 15% → 98% at mission 14. Next: Act III |
| 3 | Defeats repair half: after any lost or abandoned mission the dockyards repair half the ships it sank for free, as they already did after a super mission. The Kraken gets one destroyer back (it had been softened for spirals that no longer happen) | 8.3/8.8/6.7/6.7/3.2/0.0 → 8.2/8.6/6.7/**7.4**/3.2/**2.4** (6.5 → **6.8**) | kept | Act III at a fixed fleet was a death spiral: 67-78% first try but 2.4-6 tries, a lost battle's battleship repairs (129 each) eating most of a workshop. With the rule: Twin Dreadnoughts 1.97 → 1.16 tries, the Maelstrom 6.6 → 5.0, Patrols 1-2 4.3 → 2.8. Next: Act III's fleets, now that a defeat doesn't spiral |
| 4 | Act III fleets, tuned one mission at a time in campaign order, aiming probes at ~93% so the sequence lands near 85%: Salvage Rights 1.5x; 26 laser destroyers at Strange Lights; 10 + 14 shielded cruisers and destroyers at the Shimmer; 5/13/19 at Ghost Fleet; 22 + 22 plasma boats and 11 destroyers on the Plasma Run; the Tempest with 1 battleship, 4 cruisers, 8 destroyers; 3/3/8 on the Rail Line; Graviton Storm and the Gauntlet with cruiser and destroyer screens | 8.2/8.6/6.7/7.4/3.2/2.4 → 8.2/8.6/**8.7**/6.7/3.2/0.5 (6.8 → **6.9**) | kept | Act III is 82-98% first try and loses 25-53% of the fleet: a fight every time. Players who fought it reach the Maelstrom weaker (16%, 6.5 tries), the finale's own wall. Next: the Maelstrom. 27-29 run 1.8-2.1 tries: ease a notch later |
| 5 | The Maelstrom sails without its 4 destroyers: the Maelstrom and three Leviathan Mk IIs | 8.2/8.6/8.7/6.7/3.2/0.5 → 8.2/8.6/8.3/**7.8**/3.2/**1.9** (6.9 → **7.2**) | kept | Maelstrom 16% → 31% first try, 6.5 → 4.8 tries (still over 3.8). Act III's dip is Rail Line and Graviton Storm at 2.0-2.25 tries: the players look ahead to mission 30 when they spend, or noise; ease them a notch. Next: patrols, then the review's suggestions |
| 6 | Patrols grow their escorts, not their hull: each brings 20% more escorts than the last, from a screen of 8 destroyers and 2 light cruisers; the Maelstrom stays one ship (`grow_escorts` replaces `grow_fleet`) | 8.2/8.6/8.3/7.8/3.2/1.9 → 8.2/8.6/8.3/7.3/4.2/**7.3** (7.2 → **7.6**) | kept | Growing the hull with the super ship fixed put all of it on the escort: 2 → 16 → 32 → 52 destroyers for 1.2/1.44/1.73x the hull, a wall at Patrol 3. Probed out to Patrol 7 at 15%, 20% and 25% escort growth: 20% stays smooth for about six patrols. Patrols 1-3 now 84% first try, 23-33% lost. The 16% who fail every patrol never beat the Maelstrom (see below). Finales' dip is the Maelstrom's tries, 4.8 → 5.0, noise on an unchanged mission |
| 7 | Laser Cannons and Railguns need Rangefinders 1 instead of 2 (11 of 64 players stopped at Rangefinders 1, never got lasers, and were the whole late-game tail: 9-16% first try at 27-29, 0% at the Maelstrom and every patrol) | 8.1/8.7/7.7/6.7/3.5/6.1 → 8.1/8.3/7.6/3.9/3.5/7.3 (7.2 → 6.5, four seeds) | **reverted** | Lasers then arrive at mission 11 for everyone and flatten Act II and III: the Kraken 38% → 86% first try, the Tempest and the Gauntlet 100%. The gate is doing real work. The tail is the model not planning for prerequisites (a student sees "needs Rangefinders 2" in the shop): see Rubric concerns |
| 8 | Red's dockyards are no faster than yours: of the Red ships a lost battle sinks, half (rounded down, per squadron) stay sunk for the next try at that mission. Shown on the briefing and the Fleet page ("3 still sunk"); saved with the campaign; skirmishes unaffected. README's balancing section brought up to date | 8.1/8.7/7.7/6.7/3.5/6.1 → 8.1/8.7/**9.1**/**8.3**/3.2/**8.3** (7.2 → **8.1**, four seeds) | kept | Every try now wears Red down, so no mission is a permanent wall, for the modeled players who never reach lasers or a real student who is stuck. Maelstrom 5.3 → 3.9 tries, Rail Line 2.4 → 1.3, the Gauntlet 2.5 → 1.8, patrols ~2.4 → 1.4. Players who win sooner bank fewer workshops, so the Kraken's first try slipped (38% → 26%, 3.2 tries) and the Maelstrom is 14%: soften both next |

## Rubric concerns

* From the first review (seeds 3-4, after iteration 5): averages hide walls when the players
  split into groups (with and without lasers); a stuck-share measure would show it directly. Not
  added: mean tries already moves with the stuck share, and the bands stay as set. The review also
  found the README's balance numbers stale; brought up to date in iteration 8.

* The modeled player never buys an upgrade for what it unlocks, only for what it does now. 17% of
  modeled players stop at Rangefinders 1, so they never reach Laser Cannons, and they make up the
  whole late-game tail (they lose Rail Line, the Gauntlet, the Maelstrom and the patrols over and
  over). A real student sees the requirement on the Future Tech page. The tries numbers from
  mission 25 on are pessimistic for that reason; lowering the gate (iteration 7) broke Act II.

* Iteration 1 added a tries band to every mission (1.0-1.5 regular, 1.8 set pieces, 1.2 intro):
  stricter, not looser. It caught missions 15-17 at 76% first try but 2.0-2.5 average tries, a
  death spiral the first-try rate hides. The baseline scores the same with or without it (6.5).
* Probing a fleet from a snapshot taken before later missions changed overestimates the player:
  the modeled player spends with the next three missions in view, so harder missions ahead change
  what it buys now. Re-snapshot after changing the missions ahead of the one being probed.

* The modeled player judges purchases with a Lanchester estimate (damage x hull per stack), which
  favours deepening a stack it already has over starting a new class. Worse (found in iteration 2):
  each Red stack is scored against its *best* Blue target, so adding any softer stack (a cruiser
  beside battleships with a belt of 6) raises Red's estimated strength. At mission 20 a Light
  Cruiser scores below zero whatever it costs. So the choices criterion mostly measures the model,
  not the shipyard; it stays weighted 1 and is used as is. A fairer judge (each Red stack's fire
  split across the Blue stacks it can reach, as the AI's own danger estimate does) is for the user
  to decide on, since it changes the instrument.
* The fleet-lost bands were set from the baseline (setup, before iteration 1): Act I's corvette
  swarms lose much more hull per win than later fleets of big ships, whose damage that doesn't
  sink a ship costs nothing.
