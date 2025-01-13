"""ChamberCourt 2D grid game framework, based on PyGame.

© Reuben Thomas <rrt@sc3d.org> 2024
Released under the GPL version 3, or (at your option) any later version.
"""

import re
import sys

from .chambercourt_game import ChambercourtGame


def main(argv: list[str] = sys.argv[1:]) -> None:
    """Main function for ChamberCourt bare-bones demo game.

    Args:
        argv (str, optional): command-line parameters. Defaults to
          sys.argv[1:].
    """
    ChambercourtGame().main(argv)


if __name__ == "__main__":
    sys.argv[0] = re.sub(r"__init__.py$", "chambercourt", sys.argv[0])
    main()
