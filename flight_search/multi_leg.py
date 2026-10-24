"""Budgeted search for HYD–Paris and HEL–HYD one-way legs."""

from __future__ import annotations

from datetime import date, timedelta

from flight_search.airports import get_airports
from flight_search.config.settings import (
    MULTI_LEG_COMBINED_CANDIDATE_LIMIT,
    MULTI_LEG_LEG1_DESTINATION,
    MULTI_LEG_LEG1_ORIGIN,
    MULTI_LEG_LEG2_DESTINATION,
    MULTI_LEG_LEG2_ORIGIN,
    MULTI_LEG_NIGHTS_BETWEEN_DEPARTURES,
    MULTI_LEG_SERPAPI_BUDGET,
)


def _resolve_airport_codes(location: str) -> list[str]:
    codes = []
    for item in location.split(","):
        item = item.strip().upper()
        if not item:
            continue
        try:
            codes.extend(get_airports(item))
        except ValueError:
            codes.append(item)
    return list(dict.fromkeys(codes))


def _sample_dates(start_date: str, end_date: str, limit: int) -> list[str]:
    start, end = date.fromisoformat(start_date), date.fromisoformat(end_date)
    days = (end - start).days + 1
    if days <= 0 or limit <= 0:
        return []
    count = min(days, limit)
    if count == 1:
        return [start.isoformat()]
    # Spread a small search budget across the full flexible window.
    offsets = {(index * (days - 1)) // (count - 1) for index in range(count)}
    return [(start + timedelta(days=offset)).isoformat() for offset in sorted(offsets)]


def _cheapest_flight(payload: dict, flight_date: str) -> dict | None:
    flights = payload.get("best_flights", []) + payload.get("other_flights", [])
    priced = [flight for flight in flights if flight.get("price") is not None]
    if not priced:
        return None
    flight = min(priced, key=lambda item: item["price"])
    return {
        "departure_date": flight_date,
        "price": flight["price"],
        "duration": flight.get("total_duration"),
        "arrival_airport": (
            flight.get("flights", [])[-1].get("arrival_airport", {}).get("id")
            if flight.get("flights") else None
        ),
        "flight": flight,
    }


def _cheapest_return_flights_by_airport(
    payload: dict,
    flight_date: str,
    eligible_airports: set[str],
) -> dict[str, dict]:
    """Keep the cheapest return result separately for each origin airport."""
    flights = payload.get("best_flights", []) + payload.get("other_flights", [])
    cheapest = {}
    for flight in flights:
        if flight.get("price") is None:
            continue
        segments = flight.get("flights", [])
        if not segments:
            continue
        departure = segments[0].get("departure_airport", {})
        airport = departure.get("id")
        if airport not in eligible_airports:
            continue
        fare = {
            "departure_date": flight_date,
            "departure_airport": airport,
            "price": flight["price"],
            "duration": flight.get("total_duration"),
            "flight": flight,
        }
        if airport not in cheapest or fare["price"] < cheapest[airport]["price"]:
            cheapest[airport] = fare
    return cheapest


def search_multi_leg_itineraries(
    *,
    start_date,
    end_date,
    international_provider,
    serpapi_budget=MULTI_LEG_SERPAPI_BUDGET,
    leg1_origin=MULTI_LEG_LEG1_ORIGIN,
    leg1_destination=MULTI_LEG_LEG1_DESTINATION,
    leg2_origin=MULTI_LEG_LEG2_ORIGIN,
    leg2_destination=MULTI_LEG_LEG2_DESTINATION,
    nights_between_departures=MULTI_LEG_NIGHTS_BETWEEN_DEPARTURES,
    leg1_cache_mode="live",
    leg2_cache_mode="live",
    combined_cache_mode="live",
    combined_candidate_limit=MULTI_LEG_COMBINED_CANDIDATE_LIMIT,
):
    """Search each one-way route within budget and rank valid date pairs.

    Search the supplied two one-way routes and enforce the configured night gap.
    """
    if serpapi_budget < 0:
        raise ValueError("Provider budgets cannot be negative.")
    if nights_between_departures < 1:
        raise ValueError("The nights between departures must be at least 1.")
    if any(mode not in {"live", "cache"} for mode in (
        leg1_cache_mode, leg2_cache_mode, combined_cache_mode
    )):
        raise ValueError("Cache modes must be 'live' or 'cache'.")
    if combined_candidate_limit < 0:
        raise ValueError("Combined candidate limit cannot be negative.")
    start, end = date.fromisoformat(start_date), date.fromisoformat(end_date)
    if end < start:
        raise ValueError("The end date must be on or after the start date.")

    nights = nights_between_departures
    leg1_origins = _resolve_airport_codes(leg1_origin)
    leg1_destinations = _resolve_airport_codes(leg1_destination)
    leg2_origins = _resolve_airport_codes(leg2_origin)
    leg2_destinations = _resolve_airport_codes(leg2_destination)
    if not all((leg1_origins, leg1_destinations, leg2_origins, leg2_destinations)):
        raise ValueError("Each leg must specify an origin and destination.")
    latest_first_departure = end - timedelta(days=nights)
    if latest_first_departure < start:
        candidate_dates = []
    else:
        # Each live leg costs one call per date pair. A cached leg consumes
        # no API budget, so the live leg can use the full remaining budget.
        live_leg_count = int(leg1_cache_mode == "live") + int(leg2_cache_mode == "live")
        combined_reserve = (
            min(combined_candidate_limit, serpapi_budget)
            if combined_cache_mode == "live" else 0
        )
        available_pairs = (latest_first_departure - start).days + 1
        pair_budget = (
            available_pairs
            if live_leg_count == 0
            else max(0, (serpapi_budget - combined_reserve) // live_leg_count)
        )
        candidate_dates = _sample_dates(
            start.isoformat(), latest_first_departure.isoformat(), pair_budget
        )

    paris_fares = {}
    return_fares = {}
    errors = {"HYD-PAR": [], "HEL-HYD": []}
    cache_hits = {"leg1": 0, "leg2": 0}
    for first_date in candidate_dates:
        second_date = (
            date.fromisoformat(first_date) + timedelta(days=nights)
        ).isoformat()
        outbound_payload = international_provider.search_one_way(
            departure_id=",".join(leg1_origins),
            arrival_id=",".join(leg1_destinations),
            outbound_date=first_date,
            cache_mode=leg1_cache_mode,
        )
        cache_hits["leg1"] += int(bool(outbound_payload.get("_cache_hit")))
        if outbound_payload.get("error"):
            errors["HYD-PAR"].append(str(outbound_payload["error"]))
        outbound = _cheapest_flight(outbound_payload, first_date)
        if outbound:
            paris_fares[first_date] = outbound

        # SerpApi accepts comma-separated airport codes. This uses one call
        # Search the Helsinki return leg on the same seven-night offset date.
        return_payload = international_provider.search_one_way(
            departure_id=",".join(leg2_origins),
            arrival_id=",".join(leg2_destinations),
            outbound_date=second_date,
            cache_mode=leg2_cache_mode,
        )
        cache_hits["leg2"] += int(bool(return_payload.get("_cache_hit")))
        if return_payload.get("error"):
            errors["HEL-HYD"].append(str(return_payload["error"]))
        return_fares[second_date] = _cheapest_return_flights_by_airport(
            return_payload, second_date, set(leg2_origins)
        )

    leg_stats = [
        {
            "route": f"{','.join(leg1_origins)}-{','.join(leg1_destinations)}",
            "dates_searched": len(candidate_dates),
            "priced_dates": len(paris_fares),
            "response_errors": errors["HYD-PAR"],
        },
        {
            "route": f"{','.join(leg2_origins)}-{','.join(leg2_destinations)}",
            "dates_searched": len(candidate_dates),
            "priced_dates": sum(bool(options) for options in return_fares.values()),
            "response_errors": errors["HEL-HYD"],
        },
    ]

    itineraries = []
    for outbound_date, outbound in paris_fares.items():
        expected_return_date = (
            date.fromisoformat(outbound_date) + timedelta(days=nights)
        ).isoformat()
        for inbound in return_fares.get(expected_return_date, {}).values():
            itineraries.append({
                "leg1": outbound,
                "leg2": inbound,
                "nights_between_departures": nights,
                "total_price_inr": round(outbound["price"] + inbound["price"], 2),
            })
    itineraries.sort(key=lambda item: item["total_price_inr"])

    combined_checks = []
    combined_calls = 0
    combined_cache_hits = 0
    if not hasattr(international_provider, "search_multi_city"):
        if combined_candidate_limit:
            raise ValueError("Provider does not support multi-city searches.")
    for itinerary in itineraries[:combined_candidate_limit]:
        outbound = itinerary["leg1"]
        inbound = itinerary["leg2"]
        paris_airport = outbound.get("arrival_airport")
        if not paris_airport:
            comparison = {
                "status": "missing_airport",
                "error": "Separate-leg result did not identify its Paris arrival airport.",
            }
        else:
            multi_city_legs = [
                {
                    "departure_id": ",".join(leg1_origins),
                    "arrival_id": paris_airport,
                    "date": outbound["departure_date"],
                },
                {
                    "departure_id": inbound["departure_airport"],
                    "arrival_id": ",".join(leg2_destinations),
                    "date": inbound["departure_date"],
                },
            ]
            payload = international_provider.search_multi_city(
                multi_city_legs, cache_mode=combined_cache_mode
            )
            combined_cache_hits += int(bool(payload.get("_cache_hit")))
            if combined_cache_mode == "live":
                combined_calls += 1
            combined_fare = _cheapest_flight(payload, outbound["departure_date"])
            if combined_fare:
                difference = round(
                    combined_fare["price"] - itinerary["total_price_inr"], 2
                )
                comparison = {
                    "status": "priced",
                    "price_inr": combined_fare["price"],
                    "difference_inr": difference,
                    "cheaper_method": (
                        "combined" if difference < 0
                        else "separate" if difference > 0
                        else "same"
                    ),
                    "flight": combined_fare["flight"],
                    "legs": multi_city_legs,
                }
            else:
                comparison = {
                    "status": "no_price",
                    "error": payload.get("error", "No priced combined itinerary returned."),
                    "legs": multi_city_legs,
                }
        itinerary["combined_search"] = comparison
        combined_checks.append({
            "separate_total_inr": itinerary["total_price_inr"],
            **comparison,
        })
    return {
        "itineraries": itineraries,
        "serpapi_calls": len(candidate_dates) * (
            int(leg1_cache_mode == "live") + int(leg2_cache_mode == "live")
        ) + combined_calls,
        "provider_queries": len(candidate_dates) * 2,
        "serpapi_budget": serpapi_budget,
        "leg1_dates_searched": len(candidate_dates),
        "leg2_dates_searched": len(candidate_dates),
        "leg_stats": leg_stats,
        "leg1_priced_dates": len(paris_fares),
        "leg2_priced_dates": sum(bool(options) for options in return_fares.values()),
        "leg2_airport_options_found": sum(
            len(options) for options in return_fares.values()
        ),
        "valid_date_pairs": len(itineraries),
        "nights_between_departures": nights,
        "leg1_origin": ",".join(leg1_origins),
        "leg1_destination": ",".join(leg1_destinations),
        "leg2_origin": ",".join(leg2_origins),
        "leg2_destination": ",".join(leg2_destinations),
        "leg1_cache_mode": leg1_cache_mode,
        "leg2_cache_mode": leg2_cache_mode,
        "leg1_cache_hits": cache_hits["leg1"],
        "leg2_cache_hits": cache_hits["leg2"],
        "combined_searches": len(combined_checks),
        "combined_cache_mode": combined_cache_mode,
        "combined_cache_hits": combined_cache_hits,
        "combined_results": combined_checks,
    }
