import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from unittest.mock import patch

import webapp
from flight_search.database import db


class FareMonitorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path_patch = patch.object(db, "DATABASE_PATH", os.path.join(self.temp.name, "monitor.db"))
        self.path_patch.start()
        self.dir_patch = patch.object(db, "DATABASE_DIR", __import__("pathlib").Path(self.temp.name))
        self.dir_patch.start()
        self.env = patch.dict(os.environ, {"MONITOR_OWNER_PASSWORD": "owner-password-long", "FLASK_SECRET_KEY": "test-secret-that-is-at-least-thirty-two-characters"})
        self.env.start()
        webapp.app.config["TESTING"] = True
        webapp.app.secret_key = "test-secret-that-is-at-least-thirty-two-characters"
        self.client = webapp.app.test_client()
        db.initialize_database()

    def tearDown(self):
        self.env.stop()
        self.dir_patch.stop()
        self.path_patch.stop()
        self.temp.cleanup()

    def login(self):
        self.client.get("/monitor/login")
        with self.client.session_transaction() as session:
            csrf = session["csrf_token"]
        return self.client.post("/monitor/login", data={"password": "owner-password-long", "_csrf_token": csrf})

    def csrf(self):
        with self.client.session_transaction() as session:
            return session["csrf_token"]

    def post(self, path, data=None):
        data = dict(data or {})
        data["_csrf_token"] = self.csrf()
        return self.client.post(path, data=data)

    def create_data(self, **overrides):
        data = {"name": "Test fare watch", "start_date": "2027-01-01", "end_date": "2027-01-20",
                "nights": "5", "leg1_origin": "HYD", "leg1_destination": "MOW", "leg2_origin": "MOW",
                "leg2_destination": "HYD", "interval_days": "2", "timezone": "Asia/Kolkata",
                "api_budget": "6"}
        data.update(overrides)
        return data

    def test_monitor_pages_and_mutations_require_owner_login(self):
        response = self.client.get("/monitor")
        self.assertEqual(302, response.status_code)
        response = self.client.post("/api/monitor/jobs", data=self.create_data())
        self.assertEqual(401, response.status_code)

    def test_authenticated_state_changes_require_csrf_token(self):
        self.login()
        response = self.client.post("/api/monitor/jobs", data=self.create_data())
        self.assertEqual(400, response.status_code)

    def test_readiness_is_owner_only_and_never_returns_secret_values(self):
        self.login()
        with patch.dict(os.environ, {"SERPAPI_API_KEY": "secret-test-key", "TELEGRAM_BOT_TOKEN": "secret-bot-token"}):
            response = self.client.get("/api/monitor/readiness")
        self.assertEqual(200, response.status_code)
        self.assertNotIn("secret-test-key", response.get_data(as_text=True))
        self.assertNotIn("secret-bot-token", response.get_data(as_text=True))
        self.assertIn(response.json["database"]["status"], {"ready", "missing"})

    def test_dashboard_renders_readiness_and_fare_history_panels(self):
        self.login()
        self.post("/api/monitor/jobs", self.create_data())
        response = self.client.get("/monitor")
        self.assertEqual(200, response.status_code)
        self.assertIn(b"Configuration readiness", response.data)
        self.assertIn(b"Recent fare observations", response.data)

    def test_default_two_day_paused_schedule_timezone_and_persistent_edit(self):
        self.login()
        response = self.post("/api/monitor/jobs", self.create_data())
        self.assertEqual(302, response.status_code)
        job = db.list_monitor_jobs()[0]
        self.assertEqual(0, job["enabled"])
        self.assertEqual(2, job["interval_days"])
        self.assertEqual("Asia/Kolkata", job["timezone"])
        self.assertIsNone(job["next_run_at"])
        update = self.create_data(interval_days="3", enabled="1")
        response = self.post(f"/api/monitor/jobs/{job['id']}", update)
        self.assertEqual(302, response.status_code)
        saved = db.get_monitor_job(job["id"])
        self.assertEqual(3, saved["interval_days"])
        self.assertEqual(1, saved["enabled"])
        self.assertGreater(datetime.fromisoformat(saved["next_run_at"]), datetime.now(timezone.utc))

    def test_invalid_budget_timezone_and_interval_rejected(self):
        self.login()
        for updates in ({"api_budget": "999"}, {"timezone": "Nowhere/Invalid"}, {"interval_days": "5"}):
            response = self.post("/api/monitor/jobs", self.create_data(**updates))
            self.assertEqual(400, response.status_code)

    def test_enabled_pause_reenable_and_unrelated_edits_are_explicit(self):
        self.login()
        self.post("/api/monitor/jobs", self.create_data(enabled="1"))
        job = db.list_monitor_jobs()[0]
        self.assertEqual(1, job["enabled"])
        # Complete edit form omits unchecked checkbox: that explicitly pauses.
        self.post(f"/api/monitor/jobs/{job['id']}", self.create_data(interval_days="7"))
        job = db.get_monitor_job(job["id"])
        self.assertEqual(0, job["enabled"])
        self.assertIsNone(job["next_run_at"])
        self.assertIsNone(db.claim_monitor_run(job["id"], due_only=True))
        # Re-enable and edit an unrelated setting while explicitly keeping it on.
        self.post(f"/api/monitor/jobs/{job['id']}", self.create_data(interval_days="3", enabled="1"))
        job = db.get_monitor_job(job["id"])
        self.assertEqual(1, job["enabled"])
        self.assertEqual(3, job["interval_days"])
        self.assertIsNotNone(job["next_run_at"])

    def test_atomic_run_claim_prevents_overlap_and_history_persists(self):
        self.login()
        self.post("/api/monitor/jobs", self.create_data(enabled="1"))
        job_row = db.list_monitor_jobs()[0]
        claimed = db.claim_monitor_run(job_row["id"])
        self.assertIsNotNone(claimed)
        self.assertIsNone(db.claim_monitor_run(job_row["id"]))
        db.finish_monitor_run(claimed, "succeeded", {"serpapi_calls": 2, "itineraries": []}, next_run_at=job_row["next_run_at"])
        self.assertEqual("succeeded", db.list_monitor_runs(job_row["id"])[0]["status"])
        self.assertEqual(2, db.list_monitor_runs(job_row["id"])[0]["serpapi_calls"])

    def test_manual_run_uses_shared_search_path_with_mock_provider(self):
        self.login()
        self.post("/api/monitor/jobs", self.create_data())
        job_row = db.list_monitor_jobs()[0]
        fake_report = {"serpapi_calls": 3, "itineraries": [], "valid_date_pairs": 2, "covered_date_pairs": 1}
        with patch.dict(os.environ, {"SERPAPI_API_KEY": "mock-only"}), \
             patch.object(webapp, "SerpApiProvider"), \
             patch.object(webapp, "search_multi_leg_itineraries", return_value=fake_report) as search:
            response = self.post(f"/api/monitor/jobs/{job_row['id']}/run")
        self.assertEqual(200, response.status_code)
        self.assertEqual("succeeded", response.json["status"])
        self.assertEqual(6, search.call_args.kwargs["serpapi_budget"])

    def test_missing_or_placeholder_provider_key_fails_before_search(self):
        self.login()
        self.post("/api/monitor/jobs", self.create_data())
        job = db.list_monitor_jobs()[0]
        claimed = db.claim_monitor_run(job["id"])
        with patch.dict(os.environ, {"SERPAPI_API_KEY": "  "}), \
             patch.object(webapp, "search_multi_leg_itineraries") as search:
            self.assertEqual("failed", webapp._execute_monitor(claimed)["status"])
        search.assert_not_called()
        self.assertEqual("failed", db.list_monitor_runs(job["id"])[0]["status"])

    def test_saved_budget_above_current_ceiling_fails_before_provider_search(self):
        self.login()
        self.post("/api/monitor/jobs", self.create_data())
        job = db.list_monitor_jobs()[0]
        connection = db.get_connection()
        with connection:
            connection.execute("UPDATE fare_monitor_jobs SET api_budget=99 WHERE id=?", (job["id"],))
        connection.close()
        claim = db.claim_monitor_run(job["id"])
        with patch.dict(os.environ, {"SERPAPI_API_KEY": "mock-key"}), \
             patch.object(webapp, "search_multi_leg_itineraries") as search:
            result = webapp._execute_monitor(claim)
        self.assertEqual("failed", result["status"])
        self.assertIn("current server limit", result["error"])
        search.assert_not_called()

    def test_concurrent_workers_only_claim_one_run(self):
        self.login()
        self.post("/api/monitor/jobs", self.create_data(enabled="1"))
        job = db.list_monitor_jobs()[0]
        connection = db.get_connection()
        with connection:
            connection.execute("UPDATE fare_monitor_jobs SET next_run_at=? WHERE id=?", ("2000-01-01T00:00:00+00:00", job["id"]))
        connection.close()
        with ThreadPoolExecutor(max_workers=8) as pool:
            claims = list(pool.map(lambda _: db.claim_monitor_run(job["id"], due_only=True), range(8)))
        self.assertEqual(1, sum(claim is not None for claim in claims))

    def test_stale_runner_records_failure_and_defers_automatic_reexecution(self):
        self.login()
        self.post("/api/monitor/jobs", self.create_data(enabled="1"))
        job = db.list_monitor_jobs()[0]
        claim = db.claim_monitor_run(job["id"])
        connection = db.get_connection()
        with connection:
            connection.execute("UPDATE fare_monitor_runs SET started_at=? WHERE id=?", ("2000-01-01T00:00:00+00:00", claim["run_id"]))
        connection.close()
        self.assertIsNone(db.claim_monitor_run(job["id"], due_only=True))
        saved = db.get_monitor_job(job["id"])
        self.assertEqual(0, saved["running"])
        self.assertGreater(datetime.fromisoformat(saved["next_run_at"]), datetime.now(timezone.utc))
        self.assertEqual("failed", db.list_monitor_runs(job["id"])[0]["status"])
        # Manual runs cannot bypass the recovery cooldown either.
        self.assertIsNone(db.claim_monitor_run(job["id"], due_only=False))
        # Once the deferred schedule is due, a later scheduler invocation may retry.
        connection = db.get_connection()
        with connection:
            connection.execute("UPDATE fare_monitor_jobs SET next_run_at=? WHERE id=?", ("2000-01-01T00:00:00+00:00", job["id"]))
        connection.close()
        retry = db.claim_monitor_run(job["id"], due_only=True)
        self.assertIsNotNone(retry)
        self.assertEqual(1, db.get_monitor_job(job["id"])["running"])
        self.assertEqual("running", db.list_monitor_runs(job["id"])[0]["status"])

    def test_serpapi_provider_sets_a_bounded_request_timeout(self):
        from unittest.mock import Mock
        from flight_search.providers.serpapi_provider import (
            SERPAPI_REQUEST_TIMEOUT_SECONDS, SerpApiProvider,
        )
        provider = SerpApiProvider(api_key="test-only", save_raw_responses=False)
        provider.client = Mock()
        provider.client.search.return_value = {}
        with patch("flight_search.providers.serpapi_provider._save_cached_response", side_effect=lambda _path, value: value):
            provider.search_round_trip("HYD", "SVO", "2027-01-20", "2027-01-25")
            provider.search_one_way("HYD", "SVO", "2027-01-20")
            provider.search_multi_city([{"departure_id": "HYD", "arrival_id": "SVO", "date": "2027-01-20"}])
        self.assertEqual(3, provider.client.search.call_count)
        self.assertTrue(all(call.kwargs["timeout"] == SERPAPI_REQUEST_TIMEOUT_SECONDS
                            for call in provider.client.search.call_args_list))

    def test_telegram_suppresses_repeated_unchanged_fare_without_losing_run_history(self):
        from test_fare_change_detection import itinerary
        self.login()
        self.post("/api/monitor/jobs", self.create_data(notify_telegram="1"))
        job = db.list_monitor_jobs()[0]
        report = {"serpapi_calls": 4, "serpapi_budget": 6, "valid_date_pairs": 3,
                  "covered_date_pairs": 2, "itineraries": [itinerary(100000)], "leg_stats": []}
        partial = {"serpapi_calls": 4, "serpapi_budget": 6, "valid_date_pairs": 3,
                   "covered_date_pairs": 2, "itineraries": [itinerary(100000)],
                   "leg_stats": [{"response_errors": ["mock provider failure"]}]}
        with patch.dict(os.environ, {"SERPAPI_API_KEY": "mock-key"}), \
             patch.object(webapp, "SerpApiProvider"), \
             patch.object(webapp, "search_multi_leg_itineraries", side_effect=[partial, report, report]), \
             patch.object(webapp, "_send_monitor_notification", return_value=True) as sender:
            first = db.claim_monitor_run(job["id"])
            self.assertEqual("partially_succeeded", webapp._execute_monitor(first)["status"])
            second = db.claim_monitor_run(job["id"])
            self.assertEqual("succeeded", webapp._execute_monitor(second)["status"])
            third = db.claim_monitor_run(job["id"])
            self.assertEqual("succeeded", webapp._execute_monitor(third)["status"])
        self.assertEqual(1, sender.call_count)
        self.assertEqual(3, len(db.list_monitor_runs(job["id"])))
        self.assertIn("Notification skipped", db.list_monitor_runs(job["id"])[0]["notification_error"])

    def test_telegram_summary_uses_run_coverage_and_actual_best_fare(self):
        from unittest.mock import Mock
        job = {"name": "Test watch", "leg1_origin": "HYD", "leg1_destination": "MOW",
               "leg2_origin": "MOW", "leg2_destination": "HYD", "start_date": "2027-01-01",
               "end_date": "2027-01-20", "timezone": "Asia/Kolkata", "api_budget": 6}
        report = {"covered_date_pairs": 2, "valid_date_pairs": 8, "serpapi_calls": 4,
                  "itineraries": [{"total_price_inr": 42000}],
                  "combined_results": [{"status": "priced"}],
                  "fare_change_summary": {"new_itinerary": 0, "fare_decreased": 1, "fare_increased": 0, "no_material_change": 0, "not_observed": 0},
                  "fare_changes": [{"type": "fare_decreased", "route": "HYD → MOW → HYD · AB AB123 HYD→MOW 2027-01-10T05:00",
                                    "leg1_date": "2027-01-10", "leg2_date": "2027-01-15", "currency": "INR",
                                    "previous_fare": 50000, "current_fare": 42000, "absolute_change": 8000,
                                    "percentage_change": -16.0}]}
        response = Mock()
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "mock", "TELEGRAM_CHAT_ID": "123"}), \
             patch("requests.post", return_value=response) as post:
            response.raise_for_status.return_value = None
            self.assertTrue(webapp._send_monitor_notification(job, report, "succeeded"))
        body = post.call_args.kwargs["json"]["text"]
        self.assertIn("INR 42,000", body)
        self.assertIn("2/8 date pairs", body)
        self.assertIn("1/1 combined checks priced", body)
        self.assertIn("4/6", body)
        self.assertIn("INR 50,000 → INR 42,000 (Δ INR 8,000; -16.00%)", body)


if __name__ == "__main__":
    unittest.main()
