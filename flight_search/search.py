import os

from dotenv import load_dotenv
import serpapi

from flight_search.planner import (
    create_search_plan,
)

from flight_search.airports import (
    get_airports,
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

    max_searches is the TOTAL number of
    SerpApi calls allowed.
    """

    search_plan = create_search_plan(
        departure_id=departure_id,
        arrival_id=arrival_id,
        start_date=start_date,
        end_date=end_date,
        min_trip_days=min_trip_days,
        max_trip_days=max_trip_days,
        max_api_calls=max_searches,
    )

    if not search_plan:
        print("No searches planned.")
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

    total_searches = len(search_plan)

    print()
    print("=" * 70)
    print("INTELLIGENT FLIGHT SEARCH")
    print("=" * 70)
    print(f"Route: {departure_id} → {arrival_id}")
    print(f"Search window: {start_date} → {end_date}")
    print(f"Trip duration: {min_trip_days}–{max_trip_days} days")
    print(f"API search budget: {max_searches}")
    print(f"Actual planned searches: {total_searches}")
    print("=" * 70)
    print()

    results = []
    search_number = 0
    successful_api_searches = 0
    no_price_searches = 0
    failed_api_searches = 0

    for search in search_plan:
        search_number += 1

        departure_airport = search["departure_airport"]
        arrival_airport = search["arrival_airport"]
        departure_date = search["departure_date"]
        return_date = search["return_date"]

        print(
            f"[{search_number}/{total_searches}] "
            f"{departure_airport} → {arrival_airport} | "
            f"{departure_date} → {return_date}"
        )

        try:
            search_result = search_flights(
                departure_id=departure_airport,
                arrival_id=arrival_airport,
                outbound_date=departure_date,
                return_date=return_date,
            )

            successful_api_searches += 1

            cheapest = extract_cheapest_flight(
                results=search_result,
                departure_date=departure_date,
                return_date=return_date,
            )

            if cheapest:
                cheapest["departure_airport"] = departure_airport
                cheapest["arrival_airport"] = arrival_airport
                results.append(cheapest)

                print(f"    Cheapest: ₹{cheapest['price']:,}")
            else:
                no_price_searches += 1
                print("    API response received, but no priced flights found.")

        except Exception as error:
            failed_api_searches += 1
            print(f"    API SEARCH ERROR: {error}")

    assert search_number == total_searches, "API search count mismatch."

    ranked_results = rank_results(results=results, top_n=10)
    cheapest_result = get_cheapest_result(results)
    statistics = calculate_statistics(
        results=results,
        total_searches=search_number,
        successful_api_searches=successful_api_searches,
        no_price_searches=no_price_searches,
        failed_api_searches=failed_api_searches,
    )
    cheapest_by_airport = get_cheapest_by_airport(results)
    cheapest_by_duration = get_cheapest_by_trip_duration(results)

    print()
    print("=" * 70)
    print("SEARCH COMPLETE")
    print("=" * 70)
    print(f"API searches executed: {statistics['total_searches']}")
    print(f"API responses successful: {statistics['successful_api_searches']}")
    print(f"Priced flights found: {statistics['priced_results']}")
    print(f"No priced flights: {statistics['no_price_searches']}")
    print(f"API errors: {statistics['failed_api_searches']}")

    print()
    print("CHEAPEST OVERALL")
    print("-" * 70)
    if cheapest_result:
        print(
            f"₹{cheapest_result['price']:,} | "
            f"{cheapest_result['departure_airport']} → {cheapest_result['arrival_airport']} | "
            f"{cheapest_result['departure_date']} → {cheapest_result['return_date']}"
        )
    else:
        print("No priced flights found.")

    print()
    print("TOP FLIGHT OPTIONS")
    print("-" * 70)
    if ranked_results:
        for index, result in enumerate(ranked_results, start=1):
            print(
                f"{index}. ₹{result['price']:,} | "
                f"{result['departure_airport']} → {result['arrival_airport']} | "
                f"{result['departure_date']} → {result['return_date']}"
            )
    else:
        print("No priced flights found.")

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

    print()
    print("SEARCH STATISTICS")
    print("-" * 70)
    print(f"Total API searches: {statistics['total_searches']}")
    print(f"Successful API responses: {statistics['successful_api_searches']}")
    print(f"Priced flights found: {statistics['priced_results']}")
    print(f"No priced flights: {statistics['no_price_searches']}")
    print(f"API errors: {statistics['failed_api_searches']}")
    print(f"API success rate: {statistics['api_success_rate']}%")
    print(f"Priced result rate: {statistics['priced_result_rate']}%")
    print(f"No-price rate: {statistics['no_price_rate']}%")

    if statistics["cheapest_price"] is not None:
        print(f"Cheapest price: ₹{statistics['cheapest_price']:,}")
        print(f"Most expensive price: ₹{statistics['most_expensive_price']:,}")
        print(f"Average price: ₹{statistics['average_price']:,.2f}")
    else:
        print("No priced flight results.")

    print()
    print("=" * 70)

    return {
        "results": results,
        "ranked_results": ranked_results,
        "cheapest": cheapest_result,
        "cheapest_by_airport": cheapest_by_airport,
        "cheapest_by_duration": cheapest_by_duration,
        "statistics": statistics,
    }