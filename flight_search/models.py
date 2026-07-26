from enum import Enum


class TripType(str, Enum):
    ROUND_TRIP = "round_trip"
    ONE_WAY = "one_way"
    OPEN_JAW = "open_jaw"