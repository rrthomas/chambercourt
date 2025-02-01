"""ChamberCourt: Barebones derived game class.

© Reuben Thomas <rrt@sc3d.org> 2024
Released under the GPL version 3, or (at your option) any later version.
"""

from enum import StrEnum, auto

from .game import Game


class Tile(StrEnum):
    """An enumeration representing the available map tiles."""

    EMPTY = auto()
    BRICK = auto()
    JEWEL = auto()
    HERO = auto()


class ChambercourtGame(Game[Tile]):
    """A skeleton `Game` class."""

    def __init__(self) -> None:
        """Create a ChambercourtGame object."""
        super().__init__(
            "chambercourt",
            Tile,
            Tile.HERO,
            Tile.EMPTY,
            Tile.BRICK,
        )
