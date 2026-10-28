"""Unit tests for the frame tickers.

These are pure: no pygame, no browser, no real sleeping. The clock and the
sleep/tick primitives are injected, so the tests are deterministic and fast.
"""

from __future__ import annotations

import asyncio
import sys

from chambercourt.frame_ticker import SleepTicker, TimerTicker, make_ticker


class VirtualClock:
    """A monotonic clock which only advances when told to."""

    def __init__(self) -> None:
        """Create a clock which starts at zero."""
        self.now = 0.0

    def monotonic(self) -> float:
        """Return the current virtual time."""
        return self.now


class FakeSleep:
    """A `sleep` hook which advances a `VirtualClock`."""

    def __init__(self, clock: VirtualClock) -> None:
        """Create a sleep hook which drives `clock`."""
        self.clock = clock
        self.delays: list[float] = []

    async def __call__(self, delay: float) -> None:
        """Advance the virtual clock by `delay`."""
        assert delay >= 0, f"slept for a negative time: {delay}"
        self.delays.append(delay)
        self.clock.now += delay


class FakeClock:
    """A `pygame.time.Clock`-alike which records the fps it was asked for."""

    def __init__(self, dt_ms: float) -> None:
        """Create a clock which always reports `dt_ms`."""
        self.dt_ms = dt_ms
        self.fps_calls: list[int] = []

    def tick(self, fps: int) -> float:
        """Record the requested frame rate, and report the delay."""
        self.fps_calls.append(fps)
        return self.dt_ms


class Harness:
    """A `TimerTicker` plus the fakes it is wired to."""

    def __init__(self, fps: int = 60) -> None:
        """Wire a `TimerTicker` up to the fakes."""
        self.clock = VirtualClock()
        self.sleep = FakeSleep(self.clock)
        self.ticker = TimerTicker(
            fps, sleep=self.sleep, monotonic=self.clock.monotonic
        )

    def tick(self) -> float:
        """Run a single tick."""
        return asyncio.run(self.ticker.tick())

    def run(self, seconds: float, draw: float = 0.0) -> int:
        """Tick for `seconds` of virtual time, charging `draw` per frame.

        `draw` stands in for the work the game loop does *outside* the
        ticker - rendering, status text and so on - which is the time the
        ticker has to allow for.
        """
        start = self.clock.now
        ticks = 0
        while self.clock.now - start < seconds:
            self.tick()
            self.clock.now += draw
            ticks += 1
            assert ticks < 100_000, "ticker never advanced virtual time"
        return ticks


def test_sleep_ticker_uses_configured_fps_and_returns_seconds() -> None:
    """The ticker uses the fps it was configured with, and reports seconds."""
    clock = FakeClock(16.7)
    ticker = SleepTicker(60, clock=clock)
    dt = asyncio.run(ticker.tick())
    assert clock.fps_calls == [60]
    assert dt == 16.7 / 1000.0


def test_timer_ticker_returns_the_frame_period() -> None:
    """A tick reports the period it is pacing to."""
    assert Harness().tick() == 1 / 60


def test_timer_ticker_first_tick_waits_a_whole_frame() -> None:
    """The first tick waits a whole period, having nothing to allow for."""
    harness = Harness()
    harness.tick()
    assert harness.sleep.delays == [1 / 60]


def test_timer_ticker_paces_at_fps_when_idle() -> None:
    """A loop which draws nothing is paced at exactly the frame rate."""
    ticks = Harness().run(1.0)
    assert 59 <= ticks <= 61, f"idle loop gave {ticks} ticks in a second"


def test_timer_ticker_allows_for_the_time_spent_drawing() -> None:
    """A 12 ms frame must still give 60 ticks a second, not 50."""
    harness = Harness()
    ticks = harness.run(1.0, draw=0.012)
    assert 58 <= ticks <= 61, f"12 ms frame gave {ticks} ticks in a second"
    # After the first tick, the sleeps shrink to make room for the drawing.
    assert harness.sleep.delays[1:]
    assert all(d < 1 / 60 for d in harness.sleep.delays[1:])


def test_timer_ticker_never_sleeps_for_a_negative_time() -> None:
    """FakeSleep asserts this; a range of draw times exercises the branch."""
    for draw in (0.0, 0.005, 0.012, 0.0166, 0.025, 0.1):
        Harness().run(0.5, draw=draw)


def test_timer_ticker_goes_back_to_back_when_frames_overrun() -> None:
    """When drawing takes longer than a frame, we are draw-bound, not paced."""
    harness = Harness()
    ticks = harness.run(1.0, draw=0.025)
    assert 39 <= ticks <= 41, f"25 ms frame gave {ticks} ticks in a second"
    # Behind schedule: yield, but do not pretend to wait.
    behind = [d for d in harness.sleep.delays if d == 0]
    assert behind, "expected at least one bare yield"


def test_timer_ticker_drops_the_debt_after_a_stall() -> None:
    """After a hidden tab, resume at 60 Hz rather than repaying the debt."""
    harness = Harness()
    for _ in range(5):
        harness.tick()
        harness.clock.now += 0.012

    # The tab goes away; the browser throttles timers, so this tick is late.
    harness.clock.now += 5.0
    harness.sleep.delays.clear()
    harness.tick()
    assert harness.sleep.delays == [0], "should yield, not sleep, when late"

    # The tab comes back: pacing must return to 60 Hz at once.
    ticks = harness.run(1.0, draw=0.012)
    assert 58 <= ticks <= 61, f"after the stall, {ticks} ticks in a second"


def test_make_ticker_is_platform_specific(monkeypatch: object) -> None:
    """Emscripten gets the timer ticker; everywhere else the SDL clock."""
    assert isinstance(make_ticker(60), SleepTicker)
    monkeypatch.setattr(sys, "platform", "emscripten")  # type: ignore[attr-defined]
    assert isinstance(make_ticker(60), TimerTicker)
