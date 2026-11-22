"""Push-to-talk: only audio captured while a button is held reaches the recognizer.

The gate keeps a short pre-roll (people start talking as they press) and a short tail
after release (the end of the word), then forces a final result.
"""
from __future__ import annotations

import threading
from collections import deque

MOUSE_BUTTONS = {"x1", "x2", "middle"}  # left/right are excluded: you shoot with those


class BindingError(ValueError):
    pass


def parse_binding(spec: str) -> tuple[str, str]:
    """'mouse:x2' -> ('mouse', 'x2'); 'key:f13' -> ('key', 'f13'); 'key:v' -> ('key', 'v')."""
    kind, sep, name = spec.strip().lower().partition(":")
    if not sep or not name:
        raise BindingError(f"push_to_talk must look like 'mouse:x2' or 'key:f13', got '{spec}'")
    if kind == "mouse":
        if name not in MOUSE_BUTTONS:
            raise BindingError(f"mouse button must be one of {sorted(MOUSE_BUTTONS)}, got '{name}'")
    elif kind != "key":
        raise BindingError(f"push_to_talk kind must be 'mouse' or 'key', got '{kind}'")
    return kind, name


class PushToTalkGate:
    def __init__(self, pre_roll_blocks: int = 3, tail_seconds: float = 0.3):
        self._pre: deque[bytes] = deque(maxlen=pre_roll_blocks)
        self._tail = tail_seconds
        self._state = "idle"
        self._released_at = 0.0

    def feed(self, block: bytes, held: bool, now: float) -> tuple[list[bytes], bool]:
        """Returns (audio blocks to recognize, whether to finalize the utterance now)."""
        if self._state == "idle":
            if held:
                self._state = "active"
                out = [*self._pre, block]
                self._pre.clear()
                return out, False
            self._pre.append(block)
            return [], False
        if held:
            self._state = "active"
            return [block], False
        if self._state == "active":
            self._state = "tail"
            self._released_at = now
            return [block], False
        if now - self._released_at >= self._tail:  # tail finished
            self._state = "idle"
            self._pre.append(block)
            return [], True
        return [block], False


class ButtonState:
    """Watches a mouse button or key system-wide (the same way Discord's push-to-talk
    does). It only listens; the press still reaches the game, so bind a button the
    game doesn't use."""

    def __init__(self, spec: str):
        self.kind, self.name = parse_binding(spec)
        self._held = threading.Event()
        self._listener = None

    def is_held(self) -> bool:
        return self._held.is_set()

    def start(self) -> None:
        if self.kind == "mouse":
            from pynput import mouse

            target = getattr(mouse.Button, self.name)

            def on_click(_x, _y, button, pressed):
                if button == target:
                    (self._held.set if pressed else self._held.clear)()

            self._listener = mouse.Listener(on_click=on_click)
        else:
            from pynput import keyboard

            if len(self.name) == 1:
                target = keyboard.KeyCode.from_char(self.name)
            else:
                try:
                    target = getattr(keyboard.Key, self.name)
                except AttributeError:
                    raise BindingError(f"unknown key '{self.name}'") from None

            def matches(key):
                return key == target or (
                    isinstance(key, keyboard.KeyCode) and key.char and key.char.lower() == self.name
                )

            self._listener = keyboard.Listener(
                on_press=lambda k: matches(k) and self._held.set(),
                on_release=lambda k: matches(k) and self._held.clear(),
            )
        self._listener.daemon = True
        self._listener.start()
