"""ChamberCourt: frame pacing for the game loop.

© Reuben Thomas <rrt@sc3d.org> 2026

Released under the GPL version 3, or (at your option) any later version.

The game loop is fixed-timestep: it must be driven at exactly
`frames_per_second` ticks per second, because animation and physics are
counted in frames, not measured in elapsed time. Each tick was historically
``pygame.time.Clock.tick(fps)`` followed by ``await asyncio.sleep(0)`` to let
the event loop breathe.

That works on the desktop, but not in the browser. There, WebAssembly cannot
block, so ``Clock.tick`` implements its delay by spinning on the clock until
the target time is reached: a busy wait which pins a CPU core for the whole
of the game. ``asyncio.sleep``, by contrast, yields to the browser's event
loop - which is also what gives the browser the chance to paint.

The only genuinely platform-dependent operation is "suspend until the next
frame". This module isolates it behind `FrameTicker.tick`, so that the game
loop itself is identical everywhere.

Note that `requestAnimationFrame` is deliberately *not* used. Awaiting an
animation frame costs a whole display frame of wall-clock time (6.9 ms on a
144 Hz display, 16.7 ms on a 60 Hz one), and the game loop draws *after*
`tick()` returns, so the ticker has only ``period - drawing time`` - about
4 ms for a typical game - in which to wait. Gating every tick on an
animation frame therefore cannot keep up: measured with WinColl, a 60 Hz
display dropped to 34 ticks per second and a 144 Hz display to 51. Using it
would require inverting the loop, so that the animation frame callback
drives the loop rather than being awaited from inside it.
"""

from __future__ import annotations

import asyncio
import sys
import time
from collections.abc import Awaitable, Callable
from typing import Protocol


__all__ = [
    "FrameTicker",
    "SleepTicker",
    "TimerTicker",
    "make_ticker",
]


class FrameTicker(Protocol):
    """Paces the game loop."""

    async def tick(self) -> float:
        """Suspend until the next frame; return elapsed time, in seconds."""
        ...


class SleepTicker:
    """Desktop frame ticker.

    Sleeps until the next frame deadline, using ``pygame.time.Clock`` (which
    accounts for time already spent in the frame) and then yields to the
    event loop. This is exactly the behaviour the game had before, so the
    desktop is unaffected.
    """

    def __init__(self, fps: int, clock: object | None = None) -> None:
        """Create a `SleepTicker` running at `fps` frames per second.

        Args:
            fps (int): frames per second to run at
            clock (object | None): a ``pygame.time.Clock``-like object, for
              reuse and for testing; if `None`, a real clock is created
        """
        self.frames_per_second = fps
        if clock is None:
            import pygame

            clock = pygame.time.Clock()
        self.clock = clock

    async def tick(self) -> float:
        """Sleep until the next frame deadline, then yield."""
        dt_ms = self.clock.tick(self.frames_per_second)  # type: ignore[attr-defined]
        await asyncio.sleep(0)
        return dt_ms / 1000.0


class TimerTicker:
    """Browser frame ticker.

    Sleeps, rather than busy-waiting, until the tick is due: ``asyncio.sleep``
    yields to the browser's event loop, which is also what lets the browser
    paint. Unlike `SleepTicker` it does not need a ``pygame.time.Clock``,
    whose delay cannot block in WebAssembly.
    """

    def __init__(
        self,
        fps: int,
        *,
        sleep: Callable[[float], Awaitable[None]] | None = None,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        """Create a `TimerTicker` running at `fps` frames per second.

        Args:
            fps (int): frames per second to run at
            sleep: suspends for a number of seconds; defaults to
              `asyncio.sleep`. Injectable for testing.
            monotonic: monotonic clock; injectable for testing.
        """
        self.frames_per_second = fps
        self.period = 1.0 / fps
        self._sleep: Callable[[float], Awaitable[None]] = (
            sleep if sleep is not None else asyncio.sleep
        )
        self._monotonic = monotonic
        self._deadline: float | None = None

    async def tick(self) -> float:
        """Sleep until this tick is due.

        The tick is scheduled against an absolute deadline, advanced by one
        period per tick, rather than by sleeping for a fixed time: a timer
        which wakes late then simply shortens the next sleep, instead of
        making every tick late. (For the same reason, the time the loop
        spends drawing the frame comes out of the sleep.)

        If the loop has fallen a whole frame behind - a slow frame, or a
        hidden tab, whose timers the browser throttles - the deadline is
        moved on, so that the debt is dropped rather than repaid as a burst
        of ticks.
        """
        now = self._monotonic()
        if self._deadline is None:
            self._deadline = now
        self._deadline += self.period
        delay = self._deadline - now
        if delay > 0:
            await self._sleep(delay)
            if self._monotonic() > self._deadline + self.period:
                self._deadline = self._monotonic()
        else:
            # Nothing left of this tick to wait for. Yield, so that the
            # browser still gets to paint, but do not wait.
            await self._sleep(0)
            self._deadline = self._monotonic()
        return self.period


def make_ticker(fps: int, clock: object | None = None) -> FrameTicker:
    """Return the frame ticker for the platform we are running on.

    Args:
        fps (int): frames per second to run at
        clock (object | None): a ``pygame.time.Clock``-like object for
          `SleepTicker` to reuse; ignored by the browser ticker
    """
    if sys.platform == "emscripten":
        return TimerTicker(fps)
    return SleepTicker(fps, clock)
