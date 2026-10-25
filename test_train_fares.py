"""Unit tests for VR Finnish Train fares, models, HTTP client, and Flight-vs-Train comparison."""

from __future__ import annotations

import unittest
from datetime import datetime
from unittest.mock import MagicMock

from src.trains.client import VRTrainClient
from src.trains.comparison import TransitComparisonService
from src.trains.models import (
    FareStatus,
    SeatClass,
    TrainFareOption,
    TrainJourney,
    TrainPassengerConfig,
    TrainStation,
    get_station,
)


class TrainModelsTests(unittest.TestCase):
    """Test train station, passenger config, and journey models."""

    def test_station_resolution(self):
        hki = get_station("HKI")
        self.assertEqual(hki.code, "HKI")
        self.assertEqual(hki.name, "Helsinki Central")

        # Airport code mapping
        hel = get_station("HEL")
        self.assertEqual(hel.code, "HKI")

        rvn = get_station("RVN")
        self.assertEqual(rvn.code, "ROI")
        self.assertEqual(rvn.name, "Rovaniemi")

    def test_passenger_config_defaults_and_validation(self):
        config = TrainPassengerConfig()
        self.assertEqual(config.adults, 2)
        self.assertEqual(config.children, 0)
        self.assertEqual(config.total_passengers, 2)
        self.assertEqual(
            config.to_vr_passengers(),
            [{"type": "ADULT"}, {"type": "ADULT"}],
        )

        with self.assertRaises(ValueError):
            TrainPassengerConfig(adults=-1)

        with self.assertRaises(ValueError):
            TrainPassengerConfig(adults=0, children=0)

    def test_fare_options_and_journey_properties(self):
        hki = get_station("HKI")
        roi = get_station("ROI")
        dep = datetime.fromisoformat("2026-11-04T12:20:00")
        arr = datetime.fromisoformat("2026-11-04T20:23:00")

        eco_fare = TrainFareOption(
            name="Eco Class Seat",
            fare_class=SeatClass.ECO,
            total_price=98.50,
        )
        sleeper_fare = TrainFareOption(
            name="Private 2-Berth Sleeper Cabin",
            fare_class=SeatClass.SLEEPER_CABIN,
            total_price=179.00,
            is_sleeper=True,
            is_private_compartment=True,
        )

        journey = TrainJourney(
            journey_id="j-1",
            origin=hki,
            destination=roi,
            departure_time=dep,
            arrival_time=arr,
            duration_minutes=483,
            train_type="IC",
            train_number="IC 25",
            fare_options=[eco_fare, sleeper_fare],
        )

        self.assertEqual(journey.cheapest_fare, eco_fare)
        self.assertEqual(journey.day_seat_fare, eco_fare)
        self.assertEqual(journey.sleeper_fare, sleeper_fare)


