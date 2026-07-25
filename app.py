from flight_search.search import search_flexible_dates
from flight_search.recommendations import build_recommendation_summary

from flight_search.providers.verification import verify_top_results_with_flightapi

import os
# ==========================================
# SEARCH CONFIGURATION
# ==========================================

ORIGIN = "HYD"
DESTINATION = "MOW"

START_DATE = "2027-01-20"
END_DATE = "2027-02-13"

MIN_TRIP_DAYS = 5
MAX_TRIP_DAYS = 6

MAX_SEARCHES = 8


# ==========================================
# RUN SEARCH
# ==========================================

report = search_flexible_dates(
    departure_id=ORIGIN,
    arrival_id=DESTINATION,
    start_date=START_DATE,
    end_date=END_DATE,
    min_trip_days=MIN_TRIP_DAYS,
    max_trip_days=MAX_TRIP_DAYS,
    max_searches=MAX_SEARCHES,
)

recommendations = build_recommendation_summary(report)

ranked_results = report["ranked_results"]
cheapest = report["cheapest"]
statistics = report["statistics"]
cheapest_by_airport = report["cheapest_by_airport"]
cheapest_by_duration = report["cheapest_by_duration"]


# ==========================================
# DISPLAY SEARCH SUMMARY
# ==========================================

print()
print("=" * 70)
print("CHEAPEST FLIGHT DATE COMBINATIONS")
print("=" * 70)
print(f"Route: {ORIGIN} → {DESTINATION}")
print(f"Search window: {START_DATE} → {END_DATE}")
print(f"Trip duration: {MIN_TRIP_DAYS}–{MAX_TRIP_DAYS} days")
print(f"API searches executed: {statistics['total_searches']}")
print(f"Priced results found: {statistics['priced_results']}")
print("=" * 70)


# ==========================================
# RECOMMENDATION SUMMARY
# ==========================================

print()
print("RECOMMENDATION SUMMARY")
print("-" * 70)

print(recommendations["headline"])

if recommendations["best_alternative"]:
    alt = recommendations["best_alternative"]
    print(
        f"Next best: ₹{alt['price']:,} | "
        f"{alt['departure_airport']} → {alt['arrival_airport']} | "
        f"{alt['departure_date']} → {alt['return_date']}"
    )

if recommendations["best_airport"]:
    airport = recommendations["best_airport"]["airport"]
    result = recommendations["best_airport"]["result"]
    print(
        f"Best airport option: {airport} | "
        f"₹{result['price']:,} | "
        f"{result['departure_date']} → {result['return_date']}"
    )

if recommendations["best_duration"]:
    duration = recommendations["best_duration"]["duration"]
    result = recommendations["best_duration"]["result"]
    print(
        f"Best trip duration: {duration} days | "
        f"₹{result['price']:,} | "
        f"{result['departure_date']} → {result['return_date']}"
    )


# ==========================================
# DISPLAY CHEAPEST OVERALL
# ==========================================

print()
print("CHEAPEST OVERALL")
print("-" * 70)

if cheapest:
    print(f"Price: ₹{cheapest['price']:,}")
    print(
        f"Route: {cheapest['departure_airport']} → {cheapest['arrival_airport']}"
    )
    print(
        f"Dates: {cheapest['departure_date']} → {cheapest['return_date']}"
    )
    if cheapest.get("duration") is not None:
        print(f"Flight duration: {cheapest['duration']} minutes")
else:
    print("No priced flights found.")


# ==========================================
# DISPLAY TOP RESULTS
# ==========================================

print()
print("TOP FLIGHT OPTIONS")
print("-" * 70)

if ranked_results:
    for index, result in enumerate(ranked_results[:10], start=1):
        print()
        print(
            f"{index}. ₹{result['price']:,} | "
            f"{result['departure_airport']} → {result['arrival_airport']}"
        )
        print(
            f"   Dates: {result['departure_date']} → {result['return_date']}"
        )
        if result.get("duration") is not None:
            print(f"   Flight duration: {result['duration']} minutes")
