"""The synthesised sound effects: they build, they aren't silent, and M's setting sticks."""

import array
import os

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
pygame = pytest.importorskip("pygame")

from seabattle.ui import sound  # noqa: E402


@pytest.fixture
def audio(tmp_path, monkeypatch):
    monkeypatch.setenv("SEABATTLE_SAVE_DIR", str(tmp_path))
    sound.pre_init()
    pygame.init()
    sound.init()
    yield tmp_path
    pygame.quit()


def test_every_effect_builds_and_can_be_heard(audio):
    if not sound._state["ready"]:
        pytest.skip("no audio device")
    for name in sound.EFFECTS:
        sound.play(name, 0.1)
        effect = sound._cache[name]
        assert 0.1 <= effect.get_length() <= 2.0, name
        pcm = array.array("h", effect.get_raw())
        assert max(abs(v) for v in pcm) > 10000, f"{name} is too quiet"
    assert sound.gun_sound(28) == "gun_big" and sound.gun_sound(6) == "gun" and sound.gun_sound(3) == "gun_small"


def test_mute_is_remembered(audio):
    assert not sound.muted()
    assert sound.toggle_mute() is True
    assert (audio / "settings.json").exists()
    sound.init()
    assert sound.muted()
    sound.play("gun")  # does nothing, quietly
    assert sound.toggle_mute() is False
    sound.init()
    assert not sound.muted()
