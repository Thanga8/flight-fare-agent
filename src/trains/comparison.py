"""Comparison service between Flights and Finnish Trains (Day Seat & Night Sleeper)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, Optional

from src.trains.client import VRTrainClient
from src.trains.models import (
    FareStatus,
    TrainJourney,
    TrainPassengerConfig,
    TrainStation,
    get_station,
)

logger = logging.getLogger(__name__)

# Approximate standard FX rates for display normalization when flights are in INR
INR_PER_EUR = 90.0

# Airport <-> Train station mapping for Finland
CORRIDOR_MAP = {
    "HEL": "HKI",
    "HKI": "HEL",
    "RVN": "ROI",
    "ROI": "RVN",
}


@dataclass
class TransitComparisonResult:
    """Structured result of flight vs. train cost & schedule comparison."""
    flight_origin: str
    flight_destination: str
    train_origin: TrainStation
    train_destination: TrainStation
    travel_date: str
    passengers: TrainPassengerConfig

    # Flight details (normalized for total passengers)
    flight_total_price: Optional[float]
    flight_duration_minutes: Optional[int]
    flight_currency: str = "EUR"
    flight_flight_number: Optional[str] = None
    flight_details: Optional[Dict[str, Any]] = None

    # Daytime Train details
    cheapest_day_train: Optional[TrainJourney] = None
    day_train_total_price: Optional[float] = None
    day_train_duration_minutes: Optional[int] = None

    # Night Sleeper Train details
    cheapest_night_train: Optional[TrainJourney] = None
    night_sleeper_total_price: Optional[float] = None
    night_train_duration_minutes: Optional[int] = None

    train_currency: str = "EUR"

    # Deltas (Flight Total minus Train Total: positive means train saves money)
    flight_vs_day_train_delta: Optional[float] = None
    flight_vs_night_sleeper_delta: Optional[float] = None

    fare_status: FareStatus = FareStatus.VERIFIED_LIVE
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert comparison result to a serializable dictionary."""
        return {
            "travel_date": self.travel_date,
            "passengers": {
                "adults": self.passengers.adults,
                "children": self.passengers.children,
                "total": self.passengers.total_passengers,
            },
            "flight": {
                "route": f"{self.flight_origin} -> {self.flight_destination}",
                "total_price": self.flight_total_price,
                "duration_minutes": self.flight_duration_minutes,
                "currency": self.flight_currency,
                "flight_number": self.flight_flight_number,
            },
            "day_train": {
                "route": f"{self.train_origin.name} -> {self.train_destination.name}",
                "train": self.cheapest_day_train.train_number if self.cheapest_day_train else None,
                "total_price": self.day_train_total_price,
                "duration_minutes": self.day_train_duration_minutes,
                "currency": self.train_currency,
            },
            "night_train_sleeper": {
                "route": f"{self.train_origin.name} -> {self.train_destination.name}",
                "train": self.cheapest_night_train.train_number if self.cheapest_night_train else None,
                "total_price": self.night_sleeper_total_price,
                "duration_minutes": self.night_train_duration_minutes,
                "currency": self.train_currency,
                "hotel_night_saved": True,
            },
            "deltas_eur": {
                "flight_vs_day_train_savings": self.flight_vs_day_train_delta,
                "flight_vs_night_sleeper_savings": self.flight_vs_night_sleeper_delta,
            },
            "fare_status": self.fare_status.value,
            "summary": self.summary,
        }


