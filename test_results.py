from flight_search.results import (
    rank_results,
    get_cheapest_result,
    calculate_statistics,
    get_cheapest_by_airport,
    get_cheapest_by_trip_duration,
)


# ==========================================
# MOCK RESULTS
# ==========================================

results = [

    {
        "departure_date":
            "2027-01-20",

        "return_date":
            "2027-01-24",

        "price":
            45000,

        "departure_airport":
            "HYD",

        "arrival_airport":
            "SVO",
    },

    {
        "departure_date":
            "2027-01-22",

        "return_date":
            "2027-01-27",

        "price":
            42500,

        "departure_airport":
            "HYD",

        "arrival_airport":
            "DME",
    },

    {
        "departure_date":
            "2027-01-24",

        "return_date":
            "2027-01-30",

        "price":
            44100,

        "departure_airport":
            "HYD",

        "arrival_airport":
            "VKO",
    },

    {
        "departure_date":
            "2027-01-26",

        "return_date":
            "2027-01-31",

        "price":
            43200,

        "departure_airport":
            "HYD",

        "arrival_airport":
            "SVO",
    },

    {
        "departure_date":
            "2027-02-01",

        "return_date":
            "2027-02-05",

        "price":
            47000,

        "departure_airport":
            "HYD",

        "arrival_airport":
            "DME",
    },

]


TOTAL_SEARCHES = 10


# ==========================================
# RANK RESULTS
# ==========================================

ranked = rank_results(
    results=results,
    top_n=10,
)


# ==========================================
# CHEAPEST
# ==========================================

cheapest = get_cheapest_result(
    results
)


# ==========================================
# STATISTICS
# ==========================================

statistics = calculate_statistics(
    results=results,
    total_searches=TOTAL_SEARCHES,
)


# ==========================================
# CHEAPEST BY AIRPORT
# ==========================================

by_airport = (
    get_cheapest_by_airport(
        results
    )
)


# ==========================================
# CHEAPEST BY DURATION
# ==========================================

by_duration = (
    get_cheapest_by_trip_duration(
        results
    )
)


# ==========================================
# DISPLAY
# ==========================================

print()

print("=" * 70)

print(
    "RESULTS ENGINE TEST"
)

print("=" * 70)


print()

print(
    "TOP FLIGHTS"
)

print("-" * 70)


for index, result in enumerate(
    ranked,
    start=1,
):

    print(

        f"{index}. "

        f"₹{result['price']:,} | "

        f"{result['departure_airport']} → "

        f"{result['arrival_airport']} | "

        f"{result['departure_date']} → "

        f"{result['return_date']}"

    )


print()

print(
    "CHEAPEST OVERALL"
)

print("-" * 70)

print(

    f"₹{cheapest['price']:,} | "

    f"{cheapest['departure_airport']} → "

    f"{cheapest['arrival_airport']} | "

    f"{cheapest['departure_date']} → "

    f"{cheapest['return_date']}"

)


print()

print(
    "SEARCH STATISTICS"
)

print("-" * 70)

print(
    f"Total searches: "
    f"{statistics['total_searches']}"
)

print(
    f"Successful searches: "
    f"{statistics['successful_searches']}"
)

print(
    f"Failed searches: "
    f"{statistics['failed_searches']}"
)

print(
    f"Success rate: "
    f"{statistics['success_rate']}%"
)

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


print()

print(
    "CHEAPEST BY AIRPORT"
)

print("-" * 70)


for airport, result in (
    by_airport.items()
):

    print(

        f"{airport}: "

        f"₹{result['price']:,} | "

        f"{result['departure_date']} → "

        f"{result['return_date']}"

    )


print()

print(
    "CHEAPEST BY TRIP DURATION"
)

print("-" * 70)


for duration, result in (
    sorted(
        by_duration.items()
    )
):

    print(

        f"{duration} days: "

        f"₹{result['price']:,} | "

        f"{result['departure_date']} → "

        f"{result['return_date']}"

    )


print()

print("=" * 70)

# ==========================================
# VALIDATION
# ==========================================

assert (
    cheapest["price"]
    == 42500
)

assert (
    len(ranked)
    == 5
)

assert (
    statistics[
        "total_searches"
    ]
    == 10
)

assert (
    statistics[
        "successful_searches"
    ]
    == 5
)

assert (
    statistics[
        "failed_searches"
    ]
    == 5
)

assert (
    statistics[
        "success_rate"
    ]
    == 50.0
)

assert (
    by_airport[
        "DME"
    ]["price"]
    == 42500
)

assert (
    by_duration[
        5
    ]["price"]
    == 42500
)

print()

print(
    "✅ All results engine "
    "validation tests passed."
)