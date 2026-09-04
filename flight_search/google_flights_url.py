from urllib.parse import quote


def build_google_flights_url(
    origin: str,
    destination: str,
    departure_date: str,
    return_date: str | None = None,
) -> str:
    """
    Build a Google Flights search URL.

    This creates a search link for the route and dates.
    It does not guarantee a deep link to the exact fare
    or itinerary returned by SerpApi.
    """

    if return_date:
        query = (
            f"Flights from {origin} to {destination} "
            f"on {departure_date} through {return_date}"
        )
    else:
        query = (
            f"Flights from {origin} to {destination} "
            f"on {departure_date}"
        )

    encoded_query = quote(query)

    return (
        "https://www.google.com/travel/flights?"
        f"q={encoded_query}"
    )