import os

from dotenv import load_dotenv
import serpapi

from flight_search.planner import (
    create_search_plan,
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


# ==========================================
# SERPAPI SEARCH
# ==========================================

def search_flights(
    departure_id: str,
    arrival_id: str,
    outbound_date: str,
    return_date: str,
):
    """
    Search Google Flights through SerpApi.
    """

    if not API_KEY:
        raise ValueError(
            "SERPAPI_API_KEY not found."
        )

    client = serpapi.Client(
        api_key=API_KEY
    )

    params = {
        "engine": "google_flights",
        "departure_id": departure_id,
        "arrival_id": arrival_id,
        "outbound_date": outbound_date,
        "return_date": return_date,
        "currency": "INR",
        "hl": "en",
        "type": "1",
    }

    results = client.search(
        params
    )

    return results


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
    Search flights using an intelligent
    date and airport search plan.

    max_searches represents the TOTAL
    number of SerpApi calls allowed
    for the entire search.

    Example:

        max_searches = 10

    means at most 10 SerpApi calls,
    regardless of the number of airports.
    """

    # ==========================================
    # CREATE SEARCH PLAN
    # ==========================================

    search_plan = create_search_plan(

        departure_id=departure_id,

        arrival_id=arrival_id,

        start_date=start_date,

        end_date=end_date,

        min_trip_days=min_trip_days,

        max_trip_days=max_trip_days,

        max_api_calls=max_searches,
    )


    # ==========================================
    # HANDLE EMPTY SEARCH PLAN
    # ==========================================

    if not search_plan:

        print(
            "No searches planned."
        )

        return []


    # ==========================================
    # DISPLAY SEARCH SUMMARY
    # ==========================================

    total_searches = len(
        search_plan
    )

    print()

    print("=" * 70)

    print(
        "INTELLIGENT FLIGHT SEARCH"
    )

    print("=" * 70)

    print(
        f"Route: "
        f"{departure_id} → "
        f"{arrival_id}"
    )

    print(
        f"Search window: "
        f"{start_date} → "
        f"{end_date}"
    )

    print(
        f"Trip duration: "
        f"{min_trip_days}–"
        f"{max_trip_days} days"
    )

    print(
        f"API search budget: "
        f"{max_searches}"
    )

    print(
        f"Actual planned searches: "
        f"{total_searches}"
    )

    print("=" * 70)

    print()


    # ==========================================
    # EXECUTE SEARCH PLAN
    # ==========================================

    results = []

    search_number = 0

    for search in search_plan:

        search_number += 1

        departure_airport = (
            search[
                "departure_airport"
            ]
        )

        arrival_airport = (
            search[
                "arrival_airport"
            ]
        )

        departure_date = (
            search[
                "departure_date"
            ]
        )

        return_date = (
            search[
                "return_date"
            ]
        )


        print(
            f"[{search_number}/"
            f"{total_searches}] "
            f"{departure_airport} → "
            f"{arrival_airport} | "
            f"{departure_date} → "
            f"{return_date}"
        )


        # ======================================
        # CALL SERPAPI
        # ======================================

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


            # ==================================
            # EXTRACT CHEAPEST
            # ==================================

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


            # ==================================
            # STORE RESULT
            # ==================================

            if cheapest:

                cheapest[
                    "departure_airport"
                ] = (
                    departure_airport
                )

                cheapest[
                    "arrival_airport"
                ] = (
                    arrival_airport
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

                print(
                    "    No priced "
                    "flights found."
                )


        except Exception as error:

            print(
                f"    ERROR: "
                f"{error}"
            )


    # ==========================================
    # SEARCH COMPLETE
    # ==========================================

    # ==========================================
    # RESULTS ENGINE
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


    statistics = (
        calculate_statistics(

            results=results,

            total_searches=(
                search_number
            ),
        )
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
    # SEARCH COMPLETE SUMMARY
    # ==========================================

    print()

    print("=" * 70)

    print(
        "SEARCH COMPLETE"
    )

    print("=" * 70)

    print(
        f"API searches executed: "
        f"{search_number}"
    )

    print(
        f"Priced results found: "
        f"{len(results)}"
    )

    print()

    # ==========================================
    # CHEAPEST OVERALL
    # ==========================================

    if cheapest_result:

        print(
            "CHEAPEST OVERALL"
        )

        print("-" * 70)

        print(

            f"₹"
            f"{cheapest_result['price']:,}"
            f" | "

            f"{cheapest_result['departure_airport']}"
            f" → "
            f"{cheapest_result['arrival_airport']}"
            f" | "

            f"{cheapest_result['departure_date']}"
            f" → "
            f"{cheapest_result['return_date']}"

        )

        print()


    # ==========================================
    # TOP RESULTS
    # ==========================================

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

                f"₹"
                f"{result['price']:,}"
                f" | "

                f"{result['departure_airport']}"
                f" → "
                f"{result['arrival_airport']}"
                f" | "

                f"{result['departure_date']}"
                f" → "
                f"{result['return_date']}"

            )

    else:

        print(
            "No priced flights found."
        )


    print()


    # ==========================================
    # CHEAPEST BY AIRPORT
    # ==========================================

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

                f"₹"
                f"{result['price']:,}"
                f" | "

                f"{result['departure_date']}"
                f" → "
                f"{result['return_date']}"

            )

    else:

        print(
            "No priced flights found."
        )


    print()


    # ==========================================
    # CHEAPEST BY TRIP DURATION
    # ==========================================

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

                f"₹"
                f"{result['price']:,}"
                f" | "

                f"{result['departure_date']}"
                f" → "
                f"{result['return_date']}"

            )

    else:

        print(
            "No priced flights found."
        )


    print()


    # ==========================================
    # SEARCH STATISTICS
    # ==========================================

    print(
        "SEARCH STATISTICS"
    )

    print("-" * 70)

    print(

        f"Total searches: "
        f"{statistics['total_searches']}"

    )

    print(

        f"Successful searches: "
        f"{statistics['successful_searches']}"

    )

    print(

        f"Failed searches: "
        f"{statistics['failed_searches']}"

    )

    print(

        f"Success rate: "
        f"{statistics['success_rate']}%"

    )

    if statistics[
        "cheapest_price"
    ] is not None:

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


    # ==========================================
    # RETURN STRUCTURED REPORT
    # ==========================================

    return {

        "results":
            results,

        "ranked_results":
            ranked_results,

        "cheapest":
            cheapest_result,

        "cheapest_by_airport":
            cheapest_by_airport,

        "cheapest_by_duration":
            cheapest_by_duration,

        "statistics":
            statistics,

    }
