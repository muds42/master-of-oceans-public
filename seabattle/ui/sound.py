"""Sound effects, synthesised when first played so the game needs no audio files.

Each effect is a little shaped noise (gunfire, splashes, explosions) or a few
tones (chimes for right and wrong answers, a fanfare), built with the standard
library. If there is no audio device, every call quietly does nothing.

M toggles sound on and off anywhere in the game; the choice is saved in
``settings.json`` next to the save files.
"""

from __future__ import annotations

import array
import json
import math
import random
from typing import Callable

import pygame

from ..campaign import save_dir

RATE = 22050  # samples per second; set to the device's own rate when it opens
_state = {"ready": False, "muted": False, "channels": 1}
_cache: dict[str, pygame.mixer.Sound] = {}


def pre_init() -> None:
    """Ask for small, mono buffers; call before ``pygame.init()``."""
    try:
        pygame.mixer.pre_init(RATE, -16, 1, 512)
    except pygame.error:
        pass


def init() -> None:
    """Open the audio device if there is one, and load the mute setting."""
    global RATE
    _state["muted"] = bool(_settings().get("muted", False))
    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        rate, size, channels = pygame.mixer.get_init()
    except (pygame.error, TypeError):
        _state["ready"] = False
        return
    RATE = rate
    _state.update(ready=abs(size) == 16, channels=channels)
    pygame.mixer.set_num_channels(16)
    _cache.clear()


def muted() -> bool:
    return _state["muted"]


def toggle_mute() -> bool:
    """Switch sound off or on and remember it. Returns True if sound is now off."""
    _state["muted"] = not _state["muted"]
    settings = _settings()
    settings["muted"] = _state["muted"]
    try:
        path = save_dir() / "settings.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    except OSError:
        pass
    if _state["muted"] and _state["ready"]:
        pygame.mixer.stop()
    return _state["muted"]


def play(name: str, volume: float = 1.0) -> None:
    if _state["muted"] or not _state["ready"] or name not in EFFECTS:
        return
    sound = _cache.get(name)
    if sound is None:
        sound = _cache[name] = _make(EFFECTS[name]())
    sound.set_volume(max(0.0, min(1.0, volume)))
    sound.play()


