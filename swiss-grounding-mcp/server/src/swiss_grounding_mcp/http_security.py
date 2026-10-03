from __future__ import annotations

import hmac
import threading
import time
from collections import deque
from collections.abc import Callable, Mapping


class SlidingWindowRateLimiter:
    def __init__(
        self,
        limit: int,
        window_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._clock = clock
        self._requests: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str) -> float | None:
        if self.limit <= 0:
            return None

        now = self._clock()
        cutoff = now - self.window_seconds
        with self._lock:
            for stored_key, timestamps in list(self._requests.items()):
                while timestamps and timestamps[0] <= cutoff:
                    timestamps.popleft()
                if not timestamps:
                    del self._requests[stored_key]

            timestamps = self._requests.setdefault(key, deque())
            if len(timestamps) >= self.limit:
                return max(timestamps[0] + self.window_seconds - now, 1e-9)

            timestamps.append(now)
            return None

    def reset(self) -> None:
        with self._lock:
            self._requests.clear()


def client_ip(
    headers: Mapping[str, str], peer: str | None, trusted_header: str
) -> str:
    if trusted_header:
        header_name = trusted_header.casefold()
        for name, value in headers.items():
            if name.casefold() == header_name:
                return value.split(",", 1)[0].strip()
    return peer or "unknown"


def bearer_token_matches(authorization: str | None, expected: str) -> bool:
    if not authorization or not expected:
        return False

    parts = authorization.strip().split()
    if len(parts) != 2 or parts[0].casefold() != "bearer":
        return False
    return hmac.compare_digest(parts[1].encode(), expected.encode())


def redact(text: str, *secrets: str) -> str:
    for secret in sorted((value for value in secrets if value), key=len, reverse=True):
        text = text.replace(secret, "***")
    return text
