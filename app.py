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

MIN_TRIP_DAYS = 5
MAX_TRIP_DAYS = 6

MAX_SEARCHES = 10


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


# ==========================================
# EXTRACT RESULTS
# ==========================================

ranked_results = report[
    "ranked_results"
]

cheapest = report[
    "cheapest"
]

statistics = report[
    "statistics"
]


# ==========================================
# DISPLAY SEARCH SUMMARY
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

print(
    f"API searches executed: "
    f"{statistics['total_searches']}"
)

print(
    f"Priced results found: "
    f"{statistics['priced_results']}"
)

print("=" * 70)


# ==========================================
# DISPLAY CHEAPEST OVERALL
# ==========================================

print()

print(
    "CHEAPEST OVERALL"
)

print("-" * 70)


if cheapest:

    print(
        f"Price: "
        f"₹{cheapest['price']:,}"
    )

    print(
        f"Route: "
        f"{cheapest['departure_airport']} "
        f"→ "
        f"{cheapest['arrival_airport']}"
    )

    print(
        f"Dates: "
        f"{cheapest['departure_date']} "
        f"→ "
        f"{cheapest['return_date']}"
    )

    if cheapest.get(
        "duration"
    ) is not None:

        print(
            f"Flight duration: "
            f"{cheapest['duration']} minutes"
        )

else:

    print(
        "No priced flights found."
    )


# ==========================================
# DISPLAY TOP RESULTS
# ==========================================

print()

print(
    "TOP FLIGHT OPTIONS"
)

print("-" * 70)


if ranked_results:

    for index, result in enumerate(

        ranked_results[:10],

        start=1,

    ):

        print()

        print(

            f"{index}. "

            f"₹{result['price']:,} | "

            f"{result['departure_airport']} "
            f"→ "
            f"{result['arrival_airport']}"

        )

        print(

            f"   Dates: "
            f"{result['departure_date']} "
            f"→ "
            f"{result['return_date']}"

        )

        if result.get(
            "duration"
        ) is not None:

            print(

                f"   Flight duration: "
                f"{result['duration']} minutes"

            )

else:

    print(
        "No priced flights found."
    )


# ==========================================
# DISPLAY CHEAPEST BY AIRPORT
# ==========================================

cheapest_by_airport = report[
    "cheapest_by_airport"
]


print()

print(
    "CHEAPEST BY AIRPORT"
)

print("-" * 70)


if cheapest_by_airport:

    for airport, result in sorted(

        cheapest_by_airport.items()

    ):

        print(

            f"{airport}: "
            f"₹{result['price']:,} | "
            f"{result['departure_date']} "
            f"→ "
            f"{result['return_date']}"

        )

else:

    print(
        "No priced flights found."
    )


# ==========================================
# DISPLAY CHEAPEST BY TRIP DURATION
# ==========================================

cheapest_by_duration = report[
    "cheapest_by_duration"
]


print()

print(
    "CHEAPEST BY TRIP DURATION"
)

print("-" * 70)


if cheapest_by_duration:

    for duration, result in sorted(

        cheapest_by_duration.items()

    ):

        print(

            f"{duration} days: "
            f"₹{result['price']:,} | "
            f"{result['departure_date']} "
            f"→ "
            f"{result['return_date']}"

        )

else:

    print(
        "No priced flights found."
    )


# ==========================================
# DISPLAY SEARCH STATISTICS
# ==========================================

print()

print(
    "SEARCH STATISTICS"
)

print("-" * 70)

print(

    f"Total API searches: "
    f"{statistics['total_searches']}"

)

print(
    f"No priced flights: "
    f"{statistics['no_price_searches']}"
)

print(
    f"API errors: "
    f"{statistics['failed_api_searches']}"
)

print(
    f"API success rate: "
    f"{statistics['api_success_rate']}%"
)


if statistics[
    "cheapest_price"
] is not None:

    print(

        f"Cheapest price: "
        f"₹{statistics['cheapest_price']:,}"

    )

    print(

        f"Most expensive price: "
        f"₹{statistics['most_expensive_price']:,}"

    )

    print(

        f"Average price: "
        f"₹{statistics['average_price']:,.2f}"

    )


# ==========================================
# FINAL SEPARATOR
# ==========================================

print()

print("=" * 70)