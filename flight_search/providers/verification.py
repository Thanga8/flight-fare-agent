from __future__ import annotations

import os
from typing import Any, Dict, List

from flight_search.providers.flightapi_provider import FlightApiProvider

from flight_search.providers.flightapi_restrictions import (
    is_route_supported_by_flightapi,
)


def verify_top_results_with_flightapi(
    ranked_results: list[dict],
    max_checks: int = 3,
    api_key: str | None = None,
) -> list[dict]:
    if not ranked_results or max_checks <= 0:
        return []

    provider = FlightApiProvider(api_key=api_key or os.getenv("FLIGHTAPI_API_KEY"))

    verifications: list[dict] = []

    for result in ranked_results[:max_checks]:
    
        departure_airport = (
            result["departure_airport"]
        )
    
        arrival_airport = (
            result["arrival_airport"]
        )
    
        departure_date = (
            result["departure_date"]
        )
    
        return_date = (
            result["return_date"]
        )
    
        serpapi_price = (
            result["price"]
        )
    
        # ==========================================
        # CHECK FLIGHTAPI ROUTE SUPPORT
        # ==========================================
    
        if not is_route_supported_by_flightapi(
            departure_airport=departure_airport,
            arrival_airport=arrival_airport,
        ):
    
            verifications.append(
                {
                    "departure_airport":
                        departure_airport,
    
                    "arrival_airport":
                        arrival_airport,
    
                    "departure_date":
                        departure_date,
    
                    "return_date":
                        return_date,
    
                    "serpapi_price":
                        serpapi_price,
    
                    "flightapi_status":
                        "provider_restriction",
    
                    "flightapi_price":
                        None,
    
                    "flightapi_currency":
                        None,
    
                    "flightapi_airline":
                        None,
    
                    "flightapi_flight_number":
                        None,
    
                    "matched":
                        False,
    
                    "raw":
                        None,
                }
            )
    
            # IMPORTANT:
            # Do not call FlightAPI.
            # This saves 2 credits.
    
            continue
    
        # ==========================================
        # FLIGHTAPI SEARCH
        # ==========================================
    
        payload = provider.search_round_trip(
        
            departure_id=departure_airport,
    
            arrival_id=arrival_airport,
    
            outbound_date=departure_date,
    
            return_date=return_date,
        )
    
        cheapest = (
            provider.extract_cheapest_quote(
                payload
            )
        )
    
        status = (
            cheapest["status"]
            if cheapest
            else "no_priced_result"
        )
    
        verifications.append(
            {
                "departure_airport":
                    departure_airport,
    
                "arrival_airport":
                    arrival_airport,
    
                "departure_date":
                    departure_date,
    
                "return_date":
                    return_date,
    
                "serpapi_price":
                    serpapi_price,
    
                "flightapi_status":
                    status,
    
                "flightapi_price": (
                    cheapest.get("price")
                    if cheapest
                    else None
                ),
    
                "flightapi_currency": (
                    cheapest.get("currency")
                    if cheapest
                    else None
                ),
    
                "flightapi_airline": (
                    cheapest.get("airline")
                    if cheapest
                    else None
                ),
    
                "flightapi_flight_number": (
                    cheapest.get(
                        "flight_number"
                    )
                    if cheapest
                    else None
                ),
    
                "matched": (
                    status
                    == "priced_result"
                ),
    
                "raw":
                    payload,
            }
        )
    
    return verifications