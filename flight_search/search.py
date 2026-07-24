import os

from dotenv import load_dotenv
import serpapi

from flight_search.airports import (
    get_airports
)
# Load environment variables
load_dotenv()

API_KEY = os.getenv("SERPAPI_API_KEY")


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

    results = client.search(params)

    return results

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
        "departure_date": departure_date,
        "return_date": return_date,
        "price": cheapest["price"],
        "duration": cheapest.get(
            "total_duration"
        ),
        "flight": cheapest,
    }

from utils.dates import (
    generate_date_combinations
)

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
    Search flights across multiple
    departure and arrival airports.

    max_searches applies to each
    airport/date combination.
    """

    combinations = (
        generate_date_combinations(
            start_date=start_date,
            end_date=end_date,
            min_trip_days=min_trip_days,
            max_trip_days=max_trip_days,
        )
    )

    # Limit date combinations
    combinations = combinations[
        :max_searches
    ]

    departure_airports = (
        get_airports(departure_id)
    )

    arrival_airports = (
        get_airports(arrival_id)
    )

    results = []

    total_searches = (
        len(combinations)
        * len(departure_airports)
        * len(arrival_airports)
    )

    print(
        f"Total planned searches: "
        f"{total_searches}"
    )

    search_number = 0

    for departure_airport in (
        departure_airports
    ):

        for arrival_airport in (
            arrival_airports
        ):

            for combination in (
                combinations
            ):

                search_number += 1

                departure_date = (
                    combination[
                        "departure_date"
                    ]
                )

                return_date = (
                    combination[
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
                            f"₹{cheapest['price']:,}"
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

    return results