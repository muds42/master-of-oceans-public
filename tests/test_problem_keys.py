"""Saves keep reviews and Logbook results under generator keys, so a key must never just disappear."""

from pathlib import Path

from seabattle import campaign as cm
from seabattle import problems
from seabattle.problems import SCHOOLS, generator_named

KNOWN = Path(__file__).with_name("generator_keys.txt")


def known_keys() -> list[str]:
    return [line.strip() for line in KNOWN.read_text(encoding="utf-8").splitlines() if line.strip() and not line.startswith("#")]


def test_every_key_a_save_may_hold_still_finds_its_generator():
    """Renamed a generator? Add old key -> new key to problems.RENAMED, so players keep its results."""
    lost = [k for k in known_keys() if generator_named(k) is None]
    assert not lost, f"saves hold these keys, but no generator has them now (list them in problems.RENAMED): {lost}"


def test_every_generator_is_on_the_list():
    """A new generator's key goes on the list, so a later rename is caught."""
    current = {g.key for s in SCHOOLS.values() for g in s.generators}
    missing = sorted(current - set(known_keys()))
    assert not missing, f"add these to {KNOWN.name}: {missing}"


def test_a_renamed_generator_keeps_its_results(monkeypatch, tmp_path):
    monkeypatch.setenv("SEABATTLE_SAVE_DIR", str(tmp_path))
    monkeypatch.setitem(problems.RENAMED, "tri.old_name", "tri.pythagorean_leg")
    data = cm.Campaign(slot=1).to_dict()
    data["skills"] = {"tri.old_name": "1101", "tri.gone": "1"}
    data["review"] = {"tri.old_name": 1}
    c = cm.Campaign.from_dict(data)
    assert c.skills == {"tri.pythagorean_leg": "1101"} and c.review == {"tri.pythagorean_leg": 1}
