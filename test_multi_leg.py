import unittest
from flight_search.multi_leg import _sample_dates, search_multi_leg_itineraries


def payload(depart, arrive, price=100):
    return {"best_flights": [{"price": price, "total_duration": 10, "flights": [
        {"departure_airport": {"id": depart}, "arrival_airport": {"id": arrive}}
    ]}]}


class Provider:
    def __init__(self): self.calls = []
    def search_one_way(self, departure_id, arrival_id, outbound_date, cache_mode):
        self.calls.append(("one", cache_mode))
        if cache_mode == "cache": return payload(departure_id.split(",")[0], arrival_id.split(",")[0]) | {"_cache_hit": True}
        return payload("HYD", "CDG") if "HYD" in departure_id else payload("HEL", "HYD")
    def search_multi_city(self, legs, cache_mode):
        self.calls.append(("multi", cache_mode))
        return payload("HYD", "HYD")


class MultiLegTests(unittest.TestCase):
    def run_search(self, budget, modes=("live", "live", "live"), limit=2):
        provider = Provider()
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
        self.assertEqual(1, r["serpapi_calls"]); self.assertLessEqual(len([x for x in p.calls if x[1] == "live"]), 1)

    def test_both_legs_cached_combined_live_is_capped(self):
        p, r = self.run_search(1, ("cache", "cache", "live"))
        self.assertEqual(1, r["serpapi_calls"]); self.assertTrue(r["budget_limited"])

    def test_sampling_edges_and_inclusive_dates(self):
        self.assertEqual(["2027-01-01", "2027-01-05", "2027-01-10"], _sample_dates("2027-01-01", "2027-01-10", 3))
        self.assertEqual([], _sample_dates("2027-01-01", "2027-01-01", 0))
        with self.assertRaises(ValueError): _sample_dates("2027-02-01", "2027-01-01", 2)
        with self.assertRaises(ValueError): _sample_dates("bad", "2027-01-01", 2)

    def test_live_usage_never_exceeds_budget_across_cache_modes(self):
        for modes in (("live", "cache", "live"), ("live", "live", "live"), ("cache", "cache", "cache")):
            p, r = self.run_search(2, modes)
            self.assertLessEqual(r["serpapi_calls"], 2)
            self.assertLessEqual(sum(m == "live" for _, m in p.calls), 2)

    def test_gap_and_airports_preserved(self):
        _, r = self.run_search(20, ("live", "live", "cache"), 0)
        for item in r["itineraries"]:
            from datetime import date
            self.assertEqual(7, (date.fromisoformat(item["leg2"]["departure_date"]) - date.fromisoformat(item["leg1"]["departure_date"])).days)
            self.assertEqual("HYD", item["leg1"]["departure_airport"])
            self.assertEqual("HYD", item["leg2"]["arrival_airport"])


if __name__ == "__main__": unittest.main()
