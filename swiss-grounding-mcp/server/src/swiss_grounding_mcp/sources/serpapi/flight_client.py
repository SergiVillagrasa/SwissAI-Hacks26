from __future__ import annotations

import httpx

from swiss_grounding_mcp.config.settings import Settings


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
            raise SerpApiSourceError(f"SerpApi request failed: {exc}") from exc

        if response.status_code < 200 or response.status_code >= 300:
            raise SerpApiSourceError(
                f"SerpApi returned HTTP {response.status_code}: {response.text[:200]}"
            )

        try:
            body = response.json()
        except ValueError as exc:
            raise SerpApiSourceError(f"SerpApi returned an unparsable response: {exc}") from exc

        if not isinstance(body, dict):
            raise SerpApiSourceError("SerpApi returned an unexpected response format.")
        if body.get("error"):
            raise SerpApiSourceError(f"SerpApi returned an error: {body['error']}")
        return body
