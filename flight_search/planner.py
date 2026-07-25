from flight_search.airports import (
    get_airports,
)

from utils.dates import (
    generate_date_combinations,
    sample_date_combinations,
)


def create_search_plan(
    departure_id: str,
    arrival_id: str,
    start_date: str,
    end_date: str,
    min_trip_days: int,
    max_trip_days: int,
    max_api_calls: int,
):
    """
    Create a search plan that respects
    the total API call budget.

    The returned plan contains no API calls.
    It only determines what should be searched.
    """

    if max_api_calls <= 0:
        return []

    # ==========================================
    # GET AIRPORTS
    # ==========================================

    departure_airports = get_airports(
        departure_id
    )

    arrival_airports = get_airports(
        arrival_id
    )

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
        return []

    # ==========================================
    # CREATE AIRPORT PAIRS
    # ==========================================

    airport_pairs = []

    for departure_airport in (
        departure_airports
    ):

        for arrival_airport in (
            arrival_airports
        ):

            airport_pairs.append(
                {
                    "departure_airport":
                        departure_airport,

                    "arrival_airport":
                        arrival_airport,
                }
            )

    if not airport_pairs:
        return []

    # ==========================================
    # DETERMINE SEARCH ALLOCATION
    # ==========================================

    number_of_pairs = len(
        airport_pairs
    )

    base_allocation = (
        max_api_calls
        // number_of_pairs
    )

    remainder = (
        max_api_calls
        % number_of_pairs
    )

    search_plan = []

    # ==========================================
    # ALLOCATE SEARCHES
    # ==========================================

    for index, pair in enumerate(
        airport_pairs
    ):

        allocation = base_allocation

        # Distribute leftover searches
        # to the first few airport pairs.
        if index < remainder:
            allocation += 1

        # Don't request more dates than
        # actually exist.
        allocation = min(
            allocation,
            len(date_combinations),
        )

        selected_dates = (
            sample_date_combinations(

                combinations=(
                    date_combinations
                ),

                sample_size=allocation,
            )
        )

        for combination in (
            selected_dates
        ):

            search_plan.append(
                {
                    "departure_airport":
                        pair[
                            "departure_airport"
                        ],

                    "arrival_airport":
                        pair[
                            "arrival_airport"
                        ],

                    "departure_date":
                        combination[
                            "departure_date"
                        ],

                    "return_date":
                        combination[
                            "return_date"
                        ],

                    "trip_days":
                        combination[
                            "trip_days"
                        ],
                }
            )

    return search_plan