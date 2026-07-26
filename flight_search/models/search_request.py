from dataclasses import dataclass


@dataclass
class OpenJawSearchRequest:
    """
    Represents an explicit open-jaw flight search.

    Example:

        Outbound:
            HYD → SVO

        Return:
            HEL → HYD

    The user travels independently between SVO and HEL.
    """

    origin: str

    outbound_destination: str

    return_origin: str

    start_date: str

    end_date: str

    min_trip_days: int

    max_trip_days: int