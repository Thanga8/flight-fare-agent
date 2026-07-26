from statistics import mean


# ==========================================
# PRICE COMPARISON
# ==========================================

def analyze_price_against_history(
    current_price,
    historical_results,
):
    """
    Compare a current flight price against
    comparable historical flight prices.

    Returns statistical price analysis.
    """

    if current_price is None:

        return {
            "current_price": None,
            "historical_count": 0,
            "historical_cheapest": None,
            "historical_average": None,
            "historical_median": None,
            "historical_most_expensive": None,
            "difference_from_average": None,
            "difference_percent_from_average": None,
            "difference_from_cheapest": None,
            "difference_percent_from_cheapest": None,
            "deal_assessment": "unknown",
        }

    # ==========================================
    # EXTRACT VALID HISTORICAL PRICES
    # ==========================================

    historical_prices = [

        result["price"]

        for result in historical_results

        if result.get("price") is not None
    ]

    if not historical_prices:

        return {
            "current_price":
                current_price,

            "historical_count":
                0,

            "historical_cheapest":
                None,

            "historical_average":
                None,

            "historical_median":
                None,

            "historical_most_expensive":
                None,

            "difference_from_average":
                None,

            "difference_percent_from_average":
                None,

            "difference_from_cheapest":
                None,

            "difference_percent_from_cheapest":
                None,

            "deal_assessment":
                "insufficient_history",
        }

    # ==========================================
    # CALCULATE HISTORICAL STATISTICS
    # ==========================================

    sorted_prices = sorted(
        historical_prices
    )

    historical_cheapest = (
        min(historical_prices)
    )

    historical_most_expensive = (
        max(historical_prices)
    )

    historical_average = (
        mean(historical_prices)
    )

    # Manual median calculation
    # avoids needing additional libraries

    count = len(sorted_prices)

    middle = count // 2

    if count % 2 == 0:

        historical_median = (

            sorted_prices[middle - 1]
            +
            sorted_prices[middle]

        ) / 2

    else:

        historical_median = (
            sorted_prices[middle]
        )

    # ==========================================
    # COMPARE CURRENT PRICE
    # AGAINST HISTORICAL AVERAGE
    # ==========================================

    difference_from_average = (

        current_price
        -
        historical_average

    )

    difference_percent_from_average = (

        (
            current_price
            -
            historical_average
        )

        /

        historical_average

    ) * 100

    # ==========================================
    # COMPARE CURRENT PRICE
    # AGAINST HISTORICAL CHEAPEST
    # ==========================================

    difference_from_cheapest = (

        current_price
        -
        historical_cheapest

    )

    difference_percent_from_cheapest = (

        (
            current_price
            -
            historical_cheapest
        )

        /

        historical_cheapest

    ) * 100

    # ==========================================
    # DEAL ASSESSMENT
    # ==========================================

    if (
        current_price
        <= historical_average * 0.85
    ):

        deal_assessment = (
            "excellent"
        )

    elif (
        current_price
        <= historical_average * 0.95
    ):

        deal_assessment = (
            "good"
        )

    elif (
        current_price
        <= historical_average * 1.05
    ):

        deal_assessment = (
            "average"
        )

    elif (
        current_price
        <= historical_average * 1.15
    ):

        deal_assessment = (
            "expensive"
        )

    else:

        deal_assessment = (
            "very_expensive"
        )

    # ==========================================
    # RETURN ANALYSIS
    # ==========================================

    return {

        "current_price":
            current_price,

        "historical_count":
            count,

        "historical_cheapest":
            historical_cheapest,

        "historical_average":
            round(
                historical_average,
                2,
            ),

        "historical_median":
            historical_median,

        "historical_most_expensive":
            historical_most_expensive,

        "difference_from_average":
            round(
                difference_from_average,
                2,
            ),

        "difference_percent_from_average":
            round(
                difference_percent_from_average,
                2,
            ),

        "difference_from_cheapest":
            round(
                difference_from_cheapest,
                2,
            ),

        "difference_percent_from_cheapest":
            round(
                difference_percent_from_cheapest,
                2,
            ),

        "deal_assessment":
            deal_assessment,
    }