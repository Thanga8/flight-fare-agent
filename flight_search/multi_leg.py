"""Budgeted search for HYD–Paris and HEL–HYD one-way legs."""

from __future__ import annotations

import json
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
from flight_search.database.db import persist_multi_leg_search


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
    try:
        start, end = date.fromisoformat(start_date), date.fromisoformat(end_date)
    except (TypeError, ValueError) as error:
        raise ValueError("Dates must be valid ISO calendar dates (YYYY-MM-DD).") from error
    if end < start:
        raise ValueError("The end date must be on or after the start date.")
    if limit < 0:
        raise ValueError("Date sampling limit cannot be negative.")
    days = (end - start).days + 1
    if days <= 0 or limit <= 0:
        return []
    count = min(days, limit)
    if count == 1:
        return [start.isoformat()]
    # Spread a small search budget across the full flexible window.
    offsets = {(index * (days - 1)) // (count - 1) for index in range(count)}
    return [(start + timedelta(days=offset)).isoformat() for offset in sorted(offsets)]


def plan_multi_leg_usage(
    start_date: str,
    end_date: str,
    nights_between_departures: int,
    serpapi_budget: int,
    leg1_cache_mode: str = "live",
    leg2_cache_mode: str = "live",
    combined_cache_mode: str = "live",
    combined_candidate_limit: int = 0,
) -> dict:
    """Estimate date coverage and request bounds using the search's budget rules.

    Combined calls are candidate-dependent, so their returned count is a maximum,
    bounded by both the candidate limit and budget remaining after leg searches.
    """
    if nights_between_departures < 1:
        raise ValueError("The nights between departures must be at least 1.")
    if serpapi_budget < 0:
        raise ValueError("Provider budgets cannot be negative.")
    if any(mode not in {"live", "cache"} for mode in (
        leg1_cache_mode, leg2_cache_mode, combined_cache_mode
    )):
        raise ValueError("Cache modes must be 'live' or 'cache'.")
    if combined_candidate_limit < 0:
        raise ValueError("Combined candidate limit cannot be negative.")
    start, end = date.fromisoformat(start_date), date.fromisoformat(end_date)
    if end < start:
        raise ValueError("The end date must be on or after the start date.")
    latest_first_departure = end - timedelta(days=nights_between_departures)
    pair_count = max(0, (latest_first_departure - start).days + 1)
    live_leg_count = int(leg1_cache_mode == "live") + int(leg2_cache_mode == "live")
    if live_leg_count:
        covered_pairs = min(pair_count, serpapi_budget // live_leg_count)
    else:
        covered_pairs = pair_count
    leg1_calls = covered_pairs if leg1_cache_mode == "live" else 0
    leg2_calls = covered_pairs if leg2_cache_mode == "live" else 0
    exhaustive_leg_calls = pair_count * live_leg_count
    remaining = max(0, serpapi_budget - leg1_calls - leg2_calls)
    combined_max = (
        min(combined_candidate_limit, remaining)
        if combined_cache_mode == "live" else 0
    )
    exhaustive_combined_max = (
        combined_candidate_limit if combined_cache_mode == "live" else 0
    )
    return {
        "valid_date_pairs": pair_count,
        "covered_date_pairs": covered_pairs,
        "full_date_coverage": covered_pairs == pair_count,
        "leg1_live_requests": leg1_calls,
        "leg2_live_requests": leg2_calls,
        "leg_live_requests": leg1_calls + leg2_calls,
        "exhaustive_leg_live_requests": exhaustive_leg_calls,
        "combined_live_requests_max": combined_max,
        "exhaustive_combined_live_requests_max": exhaustive_combined_max,
        "configured_total_live_requests_max": leg1_calls + leg2_calls + combined_max,
        "exhaustive_total_live_requests_max": exhaustive_leg_calls + exhaustive_combined_max,
        "remaining_budget_after_leg_searches": remaining,
        "remaining_budget_after_max_combined": remaining - combined_max,
    }


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
        "departure_airport": (flight.get("flights", [{}])[0].get("departure_airport", {}).get("id") if flight.get("flights") else None),
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
        arrival = segments[-1].get("arrival_airport", {}).get("id")
        fare["arrival_airport"] = arrival
        key = (airport, arrival)
        if key not in cheapest or fare["price"] < cheapest[key]["price"]:
            cheapest[key] = fare
    return cheapest


def _cheapest_fares_by_airport_pair(payload: dict, flight_date: str, leg_number: int,
                                    data_source: str) -> list[dict]:
    """Normalize the cheapest priced itinerary per actual endpoint pair."""
    cheapest = {}
    for flight in payload.get("best_flights", []) + payload.get("other_flights", []):
        if flight.get("price") is None or not flight.get("flights"):
            continue
        segments = flight["flights"]
        departure = segments[0].get("departure_airport", {}).get("id")
        arrival = segments[-1].get("arrival_airport", {}).get("id")
        if not departure or not arrival:
            continue
        key = (departure, arrival)
        if key not in cheapest or flight["price"] < cheapest[key]["price"]:
            cheapest[key] = {
                "leg_number": leg_number,
                "departure_date": flight_date,
                "departure_airport": departure,
                "arrival_airport": arrival,
                "price": flight["price"],
                "currency": "INR",
                "flight": flight,
                "data_source": data_source,
                "source_fetched_at": payload.get("_source_fetched_at"),
            }
    return list(cheapest.values())


def _outcome(payload: dict, leg_number: int, flight_date: str, cache_mode: str) -> dict:
    error = payload.get("error")
    if error and str(error).startswith("CACHE_MISS:"):
        status = "cache_miss"
    elif error and str(error).startswith("STALE_CACHE:"):
        status = "stale_cache"
    elif error:
        status = "failed"
    elif _cheapest_flight(payload, flight_date) is not None:
        status = "priced"
    else:
        status = "no_price"
    return {
        "leg_number": leg_number,
        "departure_date": flight_date,
        "status": status,
        "error": str(error) if error else None,
        "data_source": "cache" if payload.get("_cache_hit") else cache_mode,
        "source_fetched_at": payload.get("_source_fetched_at"),
    }


def _google_insight_record(payload: dict, leg_number: int, departure_id: str,
                           arrival_id: str, flight_date: str, cache_mode: str) -> dict | None:
    if payload.get("error") or payload.get("_budget_exhausted"):
        return None
    if "price_insights" not in payload:
        status, encoded = "absent", None
    elif payload["price_insights"] is None:
        status, encoded = "null", "null"
    elif payload["price_insights"] == {} or payload["price_insights"] == []:
        status, encoded = "empty", json.dumps(payload["price_insights"], ensure_ascii=False)
    else:
        status, encoded = "present", json.dumps(payload["price_insights"], ensure_ascii=False, sort_keys=True)
    return {
        "leg_number": leg_number,
        "departure_id": departure_id,
        "arrival_id": arrival_id,
        "departure_date": flight_date,
        "currency": "INR",
        "insight_status": status,
        "insights_json": encoded,
        "data_source": "cache" if payload.get("_cache_hit") else cache_mode,
        "source_fetched_at": payload.get("_source_fetched_at"),
    }


def _google_insight_result(payload: dict, leg_number: int, departure_id: str,
                           arrival_id: str, flight_date: str, cache_mode: str) -> dict:
    """Expose the original one-way response insight and its request outcome."""
    result = {
        "leg_number": leg_number,
        "departure_id": departure_id,
        "arrival_id": arrival_id,
        "departure_date": flight_date,
        "currency": "INR",
        "data_source": "cache" if payload.get("_cache_hit") else cache_mode,
        "source_fetched_at": payload.get("_source_fetched_at"),
    }
    cache_status = payload.get("_cache_status")
    if payload.get("_budget_exhausted"):
        result.update(status="budget_skipped", error=payload.get("error"))
    elif cache_status == "miss":
        result.update(status="cache_miss", error=payload.get("error"))
    elif cache_status == "stale":
        result.update(status="stale_cache", error=payload.get("error"))
    elif payload.get("error"):
        status = "cache_error" if cache_mode == "cache" and not payload.get("_cache_hit") else "failed"
        result.update(status=status, error=payload.get("error"))
    elif "price_insights" not in payload:
        result["status"] = "absent"
    else:
        result["status"] = "present"
        result["price_insights"] = payload["price_insights"]
    return result


class _BudgetedProvider:
    """Gate every live SerpApi request at the provider call boundary."""
    def __init__(self, provider, budget):
        self.provider = provider
        self.budget = budget
        self.calls = 0
        self.limited = budget == 0

    def __getattr__(self, name):
        return getattr(self.provider, name)

    def _call(self, method, *args, cache_mode="live", **kwargs):
        if cache_mode == "live":
            if self.calls >= self.budget:
                self.limited = True
                return {"error": "BUDGET_EXHAUSTED: live search skipped", "_budget_exhausted": True, "_cache_hit": False}
            self.calls += 1
        result = method(*args, cache_mode=cache_mode, **kwargs)
        return result

    def search_one_way(self, *args, cache_mode="live", **kwargs):
        return self._call(self.provider.search_one_way, *args, cache_mode=cache_mode, **kwargs)

    def search_multi_city(self, *args, cache_mode="live", **kwargs):
        return self._call(self.provider.search_multi_city, *args, cache_mode=cache_mode, **kwargs)


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
    usage_plan = plan_multi_leg_usage(
        start_date, end_date, nights, serpapi_budget,
        leg1_cache_mode, leg2_cache_mode, combined_cache_mode,
        combined_candidate_limit,
    )
    leg1_origins = _resolve_airport_codes(leg1_origin)
    leg1_destinations = _resolve_airport_codes(leg1_destination)
    leg2_origins = _resolve_airport_codes(leg2_origin)
    leg2_destinations = _resolve_airport_codes(leg2_destination)
    if not all((leg1_origins, leg1_destinations, leg2_origins, leg2_destinations)):
        raise ValueError("Each leg must specify an origin and destination.")
    provider = _BudgetedProvider(international_provider, serpapi_budget)
    incomplete_reason = None
    latest_first_departure = end - timedelta(days=nights)
    available_pairs = usage_plan["valid_date_pairs"]
    pair_budget = usage_plan["covered_date_pairs"]
    if usage_plan["leg_live_requests"] < usage_plan["exhaustive_leg_live_requests"]:
        provider.limited = True
    if available_pairs and pair_budget == 0 and (
        leg1_cache_mode == "live" or leg2_cache_mode == "live"
    ):
        incomplete_reason = (
            "Budget is too small to search both legs of even one date pair; "
            "no complete date pair was priced."
        )
    candidate_dates = _sample_dates(
        start.isoformat(), latest_first_departure.isoformat(), pair_budget
    ) if available_pairs else []

    paris_fares = {}
    return_fares = {}
    stored_fares = []
    stored_outcomes = []
    stored_insights = []
    result_insights = []
    errors = {"HYD-PAR": [], "HEL-HYD": []}
    cache_hits = {"leg1": 0, "leg2": 0}
    for first_date in candidate_dates:
        second_date = (
            date.fromisoformat(first_date) + timedelta(days=nights)
        ).isoformat()
        try:
            outbound_payload = provider.search_one_way(
                departure_id=",".join(leg1_origins),
                arrival_id=",".join(leg1_destinations),
                outbound_date=first_date,
                cache_mode=leg1_cache_mode,
            )
        except Exception as error:
            outbound_payload = {"error": f"PROVIDER_ERROR: {error}", "_cache_hit": False}
        cache_hits["leg1"] += int(bool(outbound_payload.get("_cache_hit")))
        result_insights.append(_google_insight_result(
            outbound_payload, 1, ",".join(leg1_origins), ",".join(leg1_destinations),
            first_date, leg1_cache_mode,
        ))
        insight = _google_insight_record(
            outbound_payload, 1, ",".join(leg1_origins), ",".join(leg1_destinations),
            first_date, leg1_cache_mode,
        )
        if insight:
            stored_insights.append(insight)
        stored_outcomes.append(_outcome(outbound_payload, 1, first_date, leg1_cache_mode))
        stored_fares.extend(_cheapest_fares_by_airport_pair(
            outbound_payload, first_date, 1, stored_outcomes[-1]["data_source"]
        ))
        if outbound_payload.get("error"):
            errors["HYD-PAR"].append(str(outbound_payload["error"]))
        outbound = _cheapest_flight(outbound_payload, first_date)
        if outbound:
            paris_fares[first_date] = outbound

        # SerpApi accepts comma-separated airport codes. This uses one call
        # Search the Helsinki return leg on the same seven-night offset date.
        try:
            return_payload = provider.search_one_way(
                departure_id=",".join(leg2_origins),
                arrival_id=",".join(leg2_destinations),
                outbound_date=second_date,
                cache_mode=leg2_cache_mode,
            )
        except Exception as error:
            return_payload = {"error": f"PROVIDER_ERROR: {error}", "_cache_hit": False}
        cache_hits["leg2"] += int(bool(return_payload.get("_cache_hit")))
        result_insights.append(_google_insight_result(
            return_payload, 2, ",".join(leg2_origins), ",".join(leg2_destinations),
            second_date, leg2_cache_mode,
        ))
        insight = _google_insight_record(
            return_payload, 2, ",".join(leg2_origins), ",".join(leg2_destinations),
            second_date, leg2_cache_mode,
        )
        if insight:
            stored_insights.append(insight)
        stored_outcomes.append(_outcome(return_payload, 2, second_date, leg2_cache_mode))
        stored_fares.extend(_cheapest_fares_by_airport_pair(
            return_payload, second_date, 2, stored_outcomes[-1]["data_source"]
        ))
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
    if combined_cache_mode == "live" and combined_candidate_limit:
        remaining_after_legs = serpapi_budget - provider.calls
        requested_checks = min(len(itineraries), combined_candidate_limit)
        if requested_checks > remaining_after_legs:
            provider.limited = True
            if incomplete_reason is None:
                incomplete_reason = "Combined verification was limited by the remaining SerpApi budget."
    if not hasattr(provider, "search_multi_city"):
        if combined_candidate_limit:
            raise ValueError("Provider does not support multi-city searches.")
    for itinerary in itineraries[:combined_candidate_limit]:
        outbound = itinerary["leg1"]
        inbound = itinerary["leg2"]
        paris_airport = outbound.get("arrival_airport")
        if not paris_airport or not outbound.get("departure_airport") or not inbound.get("arrival_airport"):
            comparison = {
                "status": "missing_airport",
                "error": "Separate-leg result did not identify its Paris arrival airport.",
            }
        else:
            multi_city_legs = [
                {
                    "departure_id": outbound["departure_airport"],
                    "arrival_id": paris_airport,
                    "date": outbound["departure_date"],
                },
                {
                    "departure_id": inbound["departure_airport"],
                    "arrival_id": inbound["arrival_airport"],
                    "date": inbound["departure_date"],
                },
            ]
            try:
                payload = provider.search_multi_city(
                    multi_city_legs, cache_mode=combined_cache_mode
                )
            except Exception as error:
                payload = {"error": f"PROVIDER_ERROR: {error}", "_cache_hit": False}
            combined_cache_hits += int(bool(payload.get("_cache_hit")))
            if payload.get("_budget_exhausted"):
                comparison = {"status": "budget_exhausted", "error": payload["error"], "legs": multi_city_legs}
                comparison["data_source"] = "live"
                itinerary["combined_search"] = comparison
                combined_checks.append({"separate_total_inr": itinerary["total_price_inr"], **comparison})
                continue
            comparison_data_source = "cache" if payload.get("_cache_hit") else combined_cache_mode
            comparison_source_fetched_at = payload.get("_source_fetched_at")
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
                comparison_error = payload.get("error", "No priced combined itinerary returned.")
                if str(comparison_error).startswith("CACHE_MISS:"):
                    comparison_status = "cache_miss"
                elif str(comparison_error).startswith("STALE_CACHE:"):
                    comparison_status = "stale_cache"
                elif str(comparison_error).startswith("PROVIDER_ERROR:"):
                    comparison_status = "failed"
                else:
                    comparison_status = "no_price"
                comparison = {
                    "status": comparison_status,
                    "error": comparison_error,
                    "legs": multi_city_legs,
                }
            comparison["data_source"] = comparison_data_source
            comparison["source_fetched_at"] = comparison_source_fetched_at
        itinerary["combined_search"] = comparison
        combined_checks.append({
            "separate_total_inr": itinerary["total_price_inr"],
            **comparison,
        })
    report = {
        "itineraries": itineraries,
        "serpapi_calls": provider.calls,
        "budget_limited": provider.limited,
        "incomplete_reason": incomplete_reason,
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
        "google_insights": result_insights,
    }
    stored_comparisons = []
    for itinerary in itineraries[:combined_candidate_limit]:
        comparison = itinerary.get("combined_search")
        if not comparison:
            continue
        stored_comparisons.append({
            "leg1_departure_date": itinerary["leg1"]["departure_date"],
            "leg2_departure_date": itinerary["leg2"]["departure_date"],
            "separate_total": itinerary["total_price_inr"],
            "combined_price": comparison.get("price_inr"),
            "difference": comparison.get("difference_inr"),
            "status": comparison["status"],
            "details": comparison,
            "data_source": comparison.get("data_source", "not_searched"),
            "source_fetched_at": comparison.get("source_fetched_at"),
        })
    try:
        report["persistence_run_id"] = persist_multi_leg_search(
            run={
                "start_date": start.isoformat(), "end_date": end.isoformat(), "nights": nights,
                "leg1_origin": ",".join(leg1_origins), "leg1_destination": ",".join(leg1_destinations),
                "leg2_origin": ",".join(leg2_origins), "leg2_destination": ",".join(leg2_destinations),
                "leg1_cache_mode": leg1_cache_mode, "leg2_cache_mode": leg2_cache_mode,
                "combined_cache_mode": combined_cache_mode, "serpapi_budget": serpapi_budget,
                "serpapi_calls": provider.calls, "budget_limited": provider.limited,
                "statistics": {
                    "incomplete_reason": incomplete_reason, "provider_queries": report["provider_queries"],
                    "valid_date_pairs": report["valid_date_pairs"], "leg_stats": leg_stats,
                    "leg1_cache_hits": cache_hits["leg1"], "leg2_cache_hits": cache_hits["leg2"],
                    "combined_searches": len(combined_checks),
                },
            },
            fares=stored_fares,
            outcomes=stored_outcomes,
            comparisons=stored_comparisons,
            google_insights=stored_insights,
        )
    except Exception as error:
        report["persistence_error"] = str(error)
    return report
