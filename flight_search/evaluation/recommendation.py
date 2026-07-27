# ==========================================
# DISPLAY LABELS
# ==========================================

RATING_LABELS = {

    "EXCELLENT":
        "★★★★★ Excellent Deal",

    "VERY_GOOD":
        "★★★★☆ Very Good Deal",

    "GOOD":
        "★★★☆☆ Good Deal",

    "AVERAGE":
        "★★☆☆☆ Average Fare",

    "EXPENSIVE":
        "★☆☆☆☆ Expensive Fare",

    "UNKNOWN":
        "No Rating",

}


# ==========================================
# ASSESSMENT MESSAGES
# ==========================================

ASSESSMENT_MESSAGES = {

    "NEW_HISTORICAL_LOW":
        "Lowest fare recorded so far.",

    "VERY_GOOD_PRICE":
        "Well below historical average.",

    "GOOD_PRICE":
        "Below average historical pricing.",

    "ABOVE_AVERAGE":
        "Slightly above average historical price.",

    "EXPENSIVE":
        "Higher than historical prices.",

    "NO_HISTORICAL_DATA":
        "No historical comparison available.",

}


# ==========================================
# BOOKING RECOMMENDATION
# ==========================================

def generate_booking_recommendation(
    evaluation,
):
    """
    Convert the technical evaluation into a
    user-friendly booking recommendation.
    """

    fare_rating = evaluation.get(
        "fare_rating",
        "UNKNOWN",
    )

    assessment = evaluation.get(
        "assessment",
        "NO_HISTORICAL_DATA",
    )

    # ==========================================
    # BOOKING DECISION
    # ==========================================

    if fare_rating == "EXCELLENT":

        recommendation = (
            "Book immediately."
        )

    elif fare_rating == "VERY_GOOD":

        recommendation = (
            "Very good fare. Booking is recommended."
        )

    elif fare_rating == "GOOD":

        recommendation = (
            "Good fare. Worth considering."
        )

    elif fare_rating == "AVERAGE":

        recommendation = (
            "Average fare. Monitor if your travel dates are flexible."
        )

    elif fare_rating == "EXPENSIVE":

        recommendation = (
            "Wait if possible. Better prices may appear."
        )

    else:

        recommendation = (
            "Not enough historical data to recommend."
        )

    # ==========================================
    # RETURN USER-FRIENDLY SUMMARY
    # ==========================================
    return {
    
        "display_rating":
            RATING_LABELS.get(
                fare_rating,
                "No Rating",
            ),
    
        "assessment_message":
            ASSESSMENT_MESSAGES.get(
                assessment,
                "No assessment available.",
            ),
    
        "recommendation":
            recommendation,
    
    }