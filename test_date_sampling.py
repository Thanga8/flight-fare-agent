from utils.dates import (
    generate_date_combinations,
    sample_date_combinations,
)


# ==========================================
# SEARCH WINDOW
# ==========================================

START_DATE = "2027-01-20"

END_DATE = "2027-02-13"

MIN_TRIP_DAYS = 4

MAX_TRIP_DAYS = 6


# ==========================================
# GENERATE ALL COMBINATIONS
# ==========================================

all_combinations = (
    generate_date_combinations(

        start_date=START_DATE,

        end_date=END_DATE,

        min_trip_days=MIN_TRIP_DAYS,

        max_trip_days=MAX_TRIP_DAYS,
    )
)


# ==========================================
# SAMPLE ONLY 10
# ==========================================

sampled_combinations = (
    sample_date_combinations(

        combinations=all_combinations,

        sample_size=10,
    )
)


# ==========================================
# DISPLAY
# ==========================================

print()

print("=" * 70)

print("DATE SAMPLING TEST")

print("=" * 70)

print(
    f"Search window: "
    f"{START_DATE} → {END_DATE}"
)

print(
    f"Trip duration: "
    f"{MIN_TRIP_DAYS}–"
    f"{MAX_TRIP_DAYS} days"
)

print()

print(
    f"Total valid combinations: "
    f"{len(all_combinations)}"
)

print(
    f"Sampled combinations: "
    f"{len(sampled_combinations)}"
)

print()

print("=" * 70)

print("SELECTED DATES")

print("=" * 70)


for index, combination in enumerate(
    sampled_combinations,
    start=1,
):

    print(

        f"{index:2}. "
        f"{combination['departure_date']} → "
        f"{combination['return_date']} "
        f"("
        f"{combination['trip_days']} days"
        f")"

    )


print()

print("=" * 70)