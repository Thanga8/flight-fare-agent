from flight_search.planner import (
    create_search_plan,
)


plan = create_search_plan(

    departure_id="HYD",

    arrival_id="MOW",

    start_date="2027-01-20",

    end_date="2027-02-13",

    min_trip_days=5,

    max_trip_days=6,

    max_api_calls=10,

)


print()

print(
    f"Total planned searches: "
    f"{len(plan)}"
)

print()


for index, search in enumerate(
    plan,
    start=1,
):

    print(

        f"{index}. "

        f"{search['departure_airport']} → "
        f"{search['arrival_airport']} | "

        f"{search['departure_date']} → "
        f"{search['return_date']} | "

        f"{search['trip_days']} days"

    )