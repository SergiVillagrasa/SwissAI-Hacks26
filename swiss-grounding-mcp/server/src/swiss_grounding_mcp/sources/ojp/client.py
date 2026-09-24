from __future__ import annotations

import httpx

from swiss_grounding_mcp.config.settings import Settings
from swiss_grounding_mcp.domain.models import Connection, StopCandidate, StopEvent
from swiss_grounding_mcp.sources.ojp.xml_builder import (
    build_location_information_request,
    build_stop_event_request,
    build_trip_request,
)
from swiss_grounding_mcp.sources.ojp.xml_parser import (
    has_service_delivery_error,
    parse_location_information_response,
    parse_stop_event_response,
    parse_trip_response,
)


class OjpSourceError(Exception):
    """Raised when the OJP API cannot be reached or reports a failure."""


class OjpClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._http = httpx.Client(timeout=settings.ojp_timeout_seconds)

    def _post(self, body: bytes) -> bytes:
        headers = {
            "Content-Type": "application/xml",
            "Authorization": f"Bearer {self._settings.ojp_api_token}",
        }
        try:
            response = self._http.post(
                self._settings.ojp_base_url, content=body, headers=headers
            )
        except httpx.HTTPError as exc:
            raise OjpSourceError(f"OJP request failed: {exc}") from exc

        if response.status_code < 200 or response.status_code >= 300:
            raise OjpSourceError(
                f"OJP returned HTTP {response.status_code}: {response.text[:200]}"
            )

        error_message = has_service_delivery_error(response.content)
        if error_message is not None:
            raise OjpSourceError(f"OJP reported an error: {error_message}")

        return response.content

    def location_information(self, name: str) -> list[StopCandidate]:
        request_body = build_location_information_request(
            name, self._settings.ojp_requestor_ref
        )
        response_body = self._post(request_body)
        return parse_location_information_response(response_body)

    def trip_request(
        self,
        origin_ref: str,
        destination_ref: str,
        *,
        origin_name: str = "",
        destination_name: str = "",
        departure_time: str | None = None,
        arrival_time: str | None = None,
        number_of_results: int = 3,
    ) -> list[Connection]:
        request_body = build_trip_request(
            origin_ref,
            destination_ref,
            self._settings.ojp_requestor_ref,
            origin_name=origin_name,
            destination_name=destination_name,
            departure_time=departure_time,
            arrival_time=arrival_time,
            number_of_results=number_of_results,
        )
        response_body = self._post(request_body)
        return parse_trip_response(response_body)

    def get_stop_events(
        self,
        stop_ref: str,
        event_type: str = "departure",
        when: str | None = None,
        limit: int = 5,
        *,
        station_name: str = "",
    ) -> list[StopEvent]:
        request_body = build_stop_event_request(
            stop_ref,
            self._settings.ojp_requestor_ref,
            station_name=station_name,
            event_type=event_type,
            when=when,
            number_of_results=limit,
        )
        response_body = self._post(request_body)
        return parse_stop_event_response(response_body, event_type)
