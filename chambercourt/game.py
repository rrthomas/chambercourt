# © Reuben Thomas <rrt@sc3d.org> 2024
# Released under the GPL version 3, or (at your option) any later version.

import argparse
import atexit
import gettext
import importlib
import importlib.metadata
import locale
import os
import pickle
import types
import warnings
import zipfile
from itertools import chain
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, Callable, List, Tuple

import i18nparse  # type: ignore
import importlib_resources
from platformdirs import user_data_dir

from .event import handle_global_keys, handle_quit_event, quit_game
from .langdetect import language_code
from .screen import Screen
from .warnings_util import die, simple_warning

# Fix type checking for aenum
if TYPE_CHECKING:
    from enum import Enum
else:
    from aenum import Enum

# Import pygame, suppressing extra messages that it prints on startup.
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import pygame


locale.setlocale(locale.LC_ALL, "")

metadata = importlib.metadata.metadata("chambercourt")
VERSION = importlib.metadata.version("chambercourt")

# Try to set LANG for gettext if not already set
if not "LANG" in os.environ:
    lang = language_code()
    if lang is not None:
        os.environ["LANG"] = lang
i18nparse.activate()

# Set app name for SDL
os.environ["SDL_APP_NAME"] = metadata["Name"]

# Placeholder for gettext
_: Callable[[str], str] = lambda _: _

# Import pygame, suppressing extra messages that it prints on startup.
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import pygame
    import pyscroll  # type: ignore
    import pytmx  # type: ignore
    from pygame import Vector2


