import os
from dotenv import load_dotenv
from flight_search.providers import get_default_provider

from flight_search.planner import (
    create_search_plan,
)
from flight_search.planner import (
    create_initial_search_plan,
    create_adaptive_search_plan,
)
from flight_search.airports import (
    get_airports,
)
from flight_search.results import (
    rank_airports_by_price,
)
from utils.dates import (
    generate_date_combinations,
)

from flight_search.results import (
    rank_results,
    get_cheapest_result,
    calculate_statistics,
    get_cheapest_by_airport,
    get_cheapest_by_trip_duration,
)


# ==========================================
# LOAD ENVIRONMENT VARIABLES
# ==========================================

load_dotenv()

API_KEY = os.getenv(
    "SERPAPI_API_KEY"
)

_PROVIDER = None


def get_search_provider(provider=None):
    global _PROVIDER

    if provider is not None:
        return provider

    if _PROVIDER is None:
        _PROVIDER = get_default_provider()

    return _PROVIDER


def search_flights(
    departure_id: str,
    arrival_id: str,
    outbound_date: str,
    return_date: str,
    provider=None,
):
    """
    Search flights through the active provider.
    """
    active_provider = get_search_provider(provider)

    return active_provider.search_round_trip(
        departure_id=departure_id,
        arrival_id=arrival_id,
        outbound_date=outbound_date,
        return_date=return_date,
    )


# ==========================================
# EXTRACT CHEAPEST FLIGHT
# ==========================================

def extract_cheapest_flight(
    results,
    departure_date,
    return_date,
):
    """
    Extract the cheapest flight from
    SerpApi results.
    """

    best_flights = results.get(
        "best_flights",
        []
    )

    other_flights = results.get(
        "other_flights",
        []
    )

    all_flights = (
        best_flights
        + other_flights
    )

    if not all_flights:
        return None

    # Filter out results without prices
    valid_flights = [
        flight
        for flight in all_flights
        if flight.get("price") is not None
    ]

    if not valid_flights:
        return None

    cheapest = min(
        valid_flights,
        key=lambda flight: flight["price"]
    )

    return {
        "departure_date":
            departure_date,

        "return_date":
            return_date,

        "price":
            cheapest["price"],

        "duration":
            cheapest.get(
                "total_duration"
            ),

        "flight":
            cheapest,
    }


# ==========================================
# FLEXIBLE DATE SEARCH
# ==========================================

