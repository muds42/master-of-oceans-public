"""Make a 22-second promotional video: ``python docs/promo.py`` writes docs/promo.mp4.

Like screenshots.py, this drives the real game off-screen (SDL's dummy video
driver) through seeded campaigns and battles, so every frame is the game as it
plays. It follows the game's loop (solve problems, spend what they earn, fight,
boost a hit, win) at 30 frames a second, adds numbered captions and crossfades, and mixes a soundtrack from the game's own synthesised sound effects
at the moments the game played them. Needs ffmpeg on the PATH.
"""

from __future__ import annotations

import array
import copy
import math
import os
import random
import subprocess
import sys
import tempfile
import wave
from pathlib import Path
from typing import Callable

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ["SEABATTLE_SAVE_DIR"] = tempfile.mkdtemp(prefix="seabattle-promo-")  # leave the real saves alone
DOCS = Path(__file__).resolve().parent
sys.path.insert(0, str(DOCS))
sys.path.insert(0, str(DOCS.parent))

import pygame  # noqa: E402

from screenshots import act_one, act_three, mission, workshop  # noqa: E402
from seabattle.ui import sound  # noqa: E402
from seabattle.ui import theme as T  # noqa: E402
from seabattle.ui.app import App  # noqa: E402
from seabattle.ui.draw import draw_ship  # noqa: E402
from seabattle.ui.menu_scene import _Backdrop  # noqa: E402

FPS = 30
DT = 1 / FPS
W, H = T.WINDOW
AUDIO_RATE = 44100
XFADE = 10 # frames of crossfade between scenes
OUT = DOCS / "promo.mp4"


class Recorder:
    """Frames go straight to ffmpeg; the sounds the game plays are noted with their time."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.video = path.with_suffix(".video.mp4")
        self.ffmpeg = subprocess.Popen(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
             "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "20",
             "-pix_fmt", "yuv420p", str(self.video)],
            stdin=subprocess.PIPE)
        self.frames = 0
        self.sounds: list[tuple[float, str, float]] = []
        self.listening = False
        self.last: pygame.Surface | None = None  # the previous scene's last frame, to fade from
        self.fade_in = 0
        self.caption = ("", 0, 0)
        real_play = sound.play

        def play(name: str, volume: float = 1.0) -> None:
            if self.listening and name in sound.EFFECTS:
                self.sounds.append((self.frames / FPS, name, volume))
            real_play(name, volume)

        sound.play = play

    @property
    def time(self) -> float:
        return self.frames / FPS

    def scene(self, caption: str = "", step: int = 0) -> None:
        """A new scene starts: crossfade into it from the last frame, under a new caption
        (numbered with the step of the game's loop it shows)."""
        self.fade_in = XFADE if self.last is not None else 0
        self.caption = (caption, step, self.frames)
        self.listening = True

    def frame(self, surf: pygame.Surface) -> None:
        out = surf.copy()
        caption, step, start = self.caption
        if caption:
            draw_caption(out, caption, step, (self.frames - start) / FPS)
        if self.fade_in > 0 and self.last is not None:
            old = self.last.copy()
            old.set_alpha(round(255 * self.fade_in / (XFADE + 1)))
            out.blit(old, (0, 0))
            self.fade_in -= 1
        self.last = out
        self.ffmpeg.stdin.write(pygame.image.tobytes(out, "RGB"))
        self.frames += 1

    def finish(self) -> None:
        self.listening = False
        self.ffmpeg.stdin.close()
        self.ffmpeg.wait()
        track = self.path.with_suffix(".wav")
        write_soundtrack(track, self.sounds, self.time)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(self.video), "-i", str(track),
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart",
                        str(self.path)], check=True)
        self.video.unlink()
        track.unlink()
        print(f"docs/{self.path.name}: {self.time:.1f} s, {self.frames} frames, {len(self.sounds)} sounds")


