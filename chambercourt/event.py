# © Reuben Thomas <rrt@sc3d.org> 2024
# Released under the GPL version 3, or (at your option) any later version.

import os
import sys
import warnings
from typing import NoReturn


# Import pygame, suppressing extra messages that it prints on startup.
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import pygame


def quit_game() -> NoReturn:
    pygame.quit()
    sys.exit()


def handle_quit_event() -> None:
    if len(pygame.event.get(pygame.QUIT)) > 0:
        quit_game()


def handle_global_keys(event: pygame.event.Event) -> None:
    if event.key == pygame.K_F11:
        pygame.display.toggle_fullscreen()
