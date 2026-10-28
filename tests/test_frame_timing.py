"""Integration tests: the real game loop, running headless.

These drive `Game.main()` itself, rather than the tickers in isolation, so
they check that the ticker is actually wired into the loop and that the loop
is paced correctly despite the time the game spends drawing each frame.
"""

from __future__ import annotations

import asyncio
import os
import time

import pytest

from chambercourt.frame_ticker import SleepTicker, TimerTicker


pytest.importorskip("pygame")

from chambercourt.chambercourt_game import ChambercourtGame  # noqa: E402


class CountingTicker:
    """Wraps a ticker, recording the wall-clock time of each tick."""

    def __init__(self, inner: object) -> None:
        """Wrap `inner`, recording the wall-clock time of each tick."""
        self.inner = inner
        self.times: list[float] = []

    async def tick(self) -> float:
        """Tick, and record when it happened."""
        dt = await self.inner.tick()  # type: ignore[attr-defined]
        self.times.append(time.monotonic())
        return dt


class BusyTicker:
    """A deliberately spinning ticker, as a control for the CPU tests."""

    async def tick(self) -> float:
        """Spend the whole frame spinning: a control for the CPU tests."""
        deadline = time.monotonic() + 1 / 60
        while time.monotonic() < deadline:
            pass
        await asyncio.sleep(0)
        return 1 / 60


async def run_game(seconds: float, ticker: object | None = None) -> CountingTicker:
    """Run the game for `seconds`, then stop it; return the counting ticker."""
    game = ChambercourtGame()
    if ticker is not None:
        game.frame_ticker = ticker
    counting = CountingTicker(game.frame_ticker)
    game.frame_ticker = counting

    task = asyncio.create_task(game.main([]))
    try:
        await asyncio.sleep(seconds)
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    return counting


def tick_rate(times: list[float]) -> float:
    """Ticks per second, from a list of tick timestamps."""
    assert len(times) >= 2, "the game loop did not tick"
    return (len(times) - 1) / (times[-1] - times[0])


def cpu_ratio(ticker: object, seconds: float = 1.0) -> tuple[float, int]:
    """Return (CPU time / wall time, ticks) for `ticker` running alone."""

    async def run() -> tuple[float, int]:
        wall_start = time.monotonic()
        cpu_start = time.thread_time()
        ticks = 0
        while time.monotonic() - wall_start < seconds:
            await ticker.tick()  # type: ignore[attr-defined]
            ticks += 1
        wall = time.monotonic() - wall_start
        return (time.thread_time() - cpu_start) / wall, ticks

    return asyncio.run(run())


def test_game_loop_is_paced_at_about_60hz() -> None:
    """The desktop ticker, in the real loop, with real rendering."""
    counting = asyncio.run(run_game(2.0))
    rate = tick_rate(counting.times)
    assert 54 <= rate <= 66, f"game ticked at {rate:.1f} Hz"


def test_game_loop_is_paced_at_about_60hz_with_the_browser_ticker() -> None:
    """The browser ticker in the real loop: 60 Hz despite a slow frame."""
    fps = ChambercourtGame().frames_per_second
    counting = asyncio.run(run_game(2.0, TimerTicker(fps)))
    rate = tick_rate(counting.times)
    assert 54 <= rate <= 66, f"game ticked at {rate:.1f} Hz with the web ticker"


def test_game_loop_does_not_miss_whole_frames() -> None:
    """Guard: the loop keeps up, rather than falling a frame behind."""
    fps = ChambercourtGame().frames_per_second
    counting = asyncio.run(run_game(2.0, TimerTicker(fps)))
    intervals = [b - a for a, b in zip(counting.times, counting.times[1:])]
    assert intervals
    assert max(intervals) < 2 / fps, "the loop is missing whole frames"


def test_sleep_ticker_does_not_busy_wait() -> None:
    """The SDL clock sleeps, so it must not burn a core."""
    ratio, ticks = cpu_ratio(SleepTicker(60))
    assert 50 <= ticks <= 66, f"only {ticks} ticks in a second"
    assert ratio < 0.15, f"ticker used {ratio:.0%} of a core"


def test_browser_ticker_does_not_busy_wait() -> None:
    """The browser ticker sleeps, so it must not burn a core."""
    ratio, ticks = cpu_ratio(TimerTicker(60))
    assert 50 <= ticks <= 66, f"only {ticks} ticks in a second"
    assert ratio < 0.15, f"ticker used {ratio:.0%} of a core"


def test_busy_wait_would_be_detected() -> None:
    """Control for the two tests above: the metric must catch a spin."""
    ratio, _ = cpu_ratio(BusyTicker())
    assert ratio > 0.8, f"a spinning ticker only used {ratio:.0%} of a core"


def test_game_runs_without_a_display() -> None:
    """Guard: the headless harness itself must not silently do nothing."""
    assert os.environ["SDL_VIDEODRIVER"] == "dummy"
    counting = asyncio.run(run_game(1.0))
    assert len(counting.times) > 30
