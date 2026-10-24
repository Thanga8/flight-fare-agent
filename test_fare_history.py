import json
import tempfile
import unittest
from pathlib import Path

from flight_search.database import db
from webapp import app


class FareHistoryViewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old_dir, self.old_path = db.DATABASE_DIR, db.DATABASE_PATH
        db.DATABASE_DIR = Path(self.temp.name)
        db.DATABASE_PATH = Path(self.temp.name) / "history.db"
        db.initialize_database()
        self.client = app.test_client()

    def tearDown(self):
        db.DATABASE_DIR, db.DATABASE_PATH = self.old_dir, self.old_path
        self.temp.cleanup()

    @staticmethod
    def run_record():
        return {
            "start_date": "2027-02-01", "end_date": "2027-02-20", "nights": 7,
            "leg1_origin": "HYD", "leg1_destination": "PAR", "leg2_origin": "HEL", "leg2_destination": "HYD",
            "leg1_cache_mode": "live", "leg2_cache_mode": "live", "combined_cache_mode": "cache",
            "serpapi_budget": 12, "serpapi_calls": 2, "budget_limited": False, "statistics": {},
        }

    def add_fare(self, origin, destination, departure_date, price, currency, fetched_at, source="live"):
        flight = {"total_duration": 420, "flights": [{
            "airline": "Example Air", "flight_number": "EA42",
            "departure_airport": {"id": origin, "time": "08:00"},
            "arrival_airport": {"id": destination, "time": "15:00"},
        }]}
        db.persist_multi_leg_search(run=self.run_record(), fares=[{
            "leg_number": 1, "departure_date": departure_date, "departure_airport": origin,
            "arrival_airport": destination, "price": price, "currency": currency,
            "flight": flight, "data_source": source, "source_fetched_at": fetched_at,
        }], outcomes=[], comparisons=[])

    def add_insight(self, route_from, route_to, departure_date, status, insight, fetched_at):
        db.persist_multi_leg_search(run=self.run_record(), fares=[], outcomes=[], comparisons=[], google_insights=[{
            "leg_number": 1, "departure_id": route_from, "arrival_id": route_to,
            "departure_date": departure_date, "currency": "INR", "insight_status": status,
            "insights_json": None if insight is None else json.dumps(insight),
            "data_source": "live", "source_fetched_at": fetched_at,
        }])

    def test_history_filters_exact_airport_pair_date_and_currency(self):
        day = "2027-02-10"
        self.add_fare("HYD", "CDG", day, 50000, "INR", "2027-02-01T00:00:00Z")
        self.add_fare("HYD", "CDG", day, 47000, "INR", "2027-02-02T00:00:00Z", "cache")
        self.add_fare("HYD", "CDG", day, 600, "USD", "2027-02-03T00:00:00Z")
        self.add_fare("HYD", "ORY", day, 30000, "INR", "2027-02-04T00:00:00Z")
        self.add_fare("HYD", "CDG", "2027-02-11", 20000, "INR", "2027-02-05T00:00:00Z")

        response = self.client.get("/history", query_string={
            "departure_airport": "hyd", "arrival_airport": "cdg", "departure_date": day,
        })
        self.assertEqual(200, response.status_code)
        self.assertIn(b"47000.0", response.data)
        self.assertIn(b"50000.0", response.data)
        self.assertIn(b"Latest observed fare", response.data)
        self.assertIn(b"Lowest observed so far", response.data)
        self.assertIn("47000.0 – 50000.0".encode(), response.data)
        self.assertIn(b"600.0 USD", response.data)
        self.assertNotIn(b"30000.0", response.data)
        self.assertNotIn(b"20000.0", response.data)
        self.assertIn(b"Observed price over time", response.data)
        self.assertIn(b"HYD 08:00", response.data)
        self.assertIn(b"CDG 15:00", response.data)

    def test_primary_navigation_connects_search_and_history(self):
        home = self.client.get("/")
        self.assertIn(b'aria-label="Primary navigation"', home.data)
        self.assertIn(b'href="/history"', home.data)
        self.assertIn(b'aria-current="page">Search</a>', home.data)

        history = self.client.get("/history")
        self.assertEqual(200, history.status_code)
        self.assertIn(b'aria-current="page">Fare History</a>', history.data)
        self.assertIn(b'href="/"', history.data)

    def test_history_empty_state_links_to_search_route(self):
        response = self.client.get("/history", query_string={
            "departure_airport": "HYD", "arrival_airport": "CDG",
            "departure_date": "2027-02-10",
        })
        self.assertEqual(200, response.status_code)
        self.assertIn(b"No saved fare observations match", response.data)
        self.assertIn(b'href="/"', response.data)
        self.assertIn(b"collect observations for this route", response.data)

    def test_google_insights_are_separate_and_zero_is_not_treated_as_missing(self):
        day = "2027-02-10"
        self.add_fare("HYD", "CDG", day, 50000, "INR", "2027-02-01T00:00:00Z")
        self.add_insight("HYD", "CDG,ORY", day, "present", {
            "lowest_price": 0, "price_level": "low", "typical_price_range": [0, 700],
            "price_history": [[1800000000, 0], [1800086400, 650]],
        }, "2027-02-01T01:00:00Z")
        self.add_insight("HYD", "CDG", day, "absent", None, "2027-02-02T01:00:00Z")

        response = self.client.get("/history", query_string={
            "departure_airport": "HYD", "arrival_airport": "CDG", "departure_date": day,
        })
        self.assertIn(b"Google Flights-provided insight", response.data)
        self.assertIn(b"Google's lowest returned price: 0 INR", response.data)
        self.assertIn(b"Google price level: low", response.data)
        self.assertIn(b"did not include a", response.data)
        self.assertIn(b"Google historical price points", response.data)
        self.assertIn(b"Our observed fares", response.data)

    def test_empty_google_insights_are_distinguished_from_absent(self):
        day = "2027-02-12"
        self.add_fare("HEL", "HYD", day, 0, "INR", "2027-02-01T00:00:00Z", "cache")
        self.add_insight("HEL", "HYD", day, "empty", {}, "2027-02-01T01:00:00Z")
        response = self.client.get("/history", query_string={
            "departure_airport": "HEL", "arrival_airport": "HYD", "departure_date": day,
        })
        self.assertIn(b"empty Google price-insights object", response.data)
        self.assertIn(b"0.0 INR", response.data)

    def test_empty_insight_and_insufficient_history_are_explained(self):
        day = "2027-02-12"
        self.add_fare("HEL", "HYD", day, 0, "INR", "2027-02-01T00:00:00Z", "cache")
        self.add_insight("HEL", "HYD", day, "empty", {}, "2027-02-01T01:00:00Z")
        response = self.client.get("/history", query_string={
            "departure_airport": "HEL", "arrival_airport": "HYD", "departure_date": day,
        })
        self.assertIn(b"One valid observation is saved", response.data)
        self.assertIn(b"empty Google price-insights object", response.data)
        self.assertIn(b"0.0 INR", response.data)

    def test_invalid_or_incomplete_history_query_is_handled(self):
        response = self.client.get("/history", query_string={"departure_airport": "HYD"})
        self.assertEqual(200, response.status_code)
        self.assertIn(b"Enter origin, destination, and departure date", response.data)


if __name__ == "__main__":
    unittest.main()
