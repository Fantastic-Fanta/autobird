# ---------------------------------------------------------------------------
# controller.py — keyboard input simulation via pynput
# ---------------------------------------------------------------------------

import time
from pynput.keyboard import Controller as KeyboardController, Key

import config


class Controller:
    def __init__(self):
        self._kb = KeyboardController()
        self._last_jump = 0.0

    def jump(self):
        """Press and release Space, respecting the cooldown defined in config."""
        now = time.time()
        if now - self._last_jump < config.JUMP_COOLDOWN:
            return
        self._kb.press(Key.space)
        self._kb.release(Key.space)
        self._last_jump = now
