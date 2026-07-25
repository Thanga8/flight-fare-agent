from flight_search.planner import (
    create_search_plan,
)


# ==========================================
# SEARCH CONFIGURATION
# ==========================================

ORIGIN = "HYD"

DESTINATION = "MOW"

START_DATE = "2027-01-20"

END_DATE = "2027-02-13"

MIN_TRIP_DAYS = 5

MAX_TRIP_DAYS = 6

MAX_API_CALLS = 10


# ==========================================
# CREATE SEARCH PLAN
# ==========================================

plan = create_search_plan(

    departure_id=ORIGIN,

    arrival_id=DESTINATION,

    start_date=START_DATE,

    end_date=END_DATE,

    min_trip_days=MIN_TRIP_DAYS,

    max_trip_days=MAX_TRIP_DAYS,

    max_api_calls=MAX_API_CALLS,
)


# ==========================================
# DISPLAY RESULTS
# ==========================================

print()

print("=" * 70)

print("SEARCH BUDGET PLANNER TEST")

print("=" * 70)

print()

print(
    f"Route: "
    f"{ORIGIN} → {DESTINATION}"
)

print(
    f"Date window: "
    f"{START_DATE} → {END_DATE}"
)

print(
    f"Trip duration: "
    f"{MIN_TRIP_DAYS}–"
    f"{MAX_TRIP_DAYS} days"
)

print(
    f"Requested API budget: "
    f"{MAX_API_CALLS}"
)

print()

print(
    f"Planned searches: "
    f"{len(plan)}"
)

print()

print("=" * 70)

print("SEARCH PLAN")

print("=" * 70)


for index, search in enumerate(
    plan,
    start=1,
):

    print(

        f"{index:2}. "

        f"{search['departure_airport']} → "

        f"{search['arrival_airport']} | "

        f"{search['departure_date']} → "

        f"{search['return_date']} | "

        f"{search['trip_days']} days"

    )


print()

print("=" * 70)

# ==========================================
# AUTOMATED VALIDATION
# ==========================================

assert len(plan) <= MAX_API_CALLS, (
    "Search plan exceeded API budget!"
)


assert len(plan) == MAX_API_CALLS, (
    "Search plan did not use the full "
    "available API budget."
)


airport_pairs = {
    (
        search["departure_airport"],
        search["arrival_airport"],
    )
    for search in plan
}


expected_pairs = {
    ("HYD", "SVO"),
    ("HYD", "DME"),
    ("HYD", "VKO"),
}


assert airport_pairs == expected_pairs, (
    "Not all Moscow airport pairs "
    "were included."
)


print()

print(
    "✅ All planner validation tests passed."
)