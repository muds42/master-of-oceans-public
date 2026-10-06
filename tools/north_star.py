"""Score the campaign against the rubric in NORTH_STAR.md.

    python tools/north_star.py                 # run the modeled player (seeds 1 and 2) and score it
    python tools/north_star.py --reuse DIR     # score the balance_s*.json files already in DIR

It runs ``python -m seabattle.balance --json`` once per seed (about two minutes each on four cores),
pools every modeled player, and prints each mission's numbers and the rubric's scores (0-10).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from seabattle import campaign as cm  # noqa: E402
from seabattle.economy import RETROFITS, SHIP_CLASSES, TRACKS  # noqa: E402

LAST = cm.MISSION_COUNT + 3  # the scripted campaign and the first three patrols
INTRO = (1, 2, 3)  # tutorial missions: walkovers are fine
SET_PIECES = (9, 13, 16, 26, 29)  # one big ship (or two) and little else: meant to be a step harder
SUPER = (10, 20, 30)
PATROLS = tuple(range(cm.MISSION_COUNT + 1, LAST + 1))

# (first-try band, fleet-lost band), in percent. The README aims at about 85% first-try wins for most
# missions and about 75% for the set pieces.
BANDS = {
    "intro": ((85, 100), (0, 35)),
    "regular": ((78, 95), (8, 50)),
    "set_piece": ((62, 88), (12, 60)),
    "patrol": ((50, 90), (12, 60)),
}
PATROL_TRIES = (1.0, 1.8)
SUPER_FIRST = {10: (30, 50), 20: (30, 50), 30: (20, 45)}
SUPER_TRIES = {10: (1.8, 3.0), 20: (1.8, 3.0), 30: (2.2, 3.8)}
PCT_PER_POINT = 2.0  # a mission loses a point for every 2 percentage points outside a band...
TRIES_PER_POINT = 0.15  # ...and for every 0.15 tries outside one
WEIGHTS = {"act1": 2, "act2": 2, "act3": 3, "finales": 3, "choices": 1, "endgame": 1}


def outside(value: float, band: tuple[float, float]) -> float:
    lo, hi = band
    return max(lo - value, value - hi, 0.0)


def clamp10(x: float) -> float:
    return max(0.0, min(10.0, x))


def kind(n: int) -> str:
    if n in INTRO:
        return "intro"
    if n in SET_PIECES:
        return "set_piece"
    if n in PATROLS:
        return "patrol"
    return "regular"


def mission_score(n: int, first: float, tries: float, lost: float) -> float:
    """0-10 for one mission, as good as its worst part. ``first`` and ``lost`` in percent."""
    if n in SUPER:
        return min(clamp10(10 - outside(first, SUPER_FIRST[n]) / PCT_PER_POINT),
                   clamp10(10 - outside(tries, SUPER_TRIES[n]) / TRIES_PER_POINT))
    first_band, lost_band = BANDS[kind(n)]
    parts = [clamp10(10 - outside(first, first_band) / PCT_PER_POINT), clamp10(10 - outside(lost, lost_band) / PCT_PER_POINT)]
    if n in PATROLS:
        parts.append(clamp10(10 - outside(tries, PATROL_TRIES) / TRIES_PER_POINT))
    return min(parts)


def run(seeds: list[int], out: Path, players: int) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for seed in seeds:
        cmd = [sys.executable, "-m", "seabattle.balance", "--seed", str(seed), "--last", str(LAST),
               "--players", str(players), "--json", str(out / f"balance_s{seed}.json")]
        print(" ".join(cmd[1:]), flush=True)
        subprocess.run(cmd, cwd=ROOT, check=True, stdout=subprocess.DEVNULL)


def load(out: Path) -> list[dict]:
    players = []
    for path in sorted(out.glob("balance_s*.json")):
        players += json.loads(path.read_text())["players"]
    return players


def mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else float("nan")


def choices(players: list[dict]) -> tuple[float, list[str], dict[str, float]]:
    """How many of the things on sale see use, and how much of each currency gets spent.
    Returns (score, options nobody much buys, share of each currency left unspent)."""
    options = list(TRACKS) + list(SHIP_CLASSES) + list(RETROFITS)

    def bought(p: dict, option: str) -> bool:
        if option in RETROFITS:
            return any(k.endswith("/" + option) for k in p["bought"])
        return p["bought"].get(option, 0) > 0

    share = {o: mean([bought(p, o) for p in players]) for o in options}
    unused = [o for o, s in share.items() if s < 0.25]
    usage = 1 - len(unused) / len(options)
    left = {}
    for cur in ("steel", "powder", "fuel", "blueprints", "plasma"):
        earned = sum(p["earned"].get(cur, 0) for p in players)
        if earned:
            left[cur] = sum(p["bank"].get(cur, 0) for p in players) / earned
    hoard = max(left.values(), default=0)
    score = 10 * (0.5 * usage + 0.5 * clamp10(10 - max(0.0, hoard - 0.05) * 50) / 10)
    return score, unused, left


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seeds", type=int, nargs="+", default=[1, 2])
    parser.add_argument("--players", type=int, default=16)
    parser.add_argument("--out", type=Path, default=ROOT / ".north_star")
    parser.add_argument("--reuse", type=Path, help="score the JSON files already in this folder")
    args = parser.parse_args(argv)
    out = args.reuse or args.out
    if not args.reuse:
        run(args.seeds, out, args.players)
    players = load(out)
    print(f"{len(players)} modeled players")
    print(f"  #  {'Mission':24} {'kind':9} first  tries  lost  score")
    scores: dict[int, float] = {}
    for n in range(1, LAST + 1):
        rows = [p for p in players if str(n) in p["first"]]
        if not rows:
            continue
        first = 100 * mean([p["first"][str(n)] for p in rows])
        tries = mean([p["tries"][str(n)] for p in rows])
        lost = 100 * mean([p["losses"][str(n)] for p in rows])
        scores[n] = mission_score(n, first, tries, lost)
        k = "SUPER" if n in SUPER else kind(n)
        print(f"{n:3}  {cm.mission(n).name:24} {k:9} {first:4.0f}% {tries:5.2f} {lost:4.0f}%  {scores[n]:4.1f}")

    def crit(ns) -> float:
        return mean([scores[n] for n in ns if n in scores])

    choice, unused, left = choices(players)
    rubric = {
        "act1": crit(range(1, 10)),
        "act2": crit(range(11, 20)),
        "act3": crit(range(21, 30)),
        "finales": crit(SUPER),
        "choices": choice,
        "endgame": crit(PATROLS),
    }
    print("\nOptions under 25% of players buy:", ", ".join(unused) or "none")
    print("Currency left unspent (share of earned):", ", ".join(f"{k} {v:.0%}" for k, v in left.items()))
    print("\nRubric")
    for k, v in rubric.items():
        print(f"  {k:8} {v:4.1f}  (weight {WEIGHTS[k]})")
    total = sum(WEIGHTS[k] * v for k, v in rubric.items()) / sum(WEIGHTS.values())
    print(f"  weighted {total:4.1f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
