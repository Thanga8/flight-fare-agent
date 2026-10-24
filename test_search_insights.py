import unittest
from unittest.mock import patch

from flight_search.multi_leg import search_multi_leg_itineraries
from webapp import _plot_points, app


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


class PlotPointsTests(unittest.TestCase):
    def test_chart_includes_labeled_date_and_fare_axis_ticks(self):
        chart = _plot_points([
            {"timestamp": 1790899200, "price": 37000, "label": "first observation"},
            {"timestamp": 1791504000, "price": 63000, "label": "second observation"},
            {"timestamp": 1792108800, "price": 42000, "label": "third observation"},
        ])

        self.assertEqual(3, len(chart["x_ticks"]))
        self.assertTrue(all(tick["label"] for tick in chart["x_ticks"]))
        self.assertEqual(5, len(chart["y_ticks"]))
        self.assertTrue(all(tick["label"] for tick in chart["y_ticks"]))
        self.assertTrue(all(76 <= point["x"] <= 580 for point in chart["points"]))
        self.assertTrue(all(24 <= point["y"] <= 190 for point in chart["points"]))
        self.assertIn("37000", [tick["label"] for tick in chart["y_ticks"]])
        self.assertIn("63000", [tick["label"] for tick in chart["y_ticks"]])


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

    def test_cache_miss_and_stale_cache_metadata_are_distinct_without_live_fallback(self):
        class CacheOnlyProvider:
            def __init__(self):
                self.modes = []

            def search_one_way(self, departure_id, arrival_id, outbound_date, cache_mode):
                self.modes.append(cache_mode)
                if departure_id == "HYD":
                    return {
                        "error": "CACHE_MISS: no cached result",
                        "_cache_status": "miss", "_cache_hit": False,
                    }
                return {
                    "error": "STALE_CACHE: older than 24 hours",
                    "_cache_status": "stale", "_cache_hit": False,
                }

            def search_multi_city(self, legs, cache_mode):
                raise AssertionError("No combined search was requested")

        provider = CacheOnlyProvider()
        with patch("flight_search.multi_leg.persist_multi_leg_search", return_value=1):
            report = search_multi_leg_itineraries(
                start_date="2027-01-01", end_date="2027-01-08",
                international_provider=provider, serpapi_budget=0,
                leg1_origin="HYD", leg1_destination="CDG",
                leg2_origin="HEL", leg2_destination="HYD",
                nights_between_departures=7,
                leg1_cache_mode="cache", leg2_cache_mode="cache",
                combined_cache_mode="cache", combined_candidate_limit=0,
            )

        self.assertEqual(["cache", "cache"], provider.modes)
        self.assertEqual(["cache_miss", "stale_cache"], [
            item["status"] for item in report["google_insights"]
        ])
        self.assertEqual(0, report["serpapi_calls"])


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

    def test_cache_failures_have_separate_messages_from_provider_failures(self):
        cases = (
            ("cache_miss", b"No cached response was available. No live search was made"),
            ("stale_cache", b"The cached response was stale and rejected. No live search fallback was made"),
            ("cache_error", b"The cache could not provide a usable response. No live search was made"),
            ("failed", b"This search failed, so no Google insight response is available."),
        )
        for status, expected in cases:
            with self.subTest(status=status):
                response = self.render_insights(self.insight(status=status, error="example"))
                self.assertIn(expected, response.data)
                if status != "failed":
                    self.assertNotIn(b"This search failed, so no Google insight response is available.", response.data)


if __name__ == "__main__":
    unittest.main()
