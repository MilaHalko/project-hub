import math
import time
from collections import deque
from collections.abc import Callable
from typing import Self

from project_hub.core.config import Settings

Clock = Callable[[], float]

_SWEEP_ABOVE_KEYS = 10_000


class LoginThrottle:
    def __init__(
        self,
        max_login_failures: int,
        max_ip_failures: int,
        window_seconds: int,
        clock: Clock = time.monotonic,
    ) -> None:
        self._max_login = max_login_failures
        self._max_ip = max_ip_failures
        self._window = window_seconds
        self._clock = clock
        self._by_login: dict[str, deque[float]] = {}
        self._by_ip: dict[str, deque[float]] = {}

    @classmethod
    def from_settings(cls, settings: Settings, clock: Clock = time.monotonic) -> Self:
        return cls(
            settings.login_max_failures,
            settings.login_ip_max_failures,
            settings.login_window_seconds,
            clock,
        )

    def reserve(self, login: str, ip: str) -> int | None:
        """Callers must reserve before the password check: parallel guesses would otherwise all
        pass this check while the first hash is still running."""
        now = self._clock()
        if len(self._by_login) + len(self._by_ip) > _SWEEP_ABOVE_KEYS:
            self._sweep(now)
        waits = [
            wait
            for wait in (
                self._wait(self._by_login, login, self._max_login, now),
                self._wait(self._by_ip, ip, self._max_ip, now),
            )
            if wait is not None
        ]
        if waits:
            return max(waits)
        self._by_login.setdefault(login, deque()).append(now)
        self._by_ip.setdefault(ip, deque()).append(now)
        return None

    def forgive(self, login: str, ip: str) -> None:
        self._by_login.pop(login, None)
        attempts = self._by_ip.get(ip)
        if attempts:
            attempts.pop()
            if not attempts:
                del self._by_ip[ip]

    def _wait(self, store: dict[str, deque[float]], key: str, limit: int, now: float) -> int | None:
        attempts = store.get(key)
        if attempts is None:
            return None
        self._expire(attempts, now)
        if not attempts:
            del store[key]
            return None
        if len(attempts) < limit:
            return None
        return max(1, math.ceil(attempts[-limit] + self._window - now))

    def _expire(self, attempts: deque[float], now: float) -> None:
        while attempts and now - attempts[0] >= self._window:
            attempts.popleft()

    def _sweep(self, now: float) -> None:
        for store in (self._by_login, self._by_ip):
            for key in list(store):
                self._expire(store[key], now)
                if not store[key]:
                    del store[key]
