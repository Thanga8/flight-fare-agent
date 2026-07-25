from typing import Optional


# Countries that FlightAPI currently restricts
# for flight content due to provider sanctions.
FLIGHTAPI_UNSUPPORTED_COUNTRIES = {
    "RU",
}


# IATA airport → ISO country code
#
# Add airports here as we encounter them.
# This keeps the logic simple and avoids
# making another API call just to identify
# an airport's country.
AIRPORT_COUNTRIES = {
    # India
    "HYD": "IN",
    "DEL": "IN",
    "BOM": "IN",
    "MAA": "IN",
    "BLR": "IN",

    # Russia
    "SVO": "RU",
    "DME": "RU",
    "VKO": "RU",
    "ZIA": "RU",
    "MMK": "RU",
}


def get_airport_country(
    airport_code: str,
) -> Optional[str]:
    """
    Return the ISO country code for an airport.

    Returns None if the airport is not
    present in the local mapping.
    """

    return AIRPORT_COUNTRIES.get(
        airport_code.upper()
    )


def is_route_supported_by_flightapi(
    departure_airport: str,
    arrival_airport: str,
) -> bool:
    """
    Determine whether FlightAPI should be
    queried for the given airport pair.

    Unknown airports are considered supported
    so that we don't accidentally skip valid
    searches.
    """

    departure_country = (
        get_airport_country(
            departure_airport
        )
    )

    arrival_country = (
        get_airport_country(
            arrival_airport
        )
    )

    if (
        departure_country
        in FLIGHTAPI_UNSUPPORTED_COUNTRIES
    ):
        return False

    if (
        arrival_country
        in FLIGHTAPI_UNSUPPORTED_COUNTRIES
    ):
        return False

    return True