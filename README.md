# ChamberCourt

https://github.com/rrthomas/chambercourt  

by Reuben Thomas <rrt@sc3d.org>  

ChamberCourt is a framework for simple 2-D grid-based games, based on
[PyGame](https://pygame.org).

It is only intended for use by the author, mostly to resurrect a bunch of
old games he wrote a long time ago. As such, there is no documentation other
than the code. However, if anyone would like to help make it usable by
others, I would be delighted to hear from them. I would prefer to keep it as
simple as possible; however there is room for improvement in many areas. For
example, it would be nice if the games could run on the web (I have
experimented with [pygbag](https://github.com/pygame-web/pygbag/), but I
didn’t get very far yet), and some basic functionality would be nice such as
a UI for rebinding keys.

The package is named after the central courtyard of my school, Winchester
College, because I wrote this package first while resurrecting a game,
[WinColl](https://github.com/rrthomas/wincoll), named after the school.


## Installation and use
 
Install with `pip`: `pip install chambercourt`.

A demonstration front-end is available, called `chambercourt`. You can run
it directly from a Git checkout with `PYTHONPATH=. python -m chambercourt`.


## Creating and editing levels

Levels are created and edited in [Tiled](https://www.mapeditor.org/). All
in-game graphics and sounds are stored in the levels directory by
convention. A demonstration level is in `chambercourt/levels`.

Some notes about level design:

+ A set of levels is numbered according to the lexical order of their file
  names.
+ Levels need exactly one start position, given by placing the hero.


## Copyright and Disclaimer

ChamberCourt is distributed under the GNU Public License version 3, or, at
your option, any later version. See the file COPYING.

THIS PROGRAM IS PROVIDED AS IS, WITH NO WARRANTY. USE IS AT THE USER'S RISK.
Except for the files mentioned below, the package is copyright Reuben
Thomas.

The font “Acorn Mode 1”, which is based on the design of Acorn computers’
system font, is by p1.mark and Reuben Thomas and licensed under CC BY-SA
3.0.

The death buzzer sound effect was adapted from
[Buzzer sounds (Wrong answer/Error) by Breviceps](https://freesound.org/s/493163)
under CC 0.
