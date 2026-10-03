"""Run battles without graphics (AI vs AI). Handy for testing and balancing."""

from __future__ import annotations

from typing import Callable, Optional

from .ai import Controller, SimpleAI
from .battle import Battle, Event

MAX_ACTIONS = 20_000


def run_battle(
    battle: Battle,
    controllers: Optional[tuple[Controller, Controller]] = None,
    on_event: Optional[Callable[[Event], None]] = None,
) -> Battle:
    """Play a battle to the end with the given controllers (default: SimpleAI for both)."""
    if controllers is None:
        controllers = (SimpleAI(), SimpleAI())
    events = battle.start()
    for _ in range(MAX_ACTIONS):
        if on_event:
            for e in events:
                on_event(e)
        if battle.over:
            return battle
        stack = battle.active
        assert stack is not None
        events = battle.apply(controllers[stack.side].choose_action(battle, stack))
    raise RuntimeError("battle did not finish; a controller is probably stuck")
