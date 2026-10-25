"""Domain models for train stations, passenger configuration, fares, and journeys."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class FareStatus(str, Enum):
    """Status of train fare retrieval."""
    VERIFIED_LIVE = "VERIFIED_LIVE"
    SCHEDULE_ONLY_SALES_CLOSED = "SCHEDULE_ONLY_SALES_CLOSED"
    UNAVAILABLE = "UNAVAILABLE"


class SeatClass(str, Enum):
    """Train seating and compartment classes."""
    ECO = "ECO"
    EXTRA = "EXTRA"
    SLEEPER_CABIN = "SLEEPER_CABIN"
    SLEEPER_BERTH = "SLEEPER_BERTH"


@dataclass(frozen=True)
class TrainStation:
    """Represents a train railway station."""
    code: str
    name: str
    city: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    is_city_center: bool = True

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"


# Canonical station mappings for Finland (especially Helsinki and Rovaniemi corridors)
STATION_HKI = TrainStation(code="HKI", name="Helsinki Central", city="Helsinki", latitude=60.172, longitude=24.941)
STATION_PSL = TrainStation(code="PSL", name="Pasila", city="Helsinki", latitude=60.199, longitude=24.933, is_city_center=False)
STATION_ROI = TrainStation(code="ROI", name="Rovaniemi", city="Rovaniemi", latitude=66.498, longitude=25.705)
STATION_TPE = TrainStation(code="TPE", name="Tampere Central", city="Tampere", latitude=61.498, longitude=23.773)
STATION_TKU = TrainStation(code="TKU", name="Turku Central", city="Turku", latitude=60.453, longitude=22.253)
STATION_OL = TrainStation(code="OL", name="Oulu Central", city="Oulu", latitude=65.012, longitude=25.484)
STATION_KLI = TrainStation(code="KLI", name="Kemijärvi", city="Kemijärvi", latitude=66.715, longitude=27.419)

KNOWN_STATIONS: Dict[str, TrainStation] = {
    "HKI": STATION_HKI,
    "PSL": STATION_PSL,
    "ROI": STATION_ROI,
    "TPE": STATION_TPE,
    "TKU": STATION_TKU,
    "OL": STATION_OL,
    "KLI": STATION_KLI,
}

AIRPORT_TO_TRAIN_STATION_MAP: Dict[str, TrainStation] = {
    "HEL": STATION_HKI,
    "RVN": STATION_ROI,
    "TMP": STATION_TPE,
    "TKU": STATION_TKU,
    "OUL": STATION_OL,
}


def get_station(code_or_name: str) -> TrainStation:
    """Resolve a station by short code or common name."""
    clean = code_or_name.strip().upper()
    if clean in KNOWN_STATIONS:
        return KNOWN_STATIONS[clean]
    if clean in AIRPORT_TO_TRAIN_STATION_MAP:
        return AIRPORT_TO_TRAIN_STATION_MAP[clean]

    # Search by city or name
    low = code_or_name.strip().lower()
    for station in KNOWN_STATIONS.values():
        if low in station.name.lower() or low in station.city.lower():
            return station

    # Fallback to an ad-hoc station model
    return TrainStation(code=clean, name=code_or_name.strip(), city=code_or_name.strip())


@dataclass(frozen=True)
class TrainPassengerConfig:
    """Passenger configuration for train bookings and searches."""
    adults: int = 2
    children: int = 0

    def __post_init__(self):
        if self.adults < 0 or self.children < 0:
            raise ValueError("Passenger counts cannot be negative.")
        if self.total_passengers == 0:
            raise ValueError("At least one passenger is required.")

    @property
    def total_passengers(self) -> int:
        return self.adults + self.children

    def to_vr_passengers(self) -> List[Dict[str, Any]]:
        """Serialize passenger parameters for VR API payloads."""
        passengers = []
        for _ in range(self.adults):
            passengers.append({"type": "ADULT"})
        for _ in range(self.children):
            passengers.append({"type": "CHILD"})
        return passengers


@dataclass
class TrainFareOption:
    """Pricing option for a journey (e.g., standard seat, extra class, or private sleeper cabin)."""
    name: str
    fare_class: SeatClass
    total_price: Optional[float]
    currency: str = "EUR"
    status: FareStatus = FareStatus.VERIFIED_LIVE
    is_sleeper: bool = False
    is_private_compartment: bool = False
    description: str = ""
    availability: str = "AVAILABLE"

    @property
    def price_per_passenger(self) -> Optional[float]:
        # For private compartments, price is for the whole compartment
        if self.total_price is None:
            return None
        return self.total_price


@dataclass
class TrainJourney:
    """Complete train journey between an origin and destination station."""
    journey_id: str
    origin: TrainStation
    destination: TrainStation
    departure_time: datetime
    arrival_time: datetime
    duration_minutes: int
    train_type: str
    train_number: str
    transfers: int = 0
    is_night_train: bool = False
    fare_options: List[TrainFareOption] = field(default_factory=list)
    fare_status: FareStatus = FareStatus.VERIFIED_LIVE
    legs_summary: List[Dict[str, Any]] = field(default_factory=list)
    train_fill_percent: Optional[int] = None

    @property
    def cheapest_fare(self) -> Optional[TrainFareOption]:
        """Return the cheapest available fare option."""
        priced = [opt for opt in self.fare_options if opt.total_price is not None]
        if not priced:
            return None
        return min(priced, key=lambda opt: opt.total_price)

    @property
    def sleeper_fare(self) -> Optional[TrainFareOption]:
        """Return the cheapest sleeper compartment / berth option if available."""
        sleepers = [opt for opt in self.fare_options if opt.is_sleeper and opt.total_price is not None]
        if not sleepers:
            return None
        return min(sleepers, key=lambda opt: opt.total_price)

    @property
    def day_seat_fare(self) -> Optional[TrainFareOption]:
        """Return the standard daytime seat option (Eco or Extra)."""
        seats = [opt for opt in self.fare_options if not opt.is_sleeper and opt.total_price is not None]
        if not seats:
            return None
        return min(seats, key=lambda opt: opt.total_price)
