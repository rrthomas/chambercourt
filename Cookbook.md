# ChamberCourt cookbook

_This document is a work in progress; starting from a few notes, I hope to evolve it into a complete guide to writing games with ChamberCourt._

ChamberCourt is an opinionated framework for writing a particular sort of simple game.

It makes the following assumptions:

+ The game takes place on a rectangular grid.
+ Only one thing can occupy any given grid space.
+ Every object in the game, including the protagonist, has integer
  coordinates on the grid. (However, ChamberCourt gives the illusion of
  smooth movement.)

As well as the assumptions, I have adopted some conventions in the games I have written. If you follow these, it will be easier to re-use my code, and yours is more likely to work!

+ The `Game` class is instantiated just once for a game, and its `main` method called, inside which the entire game runs.
