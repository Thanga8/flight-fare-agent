import unittest
import requests
from unittest.mock import patch
from flight_search.multi_leg import _resolve_airport_codes, _sample_dates, plan_multi_leg_usage, search_multi_leg_itineraries


def payload(depart, arrive, price=100):
    return {"best_flights": [{"price": price, "total_duration": 10, "flights": [
        {"departure_airport": {"id": depart}, "arrival_airport": {"id": arrive}}
    ]}]}


class Provider:
    def __init__(self): self.calls = []; self.combined_legs = []; self.one_way_queries = []
    def search_one_way(self, departure_id, arrival_id, outbound_date, cache_mode):
        self.calls.append(("one", cache_mode))
        self.one_way_queries.append((departure_id, arrival_id, outbound_date))
        if cache_mode == "cache": return payload(departure_id.split(",")[0], arrival_id.split(",")[0]) | {"_cache_hit": True}
        return payload("HYD", "CDG") if "HYD" in departure_id else payload("HEL", "HYD")
    def search_multi_city(self, legs, cache_mode):
        self.calls.append(("multi", cache_mode))
        self.combined_legs.append(legs)
        return payload("HYD", "HYD")


class MultiLegTests(unittest.TestCase):
    def run_search(self, budget, modes=("live", "live", "live"), limit=2):
        provider = Provider()
        with patch("flight_search.multi_leg.persist_multi_leg_search", return_value=1):
            report = search_multi_leg_itineraries(
                start_date="2027-01-01", end_date="2027-01-10", international_provider=provider,
                serpapi_budget=budget, leg1_origin="HYD", leg1_destination="PAR",
                leg2_origin="HEL", leg2_destination="HYD", leg1_cache_mode=modes[0],
                leg2_cache_mode=modes[1], combined_cache_mode=modes[2], combined_candidate_limit=limit,
            )
        return provider, report

    def test_zero_budget_never_calls_live_boundary(self):
        p, r = self.run_search(0)
        self.assertEqual(0, r["serpapi_calls"]); self.assertTrue(r["budget_limited"])
        self.assertFalse(p.calls)

    def test_one_budget_hard_cap_and_report(self):
        p, r = self.run_search(1)
        self.assertEqual(0, r["serpapi_calls"])
        self.assertEqual([], r["itineraries"])
        self.assertTrue(r["budget_limited"])
        self.assertIn("too small", r["incomplete_reason"])
        self.assertEqual(0, len([x for x in p.calls if x[1] == "live"]))

    def test_both_legs_cached_combined_live_is_capped(self):
        p, r = self.run_search(1, ("cache", "cache", "live"))
        self.assertEqual(1, r["serpapi_calls"]); self.assertTrue(r["budget_limited"])

    def test_one_cached_leg_allows_one_complete_pair_with_one_live_call(self):
        p, r = self.run_search(1, ("cache", "live", "cache"), 0)
        self.assertEqual(1, r["serpapi_calls"])
        self.assertEqual(1, r["valid_date_pairs"])
        self.assertTrue(all(item["leg1"].get("price") is not None and item["leg2"].get("price") is not None for item in r["itineraries"]))

    def test_one_cached_leg_with_zero_budget_produces_no_partial_itinerary(self):
        p, r = self.run_search(0, ("cache", "live", "cache"), 0)
        self.assertEqual(0, r["serpapi_calls"])
        self.assertEqual([], r["itineraries"])
        self.assertTrue(r["budget_limited"])

    def test_sampling_edges_and_inclusive_dates(self):
        first = _sample_dates("2027-01-01", "2027-01-10", 3)
        rotated = _sample_dates("2027-01-01", "2027-01-10", 3, 1)
        self.assertEqual(["2027-01-01", "2027-01-10"], [first[0], first[-1]])
        self.assertNotEqual(first, rotated)
        self.assertEqual([], _sample_dates("2027-01-01", "2027-01-01", 0))
        with self.assertRaises(ValueError): _sample_dates("2027-02-01", "2027-01-01", 2)
        with self.assertRaises(ValueError): _sample_dates("bad", "2027-01-01", 2)

    def test_live_usage_never_exceeds_budget_across_cache_modes(self):
        for modes in (("live", "cache", "live"), ("live", "live", "live"), ("cache", "cache", "cache")):
            p, r = self.run_search(2, modes)
            self.assertLessEqual(r["serpapi_calls"], 2)
            self.assertLessEqual(sum(m == "live" for _, m in p.calls), 2)

    def test_each_itinerary_contains_two_priced_fares(self):
        _, r = self.run_search(8, ("live", "live", "cache"), 0)
        self.assertTrue(r["itineraries"])
        for item in r["itineraries"]:
            self.assertIsNotNone(item["leg1"]["price"])
            self.assertIsNotNone(item["leg2"]["price"])

    def test_combined_search_uses_selected_exact_endpoints(self):
        p, r = self.run_search(8, ("live", "live", "live"), 1)
        self.assertTrue(r["itineraries"])
        chosen = r["itineraries"][0]
        legs = p.combined_legs[0]
        self.assertEqual(chosen["leg1"]["departure_airport"], legs[0]["departure_id"])
        self.assertEqual(chosen["leg1"]["arrival_airport"], legs[0]["arrival_id"])
        self.assertEqual(chosen["leg2"]["departure_airport"], legs[1]["departure_id"])
        self.assertEqual(chosen["leg2"]["arrival_airport"], legs[1]["arrival_id"])

    def test_requests_default_adapter_does_not_retry(self):
        session = requests.Session()
        adapter = session.get_adapter("https://serpapi.com")
        self.assertEqual(0, adapter.max_retries.total)

    def test_remaining_budget_goes_to_combined_only_after_complete_pair(self):
        p, r = self.run_search(3, ("live", "live", "live"), 2)
        self.assertEqual(3, r["serpapi_calls"])
        self.assertEqual(2, sum(mode == "live" for _, mode in p.calls[:2]))
        self.assertEqual(1, sum(kind == "multi" and mode == "live" for kind, mode in p.calls))
        self.assertTrue(r["budget_limited"])

    def test_gap_and_airports_preserved(self):
        _, r = self.run_search(20, ("live", "live", "cache"), 0)
        for item in r["itineraries"]:
            from datetime import date
            self.assertEqual(7, (date.fromisoformat(item["leg2"]["departure_date"]) - date.fromisoformat(item["leg1"]["departure_date"])).days)
            self.assertEqual("HYD", item["leg1"]["departure_airport"])
            self.assertEqual("HYD", item["leg2"]["arrival_airport"])

    def test_usage_plan_inclusive_pairs_and_single_pair(self):
        plan = plan_multi_leg_usage("2027-02-03", "2027-03-15", 7, 100)
        self.assertEqual(34, plan["valid_date_pairs"])
        self.assertEqual(34, plan["covered_date_pairs"])
        one = plan_multi_leg_usage("2027-02-03", "2027-02-10", 7, 2, combined_candidate_limit=0)
        self.assertEqual(1, one["valid_date_pairs"])
        leap = plan_multi_leg_usage("2024-02-28", "2024-03-07", 2, 20)
        self.assertEqual(7, leap["valid_date_pairs"])

    def test_usage_plan_short_window_reverse_dates_and_invalid_inputs(self):
        short = plan_multi_leg_usage("2027-02-03", "2027-02-09", 7, 10)
        self.assertEqual(0, short["valid_date_pairs"])
        with self.assertRaisesRegex(ValueError, "on or after"):
            plan_multi_leg_usage("2027-02-11", "2027-02-10", 1, 10)
        for args in (("", "2027-02-10", 1, 2), ("bad", "2027-02-10", 1, 2)):
            with self.assertRaises(ValueError):
                plan_multi_leg_usage(*args)

    def test_usage_plan_independent_cache_modes_and_budget(self):
        args = ("2027-02-03", "2027-02-12", 7, 4)
        both = plan_multi_leg_usage(*args)
        self.assertEqual((3, 2), (both["valid_date_pairs"], both["covered_date_pairs"]))
        self.assertEqual((2, 2), (both["leg1_live_requests"], both["leg2_live_requests"]))
        leg1_only = plan_multi_leg_usage(*args, leg2_cache_mode="cache", combined_candidate_limit=0)
        self.assertEqual((3, 3, 0), (leg1_only["covered_date_pairs"], leg1_only["leg1_live_requests"], leg1_only["leg2_live_requests"]))
        leg2_only = plan_multi_leg_usage(*args, leg1_cache_mode="cache", combined_candidate_limit=0)
        self.assertEqual((3, 0, 3), (leg2_only["covered_date_pairs"], leg2_only["leg1_live_requests"], leg2_only["leg2_live_requests"]))
        cache_only = plan_multi_leg_usage(*args, leg1_cache_mode="cache", leg2_cache_mode="cache")
        self.assertEqual(3, cache_only["covered_date_pairs"])
        self.assertEqual(0, cache_only["leg_live_requests"])
        self.assertFalse(both["full_date_coverage"])
        self.assertEqual(0, plan_multi_leg_usage(*args[:3], 0)["covered_date_pairs"])

    def test_combined_calls_are_candidate_and_budget_limited_maxima(self):
        args = ("2027-02-03", "2027-02-12", 7, 7)
        no_candidates = plan_multi_leg_usage(*args, combined_candidate_limit=0)
        self.assertEqual(0, no_candidates["configured_total_live_requests_max"] - no_candidates["leg_live_requests"])
        cache_combined = plan_multi_leg_usage(*args, combined_cache_mode="cache", combined_candidate_limit=5)
        self.assertEqual(0, cache_combined["exhaustive_combined_live_requests_max"])
        live_combined = plan_multi_leg_usage(*args, combined_candidate_limit=5)
        self.assertEqual(5, live_combined["combined_live_requests_max"])
        self.assertEqual(5, live_combined["exhaustive_combined_live_requests_max"])
        self.assertLessEqual(live_combined["configured_total_live_requests_max"], 7)

    def test_combined_reservation_keeps_one_pair_for_small_budgets(self):
        plan = plan_multi_leg_usage("2027-01-01", "2027-01-10", 7, 3, combined_candidate_limit=2)
        self.assertEqual(1, plan["covered_date_pairs"])
        self.assertEqual(1, plan["combined_live_requests_max"])
        self.assertEqual(3, plan["configured_total_live_requests_max"])

    def test_airport_group_remains_one_provider_request_per_leg(self):
        provider = Provider()
        with patch("flight_search.multi_leg.persist_multi_leg_search", return_value=1):
            search_multi_leg_itineraries(
                start_date="2027-01-01", end_date="2027-01-08", international_provider=provider,
                serpapi_budget=2, leg1_origin="PAR", leg1_destination="HYD",
                leg2_origin="HEL", leg2_destination="HYD", combined_cache_mode="cache",
                combined_candidate_limit=0,
            )
        group_codes = _resolve_airport_codes("PAR")
        self.assertGreater(len(group_codes), 1)
        self.assertEqual(",".join(group_codes), provider.one_way_queries[0][0])
        self.assertEqual(2, len(provider.one_way_queries))


if __name__ == "__main__": unittest.main()
