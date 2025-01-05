"""ChamberCourt: Screen class.

© Reuben Thomas <rrt@sc3d.org> 2024
Released under the GPL version 3, or (at your option) any later version.
"""

import os
import warnings
from typing import Any


# Import pygame, suppressing extra messages that it prints on startup.
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import pygame

    from . import ptext


class Screen:
    """The `Screen` class deals with managing the main window.

    It blits the game window to the screen, and prints text.
    """

    def __init__(
        self,
        screen_size: tuple[int, int],
        fontname: str,
        window_scale: int = 1,
        font_scale: int = 1,
        background_colour: tuple[int, int, int] = (0, 0, 255),
    ) -> None:
        """Create a `Screen` object.

        Args:
            screen_size (tuple[int, int]): a `(width, height)` pair giving
              the screen size in pixels

            fontname (str): the monospaced font to use for text

            window_scale (int, optional): the scale factor by which the game
              window is scaled to blit it to the screen. Defaults to 1.

            font_scale (int, optional): the scale factor by which the font
              is enlarged. Defaults to 1. The font is additionally scaled by
              `window_scale`.

            background_colour (tuple[int, int, int], optional): the
              background colour of the screen. Defaults to `(0, 0, 255)`.
        """
        self.window_scale = window_scale
        self.text_colour = (255, 255, 255)
        self.background_colour = background_colour
        self.default_background_colour = background_colour
        self.font_pixels = 8 * self.window_scale * font_scale
        self.surface = pygame.display.set_mode(screen_size, pygame.SCALED, vsync=1)
        self.reinit_screen()
        self.fontname = fontname
        # Force ptext to cache the font
        self.print_screen((0, 0), "")

    def reinit_screen(self) -> None:
        """Reinitialise the screen.

        Used when transitioning between instructions and main game screens.
        """
        self.surface.fill(self.background_colour)

    def flash_background(self) -> None:
        """Set the background colour to be lighter.

        In combination with `Screen.fade_background()`, this causes the
        screen to flash, indicating that some action such as saving the
        player’s position has been accomplished.
        """
        self.background_colour = (
            min(255, self.default_background_colour[0] + 160),
            min(255, self.default_background_colour[1] + 160),
            min(255, self.default_background_colour[2] + 160),
        )

    def fade_background(self) -> None:
        """Fade the background.

        Called every frame to return the background colour to the default
        over a period of several frames.
        """
        self.background_colour = (
            max(self.background_colour[0] - 10, self.default_background_colour[0]),
            max(self.background_colour[1] - 10, self.default_background_colour[1]),
            max(self.background_colour[2] - 10, self.default_background_colour[2]),
        )

    def scale_surface(self, surface: pygame.Surface) -> pygame.Surface:
        """Scales the given surface by `self.window_scale`.

        Args:
            surface (pygame.Surface): surface to scale

        Returns:
            pygame.Surface: a new surface, that is `surface` scaled by
            `self.window_scale`.
        """
        scaled_width = surface.get_width() * self.window_scale
        scaled_height = surface.get_height() * self.window_scale
        scaled_surface = pygame.Surface((scaled_width, scaled_height))
        pygame.transform.scale(surface, (scaled_width, scaled_height), scaled_surface)
        return scaled_surface

    def show_screen(self) -> None:
        """Show the current frame, and clear the rendering buffer."""
        pygame.display.flip()
        self.reinit_screen()
        self.fade_background()

    def text_to_screen(self, pos: tuple[int, int]) -> tuple[int, int]:
        """Convert character cell coordinates to screen coordinates.

        Args:
            pos (tuple[int, int]): an `(x, y)` pair of character cell
            coordinates

        Returns:
            tuple[int, int]: the corresponding `(x, y)` pair of pixel
            coordinates
        """
        return (pos[0] * self.font_pixels, pos[1] * self.font_pixels)

    def print_screen(self, pos: tuple[int, int], msg: str, **kwargs: Any) -> None:
        """Print text on the screen at the given text character coordinates.

        A monospaced font is assumed.

        Args:
            pos (tuple[int, int]): an `(x, y)` pair of character cell coordinates
            msg (str): the text to print
            kwargs: keyword arguments to `ptext.draw`
        """
        ptext.draw(  # type: ignore[no-untyped-call]
            msg,
            self.text_to_screen(pos),
            fontname=self.fontname,
            fontsize=self.font_pixels,
            **kwargs,
        )
