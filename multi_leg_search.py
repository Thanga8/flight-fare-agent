"""Run the experimental HYD–Paris / HEL–HYD search."""

import argparse

from flight_search.config.settings import (
    MULTI_LEG_COMBINED_CANDIDATE_LIMIT,
    MULTI_LEG_END_DATE,
    MULTI_LEG_LEG1_DESTINATION,
    MULTI_LEG_LEG1_ORIGIN,
    MULTI_LEG_LEG2_DESTINATION,
    MULTI_LEG_LEG2_ORIGIN,
    MULTI_LEG_NIGHTS_BETWEEN_DEPARTURES,
    MULTI_LEG_SERPAPI_BUDGET,
    MULTI_LEG_START_DATE,
)
from flight_search.multi_leg import search_multi_leg_itineraries


def main():
    parser = argparse.ArgumentParser(
        description="Search HYD–Paris and HEL–HYD one-way legs."
    )
    parser.add_argument(
        "--live", action="store_true",
        help="Allow live SerpApi requests.",
    )
    parser.add_argument(
        "--serpapi-budget", type=int, default=MULTI_LEG_SERPAPI_BUDGET,
        help=f"SerpApi cap for this run (maximum {MULTI_LEG_SERPAPI_BUDGET}).",
    )
    parser.add_argument("--start-date", default=MULTI_LEG_START_DATE)
    parser.add_argument("--end-date", default=MULTI_LEG_END_DATE)
    parser.add_argument("--leg1-origin", default=MULTI_LEG_LEG1_ORIGIN)
    parser.add_argument("--leg1-destination", default=MULTI_LEG_LEG1_DESTINATION)
    parser.add_argument("--leg2-origin", default=MULTI_LEG_LEG2_ORIGIN)
    parser.add_argument("--leg2-destination", default=MULTI_LEG_LEG2_DESTINATION)
    parser.add_argument(
        "--nights-between-departures",
        type=int,
        default=MULTI_LEG_NIGHTS_BETWEEN_DEPARTURES,
    )
    parser.add_argument(
        "--combined-candidates",
        type=int,
        default=MULTI_LEG_COMBINED_CANDIDATE_LIMIT,
        help="Number of cheapest separate-leg candidates to compare as multi-city.",
    )
    parser.add_argument(
        "--leg1", choices=("live", "cache"), default="live",
        help="Live or cached results for HYD to Paris.",
    )
    parser.add_argument(
        "--leg2", choices=("live", "cache"), default="live",
        help="Live or cached results for HEL to HYD.",
    )
    parser.add_argument(
        "--combined", choices=("live", "cache"), default="live",
        help="Live or cached multi-city comparison for the top three candidates.",
    )
    args = parser.parse_args()
    if not 0 <= args.serpapi_budget <= MULTI_LEG_SERPAPI_BUDGET:
        parser.error(
            f"--serpapi-budget must be between 0 and {MULTI_LEG_SERPAPI_BUDGET}"
        )

    print("MULTI-CITY ITINERARY PLAN")
    print(f"Date window: {args.start_date} to {args.end_date}")
    print(f"Leg 1: {args.leg1_origin} → {args.leg1_destination}")
    print(f"Leg 2: {args.leg2_origin} → {args.leg2_destination}")
    print(f"Departure date gap: {args.nights_between_departures} nights")
    print(f"SerpApi cap: {args.serpapi_budget}")
    if not args.live:
        print("No API calls made. Re-run with --live to execute the search.")
        return

    from flight_search.providers.serpapi_provider import SerpApiProvider

    provider = SerpApiProvider(
        allow_cache_only=(
            args.leg1 == "cache" and args.leg2 == "cache"
            and args.combined == "cache"
        )
    )

    report = search_multi_leg_itineraries(
        start_date=args.start_date,
        end_date=args.end_date,
        international_provider=provider,
        serpapi_budget=args.serpapi_budget,
        leg1_origin=args.leg1_origin,
        leg1_destination=args.leg1_destination,
        leg2_origin=args.leg2_origin,
        leg2_destination=args.leg2_destination,
        nights_between_departures=args.nights_between_departures,
        leg1_cache_mode=args.leg1,
        leg2_cache_mode=args.leg2,
        combined_cache_mode=args.combined,
        combined_candidate_limit=args.combined_candidates,
    )
    print(f"SerpApi calls used: {report['serpapi_calls']}/{report['serpapi_budget']}")
    print(
        f"Leg 1 mode: {report['leg1_cache_mode']} "
        f"({report['leg1_cache_hits']} cache hits); "
        f"Leg 2 mode: {report['leg2_cache_mode']} "
        f"({report['leg2_cache_hits']} cache hits); "
        f"combined mode: {report['combined_cache_mode']} "
        f"({report['combined_cache_hits']} cache hits)"
    )
    print(
        f"{report['leg1_origin']} → {report['leg1_destination']} dates searched: "
        f"{report['leg1_dates_searched']}"
    )
    print(
        f"{report['leg2_origin']} → {report['leg2_destination']} dates searched: "
        f"{report['leg2_dates_searched']}"
    )
    print(
        "Required gap between leg departure dates: "
        f"{report['nights_between_departures']} nights"
    )
    for leg in report["leg_stats"]:
        print(
            f"{leg['route']}: {leg['priced_dates']} priced dates out of "
            f"{leg['dates_searched']} searches"
        )
        for error in leg["response_errors"]:
            print(f"  SerpApi response error: {error}")
    print(f"Complete itineraries: {len(report['itineraries'])}")
    itineraries = report["itineraries"]
    for index, itinerary in enumerate(itineraries, start=1):
        first, second = itinerary["leg1"], itinerary["leg2"]
        print(f"\n{index}. Total: INR {itinerary['total_price_inr']:,.2f}")
        print(
            f"   Leg 1: {report['leg1_origin']} → {first.get('arrival_airport') or report['leg1_destination']} "
            f"{first['departure_date']} | INR {first['price']:,}"
        )
        print(
            f"   Leg 2: {second['departure_airport']} → HYD "
            f"{second['departure_date']} | INR {second['price']:,}"
        )
        comparison = itinerary.get("combined_search")
        if comparison:
            if comparison["status"] == "priced":
                diff = comparison["difference_inr"]
                label = "combined cheaper" if diff < 0 else "separate cheaper" if diff > 0 else "same price"
                print(
                    f"   Multi-city: INR {comparison['price_inr']:,} | "
                    f"separate: INR {itinerary['total_price_inr']:,} | "
                    f"{label} by INR {abs(diff):,.2f}"
                )
            else:
                print(f"   Multi-city comparison: {comparison['status']} — {comparison.get('error', '')}")


if __name__ == "__main__":
    main()
