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
    successful_api_searches,
    no_price_searches,
    failed_api_searches,
):
    """
    Calculate detailed search statistics.

    successful_api_searches:
        Number of API requests that returned
        a valid response.

    no_price_searches:
        Number of valid API responses where
        no priced flight was found.

    failed_api_searches:
        Number of API requests that failed.
    """

    valid_results = [
        result
        for result in results
        if result.get("price") is not None
    ]

    priced_results = len(
        valid_results
    )

    # ==========================================
    # VALIDATE SEARCH COUNTS
    # ==========================================

    calculated_total = (
        successful_api_searches
        + failed_api_searches
    )

    if calculated_total != total_searches:

        raise ValueError(

            "Search statistics mismatch: "

            f"total_searches="
            f"{total_searches}, "

            f"successful_api_searches="
            f"{successful_api_searches}, "

            f"failed_api_searches="
            f"{failed_api_searches}"

        )


    # ==========================================
    # CALCULATE API SUCCESS RATE
    # ==========================================

    api_success_rate = (

        successful_api_searches
        / total_searches
        * 100

        if total_searches > 0

        else 0

    )


    # ==========================================
    # CALCULATE PRICED RESULT RATE
    # ==========================================

    priced_result_rate = (

        priced_results
        / total_searches
        * 100

        if total_searches > 0

        else 0

    )


    # ==========================================
    # NO-PRICE RATE
    # ==========================================

    no_price_rate = (

        no_price_searches
        / successful_api_searches
        * 100

        if successful_api_searches > 0

        else 0

    )


    # ==========================================
    # NO RESULTS AT ALL
    # ==========================================

    if not valid_results:

        return {

            "total_searches":
                total_searches,

            "successful_api_searches":
                successful_api_searches,

            "no_price_searches":
                no_price_searches,

            "failed_api_searches":
                failed_api_searches,

            "priced_results":
                priced_results,

            "api_success_rate":
                round(
                    api_success_rate,
                    2,
                ),

            "priced_result_rate":
                round(
                    priced_result_rate,
                    2,
                ),

            "no_price_rate":
                round(
                    no_price_rate,
                    2,
                ),

            "cheapest_price":
                None,

            "most_expensive_price":
                None,

            "average_price":
                None,

        }


    # ==========================================
    # PRICE STATISTICS
    # ==========================================

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


    # ==========================================
    # RETURN STATISTICS
    # ==========================================

    return {

        "total_searches":
            total_searches,

        "successful_api_searches":
            successful_api_searches,

        "no_price_searches":
            no_price_searches,

        "failed_api_searches":
            failed_api_searches,

        "priced_results":
            priced_results,

        "api_success_rate":
            round(
                api_success_rate,
                2,
            ),

        "priced_result_rate":
            round(
                priced_result_rate,
                2,
            ),

        "no_price_rate":
            round(
                no_price_rate,
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

def rank_airports_by_price(
    results,
):
    """
    Rank airport pairs based on the
    cheapest priced flight found.
    """

    airport_prices = {}

    for result in results:

        departure_airport = result.get(
            "departure_airport"
        )

        arrival_airport = result.get(
            "arrival_airport"
        )

        price = result.get(
            "price"
        )

        if (
            departure_airport is None
            or arrival_airport is None
            or price is None
        ):
            continue

        airport_pair = (
            f"{departure_airport}"
            f"→"
            f"{arrival_airport}"
        )

        if (
            airport_pair not in airport_prices
            or price
            < airport_prices[
                airport_pair
            ]["price"]
        ):

            airport_prices[
                airport_pair
            ] = {
                "airport_pair":
                    airport_pair,

                "departure_airport":
                    departure_airport,

                "arrival_airport":
                    arrival_airport,

                "price":
                    price,

                "result":
                    result,
            }

    return sorted(
        airport_prices.values(),
        key=lambda item: item[
            "price"
        ],
    )