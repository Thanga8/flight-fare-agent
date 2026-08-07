"""Budgeted search orchestration for HYD/MOW/MMK combined itineraries."""

from __future__ import annotations

from datetime import date, timedelta

from flight_search.results import extract_cheapest_flight
from utils.dates import sample_date_combinations


RUB_TO_INR = 1.16
MAX_SERPAPI_CALLS = 20
MAX_TRAVELPAYOUTS_CALLS = 10


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


def search_multi_leg_itineraries(
    *,
    start_date,
    end_date,
    domestic_provider,
    international_provider,
    serpapi_budget=MAX_SERPAPI_CALLS,
    travelpayouts_budget=MAX_TRAVELPAYOUTS_CALLS,
    rub_to_inr=RUB_TO_INR,
):
    """Search four-leg itineraries while enforcing separate provider budgets.

    Providers are injected so this function is fully testable with fixtures.
    It does not write to SQLite; persistence is intentionally deferred until
    live results and the combined ranking are validated.
    """

    if serpapi_budget < 0 or travelpayouts_budget < 0:
        raise ValueError("Provider budgets cannot be negative.")

    candidates = create_multi_leg_candidates(start_date, end_date)
    domestic_plan = _sample_candidates(candidates, travelpayouts_budget)
    domestic_results = []
    travelpayouts_calls = 0

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
    selected_for_international = domestic_results[:serpapi_budget]
    itineraries = []
    serpapi_calls = 0

    for candidate in selected_for_international:
        for outbound_date in candidate["international_outbound_dates"]:
            if serpapi_calls >= serpapi_budget:
                break

            payload = international_provider.search_round_trip(
                departure_id="HYD",
                arrival_id="MOW",
                outbound_date=outbound_date,
                return_date=candidate["international_return_date"],
            )
            serpapi_calls += 1
            international = extract_cheapest_flight(
                payload,
                outbound_date,
                candidate["international_return_date"],
            )
            if not international:
                continue

            arrival_date = _arrival_date_from_flight(international["flight"])
            # A combined itinerary is valid only if its actual inbound flight
            # reaches Moscow on or before the protected buffer day.
            if (
                arrival_date is None
                or arrival_date > candidate["international_arrival_target"]
            ):
                continue

            itineraries.append(
                {
                    **candidate,
                    "international": international,
                    "international_arrival_date": arrival_date,
                "international_arrival_verified": True,
                    "rub_to_inr": rub_to_inr,
                    "total_price_inr": round(
                        candidate["domestic_price_inr"] + international["price"],
                        2,
                    ),
                }
            )

        if serpapi_calls >= serpapi_budget:
            break

    itineraries.sort(key=lambda item: item["total_price_inr"])
    return {
        "itineraries": itineraries,
        "candidate_count": len(candidates),
        "domestic_candidates_searched": len(domestic_plan),
        "travelpayouts_calls": travelpayouts_calls,
        "serpapi_calls": serpapi_calls,
        "travelpayouts_budget": travelpayouts_budget,
        "serpapi_budget": serpapi_budget,
        "rub_to_inr": rub_to_inr,
    }
