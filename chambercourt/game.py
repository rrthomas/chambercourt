"""ChamberCourt: Main game class.

© Reuben Thomas <rrt@sc3d.org> 2024-2026

Released under the GPL version 3, or (at your option) any later version.
"""

import argparse
import asyncio
import atexit
import copy
import gettext
import importlib
import importlib.metadata
import importlib.resources
import locale
import math
import os
import pickle
import warnings
import zipfile
from collections.abc import Callable
from enum import StrEnum
from itertools import chain
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, cast

import i18nparse  # type: ignore
from platformdirs import user_data_dir

from .langdetect import language_code
from .raw_version import RawVersionAction
from .warnings_util import die, simple_warning


# Import pygame, suppressing extra messages that it prints on startup.
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import pygame
    import pyscroll  # type: ignore
    import pytmx  # type: ignore
    from pygame import Color, Rect, Vector2
    from pytmx.util_pygame import pygame_image_loader

    from . import ptext


locale.setlocale(locale.LC_ALL, "")

# Try to set LANG for gettext if not already set
if "LANG" not in os.environ:
    lang = language_code()
    if lang is not None:
        os.environ["LANG"] = lang
i18nparse.activate()


# Placeholder for gettext
def _(message: str) -> str:
    return message


DATA_DIR = Path(user_data_dir("chambercourt"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
SAVED_POSITION_FILE = DATA_DIR / "saved_position.pkl"


def clear_keys() -> None:
    """Discard outstanding keypress events."""
    for _ in pygame.event.get(pygame.KEYDOWN):
        pass


def sign(x: int) -> int:
    """Signum function."""
    if x > 0:
        return 1
    elif x < 0:
        return -1
    return 0


DIGIT_KEYS = {
    pygame.K_0: 0,
    pygame.K_1: 1,
    pygame.K_2: 2,
    pygame.K_3: 3,
    pygame.K_4: 4,
    pygame.K_5: 5,
    pygame.K_6: 6,
    pygame.K_7: 7,
    pygame.K_8: 8,
    pygame.K_9: 9,
    pygame.K_KP_0: 0,
    pygame.K_KP_1: 1,
    pygame.K_KP_2: 2,
    pygame.K_KP_3: 3,
    pygame.K_KP_4: 4,
    pygame.K_KP_5: 5,
    pygame.K_KP_6: 6,
    pygame.K_KP_7: 7,
    pygame.K_KP_8: 8,
    pygame.K_KP_9: 9,
}


class Game[Tile: StrEnum]:
    """The `Game` class represents the state of a game.

    This includes various constant parameters such as screen size.
    """

    def __init__(
        self,
        game_package_name: str,
        tile_constructor: Callable[[str], Tile],
        hero_tile: Tile,
        empty_tile: Tile,
        default_tile: Tile,
    ) -> None:
        """Create a Game object.

        Args:
            game_package_name (str): the name of the package
            tile_constructor (Callable[[str], Tile]): the constructor of the
              used `Tile` class
            hero_tile (Tile): the tile for the hero in the given `Tile` set
            empty_tile (Tile): the empty tile in the given `Tile` set
            default_tile (Tile): the default tile returned for any
              out-of-range coordinate in the given `Tile` set.
        """
        self.game_package_name = game_package_name
        self.tile_constructor = tile_constructor
        self.hero_tile = hero_tile
        self.empty_tile = empty_tile
        self.default_tile = default_tile

        self.screen_size = (0, 0)

        self.tile_width, self.tile_height = (16, 16)
        """The size of game tiles in pixels."""

        self.game_window_max = (8, 8)
        """The maximum size of the area in which the game world is shown.

        A pair giving the `(height, width)` of the window in game tiles.
        """

        self.screen_extra_x_chars = 0
        """Extra space required, in characters, for screen."""

        self.screen_extra_y_chars = 1
        """Extra space required, in characters, for screen."""

        self.screen_min_text_size = (40, 32)
        """Minimum number of characters across and down the screen."""

        self.min_screen_scale = 1
        """The minimum integer scale factor applied to the screen.

        The game screen is scaled by this factor before being blitted to the
        display.
        """

        self.text_colour = Color(255, 255, 255)
        """The default text colour."""

        self.default_background_colour = Color(32, 32, 32)
        """The background colour of the screen."""

        self.font_name = "acorn-mode-1.ttf"
        """The monospaced font to use for text."""

        self.font_size = 8
        """The font size in pixels."""

        self.font_scale = 1
        """The scale factor applied to the font.

        The font is scaled by `screen_scale` and then by this factor.
        """

        self.instructions_y = 12
        """The text y coordinate at which the instructions are printed."""

        self.frames_per_second = 60
        """Frames per second for the game main loop."""

        self.frames = 8
        """Number of frames over which to animate each hero move."""

        self.default_volume = 0.8
        """Default volume of sound effects."""

        self.music_volume = 0.7
        """Volume of music track."""

        self.screen_scale: int
        self.clock = pygame.time.Clock()
        self.num_levels: int
        self.levels_files: list[Path]
        self.hero_image: pygame.Surface
        self.app_icon: pygame.Surface
        self.title_image: pygame.Surface
        self.window_pixel_width: int
        self.window_pixel_height: int
        self.window_pos: tuple[int, int] = (0, 0)
        self.game_surface: pygame.Surface
        self.quit = False
        self.exit = False
        self.level = 1
        self.moves = 0
        self.level_width: int
        self.level_height: int
        self.tile_width: int
        self.tile_height: int
        self.tmx_data: dict[Path, pytmx.TiledMap] = {}
        self.map_tiles: dict[Path, pytmx.TiledTileLayer] = {}
        self.map_timestamp: dict[Path, float] = {}
        self._map_tiles: pytmx.TiledTileLayer
        self._gids: dict[Tile, int]
        self._map_layer: pyscroll.BufferedRenderer
        self._group: pyscroll.PyscrollGroup
        self.hero: Hero
        self.map_data: pyscroll.data.TiledMapData
        self._joysticks: dict[int, pygame.joystick.JoystickType] = {}
        self.music_muted = False
        self.license_string = _("""Distributed under the GNU General Public License version 3, or (at
your option) any later version. There is no warranty.""")

    @staticmethod
    def description() -> str:
        """Returns a short description of the game.

        Used in command-line `--help`.

        Returns:
            str: description of the game
        """
        # Not translated as it is for programmers, not players.
        return "Play a game."

    @staticmethod
    def instructions() -> str:
        """Instructions for the main game screen.

        Returns:
            str: A possibly multi-line string. Should be pre-wrapped to the
            width of the screen, and contain three consecutive newlines to
            indicate the position of the level selector.
        """
        # fmt: off
        # TRANSLATORS: Please keep this text wrapped to 40 characters. The font
        # used in-game is lacking many glyphs, so please test it with your
        # language and let me know if I need to add glyphs.
        # The next string is not translated as it is for programmers, not
        # players.
        return """\
Game instructions go here.
"""
        # fmt: on

    def find_asset(self, asset_file: str) -> Path:
        """Find a game asset.

        First look at the given level files directory, then fall back to the
        default levels directory for the application, then fall back to
        ChamberCourt's levels directory.

        Args:
            asset_file (str): name of asset file
        """
        levels_asset = Path(asset_file)
        if levels_asset.exists():
            return levels_asset
        else:
            fallback_asset = Path(self.app_path / "levels" / asset_file)
            if fallback_asset.exists():
                return fallback_asset
            else:
                built_in_asset = Path(self.fallback_path / "levels" / asset_file)
                if built_in_asset.exists():
                    return built_in_asset
        raise OSError(_("cannot find asset `{}'").format(asset_file))

    def init_screen(self) -> None:
        """Initialise the screen."""
        info = pygame.display.Info()
        if info.current_w <= 0 or info.current_h <= 0:
            raise ValueError("cannot get display size")

        # Fill available area, smaller dimension first
        scale = self.min_screen_scale
        if info.current_w <= info.current_h:
            # Find biggest `screen_scale` that fits
            # `self.game_window_max[0]` tiles plus
            # `self.screen_extra_x_chars` characters.
            while True:
                font_pixels = self.font_size * scale * self.font_scale
                game_window_width = (
                    info.current_w - self.screen_extra_x_chars * font_pixels
                )
                width_in_tiles = game_window_width // (self.tile_width * scale)
                if (
                    width_in_tiles < self.game_window_max[0]
                    or info.current_w // font_pixels < self.screen_min_text_size[0]
                ):
                    break
                scale += 1
        else:
            # Find biggest `screen_scale` that fits
            # `self.game_window_max[1]` tiles plus
            # `self.screen_extra_y_chars` characters.
            while True:
                font_pixels = self.font_size * scale * self.font_scale
                game_window_height = (
                    info.current_h - self.screen_extra_y_chars * font_pixels
                )
                height_in_tiles = game_window_height // (self.tile_height * scale)
                if (
                    height_in_tiles < self.game_window_max[1]
                    or info.current_h // font_pixels < self.screen_min_text_size[1]
                ):
                    break
                scale += 1

        # Set screen parameters according to the results
        scale = max(scale - 1, self.min_screen_scale)
        font_pixels = self.font_size * scale * self.font_scale
        game_window_width = info.current_w - self.screen_extra_x_chars * font_pixels
        width_in_tiles = min(
            game_window_width // (self.tile_width * scale), self.game_window_max[0]
        )
        game_window_height = info.current_h - self.screen_extra_y_chars * font_pixels
        height_in_tiles = min(
            game_window_height // (self.tile_height * scale), self.game_window_max[1]
        )

        self.screen_scale = scale
        self.font_pixels = self.font_size * self.font_scale * self.screen_scale
        self.window_size = (
            width_in_tiles * self.tile_width * self.screen_scale,
            height_in_tiles * self.tile_height * self.screen_scale,
        )
        self.screen_size = (info.current_w, info.current_h)
        self.screen_char_width = self.screen_size[0] // self.font_pixels
        self.reinit_screen()
        # Force ptext to cache the font
        self.print_screen((0, 0), "")

        self.window_pos = (
            max(
                self.screen_extra_x_chars * self.font_pixels,
                (self.surface.get_width() - self.window_size[0]) // 2,
            ),
            (
                self.surface.get_height()
                - self.window_size[1]
                - self.screen_extra_y_chars * self.font_pixels
            )
            // 2
            + self.screen_extra_y_chars * self.font_pixels,
        )

    def clear_screen(self) -> None:
        """Clear the screen."""
        self.surface.fill(self.background_colour)

    def reinit_screen(self) -> None:
        """Reinitialise the screen.

        Used when transitioning between instructions and main game screens.
        """
        self.background_colour = self.default_background_colour
        self.clear_screen()

    def flash_background(self) -> None:
        """Set the background colour to be lighter.

        In combination with `Screen.fade_background()`, this causes the
        screen to flash, indicating that some action such as saving the
        player’s position has been accomplished.
        """
        self.background_colour = Color(
            min(255, self.background_colour.r + 160),
            min(255, self.background_colour.g + 160),
            min(255, self.background_colour.b + 160),
        )

    def fade_background(self) -> None:
        """Fade the background.

        Called every frame to return the background colour to the default
        over a period of several frames.
        """
        self.background_colour = Color(
            max(self.background_colour.r - 10, self.default_background_colour.r),
            max(self.background_colour.g - 10, self.default_background_colour.g),
            max(self.background_colour.b - 10, self.default_background_colour.b),
        )

    def scale_surface(self, surface: pygame.Surface) -> pygame.Surface:
        """Scales the given surface by `self.screen_scale`.

        Args:
            surface (pygame.Surface): surface to scale

        Returns:
            pygame.Surface: a new surface, that is `surface` scaled by
            `self.screen_scale`.
        """
        scaled_width = surface.get_width() * self.screen_scale
        scaled_height = surface.get_height() * self.screen_scale
        return pygame.transform.scale(surface, (scaled_width, scaled_height))

    def show_screen(self) -> None:
        """Show the current frame, and clear the rendering buffer."""
        self.surface.blit(self.scale_surface(self.game_surface), self.window_pos)
        pygame.display.flip()
        self.clear_screen()
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

    def print_screen_raw(
        self, pos: tuple[int, int], msg: str, **kwargs
    ) -> tuple[int, int]:
        """Print text on the screen at the given pixel coordinates.

        Args:
            pos (tuple[int, int]): an `(x, y)` pair of pixel coordinates
            msg (str): the text to print
            kwargs: keyword arguments to `ptext.draw`

        Returns:
            tuple[int, int]: the position at which the text is drawn
        """
        _, pos = ptext.draw(  # type: ignore[no-untyped-call]
            msg,
            pos,
            fontname=self.font_path,
            fontsize=self.font_pixels,
            **kwargs,
        )
        return pos

    def print_screen(self, pos: tuple[int, int], msg: str, **kwargs) -> tuple[int, int]:
        """Print text on the screen at the given text character coordinates.

        A monospaced font is assumed.

        Args:
            pos (tuple[int, int]): an `(x, y)` pair of character cell coordinates
            msg (str): the text to print
            kwargs: keyword arguments to `ptext.draw`

        Returns:
            tuple[int, int]: the position at which the text is drawn
        """
        return self.print_screen_raw(
            self.text_to_screen(pos),
            msg,
            **kwargs,
        )

    def text_width(self, text: str, **kwargs) -> int:
        """Find the width of given text.

        Args:
            text (str): the text
            kwargs: tag definitions as for `ptext.draw`

        Returns:
            int: the width in pixels of the text
        """
        kwargs["fontname"] = self.font_path
        kwargs["fontsize"] = self.font_pixels
        wrapped = ptext._wrap(text, **kwargs)
        return wrapped[0].linewidth

    def load_assets(self) -> None:
        """Load game assets."""
        self.font_path = self.find_asset(self.font_name)
        self.app_icon = pygame.image.load(self.find_asset("app-icon.png"))
        self.title_image = pygame.image.load(self.find_asset("title.png"))
        self.hero_image = pygame.image.load(self.find_asset("Hero.png"))

    def init_renderer(self) -> None:
        """Set up the `pyscroll.BufferedRenderer` and its camera (group)."""
        self._map_layer = pyscroll.BufferedRenderer(
            self.map_data, (self.window_pixel_width, self.window_pixel_height)
        )
        self._group = pyscroll.PyscrollGroup(map_layer=self._map_layer)
        self._group.add(self.hero)

    def image_loader(
        self, filename: str, colorkey: pytmx.pytmx.ColorLike | None, **kwargs
    ) -> Callable[[Rect, int], pygame.Surface]:
        """Wrapper for pygame_image_loader for ChamberCourt assets.

        Args:
            filename (str): asset name; only the basename is used
            colorkey (ColorLike | None): as for `pygame_image_loader`
            kwargs (dict): as for `pygame_image_loader`.

        Returns:
            Callable[[Rect, int], pygame.Surface]: loader function
        """
        return pygame_image_loader(
            str(self.find_asset(Path(filename).name)), colorkey, **kwargs
        )

    def restart_level(self) -> None:
        """Restart the current level.

        This method is used when starting a level, when loading a saved
        position, when dying, and when restarting a level.

        It loads the level, and sets the game window size to fit.
        """
        level_file = self.levels_files[self.level - 1]
        self.load_level(level_file)
        (self.level_width, self.level_height) = self.map_data.map_size
        if self.map_data.tile_size != (self.tile_width, self.tile_height):
            raise ValueError(
                f"tile size {self.map_data.tile_size} not expected value {(self.tile_width, self.tile_height)}"
            )
        self.clamp_window()
        self.load_music(
            f"{self.level:0{math.floor(math.log10(self.num_levels) + 1)}}.ogg"
        )

        # Dict mapping tileset GIDs to map gids
        map_gids = self.map_data.tmx.gidmap
        self._gids = {}
        for i in map_gids:
            gid = map_gids[i][0][0]
            properties = self.map_data.tmx.get_tile_properties_by_gid(gid)
            assert type(properties) is dict
            tile = self.tile_constructor(properties["type"])
            self._gids[tile] = gid

        self.hero = Hero(self.hero_image)
        self.hero.position = Vector2(0, 0)

        self.init_renderer()
        self.init_game()

    def clamp_window(self) -> None:
        """Clamp the window size to the level size.

        If the level is smaller than the window, reduce the window size.
        """
        self.window_pixel_width = min(
            self.level_width * self.tile_width,
            self.window_size[0] // self.screen_scale,
        )
        self.window_pixel_height = min(
            self.level_height * self.tile_height,
            self.window_size[1] // self.screen_scale,
        )
        self.game_surface = pygame.Surface(
            (self.window_pixel_width, self.window_pixel_height)
        )

    def start_level(self) -> None:
        """Start a level, saving the initial position."""
        self.restart_level()
        self.save_position()

    def _get_gid_properties(self, gid: int) -> dict[str, Any]:
        """Look up the properties of a tile given its gid."""
        return cast(dict[str, Any], self.map_data.tmx.get_tile_properties_by_gid(gid))

    def get_tile_properties(self, tile: Tile) -> dict[str, Any]:
        """Look up the properties of a tile given its `Tile`."""
        return self._get_gid_properties(self._gids[tile])

    def get_properties(self, pos: Vector2) -> dict[str, Any]:
        """Return the properties of the tile at the given position.

        Args:
            pos (Vector2): the `(x, y)` position required, in tile
              coordinates

        Returns:
            dict[str, Any]: the properties dict
        """
        # Anything outside the map is a default tile
        x, y = int(pos.x), int(pos.y)
        if not ((0 <= x < self.level_width) and (0 <= y < self.level_height)):
            return self.get_tile_properties(self.default_tile)
        gid = self._map_tiles[y][x]  # pyright: ignore
        if gid == 0:  # Missing tiles are gaps
            return self.get_tile_properties(self.empty_tile)
        return self._get_gid_properties(gid)

    # TODO: Inline, and try to use the properties dict,
    # i.e. try to avoid calling `tile_constructor`.
    def get(self, pos: Vector2) -> Tile:
        """Return the tile at the given position.

        Args:
            pos (Vector2): the `(x, y)` position required, in tile
              coordinates

        Returns:
            Tile: the `Tile` at the given position
        """
        return self.tile_constructor(self.get_properties(pos)["type"])

    def _set(self, pos: Vector2, tile: Tile) -> None:
        x, y = int(pos.x), int(pos.y)
        if not ((0 <= x < self.level_width) and (0 <= y < self.level_height)):
            return
        self._map_tiles[y][x] = self._gids[tile]  # pyright: ignore
        # Update rendered map
        # NOTE: We invoke protected methods and access protected members.
        ml = self._map_layer
        rect = (x, y, 1, 1)
        assert ml._tile_queue is not None
        ml._tile_queue = chain(ml._tile_queue, ml.data.get_tile_images_by_rect(rect))
        assert type(self._map_layer._buffer) is pygame.Surface
        self._map_layer._flush_tile_queue(self._map_layer._buffer)

    def set(self, pos: Vector2, tile: Tile) -> None:
        """Set the tile at the given position.

        Args:
            pos (Vector2): the `(x, y)` position required, in tile
              coordinates
            tile (Tile): the `Tile` to set at the given position
        """
        # Update map twice, to allow for transparent tiles
        self._set(pos, self.empty_tile)
        self._set(pos, tile)

    def set_map(self, map_tiles: pytmx.TiledTileLayer) -> None:
        """Set the current map.

        Args:
            map_tiles (pytmx.TiledTileLayer): the tile data to use.
        """
        self._map_tiles = map_tiles
        self.map_data.tmx.layers[0].data = self._map_tiles

    def load_level(self, level: Path) -> None:
        """Load map data for given level path.

        Reload only if the file has changed.

        Args:
            level (Path): path to level file
        """
        mtime = level.stat().st_mtime
        if mtime > self.map_timestamp[level]:
            self.map_timestamp[level] = mtime
            map_data = pytmx.TiledMap(str(level), image_loader=self.image_loader)
            self.tmx_data[level] = map_data
            self.map_tiles[level] = copy.deepcopy(self.tmx_data[level].layers[0].data)
        self.map_data = pyscroll.data.TiledMapData(self.tmx_data[level])
        self.set_map(copy.deepcopy(self.map_tiles[level]))

    def set_music_volume(self) -> None:
        """Set the music volume."""
        if self.music_muted:
            pygame.mixer.music.set_volume(0.0)
        else:
            pygame.mixer.music.set_volume(self.music_volume)

    def load_music(self, filename: str) -> None:
        """Load music file for current level.

        Args:
            filename (str): name of music file.
        """
        try:
            path = self.find_asset(filename)
            pygame.mixer.music.load(path)
            self.set_music_volume()
            pygame.mixer.music.play(-1)
        except OSError:
            pass  # ignore non-existent music

    def save_position(self) -> None:
        """Save the current position."""
        self.set(self.hero.position, self.hero_tile)
        with open(SAVED_POSITION_FILE, "wb") as fh:
            pickle.dump(self._map_tiles, fh)
        self.set(self.hero.position, self.empty_tile)

    def load_position(self) -> None:
        """Reload the saved position, if any.

        If there isn't one, nothing is done.
        """
        if SAVED_POSITION_FILE.exists():
            with open(SAVED_POSITION_FILE, "rb") as fh:
                self.set_map(pickle.load(fh))
            self.init_renderer()
            self.init_game()

    async def clock_tick(self) -> None:
        """Let clock tick for a frame."""
        self.clock.tick(self.frames_per_second)
        await asyncio.sleep(0)

    def draw(self) -> None:
        """Draw the current position."""
        self._group.center(self.hero.rect.center)
        self._group.draw(self.game_surface)

    def handle_joystick_plug(self, event: pygame.event.Event) -> None:
        """Track joystick plug/unplug events.

        Args:
            event (pygame.event.Event): An event that might be a plug/unplug
              event.
        """
        if event.type == pygame.JOYDEVICEADDED:
            joy = pygame.joystick.Joystick(event.device_index)
            self._joysticks[joy.get_instance_id()] = joy
        elif event.type == pygame.JOYDEVICEREMOVED:
            del self._joysticks[event.instance_id]

    def handle_joysticks(self) -> tuple[int, int]:
        """Get joystick/gamepad input.

        Returns:
            tuple[int, int]: the desired unit velocity
        """
        dx, dy = (0, 0)
        for joystick in self._joysticks.values():
            axes = joystick.get_numaxes()
            if axes >= 2:  # Hopefully 0=L/R and 1=U/D
                lr = joystick.get_axis(0)
                if lr < -0.5:
                    dx = -1
                elif lr > 0.5:
                    dx = 1
                ud = joystick.get_axis(1)
                if ud < -0.5:
                    dy = -1
                elif ud > 0.5:
                    dy = 1
        if (dy, dy) != (0, 0):
            pygame.mouse.set_visible(False)
        return (dx, dy)

    def get_mouse(self) -> tuple[int, int]:
        """Get mouse input.

        Returns:
            tuple[int, int]: the desired unit velocity
        """
        dx, dy = 0, 0
        # Delta in game tiles from mouse click to hero
        mdelta = self.window_to_game(pygame.mouse.get_pos()) - self.hero.position
        # Force the delta to have at most one non-zero component
        if abs(mdelta.x) >= abs(2 * mdelta.y):
            (dx, dy) = (int(mdelta.x), 0)
        elif abs(mdelta.y) >= abs(2 * mdelta.x):
            (dx, dy) = (0, int(mdelta.y))
        return (dx, dy)

    def handle_game_keys(self, event: pygame.event.Event) -> None:
        """Handle in-game keypresses other than player controls.

        Args:
            event (pygame.event.Event): a keypress event.
        """
        load_pressed = False
        if event.type == pygame.KEYDOWN:
            load_pressed = event.key == pygame.K_l
        elif event.type == pygame.JOYBUTTONDOWN:
            load_pressed = event.button == 1

        save_pressed = False
        if event.type == pygame.KEYDOWN:
            save_pressed = event.key == pygame.K_s
        elif event.type == pygame.JOYBUTTONDOWN:
            save_pressed = event.button == 0

        restart_pressed = False
        if event.type == pygame.KEYDOWN:
            restart_pressed = event.key == pygame.K_r
        elif event.type == pygame.JOYBUTTONDOWN:
            restart_pressed = event.button == 3

        if load_pressed:
            self.flash_background()
            self.load_position()
        elif save_pressed:
            self.flash_background()
            self.save_position()
        if restart_pressed:
            self.flash_background()
            self.restart_level()
        if event.type == pygame.KEYDOWN and event.key == pygame.K_q:
            self.quit = True

    def handle_player_controls(
        self,
        mouse_pressed: bool,
        dx: int,
        dy: int,
        kdx: int,
        kdy: int,
        jdx: int,
        jdy: int,
    ) -> tuple[tuple[int, int], tuple[int, int], tuple[int, int]]:
        """Handle player control input during the game.

        This handles all supported input devices.

        Args:
            mouse_pressed (bool): true if mouse is used
            dx (int): current dx
            dy (int): current dy
            kdx (int): current keyboard dx
            kdy (int): current keyboard dy
            jdx (int): current joystick dx
            jdy (int): current joystick dy

        Returns:
            tuple[int, int]: desired offset.
        """
        pressed = pygame.key.get_pressed()
        new_kdx, new_kdy = (0, 0)
        if pressed[pygame.K_LEFT] or pressed[pygame.K_z]:
            new_kdx = -1
        if pressed[pygame.K_RIGHT] or pressed[pygame.K_x]:
            new_kdx = 1
        if pressed[pygame.K_UP] or pressed[pygame.K_QUOTE]:
            new_kdy = -1
        if pressed[pygame.K_DOWN] or pressed[pygame.K_SLASH]:
            new_kdy = 1
        if (new_kdx, new_kdy) != (kdx, kdy):
            kdx, kdy = (new_kdx, new_kdy)
            dx, dy = (kdx, kdy)
        (new_jdx, new_jdy) = self.handle_joysticks()
        if (new_jdx, new_jdy) != (jdx, jdy):
            jdx, jdy = (new_jdx, new_jdy)
            dx, dy = (jdx, jdy)
        if mouse_pressed:
            (dx, dy) = self.get_mouse()
        return (dx, dy), (kdx, kdy), (jdx, jdy)

    def game_to_screen(self, pos: Vector2) -> tuple[int, int]:
        """Convert game grid to screen coordinates.

        Args:
            pos (Vector2): grid coordinates

        Returns:
            tuple[int, int]: the corresponding screen coordinates
        """
        origin = self._map_layer.get_center_offset()
        return (
            origin[0] + int(pos.x) * self.tile_width,
            origin[1] + int(pos.y) * self.tile_height,
        )

    def window_to_game(self, pos: tuple[int, int]) -> Vector2:
        """Convert window coordinates to game grid.

        Args:
            pos (tuple[int, int]): screen coordinates

        Returns:
            Vector2: the corresponding game grid coordinates
        """
        origin = self._map_layer.get_center_offset()
        return Vector2(
            ((pos[0] - self.window_pos[0]) // self.screen_scale - origin[0])
            // self.tile_width,
            ((pos[1] - self.window_pos[1]) // self.screen_scale - origin[1])
            // self.tile_height,
        )

    async def title_screen(self, title_image: pygame.Surface, instructions: str) -> int:
        """Show instructions and choose start level."""
        clear_keys()
        level = None
        start_level_y = (
            self.instructions_y
            + len(instructions.split("\n\n\n", maxsplit=1)[0].split("\n"))
            + 1
        )
        play_y = start_level_y + 2
        play = False
        self.load_music("title.ogg")
        while not self.exit and not play:
            self.reinit_screen()
            self.surface.blit(
                self.scale_surface(title_image),
                (
                    (self.screen_size[0] - title_image.get_width() * self.screen_scale)
                    // 2,
                    12 * self.screen_scale,
                ),
            )
            self.print_screen(
                (0, self.instructions_y),
                instructions,
                color="grey",
                width=self.surface.get_width(),
                align="center",
            )

            # Draw level selector and find where the arrows are
            level_msg = _("Start at level: ←{}→/{}").format(
                1 if level is None else level, self.num_levels
            )
            left_arrow_index = level_msg.find("←")
            right_arrow_index = level_msg.find("→")
            arrows_y = self.print_screen(
                (0, start_level_y),
                level_msg,
                width=self.surface.get_width(),
                align="center",
            )[1]
            level_msg_width = self.text_width(level_msg)
            level_left_x = (self.surface.get_width() - level_msg_width) // 2
            left_arrow_width = self.text_width("←")
            right_arrow_width = self.text_width("→")
            left_arrow_x = (
                level_left_x
                + self.text_width(level_msg[: left_arrow_index + 1])
                - left_arrow_width
            )
            right_arrow_x = (
                level_left_x
                + self.text_width(level_msg[: right_arrow_index + 1])
                - right_arrow_width
            )
            left_zone = Rect(
                left_arrow_x,
                arrows_y,
                left_arrow_width,
                self.font_pixels,
            )
            right_zone = Rect(
                right_arrow_x,
                arrows_y,
                right_arrow_width,
                self.font_pixels,
            )
            self.print_screen_raw((left_arrow_x, arrows_y), "←", background="darkgrey")
            self.print_screen_raw((right_arrow_x, arrows_y), "→", background="darkgrey")

            # Draw play message and button
            play_msg = _("Press Space or button A to play!")
            # TRANSLATORS: this message should appear in the previous one
            # It will be highlighted as a button.
            play_index = play_msg.find(_("play"))
            play_button_y = self.print_screen(
                (0, play_y),
                play_msg,
                width=self.surface.get_width(),
                align="center",
            )[1]
            play_msg_width = self.text_width(play_msg)
            play_left_x = (self.surface.get_width() - play_msg_width) // 2
            p_width = self.text_width(play_msg[0])
            play_width = self.text_width(_("play"))
            play_x = play_left_x + self.text_width(play_msg[: play_index + 1]) - p_width
            play_zone = Rect(
                play_x,
                play_button_y,
                play_width,
                self.font_pixels,
            )
            self.print_screen_raw(
                (play_x, play_button_y), _("play"), background="darkgrey"
            )
            self.print_screen_raw(
                (0, self.screen_size[1] - self.font_pixels),
                f"v{self.version}",
                width=self.surface.get_width(),
                align="right",
                color="grey",
            )

            pygame.display.flip()
            self.handle_quit_event()
            for event in pygame.event.get():
                level_change = 0
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_q:
                        self.exit_game()
                    elif event.key == pygame.K_SPACE:
                        play = True
                    elif event.key in (
                        pygame.K_z,
                        pygame.K_LEFT,
                        pygame.K_SLASH,
                        pygame.K_DOWN,
                    ):
                        level_change = -1
                    elif event.key in (
                        pygame.K_x,
                        pygame.K_RIGHT,
                        pygame.K_QUOTE,
                        pygame.K_UP,
                    ):
                        level_change = 1
                    elif event.key in DIGIT_KEYS:
                        level = min(
                            self.num_levels, (level or 0) * 10 + DIGIT_KEYS[event.key]
                        )
                        if level == 0:
                            level = None
                    else:
                        level = None
                elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                    mouse_pos = pygame.mouse.get_pos()
                    if left_zone.collidepoint(mouse_pos[0], mouse_pos[1]):
                        level_change = -1
                    elif right_zone.collidepoint(mouse_pos[0], mouse_pos[1]):
                        level_change = 1
                    elif play_zone.collidepoint(mouse_pos[0], mouse_pos[1]):
                        play = True
                elif event.type == pygame.JOYBUTTONDOWN:
                    if event.button == 0:
                        play = True
                elif event.type in (pygame.JOYDEVICEADDED, pygame.JOYDEVICEREMOVED):
                    self.handle_joystick_plug(event)
                elif event.type in (pygame.WINDOWRESIZED, pygame.WINDOWSIZECHANGED):
                    self.init_screen()
                self.handle_global_inputs(event)
                (dx, dy) = self.handle_joysticks()
                level_change += dx - dy
                if level_change != 0:
                    level = max(1, min(self.num_levels, (level or 1) + level_change))
            await self.clock_tick()
        return max(min(level or 1, self.num_levels), 1)

    async def end_game(self) -> None:
        """Do any game-specific tear-down when the game ends."""

    async def start_play(self) -> None:
        """Do any game-specific set-up when play starts."""

    async def stop_play(self) -> None:
        """Do any game-specific tear-down when play is interrupted."""

    def update_map(self) -> None:
        """Update the map after a move.

        When this method is called, the Hero is either stationary, or has
        just completed a move to `self.hero.position`, as indicated by
        `self.hero.velocity`.
        """

    async def end_level(self) -> None:
        """End a level."""
        if self.level == self.num_levels:
            return
        origin = (
            self.game_to_screen(self.hero.position)
            + Vector2(self.tile_width, self.tile_height) / 2
        )
        max_radius = min(self.window_pixel_width, self.window_pixel_height) / 2
        min_radius = max(self.tile_width, self.tile_height) / 2 + 1
        radius_range = max_radius - min_radius
        spotlight = pygame.Surface((self.window_pixel_width, self.window_pixel_height))
        for i in range(self.frames_per_second):
            await self.clock_tick()
            spotlight.fill(Color("black"))
            radius = max_radius - ((i + 1) / self.frames_per_second) ** 2 * radius_range
            pygame.draw.circle(spotlight, Color("white"), origin, radius)
            self.draw()
            self.show_status()
            self.game_surface.blit(spotlight, (0, 0), special_flags=pygame.BLEND_MIN)
            self.show_screen()

    async def win_game(self) -> None:
        """Win the game."""
        self._group.remove(self.hero)
        max_radius = min(self.window_pixel_width, self.window_pixel_height) / 2
        min_radius = max(self.tile_width, self.tile_height) / 2 + 1
        origin = Vector2(self.game_to_screen(self.hero.position))
        destination = Vector2(0, 0)
        delta = destination - origin
        radius_range = max_radius - min_radius
        for i in range(self.frames_per_second):
            await self.clock_tick()
            factor = ((i + 1) / self.frames_per_second) ** 2
            radius = min_radius + radius_range * factor
            zoomed_hero = pygame.transform.scale(
                self.hero.image, (radius * 2, radius * 2)
            )
            self.draw()
            self.game_surface.blit(zoomed_hero, origin + delta * factor)
            self.show_screen()
        await asyncio.sleep(2.0)

    async def run(self, level: int) -> None:
        """Run the game main loop, starting on the given level.

        Args:
            level (int): the level to start at
        """
        self.quit = False
        self.level = level
        while not self.quit and self.level <= self.num_levels:
            self.start_level()
            while not self.quit and not self.finished():
                self.load_position()
                frame = 0
                moving = False
                self.moves = 0
                self.hero.velocity = Vector2(0, 0)
                self._group.update(0)
                await self.start_play()
                dx, dy = 0, 0
                kdx, kdy = 0, 0
                jdx, jdy = 0, 0
                while not self.quit and not (
                    self.finished() and (frame == 0 or not moving)
                ):
                    await self.clock_tick()

                    # Check inputs
                    mouse_pressed = False
                    for event in pygame.event.get():
                        if event.type == pygame.QUIT:
                            self.exit_game()
                        elif event.type in (pygame.KEYDOWN, pygame.JOYBUTTONDOWN):
                            self.handle_game_keys(event)
                        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                            mouse_pressed = True
                        elif event.type in (
                            pygame.WINDOWRESIZED,
                            pygame.WINDOWSIZECHANGED,
                        ):
                            self.init_screen()
                            self.clamp_window()
                            self.init_renderer()
                        self.handle_joystick_plug(event)
                        self.handle_global_inputs(event)
                    (dx, dy), (kdx, kdy), (jdx, jdy) = self.handle_player_controls(
                        mouse_pressed, dx, dy, kdx, kdy, jdx, jdy
                    )

                    # If Hero is not moving already, try to start new move
                    if not moving and (dx, dy) != (0, 0):
                        allowed_move = (0, 0)
                        try_dx, try_dy = sign(dx), sign(dy)
                        if dx != 0 and self.try_move(Vector2(try_dx, 0)):
                            allowed_move = (try_dx, 0)
                            dx -= try_dx
                        elif dy != 0 and self.try_move(Vector2(0, try_dy)):
                            allowed_move = (0, try_dy)
                            dy -= try_dy
                        if allowed_move != (0, 0):
                            self.hero.velocity = Vector2(allowed_move)
                            frame = 0
                            moving = True
                            self.moves += 1
                            kdx, kdy = 0, 0
                            jdx, jdy = 0, 0

                    # Step frame counter and animate
                    frame = (frame + 1) % self.frames
                    self._group.update(1 / self.frames)

                    # When frame counter wraps, run physics and end movement
                    if frame == 0:
                        self.update_map()
                        self.hero.velocity = Vector2(0, 0)
                        moving = False

                    # Draw and display screen.
                    self.draw()
                    self.show_status()
                    self.show_screen()
                pygame.mixer.music.fadeout(1000)
                await self.stop_play()
            if self.finished():
                await self.end_level()
                self.level += 1
        if self.level > self.num_levels:
            await self.win_game()
        await self.end_game()

    def init_game(self) -> None:
        """Initialise game state.

        This method should be overridden by games with game-specific
        initialisation.

        The base class version finds the hero in the map and sets the
        corresponding tile to `EMPTY`.
        """
        for x in range(self.level_width):
            for y in range(self.level_height):
                block = self.get(Vector2(x, y))
                if block == self.hero_tile:
                    self.hero.position = Vector2(x, y)
                    self.set(self.hero.position, self.empty_tile)

    def try_move(self, delta: Vector2) -> bool:
        """Try to move the hero by the given displacement.

        Args:
            delta (Vector2): the displacement unit vector

        Returns:
            bool: `True` if the player can move in that direction, or
              `False` otherwise.

        The default rule is that the player may not move on to
        `default_tile`, and that any other tile is set to empty when the
        player moves on to it.
        """
        newpos = self.hero.position + delta
        block = self.get(newpos)
        if block != self.default_tile:
            self.set(newpos, self.empty_tile)
            return True
        return False

    def show_status(self) -> None:
        """Update the status display.

        This method prints the current level, and should be overridden by
        game classes to print extra game-specific information.
        """
        self.print_screen(
            (0, 0),
            _("Level {}:").format(self.level)
            + " "
            + self.map_data.tmx.properties["Title"],
            width=self.surface.get_width(),
            align="center",
            color="grey",
        )

    def finished(self) -> bool:
        """Indicate whether the current level is finished.

        This method should be overridden. The default is to declare the
        level finished when only hero, default and empty tiles are left.

        Returns:
            bool: a flag indicating whether the current level is finished
        """
        for x in range(self.level_width):
            for y in range(self.level_height):
                block = self.get(Vector2(x, y))
                if block not in (self.hero_tile, self.default_tile, self.empty_tile):
                    return False
        return True

    def exit_game(self) -> None:
        """Exit the game immediately."""
        self.quit = True
        self.exit = True

    def handle_quit_event(self) -> None:
        """React to `pygame.QUIT` event."""
        if len(pygame.event.get(pygame.QUIT)) > 0:
            self.exit_game()

    def handle_global_inputs(self, event: pygame.event.Event) -> None:
        """React to inputs that work anywhere in the game.

        Args:
            event (pygame.event.Event): An event.
        """
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_f:
                pygame.display.toggle_fullscreen()
            elif event.key == pygame.K_m:
                self.music_muted = not self.music_muted
                self.set_music_volume()

        if event.type in (
            pygame.MOUSEMOTION,
            pygame.MOUSEBUTTONDOWN,
            pygame.MOUSEWHEEL,
        ):
            pygame.mouse.set_visible(True)
        elif event.type in (pygame.KEYDOWN, pygame.JOYBUTTONDOWN):
            pygame.mouse.set_visible(False)

    async def main(self, argv: list[str]) -> None:
        """Main function for the game.

        Args:
            argv (list[str]): command-line arguments
        """
        global _

        # Internationalise this module.
        with importlib.resources.as_file(importlib.resources.files()) as path:
            cat = gettext.translation("chambercourt", path / "locale", fallback=True)
            _ = cat.gettext

        metadata = importlib.metadata.metadata(self.game_package_name)
        self.version = importlib.metadata.version(self.game_package_name)
        homepage = metadata["Project-URL"].removeprefix("Homepage, ")

        # Set app name for SDL
        os.environ["SDL_APP_NAME"] = metadata["Name"]

        with importlib.resources.as_file(
            importlib.resources.files("chambercourt")
        ) as fallback_path:
            with importlib.resources.as_file(
                importlib.resources.files(self.game_package_name)
            ) as path:
                # Command-line arguments
                parser = argparse.ArgumentParser(description=self.description())
                parser.register("action", "raw_version", RawVersionAction)
                parser.add_argument(
                    "--levels",
                    metavar="DIRECTORY",
                    help=_("a directory or Zip file of levels to use"),
                )
                parser.add_argument(
                    "-V",
                    "--version",
                    action="raw_version",
                    version=(
                        """%(prog)s {}
© {}
{}
{}"""
                    ).format(
                        self.version,
                        metadata["Author-email"],
                        homepage,
                        self.license_string,
                    ),
                )
                warnings.showwarning = simple_warning(parser.prog)
                args = parser.parse_args(argv)

                self.app_path = Path(path)
                self.fallback_path = Path(fallback_path)
                self.levels_path = Path(args.levels or self.app_path / "levels")

                # Check pygame is built with all image loaders
                if not pygame.image.get_extended():
                    die(_("pygame does not have extended image format support"))

                # Initialize pygame, setting screen size if not already set
                if not pygame.display.get_init():
                    pygame.init()
                    self.surface = pygame.display.set_mode(
                        (
                            max(
                                self.game_window_max[0] * self.tile_width
                                + self.screen_extra_x_chars * self.font_size,
                                self.screen_min_text_size[0] * self.font_size,
                            ),
                            max(
                                self.game_window_max[1] * self.tile_height
                                + self.screen_extra_y_chars * self.font_size,
                                self.screen_min_text_size[1] * self.font_size,
                            ),
                        ),
                        pygame.SCALED | pygame.RESIZABLE,
                        vsync=1,
                    )
                self.load_assets()
                pygame.display.set_icon(self.app_icon)
                pygame.mouse.set_visible(False)
                pygame.font.init()
                pygame.key.set_repeat()
                pygame.joystick.init()
                pygame.display.set_caption(metadata["Name"])
                self.init_screen()

                # Load levels
                try:
                    real_levels_path: Path
                    if zipfile.is_zipfile(self.levels_path):
                        tmpdir = TemporaryDirectory()
                        real_levels_path = Path(tmpdir.name)
                        with zipfile.ZipFile(self.levels_path) as z:
                            z.extractall(real_levels_path)
                        atexit.register(lambda tmpdir: tmpdir.cleanup(), tmpdir)
                    else:
                        real_levels_path = Path(self.levels_path)
                    self.levels_files = sorted(
                        [
                            file
                            for file in real_levels_path.iterdir()
                            if (not str(file.name).startswith("."))
                            and file.is_file()
                            and file.suffix == ".tmx"
                        ]
                    )
                except OSError as err:
                    die(_("Error reading levels: {}").format(err.strerror))
                self.num_levels = len(self.levels_files)
                if self.num_levels == 0:
                    die(_("Could not find any levels"))
                for level in self.levels_files:
                    self.map_timestamp[level] = 0
                    self.load_level(level)

        # Main loop
        try:
            while self.exit is False:
                level = await self.title_screen(
                    self.title_image.convert(),
                    # TRANSLATORS: Please keep this text wrapped to 40 characters.
                    self.instructions()
                    + "\n"
                    + _("""\
Z/X - Left/Right   '/? - Up/Down
or use arrow keys, game controller
joystick, mouse or tap the screen
""")
                    + "\n"
                    + _("""\
S/Button A - Save position
L/Button B - Load position
R/Button Y - Restart level
Q - Quit game
F - toggle full screen
"""),
                )
                if not self.exit:
                    await self.run(level)
        except KeyboardInterrupt:
            self.exit_game()


class Hero(pygame.sprite.Sprite):
    """A class representing the hero.

    Args:
        pygame (pygame.sprite.Sprite): the sprite used for the hero.
    """

    def __init__(self, image: pygame.Surface) -> None:
        """Create a Hero object.

        Args:
            image (pygame.Surface): the hero image
        """
        pygame.sprite.Sprite.__init__(self)
        self.image: pygame.Surface = image
        self.velocity = Vector2(0, 0)
        self.position = Vector2(0, 0)
        self.rect: Rect = self.image.get_rect()
        self.tile_size = Vector2(self.image.get_width(), self.image.get_height())

    def update(self, dt: float) -> None:
        """Move the hero according to its velocity for the given time interval.

        Args:
            dt (float): the elapsed time in milliseconds
        """
        self.position += self.velocity * dt
        screen_pos = Vector2(
            self.position.x * self.tile_size.x, self.position.y * self.tile_size.y
        )
        self.rect.topleft = (int(screen_pos.x), int(screen_pos.y))
