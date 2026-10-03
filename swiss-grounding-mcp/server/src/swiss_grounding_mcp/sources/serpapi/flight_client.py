from __future__ import annotations

import logging

import httpx

from swiss_grounding_mcp.config.settings import Settings
from swiss_grounding_mcp.http_security import redact

logger = logging.getLogger(__name__)


class SerpApiSourceError(Exception):
    pass


class SerpApiFlightClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._http = httpx.Client(timeout=settings.serpapi_timeout_seconds)

    def search_flights(
        self,
        departure_id: str,
        arrival_id: str,
        outbound_date: str,
        currency: str,
    ) -> dict:
        if not self._settings.serpapi_api_key:
            raise SerpApiSourceError(
                "No SerpApi API key configured (SERPAPI_API_KEY is empty)."
            )

        params = {
            "engine": "google_flights",
            "departure_id": departure_id,
            "arrival_id": arrival_id,
            "outbound_date": outbound_date,
            "currency": currency,
            "type": "2",
            "api_key": self._settings.serpapi_api_key,
        }
        try:
            response = self._http.get(self._settings.serpapi_base_url, params=params)
        except httpx.HTTPError as exc:
            logger.warning(
                "SerpApi request failed (%s): %s",
                type(exc).__name__,
                redact(str(exc), self._settings.serpapi_api_key),
            )
            raise SerpApiSourceError(
                f"SerpApi request failed ({type(exc).__name__})."
            ) from exc

        if response.status_code < 200 or response.status_code >= 300:
            logger.warning(
                "SerpApi returned HTTP %s: %s",
                response.status_code,
                redact(response.text[:500], self._settings.serpapi_api_key),
            )
            raise SerpApiSourceError(f"SerpApi returned HTTP {response.status_code}.")

        try:
            body = response.json()
        except ValueError as exc:
            logger.warning(
                "SerpApi response could not be parsed: %s",
                redact(str(exc), self._settings.serpapi_api_key),
            )
            raise SerpApiSourceError("SerpApi response could not be parsed.") from exc

        if not isinstance(body, dict):
            logger.warning(
                "SerpApi returned an unexpected response format: %s",
                redact(response.text[:500], self._settings.serpapi_api_key),
            )
            raise SerpApiSourceError("SerpApi returned an unexpected response format.")
        if body.get("error"):
            logger.warning(
                "SerpApi returned an error: %s",
                redact(response.text[:500], self._settings.serpapi_api_key),
            )
            raise SerpApiSourceError("SerpApi returned an error.")
        return body