class VRTrainClientTests(unittest.TestCase):
    """Test VR HTTP client parsing with mocked API responses."""

    def setUp(self):
        self.mock_session = MagicMock()
        self.client = VRTrainClient(session=self.mock_session)

    def test_daytime_journey_search_and_seat_pricing(self):
        """Standard daytime IC train with 2 adult passengers."""
        daytime_api_response = [
            {
                "result": {
                    "data": {
                        "status": "success",
                        "options": [
                            {
                                "id": "opt-day-1",
                                "departureTime": "2026-11-04T12:20:00.000+02:00",
                                "arrivalTime": "2026-11-04T20:23:00.000+02:00",
                                "totalPrice": 15860,  # 158.60 EUR for 2 adults
                                "legs": [
                                    {
                                        "trainType": "IC",
                                        "trainNumber": "25",
                                        "productAttributes": [
                                            {"name": "ECO_CLASS_SEAT", "availability": 100},
                                        ],
                                    }
                                ],
                            }
                        ],
                    }
                }
            }
        ]

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = daytime_api_response
        self.mock_session.get.return_value = mock_resp

        journeys = self.client.search_journeys("HKI", "ROI", "2026-11-04")

        self.assertEqual(len(journeys), 1)
        j = journeys[0]
        self.assertEqual(j.train_number, "IC 25")
        self.assertEqual(j.duration_minutes, 483)
        self.assertFalse(j.is_night_train)

        # Day seat fare exists and matches 158.60 EUR
        self.assertIsNotNone(j.day_seat_fare)
        self.assertEqual(j.day_seat_fare.total_price, 158.60)
        self.assertEqual(j.day_seat_fare.status, FareStatus.VERIFIED_LIVE)

    def test_overnight_sleeper_journey_with_cabin_supplement(self):
        """Overnight Santa Claus Express train with private 2-berth sleeper supplement."""
        # Main query response with sleeper night train
        main_query_response = [
            {
                "result": {
                    "data": {
                        "status": "success",
                        "options": [
                            {
                                "id": "opt-night-1",
                                "departureTime": "2026-11-04T19:29:00.000+02:00",
                                "arrivalTime": "2026-11-05T07:20:00.000+02:00",
                                "totalPrice": 9940,  # 99.40 EUR for standard seats
                                "legs": [
                                    {
                                        "trainType": "PYO",
                                        "trainNumber": "265",
                                        "productAttributes": [
                                            {"name": "BERTH_CABIN", "availability": 10},
                                            {"name": "BED", "availability": 20},
                                        ],
                                    }
                                ],
                            }
                        ],
                    }
                }
            }
        ]

        # Supplementary ONLY_BED_CABINS query response for private sleeper compartment
        sleeper_query_response = [
            {
                "result": {
                    "data": {
                        "status": "success",
                        "options": [
                            {
                                "id": "opt-sleeper-1",
                                "departureTime": "2026-11-04T19:29:00.000+02:00",
                                "arrivalTime": "2026-11-05T07:20:00.000+02:00",
                                "totalPrice": 17900,  # 179.00 EUR for private 2-berth cabin
                                "legs": [{"trainType": "PYO", "trainNumber": "265"}],
                            }
                        ],
                    }
                }
            }
        ]

        def side_effect(url, **kwargs):
            resp = MagicMock()
            resp.status_code = 200
            if "ONLY_BED_CABINS" in url:
                resp.json.return_value = sleeper_query_response
            else:
                resp.json.return_value = main_query_response
            return resp

        self.mock_session.get.side_effect = side_effect

        journeys = self.client.search_journeys("HKI", "ROI", "2026-11-04")
        self.assertEqual(len(journeys), 1)
        j = journeys[0]
        self.assertTrue(j.is_night_train)
        self.assertEqual(j.train_number, "PYO 265")

        # Eco daytime seat price
        self.assertIsNotNone(j.day_seat_fare)
        self.assertEqual(j.day_seat_fare.total_price, 99.40)

        # Private sleeper compartment price
        self.assertIsNotNone(j.sleeper_fare)
        self.assertEqual(j.sleeper_fare.total_price, 179.00)
        self.assertTrue(j.sleeper_fare.is_sleeper)
        self.assertTrue(j.sleeper_fare.is_private_compartment)

    def test_out_of_window_date_returns_schedule_only_sales_closed(self):
        """When VR returns empty options (tickets not yet released), client returns schedule-only without raising."""
        empty_api_response = [
            {
                "result": {
                    "data": {
                        "status": "success",
                        "options": [],
                    }
                }
            }
        ]
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = empty_api_response
        self.mock_session.get.return_value = mock_resp

        journeys = self.client.search_journeys("HKI", "ROI", "2028-02-01")

        self.assertGreater(len(journeys), 0)
        for j in journeys:
            self.assertEqual(j.fare_status, FareStatus.SCHEDULE_ONLY_SALES_CLOSED)
            # Fares must not be invented
            for opt in j.fare_options:
                self.assertIsNone(opt.total_price)
                self.assertEqual(opt.status, FareStatus.SCHEDULE_ONLY_SALES_CLOSED)


