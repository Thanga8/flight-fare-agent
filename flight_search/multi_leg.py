"""Budgeted search orchestration for HYD/MOW/MMK combined itineraries."""

from __future__ import annotations

from datetime import date, timedelta

from flight_search.airports import get_airports
from flight_search.planner import create_historical_initial_search_plan
from flight_search.results import extract_cheapest_flight
from search_history import get_historical_search_priorities
from utils.dates import sample_date_combinations


RUB_TO_INR = 1.16
MAX_SERPAPI_CALLS = 20
MAX_TRAVELPAYOUTS_CALLS = 10
DOMESTIC_COMBINATIONS_TO_ADVANCE = 10


def create_multi_leg_candidates(start_date, end_date, domestic_trip_days=4):
    """Generate domestic dates whose buffered international legs stay in range."""

    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    candidates = []
    domestic_departure = start + timedelta(days=1)

    while domestic_departure + timedelta(days=domestic_trip_days + 1) <= end:
        domestic_return = domestic_departure + timedelta(days=domestic_trip_days)
        arrival_target = domestic_departure - timedelta(days=1)
        inbound_departure_options = [
            candidate_day.isoformat()
            for candidate_day in (
                arrival_target - timedelta(days=1),
                arrival_target,
            )
            if start <= candidate_day <= end
        ]
        candidates.append(
            {
                "international_arrival_target": arrival_target.isoformat(),
                "international_outbound_dates": inbound_departure_options,
                "domestic_departure_date": domestic_departure.isoformat(),
                "domestic_return_date": domestic_return.isoformat(),
                "international_return_date": (
                    domestic_return + timedelta(days=1)
                ).isoformat(),
                "domestic_trip_days": domestic_trip_days,
            }
        )
        domestic_departure += timedelta(days=1)

    return candidates


def _sample_candidates(candidates, limit):
    sampled = sample_date_combinations(
        [
            {
                "departure_date": item["domestic_departure_date"],
                "return_date": item["domestic_return_date"],
                "trip_days": item["domestic_trip_days"],
                "candidate": item,
            }
            for item in candidates
        ],
        limit,
    )
    return [item["candidate"] for item in sampled]


def _arrival_date_from_flight(flight):
    segments = flight.get("flights", [])
    if not segments:
        return None

    arrival = segments[-1].get("arrival_airport", {})
    arrival_time = arrival.get("time")
    if not arrival_time:
        return None

    return arrival_time[:10]


def _build_international_airport_candidates(domestic_results):
    """Expand each domestic date into airport-specific international searches."""

    airport_candidates = []
    for domestic_result in domestic_results:
        for outbound_date in domestic_result["international_outbound_dates"]:
            return_date = domestic_result["international_return_date"]
            trip_days = (
                date.fromisoformat(return_date) - date.fromisoformat(outbound_date)
            ).days
            for arrival_airport in get_airports("MOW"):
                airport_candidates.append(
                    {
                        "departure_airport": "HYD",
                        "arrival_airport": arrival_airport,
                        "departure_date": outbound_date,
                        "return_date": return_date,
                        "trip_days": trip_days,
                        "domestic_result": domestic_result,
                    }
                )
    return airport_candidates


