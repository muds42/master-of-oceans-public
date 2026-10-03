"""Command-line entry point: ``python -m seabattle``."""

from __future__ import annotations

import argparse
import collections
import random
import sys
import traceback
from datetime import datetime

from .scenarios import SCENARIOS


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m seabattle", description="Master of Oceans: naval tactical battles.")
    parser.add_argument("--scenario", choices=sorted(SCENARIOS), help="skip the menu and start this battle")
    parser.add_argument("--seed", type=int, help="battle seed (map and dice); random if omitted")
    parser.add_argument("--headless", action="store_true", help="no window: computer vs computer, print the battle log")
    parser.add_argument("--runs", type=int, default=1, help="with --headless: play many battles and print win rates")
    parser.add_argument("--list", action="store_true", help="list scenarios and exit")
    args = parser.parse_args(argv)

    if args.list:
        for sc in SCENARIOS.values():
            print(f"{sc.id:12} {sc.name}: {sc.description}")
        return 0

    seed = args.seed if args.seed is not None else random.randrange(100_000)
    if args.headless:
        return _headless(args.scenario or "skirmish", seed, args.runs)

    if sys.stderr is None:
        # No console (pythonw, which "Play Master of Oceans.bat" uses), so an error would vanish without a trace.
        try:
            return _play(args.scenario, seed)
        except Exception:
            return _crashed(traceback.format_exc())
    return _play(args.scenario, seed)


def _play(scenario_id: str | None, seed: int) -> int:
    try:
        from .ui.app import App
    except ImportError as exc:  # pragma: no cover - depends on the local install
        _tell(f"Could not start the game window ({exc}). Install it with: pip install -r requirements.txt")
        return 1
    app = App()
    if scenario_id:
        app.start_battle(scenario_id, seed)
    app.run()
    return 0


CRASH_LOG_KEEP = 100_000  # characters of earlier crashes kept in crash.log


def _crashed(details: str) -> int:
    """Add the error to crash.log in the save folder and say where, when there is no console to print it to."""
    from .campaign import save_dir

    message = "Master of Oceans stopped because of an error."
    try:
        log = save_dir() / "crash.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        try:
            earlier = log.read_text(encoding="utf-8", errors="replace")[-CRASH_LOG_KEEP:]
        except OSError:
            earlier = ""
        entry = f"{datetime.now():%Y-%m-%d %H:%M:%S}\n{details}"
        log.write_text(f"{earlier}\n{entry}" if earlier else entry, encoding="utf-8")
        message += f"\n\nThe details are in {log}"
    except OSError:
        message += f"\n\n{details}"
    pygame = sys.modules.get("pygame")
    if pygame is not None:
        pygame.quit()  # close the frozen game window before the message box
    _tell(message)
    return 1


def _tell(message: str) -> None:
    """Print a message, or show it in a message box on Windows when there is no console."""
    if sys.stdout is not None:
        print(message)
    elif sys.platform == "win32":
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, message, "Master of Oceans", 0x10)  # 0x10: error icon


def _headless(scenario_id: str, seed: int, runs: int) -> int:
    from .headless import run_battle

    scenario = SCENARIOS[scenario_id]
    if runs <= 1:
        from .debrief import debrief

        battle = scenario.build(seed)
        print(f"{scenario.name}, seed {seed}")
        run_battle(battle, on_event=lambda e: e.text and print(e.text))
        d = debrief(battle)
        print(f"\nDebrief for {battle.side_names[0]}:")
        for line, verdict in d.odds():
            print(f"  {line} {verdict}")
        for lesson in d.lessons:
            print(f"  * {lesson}")
        return 0
    results: collections.Counter = collections.Counter()
    rounds = 0
    for i in range(runs):
        battle = run_battle(scenario.build(seed + i))
        results[battle.winner] += 1
        rounds += battle.round
    names = scenario.build(seed).side_names
    print(f"{scenario.name}: {runs} battles, seeds {seed}..{seed + runs - 1}")
    for side in (0, 1):
        print(f"  {names[side]} wins: {results[side]} ({results[side] / runs:.0%})")
    print(f"  Draws: {results[None]} ({results[None] / runs:.0%})")
    print(f"  Average length: {rounds / runs:.1f} rounds")
    return 0


if __name__ == "__main__":
    sys.exit(main())
