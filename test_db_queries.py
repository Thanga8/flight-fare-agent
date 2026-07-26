from flight_search.database.db import (
    get_latest_search_run,
    get_flight_results_for_search_run,
)

latest_run = get_latest_search_run()

print("=" * 70)
print("LATEST SEARCH RUN")
print("=" * 70)

if latest_run:
    print(latest_run)
    print()
    print("=" * 70)
    print("FLIGHT RESULTS FOR LATEST RUN")
    print("=" * 70)

    results = get_flight_results_for_search_run(latest_run["id"])

    for index, result in enumerate(results, start=1):
        print()
        print(f"{index}. {result['departure_airport']} → {result['arrival_airport']}")
        print(f"   Dates: {result['departure_date']} → {result['return_date']}")
        print(f"   Price: {result['currency']} {result['price']:,.0f}")
        print(f"   Duration: {result['duration_minutes']} minutes")
        print(f"   Stops: {result['stops']}")
else:
    print("No search runs found.")