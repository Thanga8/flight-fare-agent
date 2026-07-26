from __future__ import annotations

import os

from flight_search.providers.verification import (
    verify_top_results_with_flightapi,
)
from flight_search.search import search_flexible_dates


# ==========================================
# SEARCH CONFIGURATION
# ==========================================

ORIGIN = "HYD"
DESTINATION = "MOW"

START_DATE = "2027-01-20"
END_DATE = "2027-02-13"

MIN_TRIP_DAYS = 5
MAX_TRIP_DAYS = 6

MAX_SEARCHES = 8


# ==========================================
# HELPER FUNCTIONS
# ==========================================

def format_duration(minutes: int | None) -> str:
    """
    Convert duration in minutes into a
    human-readable format.
    """

    if minutes is None:
        return "Unknown"

    if minutes < 60:
        return f"{minutes} minutes"

    hours = minutes // 60
    remaining_minutes = minutes % 60

    return f"{hours}h {remaining_minutes}m"


def get_number_of_stops(result: dict) -> int:
    """
    Get the number of stops from the
    underlying SerpApi flight object.
    """

    flight = result.get("flight", {})
    layovers = flight.get("layovers", [])
    return len(layovers)


def make_result_key(result: dict) -> tuple:
    """
    Create a stable identity for a result.
    """

    return (
        result.get("departure_airport"),
        result.get("arrival_airport"),
        result.get("departure_date"),
        result.get("return_date"),
        result.get("price"),
    )


def print_recommendation(
    title: str,
    result: dict | None,
    *,
    same_as: str | None = None,
    show_scores: bool = False,
) -> None:
    """
    Print a single flight recommendation.
    """

    print()
    print(title)
    print("-" * 70)

    if not result:
        print("No suitable flight found.")
        return

    if same_as is not None:
        print(f"Same as {same_as}.")
        return

    print(f"Price: ₹{result['price']:,}")

    print(
        f"Route: "
        f"{result['departure_airport']} → "
        f"{result['arrival_airport']}"
    )

    print(
        f"Dates: "
        f"{result['departure_date']} → "
        f"{result['return_date']}"
    )

    if result.get("duration") is not None:
        print(
            f"Flight duration: "
            f"{format_duration(result['duration'])}"
        )

    print(
        f"Stops: "
        f"{get_number_of_stops(result)}"
    )

    if show_scores:
        print()
        print(
            f"Final score: "
            f"{result['final_score']:.2f} / 100"
        )
        print(f"Price score: {result['price_score']:.2f}")
        print(f"Duration score: {result['duration_score']:.2f}")
        print(f"Stops score: {result['stops_score']:.2f}")
        print(
            f"Convenience score: "
            f"{result['convenience_score']:.2f}"
        )


# ==========================================
# RUN SEARCH
# ==========================================

report = search_flexible_dates(
    departure_id=ORIGIN,
    arrival_id=DESTINATION,
    start_date=START_DATE,
    end_date=END_DATE,
    min_trip_days=MIN_TRIP_DAYS,
    max_trip_days=MAX_TRIP_DAYS,
    max_searches=MAX_SEARCHES,
)


# ==========================================
# EXTRACT REPORT DATA
# ==========================================

ranked_results = report.get("ranked_results", [])
scored_results = report.get("scored_results", [])
cheapest = report.get("cheapest")
statistics = report.get("statistics", {})
cheapest_by_airport = report.get("cheapest_by_airport", {})
cheapest_by_duration = report.get("cheapest_by_duration", {})

# ==========================================
# SELECT RECOMMENDATIONS
# ==========================================

def pick_best_distinct_result(results, excluded_results):
    excluded_keys = {
        make_result_key(result)
        for result in excluded_results
        if result
    }

    for result in results:
        if make_result_key(result) not in excluded_keys:
            return result

    return None


def pick_best_for_trip_days(results, trip_days):
    candidates = [
        result
        for result in results
        if result.get("trip_days") == trip_days
    ]

    if not candidates:
        return None

    return max(
        candidates,
        key=lambda result: (
            result["final_score"],
            -result["price"],
        ),
    )


best_overall = scored_results[0] if scored_results else None

cheapest_scored = (
    min(scored_results, key=lambda result: result["price"])
    if scored_results
    else None
)

fastest = None
if scored_results:
    duration_candidates = [
        result
        for result in scored_results
        if result.get("duration") is not None
    ]
    if duration_candidates:
        fastest = min(
            duration_candidates,
            key=lambda result: result["duration"],
        )

best_5_day = pick_best_for_trip_days(scored_results, 5)
best_6_day = pick_best_for_trip_days(scored_results, 6)

best_alternative = pick_best_distinct_result(
    scored_results,
    [
        best_overall,
        cheapest_scored,
        fastest,
        best_5_day,
        best_6_day,
    ],
)

# ==========================================
# DISPLAY SEARCH SUMMARY
# ==========================================

print()
print("=" * 70)
print("FLIGHT SEARCH SUMMARY")
print("=" * 70)
print(f"Route: {ORIGIN} → {DESTINATION}")
print(f"Search window: {START_DATE} → {END_DATE}")
print(f"Trip duration: {MIN_TRIP_DAYS}–{MAX_TRIP_DAYS} days")
print(f"API searches executed: {statistics.get('total_searches', 0)}")
print(f"Priced results found: {statistics.get('priced_results', 0)}")
print("=" * 70)

# ==========================================
# FLIGHT RECOMMENDATIONS
# ==========================================

print()
print("=" * 70)
print("FLIGHT RECOMMENDATIONS")
print("=" * 70)

