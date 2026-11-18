from __future__ import annotations
import time
from typing import Callable


class CircuitBreaker:
    """Per-model breaker: CLOSED -> OPEN (after N failures) -> HALF_OPEN (after cooldown, 1 probe)."""
    def __init__(self, threshold: int = 2, cooldown_s: float = 30, clock: Callable[[], float] = time.monotonic):
        self.threshold, self.cooldown, self.clock = threshold, cooldown_s, clock
        self.failures = 0
        self.opened_at: float | None = None
        self._probing = False

    @property
    def state(self) -> str:
        if self.opened_at is None: return "closed"
        return "half_open" if self.clock() - self.opened_at >= self.cooldown else "open"

    def allow(self) -> bool:
        s = self.state
        if s == "closed": return True
        if s == "half_open" and not self._probing:
            self._probing = True
            return True
        return False

    def success(self) -> None:
        self.failures, self.opened_at, self._probing = 0, None, False

    def failure(self) -> None:
        self.failures += 1
        self._probing = False
        if self.failures >= self.threshold:
            self.opened_at = self.clock()