def search_multi_leg_itineraries(
    *,
    start_date,
    end_date,
    domestic_provider,
    international_provider,
    serpapi_budget=MAX_SERPAPI_CALLS,
    travelpayouts_budget=MAX_TRAVELPAYOUTS_CALLS,
    domestic_combination_limit=DOMESTIC_COMBINATIONS_TO_ADVANCE,
    rub_to_inr=RUB_TO_INR,
    historical_priority_provider=get_historical_search_priorities,
):
    """Search four-leg itineraries while enforcing separate provider budgets.

    Providers are injected so this function is fully testable with fixtures.
    It does not write to SQLite; persistence is intentionally deferred until
    live results and the combined ranking are validated.
    """

    if (
        serpapi_budget < 0
        or travelpayouts_budget < 0
        or domestic_combination_limit < 0
    ):
        raise ValueError("Provider budgets cannot be negative.")

    candidates = create_multi_leg_candidates(start_date, end_date)
    domestic_plan = _sample_candidates(candidates, travelpayouts_budget)
    domestic_results = []
    travelpayouts_calls = 0

    candidates_by_dates = {
        (item["domestic_departure_date"], item["domestic_return_date"]): item
        for item in candidates
    }

    if hasattr(domestic_provider, "search_round_trip_month"):
        domestic_plan = []
        month_pairs = sorted({
            (item["domestic_departure_date"][:7], item["domestic_return_date"][:7])
            for item in candidates
        })
        for departure_month, return_month in month_pairs[:travelpayouts_budget]:
            payload = domestic_provider.search_round_trip(
                departure_id="MOW",
                arrival_id="MMK",
                outbound_date=departure_month,
                return_date=return_month,
            )
            travelpayouts_calls += 1
            for offer in domestic_provider.extract_offers(payload):
                departure_at = offer.get("departure_at")
                return_at = offer.get("return_at")
                candidate = candidates_by_dates.get(
                    (departure_at[:10], return_at[:10])
                ) if departure_at and return_at else None
                if candidate:
                    domestic_results.append({
                        **candidate,
                        "domestic": offer,
                        "domestic_price_inr": round(offer["price"] * rub_to_inr, 2),
                    })

    for candidate in domestic_plan:
        payload = domestic_provider.search_round_trip(
            departure_id="MOW",
            arrival_id="MMK",
            outbound_date=candidate["domestic_departure_date"],
            return_date=candidate["domestic_return_date"],
        )
        travelpayouts_calls += 1
        offer = domestic_provider.extract_cheapest_offer(payload)
        departure_at = (offer or {}).get("departure_at")
        return_at = (offer or {}).get("return_at")
        if departure_at and departure_at[:10] != candidate["domestic_departure_date"]:
            offer = None
        if offer and return_at and return_at[:10] != candidate["domestic_return_date"]:
            offer = None
        if offer:
            domestic_results.append(
                {
                    **candidate,
                    "domestic": offer,
                    "domestic_price_inr": round(offer["price"] * rub_to_inr, 2),
                }
            )

    domestic_results.sort(key=lambda item: item["domestic_price_inr"])
    domestic_combinations_found = len(domestic_results)
    domestic_results = domestic_results[:domestic_combination_limit]
    airport_candidates = _build_international_airport_candidates(domestic_results)
    historical_candidates = historical_priority_provider(
        origin="HYD",
        destination="MOW",
        date_combinations=airport_candidates,
    )
    international_plan = create_historical_initial_search_plan(
        historical_candidates=historical_candidates,
        max_api_calls=serpapi_budget,
    )

    domestic_by_search_key = {
        (
            item["departure_airport"],
            item["arrival_airport"],
            item["departure_date"],
            item["return_date"],
        ): item["domestic_result"]
        for item in historical_candidates
    }
    itineraries = []
    serpapi_calls = 0

    for search in international_plan:
        search_key = (
            search["departure_airport"],
            search["arrival_airport"],
            search["departure_date"],
            search["return_date"],
        )
        domestic_result = domestic_by_search_key[search_key]
        payload = international_provider.search_round_trip(
            departure_id=search["departure_airport"],
            arrival_id=search["arrival_airport"],
            outbound_date=search["departure_date"],
            return_date=search["return_date"],
        )
        serpapi_calls += 1
        international = extract_cheapest_flight(
            payload,
            search["departure_date"],
            search["return_date"],
        )
        if not international:
            continue

        arrival_date = _arrival_date_from_flight(international["flight"])
        if (
            arrival_date is None
            or arrival_date > domestic_result["international_arrival_target"]
        ):
            continue

        itineraries.append(
            {
                **domestic_result,
                "international_arrival_airport": search["arrival_airport"],
                "international_planning_priority": search["planning_priority"],
                "international": international,
                "international_arrival_date": arrival_date,
                "international_arrival_verified": True,
                "rub_to_inr": rub_to_inr,
                "total_price_inr": round(
                    domestic_result["domestic_price_inr"] + international["price"],
                    2,
                ),
            }
        )

    itineraries.sort(key=lambda item: item["total_price_inr"])
    return {
        "itineraries": itineraries,
        "candidate_count": len(candidates),
        "domestic_candidates_searched": len(domestic_plan),
        "domestic_combinations_found": domestic_combinations_found,
        "domestic_combinations_selected": len(domestic_results),
        "international_searches_available": len(airport_candidates),
        "international_searches_planned": len(international_plan),
        "travelpayouts_calls": travelpayouts_calls,
        "serpapi_calls": serpapi_calls,
        "travelpayouts_budget": travelpayouts_budget,
        "serpapi_budget": serpapi_budget,
        "rub_to_inr": rub_to_inr,
    }