def draw_caption(surf: pygame.Surface, caption: str, step: int, age: float) -> None:
    """A gold-edged pill at the bottom of the screen that rises into place, with the step's
    number in a gold disc at its left."""
    rise = 1 - (1 - min(1.0, age / 0.3)) ** 3
    img = T.render_math(caption, 34, T.TEXT, bold=True)
    disc = img.get_height() + 6 if step else 0
    box = img.get_rect().inflate(48 + (disc + 12 if step else 0), 26)
    box.midbottom = (W // 2, H - 26 + round((1 - rise) * 90))
    shade = pygame.Surface(box.size, pygame.SRCALPHA)
    pygame.draw.rect(shade, (6, 12, 20, 225), shade.get_rect(), border_radius=box.height // 2)
    surf.blit(shade, box)
    pygame.draw.rect(surf, T.ACCENT, box, 2, border_radius=box.height // 2)
    if step:
        centre = (box.x + 12 + disc // 2, box.centery)
        pygame.draw.circle(surf, T.ACCENT, centre, disc // 2)
        num = T.render_math(str(step), 28, T.BG, bold=True)
        surf.blit(num, num.get_rect(center=centre))
    surf.blit(img, img.get_rect(midleft=(box.x + 24 + (disc + 12 if step else 0), box.centery)))


def write_soundtrack(path: Path, sounds: list[tuple[float, str, float]], seconds: float) -> None:
    """The game's effects where it played them, over a low swell of strings."""
    sound.RATE = AUDIO_RATE  # the effects are built at whatever rate the module says
    n = int(seconds * AUDIO_RATE)
    mix = [0.0] * n
    for i in range(n):  # an A-minor pad that swells in and out, and a soft drum every beat
        t = i / AUDIO_RATE
        env = min(1.0, t / 1.5) * min(1.0, (seconds - t) / 1.2)
        chord = sum(math.sin(math.tau * f * t + k) for k, f in enumerate((110.0, 130.8, 164.8, 220.0)))
        beat = (t * 2.0) % 1.0  # 120 bpm
        drum = math.sin(math.tau * 55 * beat / 2.0) * math.exp(-beat * 9) if t > 2.0 else 0.0
        mix[i] = env * (0.035 * chord + 0.12 * drum)
    built: dict[str, list[float]] = {}
    for at, name, volume in sounds:
        if name not in built:
            samples = sound.EFFECTS[name]()
            peak = max(1e-9, max(abs(s) for s in samples))
            built[name] = [s * 0.9 / max(1.0, peak) for s in samples]
        start = int(at * AUDIO_RATE)
        for j, s in enumerate(built[name][: max(0, n - start)]):
            mix[start + j] += volume * 0.8 * s
    peak = max(1.0, max(abs(s) for s in mix))
    pcm = array.array("h", (int(32767 * 0.95 * s / peak) for s in mix))
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(AUDIO_RATE)
        w.writeframes(pcm.tobytes())


# --------------------------------------------------------------------------- the scenes


def record(rec: Recorder, app: App, seconds: float, each: Callable[[int], None] = lambda i: None) -> None:
    for i in range(round(seconds * FPS)):
        each(i)
        app.frame(DT, [])
        rec.frame(app.screen)


def preroll(app: App, done: Callable[[], bool], limit: float = 600) -> None:
    """Play on without recording until something worth showing is about to happen."""
    t = 0.0
    while not done():
        app.frame(DT, [])
        t += DT
        if t > limit:
            raise RuntimeError("the battle never got there")


def title_card(rec: Recorder, seconds: float, subtitle: str, tagline: str, fanfare: str) -> None:
    """The title screen's ocean and squadron, our own words, and the two fleets passing below."""
    back = _Backdrop()
    back.time = 4.0
    surf = pygame.Surface(T.WINDOW)
    for i in range(round(seconds * FPS)):
        age = i / FPS
        back.update(DT)
        back.draw_backdrop(surf, "MASTER OF OCEANS", subtitle)
        img = T.render_math(tagline, 30, T.ACCENT, bold=True)
        img.set_alpha(round(255 * min(1.0, max(0.0, (age - 0.3) / 0.4))))
        surf.blit(img, img.get_rect(midtop=(W // 2, 222)))
        for side, y, hulls in ((0, 420, ("destroyer", "battleship", "cruiser")), (1, 570, ("cruiser", "battleship", "destroyer"))):
            for k, hull in enumerate(hulls):
                gap = 330 * k + 60 * age
                x = W / 2 - 330 + gap if side == 0 else W / 2 + 330 - gap
                bob = math.sin(back.time * 1.3 + k + side) * 2
                heading = 1 if side == 0 else -1
                for n in range(6):  # a foam wake astern
                    wx = x - heading * (70 + n * 16)
                    pygame.draw.ellipse(surf, T.FOAM, (wx - 9 + n, y + bob - 6 + n, 18 - 2 * n, 12 - 2 * n), 1)
                draw_ship(surf, (x, y + bob), hull, side, 0.0 if side == 0 else math.pi, 255, 1.9)
        if i == 0:
            sound.play(fanfare, 0.7)
        rec.frame(surf)


def math_station(rec: Recorder, app: App, seconds: float) -> None:
    """The workshop: two problems solved, and the steel, powder and fuel they bring."""
    for seed in range(200):
        ws = workshop(app, act_one(), "broadside", seed)
        p = ws.posed
        if p.problem.fig and p.topic.id == "triangles" and p.tier == 2 and len(p.problem.solution) <= 4:
            break
    rec.scene("Solve math problems to earn resources", 1)
    answers = (round(1.0 * FPS), round(3.0 * FPS))  # the next problem comes up 1.6 s after a right answer
    record(rec, app, seconds, lambda i: ws.answer(ws.posed.answer) if i in answers else None)


def upgrades(rec: Recorder, app: App, seconds: float) -> None:
    """The Upgrades tab: what the problems earned goes on bigger warheads and armor."""
    ws = workshop(app, act_one())
    ws.tab = "upgrades"
    rec.scene("Spend them on upgrades and new ships", 2)
    buys = {round(0.9 * FPS): "warheads", round(2.1 * FPS): "armor"}
    record(rec, app, seconds, lambda i: ws.buy_upgrade(buys[i]) if i in buys else None)


def battle(rec: Recorder, app: App, seconds: float) -> None:
    """Act III with the computer playing both fleets: cut in as the first shots are fired."""
    c = act_three()
    c.boost = False
    scene = mission(app, c)
    scene.toggle_fleet_auto()
    scene.speed = 2
    shooting = lambda: type(scene.current).__name__ in ("GunAnim", "SalvoLaunchAnim")  # noqa: E731
    preroll(app, shooting)
    rec.scene("Command your fleet against Red", 3)
    record(rec, app, seconds)


def math_boost(rec: Recorder, app: App, seconds: float) -> None:
    """A big hit freezes, the MATH BOOST box comes up, the problem is solved, and the hit lands harder."""
    scene = mission(app, act_three())
    scene.toggle_fleet_auto()
    scene.speed = 3
    preroll(app, lambda: scene.box_open and scene.chance.hit.offense)
    # roll a word problem with a sketch, like the README's shot
    for seed in range(1000):
        trial = copy.deepcopy(scene.boost)
        trial.rng = random.Random(seed)
        if (p := trial.pose()).fig and p.words:
            break
    scene.boost.rng = random.Random(seed)
    rec.scene("MATH BOOST: answer right, hit 30% harder", 4)
    scene.speed = 1

    def step(i: int) -> None:
        if i == round(1.0 * FPS):
            scene.take_boost()
        elif i == round(2.4 * FPS):
            scene.answer_boost(scene.prompt.problem.answer)
        elif i == round(3.2 * FPS):
            scene.continue_battle()

    record(rec, app, seconds, step)


def victory(rec: Recorder, app: App, seconds: float) -> None:
    """Act I to the end: the last of Red goes down, and the victory screen with its debrief."""
    scene = mission(app, act_one())
    scene.toggle_fleet_auto()
    scene.speed = 3
    preroll(app, lambda: scene.battle.over and len(scene.anims) <= 1, limit=1200)
    rec.scene("Win, learn from the debrief, and sail on", 5)
    record(rec, app, seconds)


def main() -> int:
    app = App(window_flags=0)
    rec = Recorder(OUT)
    rec.scene()
    title_card(rec, 2.6, "Naval tactics in the spirit of Master of Orion (1993)", "Blue fleet vs. Red fleet", "horn")
    math_station(rec, app, 3.6)
    upgrades(rec, app, 3.0)
    battle(rec, app, 3.8)
    math_boost(rec, app, 4.0)
    victory(rec, app, 2.2)
    rec.scene()
    title_card(rec, 2.6, "Play it:  python -m seabattle", "Build your fleet.  Sharpen your math.  Rule the seas.", "horn")
    rec.finish()
    pygame.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
