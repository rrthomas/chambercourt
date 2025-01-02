# © Reuben Thomas <rrt@sc3d.org> 2024
# Released under the GPL version 3, or (at your option) any later version.

import re
import sys
from typing import List

from . import game
from .game import app_main


def main(argv: List[str] = sys.argv[1:]) -> None:
    app_main(argv, "chambercourt", game, game.Game)


if __name__ == "__main__":
    sys.argv[0] = re.sub(r"__init__.py$", "chambercourt", sys.argv[0])
    main()
