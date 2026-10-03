from __future__ import annotations

import logging
import time

import httpx

from swiss_grounding_mcp.config.settings import Settings
from swiss_grounding_mcp.http_security import redact

logger = logging.getLogger(__name__)


class AerodataboxSourceError(Exception):
    """Raised when AeroDataBox cannot be reached or reports a failure."""


class AerodataboxClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._http = httpx.Client(timeout=settings.aerodatabox_timeout_seconds)
        self._cache: dict[tuple, tuple[float, object]] = {}

    def _headers(self) -> dict[str, str]:
        return {
            "x-rapidapi-key": self._settings.aerodatabox_api_key,
            "x-rapidapi-host": self._settings.aerodatabox_host,
        }

    def _get(self, path: str, params: dict | None = None) -> object:
        if not self._settings.aerodatabox_enable:
            raise AerodataboxSourceError(
                "AeroDataBox integration is disabled (AERODATABOX_ENABLE=false)."
            )
        if not self._settings.aerodatabox_api_key:
            raise AerodataboxSourceError(
                "No AeroDataBox API key configured (AERODATABOX_API_KEY is empty)."
            )

        cache_key = (path, tuple(sorted((params or {}).items())))
        cached = self._cache.get(cache_key)
        if cached is not None:
            cached_at, body = cached
            if time.monotonic() - cached_at < self._settings.aerodatabox_cache_seconds:
                return body

        url = f"{self._settings.aerodatabox_base_url}{path}"
        try:
            response = self._http.get(url, params=params, headers=self._headers())
        except httpx.HTTPError as exc:
            logger.warning(
                "AeroDataBox request failed (%s): %s",
                type(exc).__name__,
                redact(str(exc), self._settings.aerodatabox_api_key),
            )
            raise AerodataboxSourceError(
                f"AeroDataBox request failed ({type(exc).__name__})."
            ) from exc

        if response.status_code < 200 or response.status_code >= 300:
            logger.warning(
                "AeroDataBox returned HTTP %s: %s",
                response.status_code,
                redact(response.text[:500], self._settings.aerodatabox_api_key),
            )
            raise AerodataboxSourceError(
                f"AeroDataBox returned HTTP {response.status_code}."
            )

        # AeroDataBox returns HTTP 204 with an empty body for "no matching
        # flight", not a 2xx with an empty array/object. This is a valid
        # "no match" result, not a provider failure.
        if response.status_code == 204 or not response.content:
            body = None
        else:
            try:
                body = response.json()
            except ValueError as exc:
                logger.warning(
                    "AeroDataBox returned an unparsable response: %s",
                    redact(str(exc), self._settings.aerodatabox_api_key),
                )
                raise AerodataboxSourceError(
                    "AeroDataBox returned an unparsable response."
                ) from exc

        self._cache[cache_key] = (time.monotonic(), body)
        return body

    def get_flight_by_number(self, flight_number: str, date_local: str) -> list[dict]:
        path = f"/flights/number/{flight_number}/{date_local}"
        params = {"dateLocalRole": "Both", "withLocation": "false"}
        body = self._get(path, params)
        return body if isinstance(body, list) else []

    def get_airport_flights(
        self,
        code_type: str,
        code: str,
        from_local: str,
        to_local: str,
        *,
        direction: str = "Both",
    ) -> dict:
        path = f"/flights/airports/{code_type}/{code}/{from_local}/{to_local}"
        params = {
            "direction": direction,
            "withLeg": "true",
            "withCancelled": "true",
            "withCodeshared": "true",
            "withCargo": "false",
            "withPrivate": "false",
            "withLocation": "false",
        }
        body = self._get(path, params)
        return body if isinstance(body, dict) else {}