DATA_DIR = Path(user_data_dir("chambercourt"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
SAVED_POSITION_FILE = DATA_DIR / "saved_position.pkl"


FRAMES_PER_SECOND = 30
SUBFRAMES = 4


def clear_keys() -> None:
    for _event in pygame.event.get(pygame.KEYDOWN):
        pass


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


DEFAULT_VOLUME = 0.6


# We would like to use StrEnum + auto, but aenum does not support
# extend_enum on StrEnums.
class Tile(Enum):
    EMPTY = "empty"
    BRICK = "brick"
    HERO = "hero"


class Game:
    def __init__(
        self,
        screen: Screen,
        max_window_size: Tuple[int, int],
        levels_path: os.PathLike[str],
        hero_image: pygame.Surface,
        die_image: pygame.Surface,
        die_sound: pygame.mixer.Sound,
    ) -> None:
        self.max_window_size = max_window_size
        self.window_pixel_width: int
        self.window_pixel_height: int
        self.screen = screen
        self.window_scaled_width: int
        self.window_pos = (0, 0)
        self.game_surface: pygame.Surface
        self.hero_image = hero_image
        self.die_image = die_image
        self.die_sound = die_sound
        self.quit = False
        self.dead = False
        self.level = 1
        self.level_width: int
        self.level_height: int
        self.block_pixels: int
        self._map_blocks: pytmx.TiledTileLayer
        self._gids: dict[Tile, int]
        self._map_layer: pyscroll.BufferedRenderer
        self._group: pyscroll.PyscrollGroup
        self.hero: Hero
        self.map_data: pyscroll.data.TiledMapData
        self._joysticks: dict[int, pygame.joystick.JoystickType] = {}

        # Load levels
        try:
            real_levels_path: Path
            if zipfile.is_zipfile(levels_path):
                tmpdir = TemporaryDirectory()  # pylint: disable=consider-using-with
                real_levels_path = Path(tmpdir.name)
                with zipfile.ZipFile(levels_path) as z:
                    z.extractall(real_levels_path)
                atexit.register(lambda tmpdir: tmpdir.cleanup(), tmpdir)
            else:
                real_levels_path = Path(levels_path)
            self.levels_files = sorted(
                [item for item in real_levels_path.iterdir() if item.suffix == ".tmx"]
            )
        except IOError as err:
            die(_("Error reading levels: {}").format(err.strerror))
        self.levels = len(self.levels_files)
        if self.levels == 0:
            die(_("Could not find any levels"))

    @staticmethod
    def description() -> str:
        return "Play a game."

    @staticmethod
    def instructions() -> str:
        return "Game instructions go here."

    @staticmethod
    def screen_size() -> Tuple[int, int]:
        return (1024, 768)

    @staticmethod
    def window_size() -> Tuple[int, int]:
        return (640, 480)

    @staticmethod
    def load_assets(_levels_path: Path) -> None:
        pass

    def init_renderer(self) -> None:
        self._map_layer = pyscroll.BufferedRenderer(
            self.map_data, (self.window_pixel_width, self.window_pixel_height)
        )
        self._group = pyscroll.PyscrollGroup(map_layer=self._map_layer)
        self._group.add(self.hero)

    def restart_level(self) -> None:
        self.dead = False
        tmx_data = pytmx.load_pygame(self.levels_files[self.level - 1])
        self.map_data = pyscroll.data.TiledMapData(tmx_data)
        self._map_blocks = self.map_data.tmx.layers[0].data
        # FIXME: The level dimensions should be per-level, not class properties.
        (self.level_width, self.level_height) = self.map_data.map_size
        # FIXME: Report error if tiles are not square
        assert self.map_data.tile_size[0] == self.map_data.tile_size[1]
        self.block_pixels = self.map_data.tile_size[0]
        self.window_pixel_width = min(
            self.level_width * self.block_pixels,
            self.max_window_size[0],
        )
        self.window_pixel_height = min(
            self.level_height * self.block_pixels,
            self.max_window_size[1],
        )
        self.window_scaled_width = self.window_pixel_width * self.screen.window_scale
        self.game_surface = pygame.Surface(
            (self.window_pixel_width, self.window_pixel_height)
        )

        # Dict mapping tileset GIDs to map gids
        map_gids = self.map_data.tmx.gidmap
        self._gids = {}
        for i in map_gids:
            gid = map_gids[i][0][0]
            tile = Tile(self.map_data.tmx.get_tile_properties_by_gid(gid)["type"])
            self._gids[tile] = gid

        self.hero = Hero(self.hero_image)
        self.hero.position = Vector2(0, 0)

        self.init_renderer()
        self.init_physics()

    def start_level(self) -> None:
        self.restart_level()
        self.save_position()

    def get(self, pos: Vector2) -> Tile:
        # Anything outside the map is a brick
        x, y = int(pos.x), int(pos.y)
        if not ((0 <= x < self.level_width) and (0 <= y < self.level_height)):
            return Tile.BRICK
        block = self._map_blocks[y][x]
        if block == 0:  # Missing tiles are gaps
            block = Tile.EMPTY
        return Tile(self.map_data.tmx.get_tile_properties(x, y, 0)["type"])

    def _set(self, pos: Vector2, tile: Tile) -> None:
        self._map_blocks[int(pos.y)][int(pos.x)] = self._gids[tile]
        # Update rendered map
        # FIXME: We invoke protected methods and access protected members.
        ml = self._map_layer
        rect = (int(pos.x), int(pos.y), 1, 1)
        # pylint: disable-next=protected-access
        ml._tile_queue = chain(ml._tile_queue, ml.data.get_tile_images_by_rect(rect))
        # pylint: disable-next=protected-access
        self._map_layer._flush_tile_queue(self._map_layer._buffer)

    def set(self, pos: Vector2, tile: Tile) -> None:
        # Update map twice, to allow for transparent tiles
        self._set(pos, Tile.EMPTY)
        self._set(pos, tile)

    def save_position(self) -> None:
        self.set(self.hero.position, Tile.HERO)
        with open(SAVED_POSITION_FILE, "wb") as fh:
            pickle.dump(self._map_blocks, fh)

    def load_position(self) -> None:
        if SAVED_POSITION_FILE.exists():
            with open(SAVED_POSITION_FILE, "rb") as fh:
                self._map_blocks = pickle.load(fh)
            self.map_data.tmx.layers[0].data = self._map_blocks
            self.init_renderer()
            self.init_physics()

    def draw(self) -> None:
        self._group.center(self.hero.rect.center)
        self._group.draw(self.game_surface)

    def handle_joysticks(self) -> Tuple[int, int]:
        for event in pygame.event.get(pygame.JOYDEVICEADDED):
            joy = pygame.joystick.Joystick(event.device_index)
            self._joysticks[joy.get_instance_id()] = joy

        for event in pygame.event.get(pygame.JOYDEVICEREMOVED):
            del self._joysticks[event.instance_id]

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
        return (dx, dy)

    def handle_input(self) -> None:
        pressed = pygame.key.get_pressed()
        dx, dy = (0, 0)
        if pressed[pygame.K_LEFT] or pressed[pygame.K_z]:
            dx -= 1
        if pressed[pygame.K_RIGHT] or pressed[pygame.K_x]:
            dx += 1
        if pressed[pygame.K_UP] or pressed[pygame.K_QUOTE]:
            dy -= 1
        if pressed[pygame.K_DOWN] or pressed[pygame.K_SLASH]:
            dy += 1
        (jdx, jdy) = self.handle_joysticks()
        if (jdx, jdy) != (0, 0):
            (dx, dy) = (jdx, jdy)
        if dx != 0 and self.can_move(Vector2(dx, 0)):
            self.hero.velocity = Vector2(dx, 0)
        elif dy != 0 and self.can_move(Vector2(0, dy)):
            self.hero.velocity = Vector2(0, dy)
        if pressed[pygame.K_l]:
            self.screen.flash_background()
            self.load_position()
        elif pressed[pygame.K_s]:
            self.screen.flash_background()
            self.save_position()
        if pressed[pygame.K_r]:
            self.screen.flash_background()
            self.restart_level()
        if pressed[pygame.K_q]:
            self.quit = True

    def die(self) -> None:
        self.die_sound.play()
        self.game_surface.blit(
            self.die_image,
            self.game_to_screen(int(self.hero.position.x), int(self.hero.position.y)),
        )
        self.show_status()
        self.screen.surface.blit(
            self.screen.scale_surface(self.game_surface), self.window_pos
        )
        self.screen.show_screen()
        pygame.time.wait(1000)
        self.dead = False

    def game_to_screen(self, x: int, y: int) -> Tuple[int, int]:
        origin = self._map_layer.get_center_offset()
        return (origin[0] + x * self.block_pixels, origin[1] + y * self.block_pixels)

    def splurge(self, sprite: pygame.Surface) -> None:
        """Fill the game area with one sprite."""
        for x in range(self.level_width):
            for y in range(self.level_height):
                self.game_surface.blit(sprite, self.game_to_screen(x, y))
        self.screen.surface.blit(
            self.screen.scale_surface(self.game_surface), self.window_pos
        )
        self.screen.show_screen()
        pygame.time.wait(3000)

    def title_screen(self, title_image: pygame.Surface, instructions: str) -> int:
        """Show instructions and choose start level."""
        clear_keys()
        level = 0
        clock = pygame.time.Clock()
        instructions_y = 14
        start_level_y = (
            instructions_y
            + len(instructions.split("\n\n\n", maxsplit=1)[0].split("\n"))
            + 1
        )
        play = False
        while not play:
            self.screen.reinit_screen()
            self.screen.surface.blit(
                self.screen.scale_surface(title_image),
                (
                    (
                        self.screen_size()[0]
                        - title_image.get_width() * self.screen.window_scale
                    )
                    // 2,
                    20 * self.screen.window_scale,
                ),
            )
            self.screen.print_screen((0, 14), instructions, color="grey")
            self.screen.print_screen(
                (0, start_level_y),
                _("Start level: {}/{}").format(1 if level == 0 else level, self.levels),
                width=self.screen.surface.get_width(),
                align="center",
            )
            pygame.display.flip()
            handle_quit_event()
            for event in pygame.event.get(pygame.KEYDOWN):
                if event.key == pygame.K_q:
                    quit_game()
                elif event.key == pygame.K_SPACE:
                    play = True
                elif event.key in (
                    pygame.K_z,
                    pygame.K_LEFT,
                    pygame.K_SLASH,
                    pygame.K_DOWN,
                ):
                    level = max(1, level - 1)
                elif event.key in (
                    pygame.K_x,
                    pygame.K_RIGHT,
                    pygame.K_QUOTE,
                    pygame.K_UP,
                ):
                    level = min(self.levels, level + 1)
                elif event.key in DIGIT_KEYS:
                    level = min(self.levels, level * 10 + DIGIT_KEYS[event.key])
                else:
                    level = 0
                handle_global_keys(event)
            clock.tick(FRAMES_PER_SECOND)
        return max(min(level, self.levels), 1)

    def run(self, level: int) -> None:
        self.quit = False
        self.level = level
        clock = pygame.time.Clock()
        while not self.quit and self.level <= self.levels:
            self.start_level()
            self.show_status()
            self.screen.surface.blit(
                self.screen.scale_surface(self.game_surface), self.window_pos
            )
            self.screen.show_screen()
            while not self.quit and not self.finished():
                self.load_position()
                subframe = 0
                while not self.quit and not self.dead and not self.finished():
                    clock.tick(FRAMES_PER_SECOND)
                    for event in pygame.event.get():
                        if event.type == pygame.QUIT:
                            quit_game()
                        elif event.type == pygame.KEYDOWN:
                            handle_global_keys(event)
                        elif event.type == pygame.JOYDEVICEADDED:
                            joy = pygame.joystick.Joystick(event.device_index)
                            self._joysticks[joy.get_instance_id()] = joy
                        elif event.type == pygame.JOYDEVICEREMOVED:
                            del self._joysticks[event.instance_id]
                    if self.hero.velocity == Vector2(0, 0):
                        self.handle_input()
                        if self.hero.velocity != Vector2(0, 0):
                            self.do_move()
                            subframe = 0
                    self._group.update(1 / SUBFRAMES)
                    if subframe == SUBFRAMES - 1:
                        self.do_physics()
                    self.draw()
                    self.show_status()
                    self.screen.surface.blit(
                        self.screen.scale_surface(self.game_surface), self.window_pos
                    )
                    self.screen.show_screen()
                    subframe = (subframe + 1) % SUBFRAMES
                    if subframe == 0:
                        self.hero.velocity = Vector2(0, 0)
                if self.dead:
                    self.die()
            if self.finished():
                self.level += 1
        if self.level > self.levels:
            self.splurge(self.hero.image)

    def init_physics(self) -> None:
        for x in range(self.level_width):
            for y in range(self.level_height):
                block = self.get(Vector2(x, y))
                if block == Tile.HERO:
                    self.hero.position = Vector2(x, y)
                    self.set(self.hero.position, Tile.EMPTY)

    def do_physics(self) -> None:
        pass

    def can_move(self, velocity: Vector2) -> bool:
        newpos = self.hero.position + velocity
        return (0 <= newpos.x < self.level_width) and (
            0 <= newpos.y < self.level_height
        )

    def do_move(self) -> None:
        pass

    def show_status(self) -> None:
        self.screen.print_screen(
            (0, 0),
            _("Level {}:").format(self.level)
            + " "
            + self.map_data.tmx.properties["Title"],
            width=self.screen.surface.get_width(),
            align="center",
            color="grey",
        )

    def finished(self) -> bool:
        return False


class Hero(pygame.sprite.Sprite):  # pylint: disable=too-few-public-methods
    def __init__(self, image: pygame.Surface) -> None:
        pygame.sprite.Sprite.__init__(self)
        self.image = image
        self.velocity = Vector2(0, 0)
        self.position = Vector2(0, 0)
        self.rect = self.image.get_rect()
        assert self.image.get_width() == self.image.get_height()
        self.block_pixels = self.image.get_width()

    def update(self, dt: float) -> None:
        self.position += self.velocity * dt
        screen_pos = self.position * self.block_pixels
        self.rect.topleft = (int(screen_pos.x), int(screen_pos.y))


def app_main(
    argv: List[str],
    game_package_name: str,
    app_game_module: types.ModuleType,
    game_class: type[Game],
) -> None:
    global _

    # Internationalise this module.
    with importlib_resources.as_file(importlib_resources.files()) as path:
        cat = gettext.translation("chambercourt", path / "locale", fallback=True)
        _ = cat.gettext

    with importlib_resources.as_file(
        importlib_resources.files(app_game_module)
    ) as path:
        # Internationalise the game module.
        app_cat = gettext.translation(game_package_name, path / "locale", fallback=True)
        app_game_module._ = app_cat.gettext  # type: ignore[attr-defined]

        # Command-line arguments
        parser = argparse.ArgumentParser(description=game_class.description())
        parser.add_argument(
            "--levels",
            metavar="DIRECTORY",
            help=_("a directory or Zip file of levels to use"),
        )
        parser.add_argument(
            "-V",
            "--version",
            action="version",
            version=_("%(prog)s {} by {}").format(VERSION, metadata["Author-email"]),
        )
        warnings.showwarning = simple_warning(parser.prog)
        args = parser.parse_args(argv)

        levels_path = Path(args.levels or path / "levels")

        # Load assets.
        app_icon = pygame.image.load(path / "app-icon.png")
        title_image = pygame.image.load(path / "title.png")
        hero_image = pygame.image.load(levels_path / "Hero.png")
        die_image = pygame.image.load(levels_path / "Die.png")

        pygame.init()
        pygame.display.set_icon(app_icon)
        pygame.mouse.set_visible(False)
        pygame.font.init()
        pygame.key.set_repeat()
        pygame.joystick.init()
        pygame.display.set_caption(metadata["Name"])
        screen = Screen(game_class.screen_size(), str(path / "acorn-mode-1.ttf"), 2)
        die_sound = pygame.mixer.Sound(levels_path / "Die.wav")
        die_sound.set_volume(DEFAULT_VOLUME)
        game_class.load_assets(levels_path)
        game = game_class(
            screen,
            game_class.window_size(),
            levels_path,
            hero_image,
            die_image,
            die_sound,
        )

    try:
        while True:
            level = game.title_screen(
                title_image.convert(),
                game_class.instructions(),
            )
            game.run(level)
    except KeyboardInterrupt:
        quit_game()
