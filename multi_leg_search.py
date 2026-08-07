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
    args = parser.parse_args()

    candidates = create_multi_leg_candidates(START_DATE, END_DATE)
    print("MULTI-LEG ITINERARY PLAN")
    print(f"International window: {START_DATE} to {END_DATE}")
    print(f"Valid domestic 4-day candidates: {len(candidates)}")
    print(f"Travelpayouts cap: {MULTI_LEG_TRAVELPAYOUTS_BUDGET}")
    print(f"SerpApi cap: {MULTI_LEG_SERPAPI_BUDGET}")
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
        serpapi_budget=MULTI_LEG_SERPAPI_BUDGET,
        rub_to_inr=RUB_TO_INR,
    )

    print(
        f"Calls used: Travelpayouts {report['travelpayouts_calls']}/"
        f"{report['travelpayouts_budget']}, SerpApi {report['serpapi_calls']}/"
        f"{report['serpapi_budget']}"
    )
    print(f"Complete itineraries: {len(report['itineraries'])}")

    for index, itinerary in enumerate(report["itineraries"][:5], start=1):
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
