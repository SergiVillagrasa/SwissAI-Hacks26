from __future__ import annotations

import time

import httpx

from swiss_grounding_mcp.config.settings import Settings


class AviationstackSourceError(Exception):
    """Raised when Aviationstack cannot be reached or reports a failure."""


class AviationstackClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._http = httpx.Client(timeout=settings.aviationstack_timeout_seconds)
        self._cache: dict[tuple, tuple[float, dict]] = {}

    def _cache_key(self, params: dict) -> tuple:
        return tuple(sorted(params.items()))

    def get_flights(self, params: dict) -> dict:
        if not self._settings.aviationstack_enable:
            raise AviationstackSourceError(
                "Aviationstack integration is disabled (AVIATIONSTACK_ENABLE=false)."
            )
        if not self._settings.aviationstack_api_key:
            raise AviationstackSourceError(
                "No Aviationstack API key configured (AVIATIONSTACK_API_KEY is empty)."
            )

        cache_key = self._cache_key(params)
        cached = self._cache.get(cache_key)
        if cached is not None:
            cached_at, body = cached
            if time.monotonic() - cached_at < self._settings.aviationstack_cache_seconds:
                return body

        query = {"access_key": self._settings.aviationstack_api_key, **params}
        try:
            response = self._http.get(
                f"{self._settings.aviationstack_base_url}/flights", params=query
            )
        except httpx.HTTPError as exc:
            raise AviationstackSourceError(f"Aviationstack request failed: {exc}") from exc

        if response.status_code < 200 or response.status_code >= 300:
            raise AviationstackSourceError(
                f"Aviationstack returned HTTP {response.status_code}: {response.text[:200]}"
            )

        try:
            body = response.json()
        except ValueError as exc:
            raise AviationstackSourceError(
                f"Aviationstack returned an unparsable response: {exc}"
            ) from exc

        error = body.get("error")
        if error:
            code = error.get("code", "unknown_error")
            message = error.get("message", "no message")
            raise AviationstackSourceError(f"Aviationstack reported an error ({code}): {message}")

        self._cache[cache_key] = (time.monotonic(), body)
        return body
