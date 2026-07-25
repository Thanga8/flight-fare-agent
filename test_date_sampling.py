from utils.dates import (
    generate_date_combinations,
    sample_date_combinations,
)


START_DATE = "2027-01-20"
END_DATE = "2027-02-13"

MIN_TRIP_DAYS = 5
MAX_TRIP_DAYS = 6

SAMPLE_SIZE = 5


combinations = generate_date_combinations(
    start_date=START_DATE,
    end_date=END_DATE,
    min_trip_days=MIN_TRIP_DAYS,
    max_trip_days=MAX_TRIP_DAYS,
)


selected = sample_date_combinations(
    combinations=combinations,
    sample_size=SAMPLE_SIZE,
)


print()
print("=" * 70)
print("DATE SAMPLING TEST")
print("=" * 70)

print(
    f"Total combinations: "
    f"{len(combinations)}"
)

print(
    f"Selected combinations: "
    f"{len(selected)}"
)

print("=" * 70)


for index, combination in enumerate(
    selected,
    start=1,
):

    print(
        f"{index}. "
        f"{combination['departure_date']} → "
        f"{combination['return_date']} "
        f"("
        f"{combination['trip_days']} days"
        f")"
    )