import unittest
from unittest.mock import patch

from flight_search.multi_leg import search_multi_leg_itineraries
from webapp import app


class InsightProvider:
    def search_one_way(self, departure_id, arrival_id, outbound_date, cache_mode):
        origin = departure_id.split(",")[0]
        destination = arrival_id.split(",")[0]
        insight = {
            "typical_price_range": [12000, 18000],
            "lowest_price": 11500,
            "price_level": "low",
            "price_history": [[1800000000, 12000], [1800086400, 12500]],
        }
        return {
            "best_flights": [{
                "price": 12000,
                "flights": [{
                    "departure_airport": {"id": origin},
                    "arrival_airport": {"id": destination},
                }],
            }],
            "price_insights": insight,
            "_source_fetched_at": "2027-01-01T00:00:00Z",
        }

    def search_multi_city(self, legs, cache_mode):
        return {"error": "CACHE_MISS: test"}


class SearchInsightReportTests(unittest.TestCase):
    def test_original_provider_insights_are_exposed_per_leg_and_date(self):
        with patch("flight_search.multi_leg.persist_multi_leg_search", return_value=1):
            report = search_multi_leg_itineraries(
                start_date="2027-01-01", end_date="2027-01-08",
                international_provider=InsightProvider(), serpapi_budget=2,
                leg1_origin="HYD", leg1_destination="CDG",
                leg2_origin="HEL", leg2_destination="HYD",
                nights_between_departures=7,
                leg1_cache_mode="live", leg2_cache_mode="live",
                combined_cache_mode="cache", combined_candidate_limit=0,
            )

        self.assertEqual(2, len(report["google_insights"]))
        self.assertEqual(("HYD", "CDG", "2027-01-01"), (
            report["google_insights"][0]["departure_id"],
            report["google_insights"][0]["arrival_id"],
            report["google_insights"][0]["departure_date"],
        ))
        self.assertEqual("2027-01-08", report["google_insights"][1]["departure_date"])
        self.assertEqual([12000, 18000], report["google_insights"][0]["price_insights"]["typical_price_range"])

    def test_failed_and_budget_skipped_responses_keep_their_status(self):
        class Provider:
            def search_one_way(self, departure_id, arrival_id, outbound_date, cache_mode):
                if departure_id == "HYD":
                    return {"error": "provider unavailable"}
                return {"_budget_exhausted": True, "error": "budget exhausted"}

            def search_multi_city(self, legs, cache_mode):
                return {"error": "not used"}

        with patch("flight_search.multi_leg.persist_multi_leg_search", return_value=1):
            report = search_multi_leg_itineraries(
                start_date="2027-01-01", end_date="2027-01-08",
                international_provider=Provider(), serpapi_budget=2,
                leg1_origin="HYD", leg1_destination="CDG",
                leg2_origin="HEL", leg2_destination="HYD",
                nights_between_departures=7,
                leg1_cache_mode="live", leg2_cache_mode="live",
                combined_cache_mode="cache", combined_candidate_limit=0,
            )

        self.assertEqual(["failed", "budget_skipped"], [
            item["status"] for item in report["google_insights"]
        ])


class ResultsInsightRenderingTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.report = {
            "itineraries": [], "nights_between_departures": 7,
            "budget_limited": False, "leg1_dates_searched": 1,
            "leg2_dates_searched": 1, "leg1_origin": "HYD",
            "leg1_destination": "CDG", "leg2_origin": "HEL",
            "leg2_destination": "HYD", "serpapi_calls": 2,
            "serpapi_budget": 12, "leg1_cache_mode": "live",
            "leg2_cache_mode": "live", "leg1_cache_hits": 0,
            "leg2_cache_hits": 0, "combined_cache_mode": "cache",
            "combined_cache_hits": 0, "google_insights": [],
        }

    def render_insights(self, *insights):
        self.report["google_insights"] = list(insights)
        with patch.dict("os.environ", {"SERPAPI_API_KEY": "mock-key"}), \
             patch("webapp.SerpApiProvider"), \
             patch("webapp.search_multi_leg_itineraries", return_value=self.report):
            return self.client.post("/search", data={
                "start_date": "2027-01-01", "end_date": "2027-01-20",
                "nights_between_departures": "7", "serpapi_budget": "12",
                "combined_candidate_limit": "0", "leg1_origin": "HYD",
                "leg1_destination": "CDG", "leg2_origin": "HEL",
                "leg2_destination": "HYD", "leg1_cache_mode": "live",
                "leg2_cache_mode": "live", "combined_cache_mode": "cache",
            })

    @staticmethod
    def insight(status="present", **values):
        return {
            "leg_number": 1, "departure_id": "HYD", "arrival_id": "CDG",
            "departure_date": "2027-01-01", "currency": "INR",
            "data_source": "live", "status": status, **values,
        }

    def test_valid_range_lowest_level_and_historical_points_render(self):
        response = self.render_insights(self.insight(price_insights={
            "typical_price_range": [12345, 23456], "lowest_price": 11800,
            "price_level": "low", "price_history": [[1800000000, 13000]],
        }))
        self.assertEqual(200, response.status_code)
        self.assertIn(b"Google Flights Insights", response.data)
        self.assertIn("HYD \u2192 CDG \u00b7 2027-01-01".encode(), response.data)
        self.assertIn("Typical fare range:</strong> 12345 \u2013 23456 INR".encode(), response.data)
        self.assertIn(b"Lowest returned price: 11800 INR", response.data)
        self.assertIn(b"Price level: low", response.data)
        self.assertIn(b"Google-provided historical price points", response.data)
        self.assertIn(b"13000 INR", response.data)

    def test_absent_null_and_empty_insights_are_distinguished_from_range(self):
        absent = self.render_insights(self.insight(status="absent"))
        self.assertIn(b"This response did not include Google price insights.", absent.data)
        self.assertNotIn(b"Typical fare range not provided", absent.data)

        for raw in (None, {}, []):
            with self.subTest(raw=raw):
                response = self.render_insights(self.insight(price_insights=raw))
                self.assertIn(b"The provider returned no usable insights.", response.data)
                self.assertNotIn(b"Typical fare range not provided", response.data)

    def test_missing_or_invalid_typical_range_is_never_invented(self):
        invalid_ranges = (None, "INR 100-200", [200, 100], ["100", 200], [True, 200], [float("inf"), 200])
        for value in invalid_ranges:
            with self.subTest(value=value):
                insights = {"lowest_price": 75, "price_level": "low"}
                if value is not None:
                    insights["typical_price_range"] = value
                response = self.render_insights(self.insight(price_insights=insights))
                self.assertIn(b"Typical fare range not provided.", response.data)
                self.assertIn(b"Lowest returned price: 75 INR", response.data)
                self.assertNotIn(b"Typical fare range:</strong> 75", response.data)

    def test_failed_and_budget_skipped_searches_are_not_called_missing_insights(self):
        for status, expected in (
            ("failed", b"This search failed, so no Google insight response is available."),
            ("budget_skipped", b"This search was skipped because the SerpApi budget was exhausted."),
        ):
            with self.subTest(status=status):
                response = self.render_insights(self.insight(status=status, error="example"))
                self.assertIn(expected, response.data)
                self.assertNotIn(b"This response did not include Google price insights.", response.data)
                self.assertNotIn(b"Typical fare range not provided.", response.data)


if __name__ == "__main__":
    unittest.main()
