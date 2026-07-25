from datetime import date, timedelta


def generate_date_combinations(
    start_date: str,
    end_date: str,
    min_trip_days: int,
    max_trip_days: int,
):
    """
    Generate every valid departure/return
    date combination.
    """

    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)

    combinations = []

    current_departure = start

    while current_departure <= end:

        for trip_days in range(
            min_trip_days,
            max_trip_days + 1,
        ):

            return_date = (
                current_departure
                + timedelta(days=trip_days)
            )

            if return_date <= end:

                combinations.append(
                    {
                        "departure_date":
                            current_departure.isoformat(),

                        "return_date":
                            return_date.isoformat(),

                        "trip_days":
                            trip_days,
                    }
                )

        current_departure += timedelta(days=1)

    return combinations


def sample_date_combinations(
    combinations,
    sample_size,
):
    """
    Select date combinations distributed
    across the entire search window.

    The selected combinations are spread
    evenly across the available date range
    instead of simply taking the first N.
    """

    if not combinations:
        return []

    if sample_size <= 0:
        return []

    if len(combinations) <= sample_size:
        return combinations

    if sample_size == 1:
        return [
            combinations[0]
        ]

    sampled = []

    total = len(combinations)

    for index in range(sample_size):

        position = round(
            index
            * (total - 1)
            / (sample_size - 1)
        )

        sampled.append(
            combinations[position]
        )

    return sampled