import importlib
import json
import os
import sys
import tempfile
import types
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from flight_search.database import db
from flight_search.multi_leg import search_multi_leg_itineraries


def load_provider_module():
    # Provider tests need no SDK behavior; import against a harmless stand-in.
    dotenv_stub = types.SimpleNamespace(load_dotenv=MagicMock())
    with patch.dict(sys.modules, {
        "serpapi": types.SimpleNamespace(Client=MagicMock()),
        "dotenv": dotenv_stub,
    }):
        sys.modules.pop("flight_search.providers.serpapi_provider", None)
        return importlib.import_module("flight_search.providers.serpapi_provider")


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database_url_patch = patch.object(db, "DATABASE_URL", "")
        self.database_url_patch.start()
        self.old_dir, self.old_path = db.DATABASE_DIR, db.DATABASE_PATH
        db.DATABASE_DIR = Path(self.temp.name)
        db.DATABASE_PATH = Path(self.temp.name) / "test.db"

    def tearDown(self):
        self.database_url_patch.stop()
        db.DATABASE_DIR, db.DATABASE_PATH = self.old_dir, self.old_path
        self.temp.cleanup()

    def test_initialization_is_repeatable_and_round_trip_tables_survive(self):
        db.initialize_database()
        legacy_id = db.create_search_run("HYD", "MOW", "2027-01-01", "2027-02-01", 5, 6, 4)
        db.save_flight_result(legacy_id, {
            "departure_airport": "HYD", "arrival_airport": "MOW", "departure_date": "2027-01-01",
            "return_date": "2027-01-06", "price": 50000, "currency": "INR",
        })
        db.initialize_database()
        connection = db.get_connection()
        try:
            self.assertEqual(1, connection.execute("SELECT COUNT(*) FROM flight_results").fetchone()[0])
            tables = {r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertIn("multi_leg_search_runs", tables)
        finally:
            connection.close()

    def test_persisted_fares_comparisons_and_historical_deduplication(self):
        db.initialize_database()
        run = {
            "start_date": "2027-01-01", "end_date": "2027-02-01", "nights": 7,
            "leg1_origin": "HYD", "leg1_destination": "CDG", "leg2_origin": "HEL", "leg2_destination": "HYD",
            "leg1_cache_mode": "cache", "leg2_cache_mode": "live", "combined_cache_mode": "live",
            "serpapi_budget": 5, "serpapi_calls": 2, "budget_limited": False,
            "statistics": {"no_price": 1},
        }
        fare = {
            "leg_number": 1, "departure_date": "2027-01-01", "departure_airport": "HYD",
            "arrival_airport": "CDG", "price": 40000, "currency": "INR", "flight": {"stops": 1},
            "data_source": "cache", "source_fetched_at": "2027-01-01T01:00:00Z",
        }
        comparison = {
            "leg1_departure_date": "2027-01-01", "leg2_departure_date": "2027-01-08",
            "separate_total": 60000, "combined_price": 58000, "difference": -2000,
            "status": "priced", "details": {"airline": "Example"}, "data_source": "live",
            "source_fetched_at": "2027-01-01T02:00:00Z",
        }
        outcome = {"leg_number": 2, "departure_date": "2027-01-08", "status": "cache_miss",
                   "error": "CACHE_MISS", "data_source": "cache"}
        insight = {"leg_number": 1, "departure_id": "HYD", "arrival_id": "CDG,ORY",
                   "departure_date": "2027-01-01", "currency": "INR", "insight_status": "present",
                   "insights_json": json.dumps({"lowest_price": 0}), "data_source": "cache",
                   "source_fetched_at": "2027-01-01T01:00:00Z"}
        first = db.persist_multi_leg_search(run=run, fares=[fare], outcomes=[outcome], comparisons=[comparison], google_insights=[insight])
        second = db.persist_multi_leg_search(run=run, fares=[fare], outcomes=[outcome], comparisons=[comparison], google_insights=[insight])
        self.assertNotEqual(first, second)
        history = db.get_multi_leg_historical_prices("HYD", "CDG", "2027-01-01")
        self.assertEqual(1, len(history))
        self.assertEqual("2027-01-01T01:00:00Z", history[0]["source_fetched_at"])
        connection = db.get_connection()
        try:
            self.assertEqual(2, connection.execute("SELECT COUNT(*) FROM multi_leg_search_runs").fetchone()[0])
            self.assertEqual(2, connection.execute("SELECT COUNT(*) FROM multi_leg_comparisons").fetchone()[0])
            self.assertEqual(2, connection.execute("SELECT COUNT(*) FROM multi_leg_search_outcomes").fetchone()[0])
            self.assertEqual(1, connection.execute("SELECT COUNT(*) FROM multi_leg_google_insights").fetchone()[0])
        finally:
            connection.close()

    def test_distinct_observations_order_by_original_fetch_time(self):
        db.initialize_database()
        base = {"start_date": "2027-01-01", "end_date": "2027-02-01", "nights": 7,
                "leg1_origin": "HYD", "leg1_destination": "CDG", "leg2_origin": "HEL", "leg2_destination": "HYD",
                "leg1_cache_mode": "live", "leg2_cache_mode": "live", "combined_cache_mode": "cache",
                "serpapi_budget": 4, "serpapi_calls": 2, "budget_limited": False, "statistics": {}}
        for when, price in (("2027-01-02T00:00:00Z", 45000), ("2027-01-01T00:00:00Z", 41000)):
            fare = {"leg_number": 1, "departure_date": "2027-01-20", "departure_airport": "HYD",
                    "arrival_airport": "CDG", "price": price, "flight": {}, "data_source": "live",
                    "source_fetched_at": when}
            db.persist_multi_leg_search(run=base, fares=[fare], outcomes=[], comparisons=[])
        history = db.get_multi_leg_historical_prices("HYD", "CDG", "2027-01-20")
        self.assertEqual([41000, 45000], [row["price"] for row in history])

    def test_search_flow_persists_fares_outcomes_and_comparison(self):
        db.initialize_database()

        class Provider:
            def search_one_way(self, departure_id, arrival_id, outbound_date, cache_mode):
                from_airport, to_airport = (
                    ("HYD", "CDG") if "HYD" in departure_id else ("HEL", "HYD")
                )
                response = {"best_flights": [{"price": 20000, "flights": [{
                    "departure_airport": {"id": from_airport},
                    "arrival_airport": {"id": to_airport},
                }]}], "_source_fetched_at": "2027-01-01T00:00:00Z"}
                if from_airport == "HYD":
                    response["price_insights"] = {"lowest_price": 0, "price_level": "low"}
                return response

            def search_multi_city(self, legs, cache_mode):
                return {"best_flights": [{"price": 39000, "flights": [{
                    "departure_airport": {"id": "HYD"}, "arrival_airport": {"id": "HYD"},
                }]}], "_source_fetched_at": "2027-01-01T00:01:00Z"}

        report = search_multi_leg_itineraries(
            start_date="2027-01-01", end_date="2027-01-08", international_provider=Provider(),
            serpapi_budget=3, leg1_origin="HYD", leg1_destination="CDG",
            leg2_origin="HEL", leg2_destination="HYD", combined_candidate_limit=1,
        )
        self.assertIn("persistence_run_id", report)
        self.assertNotIn("persistence_error", report)
        connection = db.get_connection()
        try:
            self.assertEqual(2, connection.execute("SELECT COUNT(*) FROM multi_leg_fare_observations").fetchone()[0])
            self.assertEqual("priced", connection.execute("SELECT status FROM multi_leg_search_outcomes WHERE leg_number=1").fetchone()[0])
            self.assertEqual(1, connection.execute("SELECT COUNT(*) FROM multi_leg_comparisons").fetchone()[0])
            statuses = {row[0] for row in connection.execute("SELECT insight_status FROM multi_leg_google_insights")}
            self.assertEqual({"present", "absent"}, statuses)
        finally:
            connection.close()


class CacheFreshnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.provider_module = load_provider_module()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.cache = Path(self.temp.name) / "response.json"
        self.module = self.provider_module
        self.now = datetime(2027, 1, 2, tzinfo=timezone.utc)
        self.clock_patch = patch.object(self.module, "_utc_now", return_value=self.now)
        self.clock_patch.start()

    def tearDown(self):
        self.clock_patch.stop()
        self.temp.cleanup()

    def write_cache(self, metadata="normal", age=timedelta(hours=1)):
        body = {"best_flights": []}
        if metadata == "normal":
            body["_serpapi_cache"] = {"fetched_at": (self.now - age).isoformat().replace("+00:00", "Z")}
        elif metadata == "malformed":
            body["_serpapi_cache"] = {"fetched_at": "yesterday-ish"}
        elif metadata == "empty":
            body["_serpapi_cache"] = {}
        elif metadata == "future":
            body["_serpapi_cache"] = {"fetched_at": (self.now + timedelta(minutes=1)).isoformat()}
        self.cache.write_text(json.dumps(body), encoding="utf-8")

    def test_fresh_and_older_than_24h_cache(self):
        self.write_cache()
        self.assertEqual("hit", self.module._read_fresh_cache(self.cache, "test")["_cache_status"])
        self.write_cache(age=timedelta(hours=24))
        self.assertEqual("hit", self.module._read_fresh_cache(self.cache, "test")["_cache_status"])
        self.write_cache(age=timedelta(hours=24, seconds=1))
        self.assertEqual("stale", self.module._read_fresh_cache(self.cache, "test")["_cache_status"])

    def test_recent_and_stale_legacy_mtime(self):
        self.cache.write_text(json.dumps({"best_flights": []}), encoding="utf-8")
        os.utime(self.cache, (self.now.timestamp() - 30, self.now.timestamp() - 30))
        self.assertEqual("hit", self.module._read_fresh_cache(self.cache, "legacy")["_cache_status"])
        os.utime(self.cache, (self.now.timestamp() - 90000, self.now.timestamp() - 90000))
        self.assertEqual("stale", self.module._read_fresh_cache(self.cache, "legacy")["_cache_status"])

    def test_missing_malformed_and_future_metadata_rejected(self):
        for mode in ("empty", "malformed", "future"):
            with self.subTest(mode=mode):
                self.write_cache(metadata=mode)
                result = self.module._read_fresh_cache(self.cache, "test")
                self.assertEqual("stale", result["_cache_status"])
                self.assertIn("STALE_CACHE", result["error"])

    def test_stale_cache_only_never_uses_live_client(self):
        self.write_cache(age=timedelta(days=2))
        provider = self.module.SerpApiProvider(api_key="test", save_raw_responses=False)
        provider.client.search = MagicMock()
        with patch.object(provider, "_one_way_cache_path", return_value=self.cache):
            result = provider.search_one_way("HYD", "CDG", "2027-02-01", cache_mode="cache")
        self.assertEqual("stale", result["_cache_status"])
        provider.client.search.assert_not_called()
        with patch.object(provider, "_query_cache_path", return_value=self.cache):
            result = provider.search_multi_city([], cache_mode="cache")
        self.assertEqual("stale", result["_cache_status"])
        provider.client.search.assert_not_called()

    def test_live_search_refreshes_timestamp_metadata_for_both_search_types(self):
        provider = self.module.SerpApiProvider(api_key="test", save_raw_responses=False)
        provider.client.search = MagicMock(return_value={"best_flights": []})
        one_way_path = Path(self.temp.name) / "one.json"
        multi_path = Path(self.temp.name) / "multi.json"
        with patch.object(provider, "_one_way_cache_path", return_value=one_way_path), \
             patch.object(provider, "_query_cache_path", return_value=multi_path):
            one = provider.search_one_way("HYD", "CDG", "2027-02-01", cache_mode="live")
            multi = provider.search_multi_city([], cache_mode="live")
        for response, path in ((one, one_way_path), (multi, multi_path)):
            cached = json.loads(path.read_text(encoding="utf-8"))
            self.assertIn("fetched_at", cached["_serpapi_cache"])
            self.assertEqual("live", response["_cache_status"])
        self.assertEqual(2, provider.client.search.call_count)


if __name__ == "__main__":
    unittest.main()