def _settings() -> dict:
    try:
        data = json.loads((save_dir() / "settings.json").read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _make(samples: list[float]) -> pygame.mixer.Sound:
    """16-bit samples for the mixer, in however many channels it opened with."""
    peak = max(1e-9, max(abs(s) for s in samples))
    scale = 32767 * 0.9 / max(1.0, peak)
    pcm = array.array("h", (int(s * scale) for s in samples for _ in range(_state["channels"])))
    return pygame.mixer.Sound(buffer=pcm.tobytes())


# --------------------------------------------------------------------------- building blocks


def _n(seconds: float) -> int:
    return int(RATE * seconds)


def _noise(seconds: float, smooth: float, decay: float, seed: int, attack: float = 0.003) -> list[float]:
    """Random noise through a one-pole low-pass (smaller ``smooth`` = deeper), fading out."""
    rng = random.Random(seed)
    out, y = [], 0.0
    for i in range(_n(seconds)):
        t = i / RATE
        y += smooth * (rng.uniform(-1, 1) - y)
        out.append(y * min(1.0, t / attack) * math.exp(-t / decay))
    return out


def _tone(freq: float, seconds: float, decay: float, shape: Callable[[float], float] = math.sin,
          attack: float = 0.005, slide: float = 0.0) -> list[float]:
    """A note: ``shape`` is the waveform, ``slide`` bends the pitch (octaves over the note)."""
    out, phase = [], 0.0
    for i in range(_n(seconds)):
        t = i / RATE
        f = freq * 2 ** (slide * t / seconds)
        phase += math.tau * f / RATE
        out.append(shape(phase) * min(1.0, t / attack) * math.exp(-t / decay))
    return out


def _mix(*parts: tuple[float, float, list[float]]) -> list[float]:
    """Mix (start seconds, gain, samples) parts."""
    length = max(_n(start) + len(s) for start, _, s in parts)
    out = [0.0] * length
    for start, gain, s in parts:
        o = _n(start)
        for i, v in enumerate(s):
            out[o + i] += gain * v
    return out


def _square(phase: float) -> float:
    return 0.6 if math.sin(phase) >= 0 else -0.6


def _saw(phase: float) -> float:
    return ((phase / math.tau) % 1.0) * 2 - 1


def _notes(freqs: list[float], step: float, length: float, decay: float, gain: float = 1.0) -> list[float]:
    return _mix(*[(i * step, gain, _mix((0, 1.0, _tone(f, length, decay)), (0, 0.25, _tone(2 * f, length, decay / 2))))
                  for i, f in enumerate(freqs)])


# --------------------------------------------------------------------------- the effects

EFFECTS: dict[str, Callable[[], list[float]]] = {
    # battle
    "gun_big": lambda: _mix((0, 1.0, _noise(0.7, 0.05, 0.18, 1)), (0, 0.8, _tone(55, 0.5, 0.15, slide=-0.5))),
    "gun": lambda: _mix((0, 0.9, _noise(0.35, 0.12, 0.08, 2)), (0, 0.5, _tone(90, 0.25, 0.07, slide=-0.6))),
    "gun_small": lambda: _noise(0.15, 0.45, 0.035, 3),
    "splash": lambda: _noise(0.5, 0.25, 0.14, 4, attack=0.04),
    "launch": lambda: _mix((0, 0.7, _noise(0.45, 0.2, 0.12, 5, attack=0.03)), (0, 0.5, _tone(70, 0.3, 0.1))),
    "missile": lambda: _mix((0, 0.8, _noise(0.8, 0.3, 0.35, 6, attack=0.08)),
                            (0, 0.25, _tone(300, 0.8, 0.4, _saw, attack=0.08, slide=0.6))),
    "laser": lambda: _mix((0, 0.8, _tone(1800, 0.3, 0.1, _saw, slide=-1.6)), (0, 0.5, _tone(900, 0.3, 0.1, _square, slide=-1.2))),
    "explosion": lambda: _mix((0, 1.0, _noise(1.0, 0.06, 0.3, 7)), (0.02, 0.6, _noise(0.6, 0.3, 0.1, 8)),
                              (0, 0.7, _tone(45, 0.8, 0.3, slide=-0.4))),
    "sink": lambda: _mix((0, 0.9, _noise(1.4, 0.03, 0.6, 9, attack=0.1)), (0.1, 0.4, _tone(90, 1.2, 0.6, _saw, slide=-1.0))),
    "victory": lambda: _notes([523.3, 659.3, 784.0, 1046.5], 0.14, 0.5, 0.25),
    "defeat": lambda: _notes([392.0, 311.1, 261.6], 0.22, 0.6, 0.3),
    "boost": lambda: _notes([784.0, 1046.5, 1568.0], 0.07, 0.4, 0.14, 0.7),  # a MATH BOOST box comes up
    # workshop
    "right": lambda: _notes([659.3, 987.8], 0.09, 0.3, 0.12, 0.8),
    "wrong": lambda: _tone(160, 0.3, 0.15, _square, slide=-0.4),
    "buy": lambda: _notes([1318.5, 1760.0], 0.06, 0.2, 0.06, 0.6),
    "error": lambda: _tone(120, 0.15, 0.06, _square),
    "horn": lambda: _mix((0, 0.6, _tone(110, 1.0, 0.8, _saw, attack=0.08)), (0, 0.4, _tone(165, 1.0, 0.8, _saw, attack=0.08))),
}


def gun_sound(max_damage: int) -> str:
    """Big guns boom, small ones crack."""
    return "gun_big" if max_damage >= 15 else "gun" if max_damage >= 5 else "gun_small"

