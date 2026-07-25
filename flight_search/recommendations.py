# flight_search/recommendations.py

def _format_result(result):
    if not result:
        return "No priced flights found."

    line = (
        f"₹{result['price']:,} | "
        f"{result['departure_airport']} → {result['arrival_airport']} | "
        f"{result['departure_date']} → {result['return_date']}"
    )

    if result.get("duration") is not None:
        line += f" | {result['duration']} minutes"

    return line


def build_recommendation_summary(report):
    ranked_results = report.get("ranked_results", [])
    cheapest = report.get("cheapest")
    cheapest_by_airport = report.get("cheapest_by_airport", {})
    cheapest_by_duration = report.get("cheapest_by_duration", {})
    statistics = report.get("statistics", {})

    best_alternative = ranked_results[1] if len(ranked_results) > 1 else None

    best_airport = None
    if cheapest_by_airport:
        airport, result = min(
            cheapest_by_airport.items(),
            key=lambda item: item[1]["price"],
        )
        best_airport = {
            "airport": airport,
            "result": result,
        }

    best_duration = None
    if cheapest_by_duration:
        duration, result = min(
            cheapest_by_duration.items(),
            key=lambda item: item[1]["price"],
        )
        best_duration = {
            "duration": duration,
            "result": result,
        }

    headline = "No priced flights found."
    if cheapest:
        headline = (
            f"Best overall: {_format_result(cheapest)}"
        )

    return {
        "headline": headline,
        "best_overall": cheapest,
        "best_alternative": best_alternative,
        "best_airport": best_airport,
        "best_duration": best_duration,
        "top_ranked": ranked_results[:3],
        "statistics": statistics,
    }