class TransitComparisonService:
    """Service to compare cost and convenience of Flights vs Trains for 2 adults."""

    def __init__(
        self,
        vr_client: Optional[VRTrainClient] = None,
        flight_provider: Optional[Any] = None,
        inr_per_eur_rate: float = INR_PER_EUR,
    ):
        self.vr_client = vr_client or VRTrainClient()
        self.flight_provider = flight_provider
        self.fx_rate = inr_per_eur_rate

    def compare(
        self,
        origin: str,
        destination: str,
        travel_date: str | date | datetime,
        passenger_config: Optional[TrainPassengerConfig] = None,
        flight_cache_mode: str = "cache",
        flight_payload: Optional[Dict[str, Any]] = None,
    ) -> TransitComparisonResult:
        """
        Compare Flights vs Trains for origin and destination on a given date.
        
        Normalized for configured passengers (default: 2 adults).
        """
        passengers = passenger_config or TrainPassengerConfig(adults=2)
        date_str = self._normalize_date(travel_date)

        # 1. Resolve airport codes and train station models
        flight_origin, train_origin = self._resolve_route_endpoints(origin, default_airport="HEL", default_train="HKI")
        flight_dest, train_dest = self._resolve_route_endpoints(destination, default_airport="RVN", default_train="ROI")

        # 2. Fetch train journeys
        train_journeys = self.vr_client.search_journeys(
            origin=train_origin,
            destination=train_dest,
            travel_date=date_str,
            passenger_config=passengers,
        )

        # Find cheapest day train seat and night train sleeper
        cheapest_day_train: Optional[TrainJourney] = None
        day_seat_price: Optional[float] = None

        cheapest_night_train: Optional[TrainJourney] = None
        night_sleeper_price: Optional[float] = None

        fare_status = FareStatus.VERIFIED_LIVE
        if train_journeys:
            # Check if all returned journeys are schedule-only
            if all(j.fare_status == FareStatus.SCHEDULE_ONLY_SALES_CLOSED for j in train_journeys):
                fare_status = FareStatus.SCHEDULE_ONLY_SALES_CLOSED

            day_candidates = [j for j in train_journeys if not j.is_night_train and j.day_seat_fare]
            if day_candidates:
                cheapest_day_train = min(day_candidates, key=lambda j: j.day_seat_fare.total_price or float("inf"))
                if cheapest_day_train.day_seat_fare and cheapest_day_train.day_seat_fare.total_price is not None:
                    day_seat_price = cheapest_day_train.day_seat_fare.total_price

            night_candidates = [j for j in train_journeys if j.is_night_train and j.sleeper_fare]
            if night_candidates:
                cheapest_night_train = min(night_candidates, key=lambda j: j.sleeper_fare.total_price or float("inf"))
                if cheapest_night_train.sleeper_fare and cheapest_night_train.sleeper_fare.total_price is not None:
                    night_sleeper_price = cheapest_night_train.sleeper_fare.total_price

        # 3. Fetch flight results
        flight_info = self._get_flight_data(
            departure_airport=flight_origin,
            arrival_airport=flight_dest,
            flight_date=date_str,
            cache_mode=flight_cache_mode,
            flight_payload=flight_payload,
            passengers=passengers,
        )

        flight_total_eur = flight_info.get("price_eur")
        flight_duration = flight_info.get("duration")
        flight_number = flight_info.get("flight_number")

        # 4. Compute cost deltas (Flight - Train: positive means train is cheaper)
        flight_vs_day_delta = None
        if flight_total_eur is not None and day_seat_price is not None:
            flight_vs_day_delta = round(flight_total_eur - day_seat_price, 2)

        flight_vs_sleeper_delta = None
        if flight_total_eur is not None and night_sleeper_price is not None:
            flight_vs_sleeper_delta = round(flight_total_eur - night_sleeper_price, 2)

        # 5. Build human-readable summary
        summary = self._build_summary(
            date_str=date_str,
            passengers=passengers,
            flight_origin=flight_origin,
            flight_dest=flight_dest,
            flight_total=flight_total_eur,
            day_seat_price=day_seat_price,
            night_sleeper_price=night_sleeper_price,
            flight_vs_day_delta=flight_vs_day_delta,
            flight_vs_sleeper_delta=flight_vs_sleeper_delta,
            fare_status=fare_status,
        )

        return TransitComparisonResult(
            flight_origin=flight_origin,
            flight_destination=flight_dest,
            train_origin=train_origin,
            train_destination=train_dest,
            travel_date=date_str,
            passengers=passengers,
            flight_total_price=flight_total_eur,
            flight_duration_minutes=flight_duration,
            flight_currency="EUR",
            flight_flight_number=flight_number,
            flight_details=flight_info.get("raw"),
            cheapest_day_train=cheapest_day_train,
            day_train_total_price=day_seat_price,
            day_train_duration_minutes=cheapest_day_train.duration_minutes if cheapest_day_train else None,
            cheapest_night_train=cheapest_night_train,
            night_sleeper_total_price=night_sleeper_price,
            night_train_duration_minutes=cheapest_night_train.duration_minutes if cheapest_night_train else None,
            train_currency="EUR",
            flight_vs_day_train_delta=flight_vs_day_delta,
            flight_vs_night_sleeper_delta=flight_vs_sleeper_delta,
            fare_status=fare_status,
            summary=summary,
        )

    def _get_flight_data(
        self,
        departure_airport: str,
        arrival_airport: str,
        flight_date: str,
        cache_mode: str,
        flight_payload: Optional[Dict[str, Any]],
        passengers: TrainPassengerConfig,
    ) -> Dict[str, Any]:
        """Retrieve and normalize flight price for total passengers."""
        payload = flight_payload
        if payload is None and self.flight_provider is not None:
            try:
                payload = self.flight_provider.search_one_way(
                    departure_id=departure_airport,
                    arrival_id=arrival_airport,
                    outbound_date=flight_date,
                    cache_mode=cache_mode,
                )
            except Exception as err:
                logger.warning("Flight search provider returned error: %s", err)
                payload = None

        if not payload or not isinstance(payload, dict):
            return {}

        flights = payload.get("best_flights", []) + payload.get("other_flights", [])
        priced = [f for f in flights if f.get("price") is not None]
        if not priced:
            return {"raw": payload}

        cheapest = min(priced, key=lambda f: f["price"])
        raw_price = cheapest["price"]
        currency = payload.get("search_parameters", {}).get("currency", "INR")

        # Convert to EUR if flight is quoted in INR
        if currency.upper() == "INR":
            price_eur_single = raw_price / self.fx_rate
        else:
            price_eur_single = float(raw_price)

        # Flights are quoted per passenger, multiply by adults count
        flight_total_eur = round(price_eur_single * passengers.adults, 2)

        # Extract flight number
        segments = cheapest.get("flights", [])
        flight_number = segments[0].get("flight_number") if segments else None

        return {
            "price_eur": flight_total_eur,
            "duration": cheapest.get("total_duration"),
            "flight_number": flight_number,
            "raw": cheapest,
        }

    def _resolve_route_endpoints(self, location: str, default_airport: str, default_train: str) -> tuple[str, TrainStation]:
        """Map user location input into both an airport code and a TrainStation object."""
        clean = location.strip().upper()
        if clean in {"HEL", "HKI", "HELSINKI"}:
            return "HEL", get_station("HKI")
        if clean in {"RVN", "ROI", "ROVANIEMI"}:
            return "RVN", get_station("ROI")
        if clean in CORRIDOR_MAP:
            other = CORRIDOR_MAP[clean]
            if len(clean) == 3 and clean in {"HEL", "RVN", "TMP", "TKU", "OUL"}:
                return clean, get_station(other)
            return other, get_station(clean)

        # Fallback
        train_st = get_station(location)
        airport_code = CORRIDOR_MAP.get(train_st.code, default_airport)
        return airport_code, train_st

    @staticmethod
    def _normalize_date(travel_date: str | date | datetime) -> str:
        """Ensure date is formatted as YYYY-MM-DD."""
        if isinstance(travel_date, datetime):
            return travel_date.date().isoformat()
        if isinstance(travel_date, date):
            return travel_date.isoformat()
        if isinstance(travel_date, str):
            clean = travel_date.strip()
            if "T" in clean:
                clean = clean.split("T")[0]
            elif " " in clean:
                clean = clean.split(" ")[0]
            date.fromisoformat(clean)
            return clean
        raise ValueError(f"Invalid date format: {travel_date}")

    @staticmethod
    def _build_summary(
        date_str: str,
        passengers: TrainPassengerConfig,
        flight_origin: str,
        flight_dest: str,
        flight_total: Optional[float],
        day_seat_price: Optional[float],
        night_sleeper_price: Optional[float],
        flight_vs_day_delta: Optional[float],
        flight_vs_sleeper_delta: Optional[float],
        fare_status: FareStatus,
    ) -> str:
        """Construct a concise, informative text summary of the comparison."""
        count_str = f"{passengers.adults} adult(s)"
        lines = [f"Transit Comparison for {flight_origin} <-> {flight_dest} on {date_str} ({count_str}):"]

        if fare_status == FareStatus.SCHEDULE_ONLY_SALES_CLOSED:
            lines.append("  [Notice] Train fares not yet on sale for this date (schedule-only).")

        if flight_total is not None:
            lines.append(f"  * Flight Total: EUR {flight_total:.2f}")
        else:
            lines.append("  * Flight: No verified flight fare found in cache/live.")

        if day_seat_price is not None:
            lines.append(f"  * Day Train Seats: EUR {day_seat_price:.2f}")
            if flight_vs_day_delta is not None:
                if flight_vs_day_delta > 0:
                    lines.append(f"    -> Day train saves EUR {flight_vs_day_delta:.2f} compared to flights.")
                else:
                    lines.append(f"    -> Flights are EUR {-flight_vs_day_delta:.2f} cheaper than day train.")

        if night_sleeper_price is not None:
            lines.append(f"  * Night Train (Private 2-Berth Sleeper Cabin): EUR {night_sleeper_price:.2f}")
            if flight_vs_sleeper_delta is not None:
                if flight_vs_sleeper_delta > 0:
                    lines.append(f"    -> Night sleeper cabin saves EUR {flight_vs_sleeper_delta:.2f} vs flights (+ saves 1 hotel night).")
                else:
                    lines.append(f"    -> Flights are EUR {-flight_vs_sleeper_delta:.2f} less than private sleeper cabin (excluding hotel savings).")

        return "\n".join(lines)
