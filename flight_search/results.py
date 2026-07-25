def rank_results(
    results,
    top_n=10,
):
    """
    Sort flight results by price
    and return the cheapest results.
    """

    if not results:
        return []

    # Remove results without valid prices
    valid_results = [
        result
        for result in results
        if result.get("price") is not None
    ]

    # Sort cheapest first
    sorted_results = sorted(
        valid_results,
        key=lambda result: result["price"],
    )

    # Return only top N
    return sorted_results[:top_n]


def get_cheapest_result(
    results,
):
    """
    Return the single cheapest
    flight result.
    """

    ranked_results = rank_results(
        results=results,
        top_n=1,
    )

    if not ranked_results:
        return None

    return ranked_results[0]

def calculate_statistics(
    results,
    total_searches,
):
    """
    Calculate summary statistics
    for the flight search.
    """

    valid_results = [
        result
        for result in results
        if result.get("price") is not None
    ]

    successful_searches = len(
        valid_results
    )

    failed_searches = (
        total_searches
        - successful_searches
    )

    if not valid_results:

        return {
            "total_searches":
                total_searches,

            "successful_searches":
                0,

            "failed_searches":
                failed_searches,

            "success_rate":
                0,

            "cheapest_price":
                None,

            "most_expensive_price":
                None,

            "average_price":
                None,
        }

    prices = [
        result["price"]
        for result in valid_results
    ]

    cheapest_price = min(
        prices
    )

    most_expensive_price = max(
        prices
    )

    average_price = (
        sum(prices)
        / len(prices)
    )

    success_rate = (
        successful_searches
        / total_searches
        * 100
        if total_searches > 0
        else 0
    )

    return {
        "total_searches":
            total_searches,

        "successful_searches":
            successful_searches,

        "failed_searches":
            failed_searches,

        "success_rate":
            round(
                success_rate,
                2,
            ),

        "cheapest_price":
            cheapest_price,

        "most_expensive_price":
            most_expensive_price,

        "average_price":
            round(
                average_price,
                2,
            ),
    }
def get_cheapest_by_airport(
    results,
):
    """
    Find the cheapest result for
    each arrival airport.
    """

    cheapest_by_airport = {}

    for result in results:

        airport = result.get(
            "arrival_airport"
        )

        price = result.get(
            "price"
        )

        if (
            airport is None
            or price is None
        ):
            continue

        if (
            airport
            not in cheapest_by_airport
        ):

            cheapest_by_airport[
                airport
            ] = result

        elif (
            price
            < cheapest_by_airport[
                airport
            ]["price"]
        ):

            cheapest_by_airport[
                airport
            ] = result

    return cheapest_by_airport

def get_cheapest_by_trip_duration(
    results,
):
    """
    Find the cheapest result for
    each trip duration.
    """

    cheapest_by_duration = {}

    for result in results:

        departure_date = result.get(
            "departure_date"
        )

        return_date = result.get(
            "return_date"
        )

        price = result.get(
            "price"
        )

        if (
            departure_date is None
            or return_date is None
            or price is None
        ):
            continue

        from datetime import date

        departure = date.fromisoformat(
            departure_date
        )

        return_day = date.fromisoformat(
            return_date
        )

        trip_days = (
            return_day
            - departure
        ).days

        if (
            trip_days
            not in cheapest_by_duration
        ):

            cheapest_by_duration[
                trip_days
            ] = result

        elif (
            price
            < cheapest_by_duration[
                trip_days
            ]["price"]
        ):

            cheapest_by_duration[
                trip_days
            ] = result

    return cheapest_by_duration

