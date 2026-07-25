from __future__ import annotations

import os
from typing import Any, Dict, Iterable, Optional

import requests

from flight_search.providers.base import FlightSearchProvider


class FlightApiProvider(FlightSearchProvider):
    name = "flightapi"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://api.flightapi.io",
        timeout: int = 30,
    ):
        self.api_key = (
            api_key
            or os.getenv("FLIGHTAPI_API_KEY")
        )

        if not self.api_key:
            raise ValueError(
                "FLIGHTAPI_API_KEY not found."
            )

        self.base_url = (
            base_url.rstrip("/")
        )

        self.timeout = timeout

        self.session = (
            requests.Session()
        )

    def _roundtrip_url(
        self,
        departure_id: str,
        arrival_id: str,
        outbound_date: str,
        return_date: str,
        adults: int = 1,
        children: int = 0,
        infants: int = 0,
        cabin: str = "Economy",
        currency: str = "INR",
    ) -> str:

        return (
            f"{self.base_url}/roundtrip/"
            f"{self.api_key}/"
            f"{departure_id}/"
            f"{arrival_id}/"
            f"{outbound_date}/"
            f"{return_date}/"
            f"{adults}/"
            f"{children}/"
            f"{infants}/"
            f"{cabin}/"
            f"{currency}"
        )

    def search_round_trip(
        self,
        departure_id: str,
        arrival_id: str,
        outbound_date: str,
        return_date: str,
    ) -> Dict[str, Any]:

        url = self._roundtrip_url(
            departure_id=departure_id,
            arrival_id=arrival_id,
            outbound_date=outbound_date,
            return_date=return_date,
        )

        response = self.session.get(
            url,
            timeout=self.timeout,
        )

        response.raise_for_status()

        return response.json()

    @staticmethod
    def _iter_dicts_with_price(
        payload: Any,
    ) -> Iterable[Dict[str, Any]]:

        if isinstance(
            payload,
            dict,
        ):

            price = payload.get(
                "price"
            )

            if isinstance(
                price,
                (int, float),
            ):

                yield payload

            for value in payload.values():

                yield from (
                    FlightApiProvider
                    ._iter_dicts_with_price(
                        value
                    )
                )

        elif isinstance(
            payload,
            list,
        ):

            for item in payload:

                yield from (
                    FlightApiProvider
                    ._iter_dicts_with_price(
                        item
                    )
                )

    def detect_route_restriction(
        self,
        payload: Dict[str, Any],
    ) -> str | None:
        """
        Detect provider-level route restrictions
        anywhere in the FlightAPI response.
        """

        def search_value(
            value: Any,
        ) -> bool:

            if isinstance(
                value,
                dict,
            ):

                for key, item in value.items():

                    if search_value(key):
                        return True

                    if search_value(item):
                        return True

                return False

            if isinstance(
                value,
                list,
            ):

                for item in value:

                    if search_value(item):
                        return True

                return False

            if isinstance(
                value,
                str,
            ):

                normalized = (
                    value.lower()
                )

                if (
                    "international sanctions"
                    in normalized
                ):
                    return True

                if (
                    "travelling to, from or within russia"
                    in normalized
                ):
                    return True

                if (
                    "traveling to, from or within russia"
                    in normalized
                ):
                    return True

            return False

        if search_value(payload):

            return "provider_restriction"

        return None

    def extract_cheapest_quote(
        self,
        payload: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Extract the cheapest quote from a
        FlightAPI response.

        Returns a status even when no priced
        itinerary exists.
        """

        restriction = (
            self.detect_route_restriction(
                payload
            )
        )

        if restriction:

            return {
                "status":
                    restriction,

                "price":
                    None,

                "currency":
                    None,

                "airline":
                    None,

                "flight_number":
                    None,

                "raw":
                    payload,
            }

        candidates = list(
            self._iter_dicts_with_price(
                payload
            )
        )

        if not candidates:

            return {
                "status":
                    "no_priced_result",

                "price":
                    None,

                "currency":
                    None,

                "airline":
                    None,

                "flight_number":
                    None,

                "raw":
                    payload,
            }

        cheapest = min(
            candidates,
            key=lambda item: item[
                "price"
            ],
        )

        return {
            "status":
                "priced_result",

            "price":
                cheapest.get(
                    "price"
                ),

            "currency":
                cheapest.get(
                    "currency"
                ),

            "airline":
                cheapest.get(
                    "airline"
                ),

            "flight_number":
                (
                    cheapest.get(
                        "flightNumber"
                    )
                    or
                    cheapest.get(
                        "flight_number"
                    )
                ),

            "raw":
                cheapest,
        }