"""Finnish train search and fare integration module."""

from src.trains.client import VRTrainClient
from src.trains.comparison import (
    TransitComparisonResult,
    TransitComparisonService,
)
from src.trains.models import (
    FareStatus,
    SeatClass,
    TrainFareOption,
    TrainJourney,
    TrainPassengerConfig,
    TrainStation,
    get_station,
)

__all__ = [
    "FareStatus",
    "SeatClass",
    "TrainFareOption",
    "TrainJourney",
    "TrainPassengerConfig",
    "TrainStation",
    "TransitComparisonResult",
    "TransitComparisonService",
    "VRTrainClient",
    "get_station",
]
