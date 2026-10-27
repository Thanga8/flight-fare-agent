import unittest
import importlib
import os
from pathlib import Path
from unittest.mock import patch

import webapp as webapp_module
from webapp import _booking_links, app
from flight_search.config import settings


class WebAppTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_landing_page_loads_without_searching(self):
        response = self.client.get("/")

        self.assertEqual(200, response.status_code)
        self.assertIn(b"Search possible itineraries", response.data)
        self.assertIn(b'name="viewport"', response.data)
        self.assertIn(b"API Usage Preview", response.data)
        self.assertIn(b"api_usage_preview.js", response.data)
        self.assertIn(b'name="serpapi_budget" value="50" min="0" max="50"', response.data)

    def test_budget_default_and_maximum_settings(self):
        self.assertEqual(50, settings.DEFAULT_MULTI_LEG_SERPAPI_BUDGET)
        self.assertEqual(50, settings.MULTI_LEG_SERPAPI_BUDGET)
        self.assertEqual(50, settings.MAX_WEB_SERPAPI_BUDGET)

    def test_custom_budget_setting_cannot_raise_hard_maximum(self):
        with patch.dict(os.environ, {"MAX_WEB_SERPAPI_BUDGET": "175"}, clear=True):
            importlib.reload(settings)
            importlib.reload(webapp_module)
            self.assertEqual(50, settings.MAX_WEB_SERPAPI_BUDGET)
            self.assertEqual(50, webapp_module.MAX_WEB_SERPAPI_BUDGET)
            self.assertEqual(50, settings.MULTI_LEG_SERPAPI_BUDGET)
            self.assertEqual(50, webapp_module.MONITOR_MAX_BUDGET)
        importlib.reload(settings)
        importlib.reload(webapp_module)

    def test_default_budget_ceiling_is_capped_by_lower_custom_maximum(self):
        with patch.dict(os.environ, {"MAX_WEB_SERPAPI_BUDGET": "8"}, clear=True):
            importlib.reload(settings)
            self.assertEqual(8, settings.MULTI_LEG_SERPAPI_BUDGET)
        importlib.reload(settings)

    def test_invalid_budget_maximum_environment_value_has_clear_error(self):
        with patch.dict(os.environ, {"MAX_WEB_SERPAPI_BUDGET": "not-a-number"}, clear=True):
            with self.assertRaisesRegex(ValueError, "MAX_WEB_SERPAPI_BUDGET must be a non-negative integer"):
                importlib.reload(settings)
        importlib.reload(settings)

    def test_search_accepts_budget_within_maximum_and_rejects_above_it(self):
        form = {
            "start_date": "2027-02-03", "end_date": "2027-03-15",
            "nights_between_departures": "7", "serpapi_budget": "50",
            "combined_candidate_limit": "0", "leg1_origin": "HYD",
            "leg1_destination": "PAR", "leg2_origin": "HEL",
            "leg2_destination": "HYD", "leg1_cache_mode": "cache",
            "leg2_cache_mode": "cache", "combined_cache_mode": "cache",
        }
        report = {"itineraries": [], "google_insights": []}
        with patch("webapp.SerpApiProvider"), patch(
            "webapp.search_multi_leg_itineraries", return_value=report
        ) as search:
            accepted = self.client.post("/search", data=form)
            self.assertEqual(200, accepted.status_code)
            self.assertEqual(50, search.call_args.kwargs["serpapi_budget"])
            form["serpapi_budget"] = "51"
            rejected = self.client.post("/search", data=form)
        self.assertEqual(400, rejected.status_code)
        self.assertIn(b"SerpApi budget must be between 0 and 50.", rejected.data)
        self.assertEqual(1, search.call_count)

    def test_preview_script_reacts_to_all_planning_controls_without_network_calls(self):
        script = (Path(__file__).parent / "static" / "api_usage_preview.js").read_text(encoding="utf-8")
        for name in (
            "start_date", "end_date", "nights_between_departures", "serpapi_budget",
            "leg1_cache_mode", "leg2_cache_mode", "combined_candidate_limit", "combined_cache_mode",
        ):
            self.assertIn(f"'{name}'", script)
        self.assertIn("addEventListener('input', updatePreview)", script)
        self.assertNotIn("fetch(", script)
        self.assertNotIn("XMLHttpRequest", script)

    def test_invalid_date_window_does_not_call_providers(self):
        with patch("webapp.SerpApiProvider") as provider_factory, patch(
            "webapp.search_multi_leg_itineraries"
        ) as search:
            response = self.client.post(
                "/search",
                data={"start_date": "2027-02-13", "end_date": "2027-01-20"},
            )

        self.assertEqual(400, response.status_code)
        self.assertIn(b"The end date must be on or after the start date.", response.data)
        provider_factory.assert_not_called()
        search.assert_not_called()

    def test_availability_links_include_the_specific_dates(self):
        links = _booking_links(
            {
                "leg1": {
                    "arrival_airport": "CDG",
                    "departure_date": "2027-01-24",
                },
                "leg2": {
                    "departure_airport": "HEL",
                    "departure_date": "2027-01-31",
                },
            },
            {
                "leg1_origin": "HYD",
                "leg1_destination": "PAR",
                "leg2_destination": "HYD",
            },
        )

        self.assertIn("HYD", links["leg1"])
        self.assertIn("2027-01-24", links["leg1"])
        self.assertIn("2027-01-31", links["leg2"])


if __name__ == "__main__":
    unittest.main()
