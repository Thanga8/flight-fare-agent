from flight_search.search import (
    search_flexible_dates,
)


ORIGIN = "HYD"
DESTINATION = "MOW"

START_DATE = "2027-01-20"
END_DATE = "2027-02-13"

MIN_TRIP_DAYS = 5
MAX_TRIP_DAYS = 6

# IMPORTANT:
# Use only 1 search for inspection.
# This consumes 1 SerpApi search.
MAX_SEARCHES = 1


report = search_flexible_dates(

    departure_id=ORIGIN,

    arrival_id=DESTINATION,

    start_date=START_DATE,

    end_date=END_DATE,

    min_trip_days=MIN_TRIP_DAYS,

    max_trip_days=MAX_TRIP_DAYS,

    max_searches=MAX_SEARCHES,
)


print()
print("=" * 70)
print("RAW FLIGHT OBJECT INSPECTION")
print("=" * 70)


results = report.get(
    "results",
    []
)


if not results:

    print(
        "No priced flight results found."
    )

else:

    flight = results[0].get(
        "flight"
    )

    print()
    print(
        "Result metadata:"
    )

    print(
        f"Departure airport: "
        f"{results[0].get('departure_airport')}"
    )

    print(
        f"Arrival airport: "
        f"{results[0].get('arrival_airport')}"
    )

    print(
        f"Departure date: "
        f"{results[0].get('departure_date')}"
    )

    print(
        f"Return date: "
        f"{results[0].get('return_date')}"
    )

    print()
    print(
        "Flight object:"
    )

    print("=" * 70)

    print(
        flight
    )

    print("=" * 70)