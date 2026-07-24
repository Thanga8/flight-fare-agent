from datetime import date, timedelta


def generate_date_combinations(
    start_date: str,
    end_date: str,
    min_trip_days: int,
    max_trip_days: int,
):
    """
    Generate valid departure and return date combinations.

    Example:
        start_date = 2027-01-20
        end_date = 2027-02-13
        min_trip_days = 6
        max_trip_days = 10
    """

    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)

    combinations = []

    current_departure = start

    while current_departure <= end:

        for trip_days in range(
            min_trip_days,
            max_trip_days + 1
        ):

            return_date = (
                current_departure
                + timedelta(days=trip_days)
            )

            # Make sure return date stays
            # within the overall search window
            if return_date <= end:

                combinations.append({
                    "departure_date": current_departure.isoformat(),
                    "return_date": return_date.isoformat(),
                    "trip_days": trip_days,
                })

        current_departure += timedelta(days=1)

    return combinations