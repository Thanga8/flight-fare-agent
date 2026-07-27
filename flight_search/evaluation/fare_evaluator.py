# ==========================================
# FARE EVALUATOR
# ==========================================


def evaluate_fare(
    current_price,
    historical_analysis,
):
    """
    Evaluate the current flight fare using
    historical price intelligence.

    historical_analysis should be the output
    from analyze_price_intelligence().
    """

    # ==========================================
    # EXTRACT HISTORICAL ANALYSIS
    # ==========================================

    analysis = (
        historical_analysis
        .get(
            "historical_analysis",
            {},
        )
    )

    assessment = (
        analysis.get(
            "assessment"
        )
    )

    confidence = (
        analysis.get(
            "confidence"
        )
    )

    comparison_level = (
        analysis.get(
            "comparison_level"
        )
    )

    historical_low = (
        analysis.get(
            "historical_low"
        )
    )

    historical_average = (
        analysis.get(
            "historical_average"
        )
    )

    historical_high = (
        analysis.get(
            "historical_high"
        )
    )

    historical_count = (
        analysis.get(
            "historical_count",
            0,
        )
    )

    difference_from_low_percent = (
        analysis.get(
            "difference_from_low_percent"
        )
    )

    difference_from_average_percent = (
        analysis.get(
            "difference_from_average_percent"
        )
    )

    # ==========================================
    # NO HISTORICAL DATA
    # ==========================================

    if assessment == "NO_HISTORICAL_DATA":

        return {

            "current_price":
                current_price,

            "historical_low":
                None,

            "historical_average":
                None,

            "historical_high":
                None,

            "historical_count":
                0,

            "comparison_level":
                "none",

            "assessment":
                "NO_HISTORICAL_DATA",

            "confidence":
                "NONE",

            "fare_rating":
                "UNKNOWN",

        }

    # ==========================================
    # FARE RATING
    # ==========================================

    if assessment == "NEW_HISTORICAL_LOW":

        fare_rating = "EXCELLENT"

    elif assessment == "VERY_GOOD_PRICE":

        fare_rating = "VERY_GOOD"

    elif assessment == "GOOD_PRICE":

        fare_rating = "GOOD"

    elif assessment == "ABOVE_AVERAGE":

        fare_rating = "AVERAGE"

    elif assessment == "EXPENSIVE":

        fare_rating = "EXPENSIVE"

    else:

        fare_rating = "UNKNOWN"

    # ==========================================
    # NUMERICAL FARE SCORE
    # ==========================================

    fare_scores = {

        "EXCELLENT": 100,

        "VERY_GOOD": 85,

        "GOOD": 70,

        "AVERAGE": 50,

        "EXPENSIVE": 20,

        "UNKNOWN": 0,

    }

    fare_score = fare_scores.get(
        fare_rating,
        0,
    )
    # ==========================================
    # RETURN EVALUATION
    # ==========================================

    return {

        "current_price":
            current_price,

        "historical_low":
            historical_low,

        "historical_average":
            historical_average,

        "historical_high":
            historical_high,

        "historical_count":
            historical_count,

        "comparison_level":
            comparison_level,

        "assessment":
            assessment,

        "fare_rating":
            fare_rating,

        "fare_score":
            fare_score,

        "confidence":
            confidence,

        "difference_from_low_percent":
            difference_from_low_percent,

        "difference_from_average_percent":
            difference_from_average_percent,

    }