"""Window, main loop and scene switching."""

from __future__ import annotations

from typing import Optional

import pygame

from .. import campaign as campaign_mod
from ..scenarios import SCENARIOS
from . import sound
from . import theme as T
from .battle_scene import BattleScene
from .menu_scene import QuickBattleScene, SlotScene, TitleScene
from .workshop_scene import WorkshopScene


class App:
    def __init__(self, window_flags: Optional[int] = None) -> None:
        sound.pre_init()
        pygame.init()
        sound.init()
        T.reset()
        flags = pygame.SCALED | pygame.RESIZABLE if window_flags is None else window_flags
        pygame.display.set_icon(pygame.image.load(T.ICON))  # before set_mode, which some systems need
        self.screen = pygame.display.set_mode(T.WINDOW, flags)
        pygame.display.set_caption("Master of Oceans")
        self.clock = pygame.time.Clock()
        self.running = True
        self.settings = {"scenario": "skirmish", "school": "algebra"}
        self.notice = ("", 0.0)  # short message drawn over any scene, e.g. "Sound off"
        try:  # saves used to live in the game folder
            self.moved_saves = campaign_mod.move_old_saves()
        except OSError:
            self.moved_saves = []
        self.scene = TitleScene(self)

    # ---- navigation ---------------------------------------------------------------

    def to_title(self) -> None:
        self.scene = TitleScene(self)

    to_menu = to_title

    def to_quick_battle(self) -> None:
        self.scene = QuickBattleScene(self)

    def to_slots(self) -> None:
        self.scene = SlotScene(self)

    def start_battle(self, scenario_id: str, seed: int) -> None:
        """A quick battle with a preset scenario; the player is always Blue."""
        self.settings["scenario"] = scenario_id
        self.scene = BattleScene(self, SCENARIOS[scenario_id].build(seed), scenario_id=scenario_id)

    def open_workshop(self, campaign) -> None:
        self.scene = WorkshopScene(self, campaign)

    def start_mission(self, campaign, skirmish: Optional[int] = None) -> None:
        """The campaign's next mission, or a skirmish replay of mission ``skirmish``."""
        self.scene = BattleScene(self, campaign.build_battle(skirmish), campaign=campaign, skirmish=skirmish)

    # ---- loop ---------------------------------------------------------------------

    def frame(self, dt: float, events: list[pygame.event.Event]) -> None:
        for event in events:
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_m:
                self.notice = ("Sound off  (M to turn it on)" if sound.toggle_mute() else "Sound on", 1.6)
            else:
                self.scene.handle(event)
        self.scene.update(dt)
        self.scene.draw(self.screen)
        message, left = self.notice
        if left > 0:
            self.notice = (message, left - dt)
            img = T.render(message, 22, T.TEXT)
            box = img.get_rect(midtop=(T.WINDOW[0] // 2, 8)).inflate(24, 12)
            pygame.draw.rect(self.screen, (8, 14, 22), box, border_radius=8)
            pygame.draw.rect(self.screen, T.ACCENT, box, 1, border_radius=8)
            self.screen.blit(img, img.get_rect(center=box.center))

    def run(self) -> None:
        while self.running:
            dt = min(0.05, self.clock.tick(60) / 1000)
            self.frame(dt, pygame.event.get())
            pygame.display.flip()
        pygame.quit()