print_recommendation(
    "🏆 BEST OVERALL",
    best_overall,
    show_scores=True,
)

print_recommendation(
    "💰 CHEAPEST",
    cheapest_scored,
    same_as="Best Overall"
    if cheapest_scored
    and best_overall
    and make_result_key(cheapest_scored) == make_result_key(best_overall)
    else None,
)

print_recommendation(
    "⚡ FASTEST",
    fastest,
    same_as="Best Overall"
    if fastest
    and best_overall
    and make_result_key(fastest) == make_result_key(best_overall)
    else None,
)

print_recommendation(
    "📅 BEST 5-DAY TRIP",
    best_5_day,
    same_as="Best Overall"
    if best_5_day
    and best_overall
    and make_result_key(best_5_day) == make_result_key(best_overall)
    else None,
)

print_recommendation(
    "📅 BEST 6-DAY TRIP",
    best_6_day,
    same_as="Best Overall"
    if best_6_day
    and best_overall
    and make_result_key(best_6_day) == make_result_key(best_overall)
    else None,
)

print_recommendation(
    "💡 DISTINCT ALTERNATIVE",
    best_alternative,
)

# ==========================================
# TOP SCORED FLIGHTS
# ==========================================

print()
print("=" * 70)
print("TOP SCORED FLIGHTS")
print("=" * 70)

if scored_results:
    for index, result in enumerate(scored_results[:10], start=1):
        print()
        print(
            f"{index}. "
            f"₹{result['price']:,} | "
            f"{result['departure_airport']} → {result['arrival_airport']} | "
            f"Score: {result['final_score']:.2f}"
        )
        print(
            f"   Dates: "
            f"{result['departure_date']} → {result['return_date']}"
        )
        if result.get("duration") is not None:
            print(
                f"   Flight duration: "
                f"{format_duration(result['duration'])}"
            )
        print(
            f"   Stops: "
            f"{get_number_of_stops(result)}"
        )
        print(
            f"   Price: {result['price_score']:.2f} | "
            f"Duration: {result['duration_score']:.2f} | "
            f"Stops: {result['stops_score']:.2f} | "
            f"Convenience: {result['convenience_score']:.2f}"
        )
else:
    print("No scored flight results found.")


# ==========================================
# FLIGHTAPI.IO CROSS-CHECK
# ==========================================

print()
print("FLIGHTAPI.IO CROSS-CHECK")
print("-" * 70)

flightapi_key = os.getenv("FLIGHTAPI_API_KEY")

if flightapi_key and ranked_results:
    verifications = verify_top_results_with_flightapi(
        ranked_results=ranked_results,
        max_checks=3,
        api_key=flightapi_key,
    )

    for index, item in enumerate(verifications, start=1):
        print()
        print(
            f"{index}. "
            f"{item['departure_airport']} → "
            f"{item['arrival_airport']} | "
            f"{item['departure_date']} → "
            f"{item['return_date']}"
        )
        print(
            f"   SerpApi: "
            f"₹{item['serpapi_price']:,}"
        )

        if item["flightapi_status"] == "priced_result":
            print(
                f"   FlightAPI: "
                f"{item['flightapi_currency'] or ''} "
                f"{item['flightapi_price']}"
            )
        elif item["flightapi_status"] == "provider_restriction":
            print(
                "   FlightAPI: "
                "Skipped — provider restriction "
                "(Russia-related route)"
            )
        else:
            print("   FlightAPI: No priced result")
else:
    print(
        "FlightAPI cross-check skipped "
        "(missing FLIGHTAPI_API_KEY or no ranked results)."
    )


# ==========================================
# DISPLAY CHEAPEST BY AIRPORT
# ==========================================

print()
print("CHEAPEST BY AIRPORT")
print("-" * 70)

if cheapest_by_airport:
    for airport, result in sorted(cheapest_by_airport.items()):
        print(
            f"{airport}: ₹{result['price']:,} | "
            f"{result['departure_date']} → {result['return_date']}"
        )
else:
    print("No priced flights found.")


# ==========================================
# DISPLAY CHEAPEST BY TRIP DURATION
# ==========================================

print()
print("CHEAPEST BY TRIP DURATION")
print("-" * 70)

if cheapest_by_duration:
    for duration, result in sorted(cheapest_by_duration.items()):
        print(
            f"{duration} days: ₹{result['price']:,} | "
            f"{result['departure_date']} → {result['return_date']}"
        )
else:
    print("No priced flights found.")


# ==========================================
# DISPLAY SEARCH STATISTICS
# ==========================================

print()
print("SEARCH STATISTICS")
print("-" * 70)

print(f"Total API searches: {statistics.get('total_searches', 0)}")
print(f"Successful API responses: {statistics.get('successful_api_searches', 0)}")
print(f"Priced flights found: {statistics.get('priced_results', 0)}")
print(f"No priced flights: {statistics.get('no_price_searches', 0)}")
print(f"API errors: {statistics.get('failed_api_searches', 0)}")
print(f"API success rate: {statistics.get('api_success_rate', 0)}%")
print(f"Priced result rate: {statistics.get('priced_result_rate', 0)}%")
print(f"No-price rate: {statistics.get('no_price_rate', 0)}%")

if statistics.get("cheapest_price") is not None:
    print(f"Cheapest price: ₹{statistics['cheapest_price']:,}")
    print(f"Most expensive price: ₹{statistics['most_expensive_price']:,}")
    print(f"Average price: ₹{statistics['average_price']:,.2f}")
else:
    print("No priced flight results.")

print()
print("=" * 70)

