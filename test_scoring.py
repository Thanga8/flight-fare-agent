from flight_search.scoring import (
    calculate_final_score,
)

def format_duration(minutes):
    """
    Convert duration in minutes into a
    human-readable hours and minutes format.
    """

    if minutes < 60:
        return f"{minutes} minutes"

    hours = minutes // 60
    remaining_minutes = minutes % 60

    return (
        f"{hours}h "
        f"{remaining_minutes}m"
    )
# ==========================================
# TEST ITINERARIES
# ==========================================

flights = [

    {
        "name": "Cheapest",

        "price": 67680,

        "total_duration": 2280,

        "layovers": [
            {
                "duration": 900,
                "name": "Example Airport",
                "id": "XXX",
            },
            {
                "duration": 180,
                "name": "Example Airport 2",
                "id": "YYY",
            },
        ],

        "flights": [
            {
                "overnight": False,
            },
            {
                "overnight": False,
            },
        ],
    },

    {
        "name": "Best Value",

        "price": 70200,

        "total_duration": 1020,

        "layovers": [
            {
                "duration": 180,
                "name": "Example Airport",
                "id": "XXX",
            },
        ],

        "flights": [
            {
                "overnight": False,
            },
            {
                "overnight": False,
            },
        ],
    },

    {
        "name": "Fastest",

        "price": 72500,

        "total_duration": 720,

        "layovers": [
            {
                "duration": 120,
                "name": "Example Airport",
                "id": "XXX",
            },
        ],

        "flights": [
            {
                "overnight": False,
            },
            {
                "overnight": False,
            },
        ],
    },

    {
        "name": "Long Layover",

        "price": 69000,

        "total_duration": 1800,

        "layovers": [
            {
                "duration": 1080,
                "name": "Example Airport",
                "id": "XXX",
            },
        ],

        "flights": [
            {
                "overnight": True,
            },
            {
                "overnight": False,
            },
        ],
    },
]


# ==========================================
# PREPARE DATA
# ==========================================

all_prices = [

    flight["price"]

    for flight in flights

]


all_durations = [

    flight["total_duration"]

    for flight in flights

]


# ==========================================
# CALCULATE SCORES
# ==========================================

scored_flights = []


for flight in flights:

    scores = calculate_final_score(

        flight=flight,

        all_prices=all_prices,

        all_durations=all_durations,

    )

    scored_flights.append(

        {
            "name":
                flight["name"],

            "price":
                flight["price"],

            "duration":
                flight["total_duration"],

            **scores,
        }

    )


# ==========================================
# SORT BY FINAL SCORE
# ==========================================

scored_flights.sort(

    key=lambda result:
        result["final_score"],

    reverse=True,

)


# ==========================================
# DISPLAY RESULTS
# ==========================================

print()

print("=" * 70)

print(
    "FLIGHT SCORING TEST"
)

print("=" * 70)


for index, result in enumerate(

    scored_flights,

    start=1,

):

    print()

    print(

        f"{index}. "
        f"{result['name']}"

    )

    print(

        f"   Price: "
        f"₹{result['price']:,}"

    )

    print(

        f"   Duration: "
        f"{result['duration']} minutes"

    )

    print(

        f"   Price score: "
        f"{result['price_score']}"

    )

    print(
        f"   Duration: "
        f"{format_duration(result['duration'])}"
    )

    print(

        f"   Stops score: "
        f"{result['stops_score']}"

    )

    print(

        f"   Convenience score: "
        f"{result['convenience_score']}"

    )

    print(

        f"   FINAL SCORE: "
        f"{result['final_score']}"

    )


print()

print("=" * 70)