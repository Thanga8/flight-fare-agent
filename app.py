from flight_search.search import (
    search_flexible_dates
)


# ==========================================
# SEARCH CONFIGURATION
# ==========================================

ORIGIN = "HYD"
DESTINATION = "MOW"

START_DATE = "2027-01-20"
END_DATE = "2027-02-13"

MIN_TRIP_DAYS = 4
MAX_TRIP_DAYS = 6

MAX_SEARCHES = 10


# ==========================================
# RUN SEARCH
# ==========================================

results = search_flexible_dates(

    departure_id=ORIGIN,

    arrival_id=DESTINATION,

    start_date=START_DATE,

    end_date=END_DATE,

    min_trip_days=MIN_TRIP_DAYS,

    max_trip_days=MAX_TRIP_DAYS,

    max_searches=MAX_SEARCHES,
)


# ==========================================
# SORT BY PRICE
# ==========================================

results.sort(
    key=lambda result: result["price"]
)


# ==========================================
# DISPLAY RESULTS
# ==========================================

print()
print("=" * 70)

print(
    "CHEAPEST FLIGHT DATE COMBINATIONS"
)

print("=" * 70)

print(
    f"Route: "
    f"{ORIGIN} → {DESTINATION}"
)

print(
    f"Search window: "
    f"{START_DATE} → {END_DATE}"
)

print(
    f"Trip duration: "
    f"{MIN_TRIP_DAYS}–"
    f"{MAX_TRIP_DAYS} days"
)

print("=" * 70)


for index, result in enumerate(
    results[:10],
    start=1
):

    print()

    print(
        f"{index}. "
        f"{result['departure_date']} → "
        f"{result['return_date']}"
    )

    print(
        f"   Price: "
        f"₹{result['price']:,}"
    )

    print(
        f"   Duration: "
        f"{result['duration']} minutes"
    )


print()
print("=" * 70)