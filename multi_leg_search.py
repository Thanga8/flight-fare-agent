"""Run the experimental HYD/MOW/MMK combined-itinerary search explicitly."""

import argparse

from flight_search.config.settings import (
    END_DATE,
    MULTI_LEG_SERPAPI_BUDGET,
    MULTI_LEG_TRAVELPAYOUTS_BUDGET,
    RUB_TO_INR,
    START_DATE,
)
from flight_search.multi_leg import (
    create_multi_leg_candidates,
    search_multi_leg_itineraries,
)


def main():
    parser = argparse.ArgumentParser(
        description="Search the experimental HYD/MOW/MMK itinerary."
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Allow live Travelpayouts and SerpApi requests.",
    )
    parser.add_argument(
        "--serpapi-budget",
        type=int,
        default=MULTI_LEG_SERPAPI_BUDGET,
        help="SerpApi cap for this run (maximum 20).",
    )
    parser.add_argument(
        "--show-all",
        action="store_true",
        help="Print every complete itinerary rather than only the top five.",
    )
    args = parser.parse_args()
    if not 0 <= args.serpapi_budget <= MULTI_LEG_SERPAPI_BUDGET:
        parser.error("--serpapi-budget must be between 0 and 20")

    candidates = create_multi_leg_candidates(START_DATE, END_DATE)
    print("MULTI-LEG ITINERARY PLAN")
    print(f"International window: {START_DATE} to {END_DATE}")
    print(f"Valid domestic 4-day candidates: {len(candidates)}")
    print(f"Travelpayouts cap: {MULTI_LEG_TRAVELPAYOUTS_BUDGET}")
    print(f"SerpApi cap: {args.serpapi_budget}")
    print(f"Conversion: 1 RUB = {RUB_TO_INR} INR")

    if not args.live:
        print("No API calls made. Re-run with --live to execute the search.")
        return

    from flight_search.providers.serpapi_provider import SerpApiProvider
    from flight_search.providers.travelpayouts_provider import TravelpayoutsProvider

    report = search_multi_leg_itineraries(
        start_date=START_DATE,
        end_date=END_DATE,
        domestic_provider=TravelpayoutsProvider(),
        international_provider=SerpApiProvider(),
        travelpayouts_budget=MULTI_LEG_TRAVELPAYOUTS_BUDGET,
        serpapi_budget=args.serpapi_budget,
        rub_to_inr=RUB_TO_INR,
    )

    print(
        f"Calls used: Travelpayouts {report['travelpayouts_calls']}/"
        f"{report['travelpayouts_budget']}, SerpApi {report['serpapi_calls']}/"
        f"{report['serpapi_budget']}"
    )
    print(
        f"Eligible domestic 4-day combinations found: "
        f"{report['domestic_combinations_found']}"
    )
    print(
        f"Cheapest domestic combinations advanced: "
        f"{report['domestic_combinations_selected']}"
    )
    print(
        f"Airport/date international candidates available: "
        f"{report['international_searches_available']}"
    )
    print(
        f"International searches selected within the SerpApi budget: "
        f"{report['international_searches_planned']}"
    )
    print(f"Complete itineraries: {len(report['itineraries'])}")

    itineraries_to_show = (
        report["itineraries"]
        if args.show_all else report["itineraries"][:5]
    )
    for index, itinerary in enumerate(itineraries_to_show, start=1):
        domestic = itinerary["domestic"]
        international = itinerary["international"]
        print()
        print(f"{index}. Total: INR {itinerary['total_price_inr']:,.2f}")
        print(
            "   Domestic: "
            f"MOW -> MMK {itinerary['domestic_departure_date']} | "
            f"MMK -> MOW {itinerary['domestic_return_date']} | "
            f"RUB {domestic['price']:,} = INR {itinerary['domestic_price_inr']:,.2f}"
        )
        print(
            "   International: "
            f"HYD -> MOW {international['departure_date']} | "
            f"MOW -> HYD {international['return_date']} | "
            f"INR {international['price']:,}"
        )


if __name__ == "__main__":
    main()
