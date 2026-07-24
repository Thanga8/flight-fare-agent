AIRPORT_GROUPS = {

    "HYD": [
        "HYD"
    ],

    "MAA": [
        "MAA"
    ],

    "BLR": [
        "BLR"
    ],

    "BOM": [
        "BOM"
    ],

    "DEL": [
        "DEL"
    ],

    "HEL": [
        "HEL"
    ],

    "MOW": [
        "SVO",
        "DME",
        "VKO"
    ],

    "SVO": [
        "SVO"
    ],

    "DME": [
        "DME"
    ],

    "VKO": [
        "VKO"
    ],

}
def get_airports(location):
    """
    Return the list of airports associated
    with a location.
    """

    location = location.upper()

    if location not in AIRPORT_GROUPS:
        raise ValueError(
            f"Unknown airport or location: "
            f"{location}"
        )

    return AIRPORT_GROUPS[location]