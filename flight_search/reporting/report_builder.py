from flight_search.evaluation.flight_evaluator import (
    evaluate_flight,
)


def build_console_report(report):
    """
    Convert the raw search report into a
    user-friendly structure for displaying
    in the console.
    """

    scored_results = report.get(
        "scored_results",
        [],
    )

    evaluated_results = []

    for flight in scored_results:

        evaluated_results.append(
            evaluate_flight(flight)
        )

    return {

        "statistics":
            report.get("statistics"),

        "cheapest":
            report.get("cheapest"),

        "results":
            evaluated_results,

    }