class TransitComparisonServiceTests(unittest.TestCase):
    """Test TransitComparisonService calculation and delta logic."""

    def test_comparison_with_day_seat_and_night_sleeper(self):
        """Compare flight total (€300 for 2 adults) with day train (€120) and sleeper (€180)."""
        mock_vr = MagicMock(spec=VRTrainClient)
        hki = get_station("HKI")
        roi = get_station("ROI")

        day_journey = TrainJourney(
            journey_id="day-1",
            origin=hki,
            destination=roi,
            departure_time=datetime.fromisoformat("2026-11-04T12:00:00"),
            arrival_time=datetime.fromisoformat("2026-11-04T20:00:00"),
            duration_minutes=480,
            train_type="IC",
            train_number="IC 25",
            fare_options=[
                TrainFareOption(name="Eco Seat", fare_class=SeatClass.ECO, total_price=120.0),
            ],
        )

        night_journey = TrainJourney(
            journey_id="night-1",
            origin=hki,
            destination=roi,
            departure_time=datetime.fromisoformat("2026-11-04T19:00:00"),
            arrival_time=datetime.fromisoformat("2026-11-05T07:00:00"),
            duration_minutes=720,
            train_type="Night Train",
            train_number="PYO 265",
            is_night_train=True,
            fare_options=[
                TrainFareOption(name="Eco Seat", fare_class=SeatClass.ECO, total_price=90.0),
                TrainFareOption(
                    name="Private 2-Berth Sleeper Cabin",
                    fare_class=SeatClass.SLEEPER_CABIN,
                    total_price=180.0,
                    is_sleeper=True,
                    is_private_compartment=True,
                ),
            ],
        )

        mock_vr.search_journeys.return_value = [day_journey, night_journey]

        # Mock flight payload: €150 per person * 2 adults = €300
        flight_payload = {
            "search_parameters": {"currency": "EUR"},
            "best_flights": [
                {
                    "price": 150.0,
                    "total_duration": 80,
                    "flights": [{"flight_number": "AY 533"}],
                }
            ],
        }

        service = TransitComparisonService(vr_client=mock_vr)
        result = service.compare(
            origin="HEL",
            destination="RVN",
            travel_date="2026-11-04",
            passenger_config=TrainPassengerConfig(adults=2),
            flight_payload=flight_payload,
        )

        self.assertEqual(result.flight_total_price, 300.0)
        self.assertEqual(result.day_train_total_price, 120.0)
        self.assertEqual(result.night_sleeper_total_price, 180.0)

        # Deltas: Flight - Train (positive means train is cheaper)
        self.assertEqual(result.flight_vs_day_train_delta, 180.0)      # 300 - 120
        self.assertEqual(result.flight_vs_night_sleeper_delta, 120.0)  # 300 - 180
        self.assertIn("Day train saves EUR 180.00", result.summary)
        self.assertIn("Night sleeper cabin saves EUR 120.00", result.summary)

    def test_comparison_with_flight_in_inr(self):
        """Flight quoted in INR (e.g. ₹13,500 per person) converted to EUR (fx=90)."""
        mock_vr = MagicMock(spec=VRTrainClient)
        mock_vr.search_journeys.return_value = []

        # ₹13,500 / 90 = €150 per adult -> €300 for 2 adults
        flight_payload = {
            "search_parameters": {"currency": "INR"},
            "best_flights": [
                {
                    "price": 13500,
                    "total_duration": 85,
                    "flights": [{"flight_number": "AY 535"}],
                }
            ],
        }

        service = TransitComparisonService(vr_client=mock_vr, inr_per_eur_rate=90.0)
        result = service.compare(
            origin="HEL",
            destination="RVN",
            travel_date="2026-11-04",
            passenger_config=TrainPassengerConfig(adults=2),
            flight_payload=flight_payload,
        )

        self.assertEqual(result.flight_total_price, 300.0)

    def test_comparison_when_sales_are_closed(self):
        """When train sales are closed (schedule only), result reflects SCHEDULE_ONLY_SALES_CLOSED."""
        mock_vr = MagicMock(spec=VRTrainClient)
        hki = get_station("HKI")
        roi = get_station("ROI")

        sched_journey = TrainJourney(
            journey_id="sched-1",
            origin=hki,
            destination=roi,
            departure_time=datetime.fromisoformat("2028-02-01T12:00:00"),
            arrival_time=datetime.fromisoformat("2028-02-01T20:00:00"),
            duration_minutes=480,
            train_type="IC",
            train_number="IC 25",
            fare_status=FareStatus.SCHEDULE_ONLY_SALES_CLOSED,
            fare_options=[
                TrainFareOption(
                    name="Eco Seat",
                    fare_class=SeatClass.ECO,
                    total_price=None,
                    status=FareStatus.SCHEDULE_ONLY_SALES_CLOSED,
                )
            ],
        )
        mock_vr.search_journeys.return_value = [sched_journey]

        service = TransitComparisonService(vr_client=mock_vr)
        result = service.compare(
            origin="HEL",
            destination="RVN",
            travel_date="2028-02-01",
            flight_payload={"best_flights": []},
        )

        self.assertEqual(result.fare_status, FareStatus.SCHEDULE_ONLY_SALES_CLOSED)
        self.assertIsNone(result.day_train_total_price)
        self.assertIsNone(result.night_sleeper_total_price)
        self.assertIsNone(result.flight_vs_day_train_delta)
        self.assertIn("Train fares not yet on sale", result.summary)


if __name__ == "__main__":
    unittest.main()
