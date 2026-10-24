"""Telegram presentation for the experimental two-leg itinerary search."""

from flight_search.config.settings import (
    MULTI_LEG_END_DATE,
    MULTI_LEG_SERPAPI_BUDGET,
    MULTI_LEG_START_DATE,
)
from flight_search.multi_leg import search_multi_leg_itineraries
from flight_search.providers.serpapi_provider import SerpApiProvider


def format_multi_leg_report(report):
    lines = [
        "MULTI-CITY FARE RESULTS",
        f"SerpApi calls: {report['serpapi_calls']}/{report['serpapi_budget']}",
        "",
    ]
    if not report["itineraries"]:
        lines.append("No priced HYD–Paris / HEL–HYD date pair was found.")
    for index, itinerary in enumerate(report["itineraries"][:3], start=1):
        first, second = itinerary["leg1"], itinerary["leg2"]
        lines.extend([
            f"{index}. Total: INR {itinerary['total_price_inr']:,.2f}",
            f"HYD - Paris: {first['departure_date']} · INR {first['price']:,}",
            f"{second['departure_airport']} - HYD: {second['departure_date']} · INR {second['price']:,}",
            f"Gap between departure dates: {itinerary['nights_between_departures']} nights",
        ])
        comparison = itinerary.get("combined_search")
        if comparison and comparison.get("status") == "priced":
            lines.append(
                f"Combined multi-city: INR {comparison['price_inr']:,} "
                f"(difference vs separate: INR {comparison['difference_inr']:+,.2f})"
            )
        elif comparison:
            lines.append(f"Combined multi-city: {comparison['status']}")
        lines.append("")
    return "\n".join(lines).rstrip()


async def multi_search_command(update, context):
    await update.message.reply_text(
        "Starting HYD - Paris / HEL - HYD search. "
        f"Maximum calls: {MULTI_LEG_SERPAPI_BUDGET} SerpApi."
    )
    try:
        report = search_multi_leg_itineraries(
            start_date=MULTI_LEG_START_DATE,
            end_date=MULTI_LEG_END_DATE,
            international_provider=SerpApiProvider(),
            serpapi_budget=MULTI_LEG_SERPAPI_BUDGET,
        )
        await update.message.reply_text(format_multi_leg_report(report))
    except Exception as error:
        await update.message.reply_text(f"Multi-city search failed: {error}")
