import os
import tempfile
import unittest
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
        self.env = patch.dict(os.environ, {"MONITOR_OWNER_PASSWORD": "owner-test", "FLASK_SECRET_KEY": "test-secret"})
        self.env.start()
        webapp.app.config["TESTING"] = True
        webapp.app.secret_key = "test-secret"
        self.client = webapp.app.test_client()
        db.initialize_database()

    def tearDown(self):
        self.env.stop()
        self.dir_patch.stop()
        self.path_patch.stop()
        self.temp.cleanup()

    def login(self):
        return self.client.post("/monitor/login", data={"password": "owner-test"})

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

    def test_default_two_day_paused_schedule_timezone_and_persistent_edit(self):
        self.login()
        response = self.client.post("/api/monitor/jobs", data=self.create_data())
        self.assertEqual(302, response.status_code)
        job = db.list_monitor_jobs()[0]
        self.assertEqual(0, job["enabled"])
        self.assertEqual(2, job["interval_days"])
        self.assertEqual("Asia/Kolkata", job["timezone"])
        self.assertIsNone(job["next_run_at"])
        update = self.create_data(interval_days="3", enabled="1")
        response = self.client.post(f"/api/monitor/jobs/{job['id']}", data=update)
        self.assertEqual(302, response.status_code)
        saved = db.get_monitor_job(job["id"])
        self.assertEqual(3, saved["interval_days"])
        self.assertEqual(1, saved["enabled"])
        self.assertGreater(datetime.fromisoformat(saved["next_run_at"]), datetime.now(timezone.utc))

    def test_invalid_budget_timezone_and_interval_rejected(self):
        self.login()
        for updates in ({"api_budget": "999"}, {"timezone": "Nowhere/Invalid"}, {"interval_days": "5"}):
            response = self.client.post("/api/monitor/jobs", data=self.create_data(**updates))
            self.assertEqual(400, response.status_code)

    def test_atomic_run_claim_prevents_overlap_and_history_persists(self):
        self.login()
        self.client.post("/api/monitor/jobs", data=self.create_data(enabled="1"))
        job_row = db.list_monitor_jobs()[0]
        claimed = db.claim_monitor_run(job_row["id"])
        self.assertIsNotNone(claimed)
        self.assertIsNone(db.claim_monitor_run(job_row["id"]))
        db.finish_monitor_run(claimed, "succeeded", {"serpapi_calls": 2, "itineraries": []}, next_run_at=job_row["next_run_at"])
        self.assertEqual("succeeded", db.list_monitor_runs(job_row["id"])[0]["status"])
        self.assertEqual(2, db.list_monitor_runs(job_row["id"])[0]["serpapi_calls"])

    def test_manual_run_uses_shared_search_path_with_mock_provider(self):
        self.login()
        self.client.post("/api/monitor/jobs", data=self.create_data())
        job_row = db.list_monitor_jobs()[0]
        fake_report = {"serpapi_calls": 3, "itineraries": [], "valid_date_pairs": 2, "covered_date_pairs": 1}
        with patch.dict(os.environ, {"SERPAPI_API_KEY": "mock-only"}), \
             patch.object(webapp, "SerpApiProvider"), \
             patch.object(webapp, "search_multi_leg_itineraries", return_value=fake_report) as search:
            response = self.client.post(f"/api/monitor/jobs/{job_row['id']}/run")
        self.assertEqual(200, response.status_code)
        self.assertEqual("partially_succeeded", response.json["status"])
        self.assertEqual(6, search.call_args.kwargs["serpapi_budget"])

    def test_telegram_summary_uses_run_coverage_and_actual_best_fare(self):
        from unittest.mock import Mock
        job = {"name": "Test watch", "leg1_origin": "HYD", "leg1_destination": "MOW",
               "leg2_origin": "MOW", "leg2_destination": "HYD", "start_date": "2027-01-01",
               "end_date": "2027-01-20", "timezone": "Asia/Kolkata", "api_budget": 6}
        report = {"covered_date_pairs": 2, "valid_date_pairs": 8, "serpapi_calls": 4,
                  "itineraries": [{"total_price_inr": 42000}],
                  "combined_results": [{"status": "priced"}]}
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


if __name__ == "__main__":
    unittest.main()
