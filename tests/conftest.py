"""Test configuration.

The SDL drivers are forced to their headless stubs *before* pygame is
imported by any test module, so that the game can run without a display or
an audio device.
"""

import os


os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
