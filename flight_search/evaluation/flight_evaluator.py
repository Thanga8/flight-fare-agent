from flight_search.evaluation.fare_evaluator import (
    evaluate_fare,
)

from flight_search.evaluation.recommendation import (
    generate_booking_recommendation,
)

from search_history import (
    analyze_price_intelligence,
)


def evaluate_flight(
    flight,
):
    """
    Combine

    • Flight scoring
    • Historical fare analysis
    • Fare evaluation
    • Booking recommendation

    into one evaluation object.
    """

    historical_analysis = (
        analyze_price_intelligence(

            origin=flight["departure_airport"],

            destination=flight["arrival_airport"],

            departure_date=flight["departure_date"],

            return_date=flight["return_date"],

            current_price=flight["price"],

        )
    )

    fare_evaluation = evaluate_fare(

        current_price=flight["price"],

        historical_analysis=historical_analysis,

    )

    # ==========================================
    # BUILD COMPLETE EVALUATION
    # ==========================================

    evaluation = {

        **flight,

        **fare_evaluation,

    }

    # ==========================================
    # GENERATE USER RECOMMENDATION
    # ==========================================

    recommendation = (
        generate_booking_recommendation(
            evaluation
        )
    )

    evaluation["recommendation"] = recommendation

    return evaluation