def search_flexible_dates(
    departure_id: str,
    arrival_id: str,
    start_date: str,
    end_date: str,
    min_trip_days: int,
    max_trip_days: int,
    max_searches: int = 20,
):
    """
    Search flights using adaptive airport
    budget allocation.

    Phase 1:
        Explore all airport pairs.

    Phase 2:
        Allocate remaining API calls to
        promising airport pairs.

    max_searches is the TOTAL number of
    SerpApi calls allowed.
    """

    if max_searches <= 0:
        print("API search budget must be greater than 0.")

        return {
            "results": [],
            "ranked_results": [],
            "cheapest": None,
            "cheapest_by_airport": {},
            "cheapest_by_duration": {},
            "statistics": {
                "total_searches": 0,
                "successful_api_searches": 0,
                "no_price_searches": 0,
                "failed_api_searches": 0,
                "priced_results": 0,
                "api_success_rate": 0,
                "priced_result_rate": 0,
                "no_price_rate": 0,
                "cheapest_price": None,
                "most_expensive_price": None,
                "average_price": None,
            },
        }

    # ==========================================
    # GENERATE DATE COMBINATIONS
    # ==========================================

    date_combinations = (
        generate_date_combinations(
            start_date=start_date,
            end_date=end_date,
            min_trip_days=min_trip_days,
            max_trip_days=max_trip_days,
        )
    )

    if not date_combinations:
        print("No valid date combinations found.")

        return {
            "results": [],
            "ranked_results": [],
            "cheapest": None,
            "cheapest_by_airport": {},
            "cheapest_by_duration": {},
            "statistics": {
                "total_searches": 0,
                "successful_api_searches": 0,
                "no_price_searches": 0,
                "failed_api_searches": 0,
                "priced_results": 0,
                "api_success_rate": 0,
                "priced_result_rate": 0,
                "no_price_rate": 0,
                "cheapest_price": None,
                "most_expensive_price": None,
                "average_price": None,
            },
        }

    # ==========================================
    # DETERMINE PHASE 1 BUDGET
    # ==========================================

    exploration_budget = max(
        1,
        int(
            max_searches * 0.6
        ),
    )

    exploration_budget = min(
        exploration_budget,
        max_searches,
    )

    adaptive_budget = (
        max_searches
        - exploration_budget
    )

    # ==========================================
    # CREATE PHASE 1 PLAN
    # ==========================================

    exploration_plan = (
        create_initial_search_plan(
            departure_id=departure_id,
            arrival_id=arrival_id,
            start_date=start_date,
            end_date=end_date,
            min_trip_days=min_trip_days,
            max_trip_days=max_trip_days,
            max_api_calls=exploration_budget,
        )
    )

    if not exploration_plan:
        print("No exploration searches planned.")

        return {
            "results": [],
            "ranked_results": [],
            "cheapest": None,
            "cheapest_by_airport": {},
            "cheapest_by_duration": {},
            "statistics": {
                "total_searches": 0,
                "successful_api_searches": 0,
                "no_price_searches": 0,
                "failed_api_searches": 0,
                "priced_results": 0,
                "api_success_rate": 0,
                "priced_result_rate": 0,
                "no_price_rate": 0,
                "cheapest_price": None,
                "most_expensive_price": None,
                "average_price": None,
            },
        }

    print()
    print("=" * 70)
    print("ADAPTIVE FLIGHT SEARCH")
    print("=" * 70)
    print(
        f"Route: "
        f"{departure_id} → {arrival_id}"
    )
    print(
        f"Search window: "
        f"{start_date} → {end_date}"
    )
    print(
        f"Trip duration: "
        f"{min_trip_days}–"
        f"{max_trip_days} days"
    )
    print(
        f"Total API search budget: "
        f"{max_searches}"
    )
    print(
        f"Phase 1 exploration budget: "
        f"{exploration_budget}"
    )
    print(
        f"Phase 2 adaptive budget: "
        f"{adaptive_budget}"
    )
    print("=" * 70)

    # ==========================================
    # SEARCH TRACKING
    # ==========================================

    results = []

    all_searches = []

    successful_api_searches = 0
    no_price_searches = 0
    failed_api_searches = 0

    # ==========================================
    # INNER SEARCH EXECUTOR
    # ==========================================

    def execute_search_plan(
        search_plan,
        phase_name,
    ):

        nonlocal successful_api_searches
        nonlocal no_price_searches
        nonlocal failed_api_searches

        for search in search_plan:

            search_number = (
                len(all_searches) + 1
            )

            departure_airport = search[
                "departure_airport"
            ]

            arrival_airport = search[
                "arrival_airport"
            ]

            departure_date = search[
                "departure_date"
            ]

            return_date = search[
                "return_date"
            ]

            print()
            print(
                f"[{search_number}/"
                f"{max_searches}] "
                f"{phase_name} | "
                f"{departure_airport} → "
                f"{arrival_airport} | "
                f"{departure_date} → "
                f"{return_date}"
            )

            try:

                search_result = (
                    search_flights(
                        departure_id=(
                            departure_airport
                        ),
                        arrival_id=(
                            arrival_airport
                        ),
                        outbound_date=(
                            departure_date
                        ),
                        return_date=(
                            return_date
                        ),
                    )
                )

                successful_api_searches += 1

                cheapest = (
                    extract_cheapest_flight(
                        results=search_result,
                        departure_date=(
                            departure_date
                        ),
                        return_date=(
                            return_date
                        ),
                    )
                )

                if cheapest:

                    cheapest[
                        "departure_airport"
                    ] = departure_airport

                    cheapest[
                        "arrival_airport"
                    ] = arrival_airport

                    cheapest[
                        "trip_days"
                    ] = search.get(
                        "trip_days"
                    )

                    results.append(
                        cheapest
                    )

                    print(
                        f"    Cheapest: "
                        f"₹"
                        f"{cheapest['price']:,}"
                    )

                else:

                    no_price_searches += 1

                    print(
                        "    API response received, "
                        "but no priced flights found."
                    )

            except Exception as error:

                failed_api_searches += 1

                print(
                    f"    API SEARCH ERROR: "
                    f"{error}"
                )

            all_searches.append(
                search
            )

    # ==========================================
    # PHASE 1 — EXPLORATION
    # ==========================================

    print()
    print(
        "PHASE 1 — EXPLORATION"
    )
    print("-" * 70)

    execute_search_plan(
        search_plan=exploration_plan,
        phase_name="EXPLORE",
    )

    # ==========================================
    # RANK AIRPORTS
    # ==========================================

    airport_rankings = (
        rank_airports_by_price(
            results
        )
    )

    print()
    print(
        "AIRPORT PERFORMANCE AFTER EXPLORATION"
    )
    print("-" * 70)

    if airport_rankings:

        for index, ranking in enumerate(
            airport_rankings,
            start=1,
        ):

            print(
                f"{index}. "
                f"{ranking['departure_airport']} → "
                f"{ranking['arrival_airport']} | "
                f"₹{ranking['price']:,}"
            )

    else:

        print(
            "No priced flights found during "
            "exploration."
        )

    # ==========================================
    # PHASE 2 — ADAPTIVE SEARCH
    # ==========================================

    remaining_budget = (
        max_searches
        - len(all_searches)
    )

    adaptive_plan = (
        create_adaptive_search_plan(
            date_combinations=(
                date_combinations
            ),
            airport_rankings=(
                airport_rankings
            ),
            already_searched=(
                all_searches
            ),
            remaining_api_calls=(
                remaining_budget
            ),
        )
    )

    print(
        f"Adaptive searches planned: "
        f"{len(adaptive_plan)}"
    )

    print(
        f"Total searches after adaptive planning: "
        f"{len(all_searches) + len(adaptive_plan)}"
    )

    print()
    print(
        "PHASE 2 — ADAPTIVE SEARCH"
    )
    print("-" * 70)

    if adaptive_plan:

        execute_search_plan(
            search_plan=adaptive_plan,
            phase_name="ADAPT",
        )

    else:

        print(
            "No additional adaptive searches "
            "were planned."
        )

    # ==========================================
    # FINAL SAFETY CHECK
    # ==========================================

    assert (
        len(all_searches)
        <= max_searches
    ), (
        "API search budget exceeded."
    )

    # ==========================================
    # FINAL RESULTS
    # ==========================================

    ranked_results = rank_results(
        results=results,
        top_n=10,
    )

    cheapest_result = (
        get_cheapest_result(
            results
        )
    )

    statistics = calculate_statistics(
        results=results,
        total_searches=(
            len(all_searches)
        ),
        successful_api_searches=(
            successful_api_searches
        ),
        no_price_searches=(
            no_price_searches
        ),
        failed_api_searches=(
            failed_api_searches
        ),
    )

    cheapest_by_airport = (
        get_cheapest_by_airport(
            results
        )
    )

    cheapest_by_duration = (
        get_cheapest_by_trip_duration(
            results
        )
    )

    # ==========================================
    # FINAL REPORT
    # ==========================================

    print()
    print("=" * 70)
    print("SEARCH COMPLETE")
    print("=" * 70)

    print(
        f"API searches executed: "
        f"{statistics['total_searches']}"
    )

    print(
        f"API responses successful: "
        f"{statistics['successful_api_searches']}"
    )

    print(
        f"Priced flights found: "
        f"{statistics['priced_results']}"
    )

    print(
        f"No priced flights: "
        f"{statistics['no_price_searches']}"
    )

    print(
        f"API errors: "
        f"{statistics['failed_api_searches']}"
    )

    print()
    print(
        "CHEAPEST OVERALL"
    )

    print("-" * 70)

    if cheapest_result:

        print(
            f"₹{cheapest_result['price']:,} | "
            f"{cheapest_result['departure_airport']} → "
            f"{cheapest_result['arrival_airport']} | "
            f"{cheapest_result['departure_date']} → "
            f"{cheapest_result['return_date']}"
        )

    else:

        print(
            "No priced flights found."
        )

    print()
    print(
        "TOP FLIGHT OPTIONS"
    )

    print("-" * 70)

    if ranked_results:

        for index, result in enumerate(
            ranked_results,
            start=1,
        ):

            print(
                f"{index}. "
                f"₹{result['price']:,} | "
                f"{result['departure_airport']} → "
                f"{result['arrival_airport']} | "
                f"{result['departure_date']} → "
                f"{result['return_date']}"
            )

    else:

        print(
            "No priced flights found."
        )

    print()
    print(
        "CHEAPEST BY AIRPORT"
    )

    print("-" * 70)

    if cheapest_by_airport:

        for airport, result in sorted(
            cheapest_by_airport.items()
        ):

            print(
                f"{airport}: "
                f"₹{result['price']:,} | "
                f"{result['departure_date']} → "
                f"{result['return_date']}"
            )

    else:

        print(
            "No priced flights found."
        )

    print()
    print(
        "CHEAPEST BY TRIP DURATION"
    )

    print("-" * 70)

    if cheapest_by_duration:

        for duration, result in sorted(
            cheapest_by_duration.items()
        ):

            print(
                f"{duration} days: "
                f"₹{result['price']:,} | "
                f"{result['departure_date']} → "
                f"{result['return_date']}"
            )

    else:

        print(
            "No priced flights found."
        )

    print()
    print(
        "SEARCH STATISTICS"
    )

    print("-" * 70)

    print(
        f"Total API searches: "
        f"{statistics['total_searches']}"
    )

    print(
        f"Successful API responses: "
        f"{statistics['successful_api_searches']}"
    )

    print(
        f"Priced flights found: "
        f"{statistics['priced_results']}"
    )

    print(
        f"No priced flights: "
        f"{statistics['no_price_searches']}"
    )

    print(
        f"API errors: "
        f"{statistics['failed_api_searches']}"
    )

    print(
        f"API success rate: "
        f"{statistics['api_success_rate']}%"
    )

    print(
        f"Priced result rate: "
        f"{statistics['priced_result_rate']}%"
    )

    print(
        f"No-price rate: "
        f"{statistics['no_price_rate']}%"
    )

    if (
        statistics[
            "cheapest_price"
        ]
        is not None
    ):

        print(
            f"Cheapest price: "
            f"₹"
            f"{statistics['cheapest_price']:,}"
        )

        print(
            f"Most expensive price: "
            f"₹"
            f"{statistics['most_expensive_price']:,}"
        )

        print(
            f"Average price: "
            f"₹"
            f"{statistics['average_price']:,.2f}"
        )

    else:

        print(
            "No priced flight results."
        )

    print()
    print("=" * 70)

    return {
        "results": results,
        "ranked_results": ranked_results,
        "cheapest": cheapest_result,
        "cheapest_by_airport": (
            cheapest_by_airport
        ),
        "cheapest_by_duration": (
            cheapest_by_duration
        ),
        "statistics": statistics,
    }