else:
    print("No priced flights found.")

print()
print("FLIGHTAPI.IO CROSS-CHECK")
print("-" * 70)

flightapi_key = os.getenv("FLIGHTAPI_API_KEY")

if flightapi_key and ranked_results:
    verifications = verify_top_results_with_flightapi(
        ranked_results=ranked_results,
        max_checks=3,
        api_key=flightapi_key,
    )

    for index, item in enumerate(verifications, start=1):
        if (
            item["flightapi_status"]
            == "priced_result"
        ):
        
            print(
                f"{index}. "
                f"{item['departure_airport']} → "
                f"{item['arrival_airport']} | "
                f"{item['departure_date']} → "
                f"{item['return_date']}"
            )
        
            print(
                f"   SerpApi: "
                f"₹{item['serpapi_price']:,}"
            )
        
            print(
                f"   FlightAPI: "
                f"{item['flightapi_currency'] or ''} "
                f"{item['flightapi_price']}"
            )
        
        elif (
            item["flightapi_status"]
            == "provider_restriction"
        ):
        
            print(
                f"{index}. "
                f"{item['departure_airport']} → "
                f"{item['arrival_airport']} | "
                f"{item['departure_date']} → "
                f"{item['return_date']}"
            )
        
            print(
                f"   SerpApi: "
                f"₹{item['serpapi_price']:,}"
            )
        
            print(
                "   FlightAPI: "
                "Skipped — provider restriction "
                "(Russia-related route)"
            )
        
        else:
        
            print(
                f"{index}. "
                f"{item['departure_airport']} → "
                f"{item['arrival_airport']} | "
                f"{item['departure_date']} → "
                f"{item['return_date']}"
            )
        
            print(
                f"   SerpApi: "
                f"₹{item['serpapi_price']:,}"
            )
        
            print(
                "   FlightAPI: "
                "No priced result"
            )        
else:
    print("FlightAPI cross-check skipped (missing FLIGHTAPI_API_KEY or no ranked results).")


# ==========================================
# DISPLAY CHEAPEST BY AIRPORT
# ==========================================

print()
print("CHEAPEST BY AIRPORT")
print("-" * 70)

if cheapest_by_airport:
    for airport, result in sorted(cheapest_by_airport.items()):
        print(
            f"{airport}: ₹{result['price']:,} | "
            f"{result['departure_date']} → {result['return_date']}"
        )
else:
    print("No priced flights found.")


# ==========================================
# DISPLAY CHEAPEST BY TRIP DURATION
# ==========================================

print()
print("CHEAPEST BY TRIP DURATION")
print("-" * 70)

if cheapest_by_duration:
    for duration, result in sorted(cheapest_by_duration.items()):
        print(
            f"{duration} days: ₹{result['price']:,} | "
            f"{result['departure_date']} → {result['return_date']}"
        )
else:
    print("No priced flights found.")


# ==========================================
# DISPLAY SEARCH STATISTICS
# ==========================================

print()
print("SEARCH STATISTICS")
print("-" * 70)

print(f"Total API searches: {statistics['total_searches']}")
print(f"Successful API responses: {statistics['successful_api_searches']}")
print(f"Priced flights found: {statistics['priced_results']}")
print(f"No priced flights: {statistics['no_price_searches']}")
print(f"API errors: {statistics['failed_api_searches']}")
print(f"API success rate: {statistics['api_success_rate']}%")
print(f"Priced result rate: {statistics['priced_result_rate']}%")
print(f"No-price rate: {statistics['no_price_rate']}%")

if statistics["cheapest_price"] is not None:
    print(f"Cheapest price: ₹{statistics['cheapest_price']:,}")
    print(f"Most expensive price: ₹{statistics['most_expensive_price']:,}")
    print(f"Average price: ₹{statistics['average_price']:,.2f}")
else:
    print("No priced flight results.")


print()
print("=" * 70)