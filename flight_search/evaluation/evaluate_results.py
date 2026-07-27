from .flight_evaluator import evaluate_flight


def evaluate_results(
    scored_results,
    origin,
    destination,
):

    evaluated = []

    for flight in scored_results:

        evaluated.append(
            evaluate_flight(
                origin=origin,
                destination=destination,
                flight=flight,
            )
        )

    return evaluated