from __future__ import annotations

import os

from flight_search.providers.verification import (
    verify_top_results_with_flightapi,
)
from flight_search.search import search_flexible_dates

from flight_search.logging import logger

from flight_search.config import *
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
def run_search(
    verbose=True,
):
    report = search_flexible_dates(
        departure_id=ORIGIN,
        arrival_id=DESTINATION,
        start_date=START_DATE,
        end_date=END_DATE,
        min_trip_days=MIN_TRIP_DAYS,
        max_trip_days=MAX_TRIP_DAYS,
        max_searches=MAX_SEARCHES,
    )

    logger.set_verbose(verbose)
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

    logger.info()
    logger.info("=" * 70)
    logger.info("FLIGHT SEARCH SUMMARY")
    logger.info("=" * 70)
    logger.info(f"Route: {ORIGIN} → {DESTINATION}")
    logger.info(f"Search window: {START_DATE} → {END_DATE}")
    logger.info(f"Trip duration: {MIN_TRIP_DAYS}–{MAX_TRIP_DAYS} days")
    logger.info(f"API searches executed: {statistics.get('total_searches', 0)}")
    logger.info(f"Priced results found: {statistics.get('priced_results', 0)}")
    logger.info("=" * 70)

    # ==========================================
    # FLIGHT RECOMMENDATIONS
    # ==========================================

    logger.info()
    logger.info("=" * 70)
    logger.info("FLIGHT RECOMMENDATIONS")
    logger.info("=" * 70)

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

    logger.info()
    logger.info("=" * 70)
    logger.info("TOP SCORED FLIGHTS")
    logger.info("=" * 70)

    if scored_results:
        for index, result in enumerate(scored_results[:10], start=1):
            logger.info()
            logger.info(
                f"{index}. "
                f"₹{result['price']:,} | "
                f"{result['departure_airport']} → {result['arrival_airport']} | "
                f"Score: {result['final_score']:.2f}"
            )
            logger.info(
                f"   Dates: "
                f"{result['departure_date']} → {result['return_date']}"
            )
            if result.get("duration") is not None:
                logger.info(
                    f"   Flight duration: "
                    f"{format_duration(result['duration'])}"
                )
            logger.info(
                f"   Stops: "
                f"{get_number_of_stops(result)}"
            )
            logger.info(
                f"   Price: {result['price_score']:.2f} | "
                f"Duration: {result['duration_score']:.2f} | "
                f"Stops: {result['stops_score']:.2f} | "
                f"Convenience: {result['convenience_score']:.2f}"
            )
    else:
        logger.info("No scored flight results found.")


    # ==========================================
    # FLIGHTAPI.IO CROSS-CHECK
    # ==========================================

    logger.info()
    logger.info("FLIGHTAPI.IO CROSS-CHECK")
    logger.info("-" * 70)

    flightapi_key = os.getenv("FLIGHTAPI_API_KEY")

    if flightapi_key and ranked_results:
        verifications = verify_top_results_with_flightapi(
            ranked_results=ranked_results,
            max_checks=3,
            api_key=flightapi_key,
        )

        for index, item in enumerate(verifications, start=1):
            logger.info()
            logger.info(
                f"{index}. "
                f"{item['departure_airport']} → "
                f"{item['arrival_airport']} | "
                f"{item['departure_date']} → "
                f"{item['return_date']}"
            )
            logger.info(
                f"   SerpApi: "
                f"₹{item['serpapi_price']:,}"
            )

            if item["flightapi_status"] == "priced_result":
                logger.info(
                    f"   FlightAPI: "
                    f"{item['flightapi_currency'] or ''} "
                    f"{item['flightapi_price']}"
                )
            elif item["flightapi_status"] == "provider_restriction":
                logger.info(
                    "   FlightAPI: "
                    "Skipped — provider restriction "
                    "(Russia-related route)"
                )
            else:
                logger.info("   FlightAPI: No priced result")
    else:
        logger.info(
            "FlightAPI cross-check skipped "
            "(missing FLIGHTAPI_API_KEY or no ranked results)."
        )


    # ==========================================
    # DISPLAY CHEAPEST BY AIRPORT
    # ==========================================

    logger.info()
    logger.info("CHEAPEST BY AIRPORT")
    logger.info("-" * 70)

    if cheapest_by_airport:
        for airport, result in sorted(cheapest_by_airport.items()):
            logger.info(
                f"{airport}: ₹{result['price']:,} | "
                f"{result['departure_date']} → {result['return_date']}"
            )
    else:
        logger.info("No priced flights found.")


    # ==========================================
    # DISPLAY CHEAPEST BY TRIP DURATION
    # ==========================================

    logger.info()
    logger.info("CHEAPEST BY TRIP DURATION")
    logger.info("-" * 70)

    if cheapest_by_duration:
        for duration, result in sorted(cheapest_by_duration.items()):
            logger.info(
                f"{duration} days: ₹{result['price']:,} | "
                f"{result['departure_date']} → {result['return_date']}"
            )
    else:
        logger.info("No priced flights found.")


    # ==========================================
    # DISPLAY SEARCH STATISTICS
    # ==========================================

    logger.info()
    logger.info("SEARCH STATISTICS")
    logger.info("-" * 70)

    logger.info(f"Total API searches: {statistics.get('total_searches', 0)}")
    logger.info(f"Successful API responses: {statistics.get('successful_api_searches', 0)}")
    logger.info(f"Priced flights found: {statistics.get('priced_results', 0)}")
    logger.info(f"No priced flights: {statistics.get('no_price_searches', 0)}")
    logger.info(f"API errors: {statistics.get('failed_api_searches', 0)}")
    logger.info(f"API success rate: {statistics.get('api_success_rate', 0)}%")
    logger.info(f"Priced result rate: {statistics.get('priced_result_rate', 0)}%")
    logger.info(f"No-price rate: {statistics.get('no_price_rate', 0)}%")

    if statistics.get("cheapest_price") is not None:
        logger.info(f"Cheapest price: ₹{statistics['cheapest_price']:,}")
        logger.info(f"Most expensive price: ₹{statistics['most_expensive_price']:,}")
        logger.info(f"Average price: ₹{statistics['average_price']:,.2f}")
    else:
        logger.info("No priced flight results.")

    logger.info()
    logger.info("=" * 70)

    return report

if __name__ == "__main__":
    run_search(verbose=True)