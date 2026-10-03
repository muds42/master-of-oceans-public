"""The README's numbers for the rules match the code, so a change to a rule can't leave the README behind.

Only the numbers that come straight from a constant are checked. When one of these fails,
change the README to match (or the constant back).
"""

from pathlib import Path

import pytest

from seabattle import boost
from seabattle.problems import LEVELS, STREAK_CAP, STREAK_STEP, TIER_PAY, WRONG_PENALTY, level_pay

README = " ".join((Path(__file__).parent.parent / "README.md").read_text(encoding="utf-8").split())


def pct(x: float) -> str:
    return f"{x:.0%}"


def times(x: float) -> str:
    return f"x{x:g}"


CLAIMS = [
    # Math Boost
    f"answer makes the hit {pct(boost.BOOST)} stronger (or Red's {pct(boost.BOOST)} weaker). A wrong one costs {pct(boost.PENALTY)}.",
    f"answer right and it does {pct(boost.BOOST)} more damage; answer wrong and it does {pct(boost.PENALTY)} less.",
    f"answer right and they take {pct(boost.BOOST)} less; answer wrong and they take {pct(boost.PENALTY)} more.",
    f"{boost.MAX_PER_SUPER_MISSION} come up instead of {boost.MAX_PER_BATTLE}.",
    *[f"| {lv + 1} | {pct(odds)} |" for lv, odds in enumerate(boost.LEVEL_ODDS)],
    # Workshop pay
    f"A few-step problem pays {times(TIER_PAY[2])} that base and a multi-step problem pays {times(TIER_PAY[3])},",
    f"about {times(round(level_pay(1), 2))} at level 1, {times(round(level_pay(3), 2))} at level 3 and "
    f"{times(round(level_pay(max(LEVELS)), 2))} at level 5.",
    f"+{pct(STREAK_STEP)} for each right answer in a row, up to +{pct(STREAK_STEP * STREAK_CAP)}.",
    f"Wrong answers cost {pct(WRONG_PENALTY)} of what the problem would have paid",
]


@pytest.mark.parametrize("claim", CLAIMS)
def test_the_readme_says_what_the_code_does(claim):
    assert claim in README, f"README.md should say: {claim!r}"
