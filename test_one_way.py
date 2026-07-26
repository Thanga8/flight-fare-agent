from flight_search.search import (
    search_one_way_dates
)


ORIGIN = "HYD"
DESTINATION = "SVO"

START_DATE = "2027-01-20"
END_DATE = "2027-01-25"

MAX_SEARCHES = 3


results = search_one_way_dates(
    departure_id=ORIGIN,
    arrival_id=DESTINATION,
    start_date=START_DATE,
    end_date=END_DATE,
    max_searches=MAX_SEARCHES,
)


print()
print("=" * 70)
print("ONE-WAY SEARCH RESULTS")
print("=" * 70)


for index, result in enumerate(
    results,
    start=1,
):

    print()

    print(
        f"{index}. "
        f"₹{result['price']:,} | "
        f"{result['departure_airport']} → "
        f"{result['arrival_airport']}"
    )

    print(
        f"   Date: "
        f"{result['departure_date']}"
    )

    print(
        f"   Trip type: "
        f"{result['trip_type']}"
    )

    if result.get("duration") is not None:

        print(
            f"   Duration: "
            f"{result['duration']} minutes"
        )