import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from flight_search.monitoring import classify_fare_changes, itinerary_identity, normalize_run_itineraries
from flight_search.database import db


JOB = {"id": 7, "leg1_origin": "HYD", "leg1_destination": "MOW", "leg2_origin": "MOW", "leg2_destination": "HYD",
       "start_date": "2027-01-01", "end_date": "2027-02-01", "nights": 5}


def fare(leg, departure, arrival, price, when="2027-01-10 05:00", flight_no="AB123"):
    return {"departure_date": departure, "price": price, "flight": {"flights": [{
        "departure_airport": {"id": leg, "time": when}, "arrival_airport": {"id": arrival, "time": "2027-01-10 12:00"},
        "airline_code": "AB", "flight_number": flight_no}]}}


def itinerary(price=100000, when="2027-01-10 05:00"):
    return {"leg1": fare("HYD", "2027-01-10", "MOW", 50000, when),
            "leg2": fare("MOW", "2027-01-15", "HYD", 50000, "2027-01-15 09:00"),
            "total_price_inr": price}


class FareChangeDetectionTests(unittest.TestCase):
    def test_stable_identity_normalizes_time_format_and_ignores_provider_ids(self):
        left, right = itinerary_identity(itinerary(), JOB), itinerary_identity(itinerary(99000, "2027-01-10T05:00"), JOB)
        self.assertEqual(left[0], right[0])

    def test_identity_scopes_route_window_cabin_passengers_and_departure(self):
        original = itinerary_identity(itinerary(), JOB)[0]
        for changed in (JOB | {"leg1_origin": "DEL"}, JOB | {"end_date": "2027-02-02"},
                       JOB | {"cabin": "business"}, JOB | {"passengers": 2}):
            self.assertNotEqual(original, itinerary_identity(itinerary(), changed)[0])
        self.assertNotEqual(original, itinerary_identity(itinerary(when="2027-01-10 06:00"), JOB)[0])

    def test_duplicate_results_keep_one_cheapest_observation(self):
        current = normalize_run_itineraries({"itineraries": [itinerary(100000), itinerary(98000)]}, JOB)
        self.assertEqual(1, len(current))
        self.assertEqual(98000, current[0]["fare"])

    def test_missing_segment_time_and_flight_number_is_not_guessed(self):
        weak = itinerary()
        weak["leg1"]["flight"]["flights"][0]["departure_airport"].pop("time")
        weak["leg1"]["flight"]["flights"][0].pop("flight_number")
        weak["leg1"]["flight"]["flights"][0].pop("airline_code")
        self.assertIsNone(itinerary_identity(weak, JOB))
        self.assertEqual([], normalize_run_itineraries({"itineraries": [weak]}, JOB))

    def test_new_baseline_material_changes_boundaries_and_small_changes(self):
        old = normalize_run_itineraries({"itineraries": [itinerary(100000)]}, JOB)
        old[0]["observed_at"] = "2026-10-25T00:00:00+00:00"
        first = classify_fare_changes(old, [])
        self.assertEqual("new_itinerary", first[0]["type"])
        decrease = normalize_run_itineraries({"itineraries": [itinerary(97000)]}, JOB)
        decrease[0]["observed_at"] = "2026-10-26T00:00:00+00:00"
        self.assertEqual("fare_decreased", classify_fare_changes(decrease, old)[0]["type"])
        increase = normalize_run_itineraries({"itineraries": [itinerary(103000)]}, JOB)
        increase[0]["observed_at"] = "2026-10-27T00:00:00+00:00"
        self.assertEqual("fare_increased", classify_fare_changes(increase, old)[0]["type"])
        subthreshold = normalize_run_itineraries({"itineraries": [itinerary(99500)]}, JOB)
        self.assertEqual("no_material_change", classify_fare_changes(subthreshold, old)[0]["type"])

    def test_not_observed_and_currency_mismatch_are_not_price_changes(self):
        old = {"identity_key": "old", "fare": 50000, "currency": "INR", "observed_at": "then", "route": "HYD → MOW → HYD",
               "leg1_date": "2027-01-10", "leg2_date": "2027-01-15"}
        absent = classify_fare_changes([], [old])[0]
        self.assertEqual("not_observed", absent["type"])
        current = old | {"currency": "USD", "fare": 49000, "itinerary": {}}
        mismatch = classify_fare_changes([current], [old])[0]
        self.assertEqual("currency_mismatch", mismatch["type"])
        foreign_old = old | {"currency": "USD", "fare": 100000, "identity": {}, "itinerary": {}}
        foreign_current = foreign_old | {"fare": 80000, "observed_at": "now", "itinerary": {}}
        self.assertEqual("no_material_change", classify_fare_changes([foreign_current], [foreign_old])[0]["type"])

    def test_absolute_threshold_boundary_is_inclusive(self):
        old = normalize_run_itineraries({"itineraries": [itinerary(33333.33)]}, JOB)
        old[0]["observed_at"] = "then"
        current = normalize_run_itineraries({"itineraries": [itinerary(32333.33)]}, JOB)
        current[0]["observed_at"] = "now"
        change = classify_fare_changes(current, old)[0]
        self.assertEqual("fare_decreased", change["type"])
        self.assertEqual(1000.0, change["absolute_change"])

    def test_failed_run_does_not_replace_successful_history_baseline(self):
        temp = tempfile.TemporaryDirectory()
        with patch.object(db, "DATABASE_PATH", Path(temp.name) / "fare.db"), patch.object(db, "DATABASE_DIR", Path(temp.name)):
            db.initialize_database()
            job = db.save_monitor_job(JOB | {"name": "History", "enabled": 0, "interval_days": 2, "timezone": "Asia/Kolkata",
                "api_budget": 6, "notify_telegram": 0, "next_run_at": None})
            first_run = db.claim_monitor_run(job["id"])
            db.finish_monitor_run(first_run, "succeeded", {"serpapi_calls": 3, "serpapi_budget": 6, "itineraries": [itinerary(100000)]})
            failed_run = db.claim_monitor_run(job["id"])
            db.finish_monitor_run(failed_run, "partially_succeeded", {"serpapi_calls": 2, "serpapi_budget": 6, "itineraries": [itinerary(1000)]})
            empty_run = db.claim_monitor_run(job["id"])
            empty_report = {"serpapi_calls": 3, "serpapi_budget": 6, "itineraries": []}
            db.finish_monitor_run(empty_run, "succeeded", empty_report)
            self.assertEqual(1, empty_report["fare_change_summary"]["not_observed"])
            next_run = db.claim_monitor_run(job["id"])
            report = {"serpapi_calls": 3, "serpapi_budget": 6, "itineraries": [itinerary(97000)]}
            db.finish_monitor_run(next_run, "succeeded", report)
            self.assertEqual(1, report["fare_change_summary"]["fare_decreased"])
            self.assertEqual(100000, report["fare_changes"][0]["previous_fare"])
            history = db.get_monitor_fare_history(job["id"])
            self.assertEqual(2, len(history))
        temp.cleanup()


if __name__ == "__main__":
    unittest.main()
