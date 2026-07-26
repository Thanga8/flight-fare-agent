from typing import Any, Dict, List


# ==========================================
# SCORING WEIGHTS
# ==========================================

PRICE_WEIGHT = 0.50

DURATION_WEIGHT = 0.25

STOPS_WEIGHT = 0.15

CONVENIENCE_WEIGHT = 0.10


# ==========================================
# PRICE SCORE
# ==========================================

def calculate_price_score(
    price: float,
    all_prices: List[float],
) -> float:
    """
    Calculate a normalized price score
    between 0 and 100.

    Cheapest flight gets 100.
    Most expensive gets 0.

    If all prices are identical,
    every flight receives 100.
    """

    if not all_prices:

        return 0.0

    cheapest_price = min(
        all_prices
    )

    most_expensive_price = max(
        all_prices
    )

    if (
        cheapest_price
        == most_expensive_price
    ):

        return 100.0

    score = (

        (
            most_expensive_price
            - price
        )

        /

        (
            most_expensive_price
            - cheapest_price
        )

    ) * 100

    return max(
        0.0,
        min(
            100.0,
            score,
        ),
    )


# ==========================================
# DURATION SCORE
# ==========================================

def calculate_duration_score(
    duration: int,
    all_durations: List[int],
) -> float:
    """
    Calculate a normalized duration score
    between 0 and 100.

    Shortest flight gets 100.
    Longest flight gets 0.
    """

    if not all_durations:

        return 0.0

    shortest_duration = min(
        all_durations
    )

    longest_duration = max(
        all_durations
    )

    if (
        shortest_duration
        == longest_duration
    ):

        return 100.0

    score = (

        (
            longest_duration
            - duration
        )

        /

        (
            longest_duration
            - shortest_duration
        )

    ) * 100

    return max(
        0.0,
        min(
            100.0,
            score,
        ),
    )


# ==========================================
# STOPS SCORE
# ==========================================

def calculate_stops_score(
    flight: Dict[str, Any],
) -> float:
    """
    Calculate a score based on
    the number of stops.
    """

    layovers = flight.get(
        "layovers",
        [],
    )

    number_of_stops = len(
        layovers
    )

    if number_of_stops == 0:

        return 100.0

    if number_of_stops == 1:

        return 75.0

    if number_of_stops == 2:

        return 40.0

    return 10.0


# ==========================================
# CONVENIENCE SCORE
# ==========================================

def calculate_convenience_score(
    flight: Dict[str, Any],
) -> float:
    """
    Calculate convenience based on
    layover duration and overnight flights.
    """

    score = 100.0

    layovers = flight.get(
        "layovers",
        [],
    )

    # --------------------------------------
    # LAYOVER PENALTY
    # --------------------------------------

    for layover in layovers:

        duration = layover.get(
            "duration",
            0,
        )

        if duration <= 120:
            # 2 hours or less
            score -= 5

        elif duration <= 240:
            # 2–4 hours
            score -= 10

        elif duration <= 360:
            # 4–6 hours
            score -= 20

        elif duration <= 720:
            # 6–12 hours
            score -= 35

        else:
            # More than 12 hours
            score -= 50

    # --------------------------------------
    # OVERNIGHT PENALTY
    # --------------------------------------

    flights = flight.get(
        "flights",
        [],
    )

    overnight_count = sum(

        1

        for segment in flights

        if segment.get(
            "overnight",
            False,
        )

    )

    score -= (
        overnight_count
        * 15
    )

    return max(
        0.0,
        min(
            100.0,
            score,
        ),
    )


# ==========================================
# FINAL SCORE
# ==========================================

def calculate_final_score(
    flight: Dict[str, Any],
    all_prices: List[float],
    all_durations: List[int],
) -> Dict[str, Any]:
    """
    Calculate all component scores
    and the final weighted score.
    """

    price = flight.get(
        "price"
    )

    duration = flight.get(
        "total_duration"
    )

    if price is None:

        raise ValueError(
            "Flight is missing price."
        )

    if duration is None:

        raise ValueError(
            "Flight is missing total_duration."
        )

    price_score = (
        calculate_price_score(
            price=price,
            all_prices=all_prices,
        )
    )

    duration_score = (
        calculate_duration_score(
            duration=duration,
            all_durations=all_durations,
        )
    )

    stops_score = (
        calculate_stops_score(
            flight=flight,
        )
    )

    convenience_score = (
        calculate_convenience_score(
            flight=flight,
        )
    )

    final_score = (

        (
            price_score
            * PRICE_WEIGHT
        )

        +

        (
            duration_score
            * DURATION_WEIGHT
        )

        +

        (
            stops_score
            * STOPS_WEIGHT
        )

        +

        (
            convenience_score
            * CONVENIENCE_WEIGHT
        )

    )

    return {

        "price_score":
            round(
                price_score,
                2,
            ),

        "duration_score":
            round(
                duration_score,
                2,
            ),

        "stops_score":
            round(
                stops_score,
                2,
            ),

        "convenience_score":
            round(
                convenience_score,
                2,
            ),

        "final_score":
            round(
                final_score,
                2,
            ),
    }