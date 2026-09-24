from __future__ import annotations

import httpx

from swiss_grounding_mcp.config.settings import Settings
from swiss_grounding_mcp.domain.models import Connection, FareProduct, StopCandidate, StopEvent
from swiss_grounding_mcp.sources.ojp.xml_builder import (
    build_fare_request,
    build_location_information_request,
    build_stop_event_request,
    build_trip_request,
)
from swiss_grounding_mcp.sources.ojp.xml_parser import (
    has_service_delivery_error,
    parse_fare_response,
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

    def _post(self, body: bytes, *, url: str | None = None) -> bytes:
        headers = {
            "Content-Type": "application/xml",
            "Authorization": f"Bearer {self._settings.ojp_api_token}",
        }
        target_url = url or self._settings.ojp_base_url
        try:
            response = self._http.post(target_url, content=body, headers=headers)
        except httpx.HTTPError as exc:
            raise OjpSourceError(f"OJP request failed: {exc}") from exc

        if response.status_code < 200 or response.status_code >= 300:
            raise OjpSourceError(
                f"OJP returned HTTP {response.status_code}: {response.text[:200]}"
            )

        try:
            error_message = has_service_delivery_error(response.content)
        except Exception as exc:
            raise OjpSourceError(f"OJP response could not be parsed: {exc}") from exc
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

    def fare_request(
        self,
        origin_ref: str,
        destination_ref: str,
        *,
        origin_name: str = "",
        destination_name: str = "",
        departure_time: str | None = None,
        travel_class: str = "2",
        discount_card: str | None = None,
    ) -> list[FareProduct]:
        request_body = build_fare_request(
            origin_ref,
            destination_ref,
            self._settings.ojp_requestor_ref,
            origin_name=origin_name,
            destination_name=destination_name,
            departure_time=departure_time,
            travel_class=travel_class,
            discount_card=discount_card,
        )
        try:
            response_body = self._post(
                request_body, url=self._settings.ojp_fare_url
            )
        except OjpSourceError:
            return []
        try:
            return parse_fare_response(response_body)
        except Exception:
            return []

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
