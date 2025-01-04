"""
ChamberCourt: Screen class.

© Reuben Thomas <rrt@sc3d.org> 2024
Released under the GPL version 3, or (at your option) any later version.
"""

import os
import warnings
from typing import Any, Tuple

# Import pygame, suppressing extra messages that it prints on startup.
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import pygame

    from . import ptext


class Screen:
    """
    The `Screen` class deals with managing the main window, blitting the
    game window to it, and printing text.
    """
    def __init__(
        self, screen_size: Tuple[int, int], fontname: str, window_scale: int = 1
    ) -> None:
        self.window_scale = window_scale
        self.text_colour = (255, 255, 255)
        self.background_colour = (0, 0, 255)
        self.font_pixels = 8 * self.window_scale
        self.surface = pygame.display.set_mode(screen_size, pygame.SCALED)
        self.reinit_screen()
        self.fontname = fontname
        # Force ptext to cache the font
        self.print_screen((0, 0), "")

    def reinit_screen(self) -> None:
        """
        Reinitialise the screen.

        Used when transitioning between instructions and main game screens.
        """
        self.surface.fill(self.background_colour)

    def flash_background(self) -> None:
        """
        Set the background colour to be lighter. In combination with
        `Screen.fade_background()`, this causes the screen to flash,
        indicating that some action such as saving the player’s position has
        been accomplished.
        """
        self.background_colour = (160, 160, 255)

    def fade_background(self) -> None:
        """
        Called every frame to return the background colour to the default
        over a period of several frames.
        """
        self.background_colour = (
            max(self.background_colour[0] - 10, 0),
            max(self.background_colour[0] - 10, 0),
            255,
        )

    def scale_surface(self, surface: pygame.Surface) -> pygame.Surface:
        """
        A utility method that scales the given surface by `self.window_scale`.

        :param surface: surface to scale
        :type surface: pygame.Surface
        :return: a new surface, that is `surface` scaled by `self.window_scale`.
        :rtype: pygame.Surface
        """
        scaled_width = surface.get_width() * self.window_scale
        scaled_height = surface.get_height() * self.window_scale
        scaled_surface = pygame.Surface((scaled_width, scaled_height))
        pygame.transform.scale(surface, (scaled_width, scaled_height), scaled_surface)
        return scaled_surface

    def show_screen(self) -> None:
        """
        Show the current frame, and clear the rendering buffer ready for the
        next frame.
        """
        pygame.display.flip()
        self.surface.fill(self.background_colour)
        self.fade_background()

    def text_to_screen(self, pos: Tuple[int, int]) -> Tuple[int, int]:
        """
        Convert character cell coordinates to screen coordinates.

        :param pos: an `(x, y)` pair of character cell coordinates.
        :type pos: Tuple[int, int]
        :return: the corresponding `(x, y)` pair of pixel coordinates
        :rtype: Tuple[int, int]
        """
        return (pos[0] * self.font_pixels, pos[1] * self.font_pixels)

    def print_screen(self, pos: Tuple[int, int], msg: str, **kwargs: Any) -> None:
        """
        Print text on the screen at the given text character coordinates. A
        monospaced font is assumed.

        :param pos: an `(x, y)` pair of character cell coordinates.
        :type pos: Tuple[int, int]
        :param msg: The text to print.
        :type msg: str
        :param *kwargs: Keyword arguments to pass to `ptext` (q.v.).
        """
        ptext.draw(  # type: ignore[no-untyped-call]
            msg,
            self.text_to_screen(pos),
            fontname=self.fontname,
            fontsize=self.font_pixels,
            **kwargs,
        )
