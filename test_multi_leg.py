import unittest

from flight_search.multi_leg import (
    create_multi_leg_candidates,
    search_multi_leg_itineraries,
)


class FakeDomesticProvider:
    def __init__(self):
        self.calls = []

    def search_round_trip(self, **kwargs):
        self.calls.append(kwargs)
        day = int(kwargs["outbound_date"][-2:])
        return {"success": True, "data": [{"price": 6000 + day, "airline": "DP"}]}

    @staticmethod
    def extract_cheapest_offer(payload):
        offer = payload["data"][0]
        return {"price": offer["price"], "currency": "RUB", "airline": offer["airline"]}


class FakeInternationalProvider:
    def __init__(self, late_arrival=False):
        self.calls = []
        self.late_arrival = late_arrival

    def search_round_trip(self, **kwargs):
        self.calls.append(kwargs)
        arrival_day = kwargs["outbound_date"] if not self.late_arrival else kwargs["return_date"]
        return {
            "best_flights": [{
                "price": 50000,
                "total_duration": 600,
                "flights": [{"arrival_airport": {"time": f"{arrival_day}T20:00:00"}}],
            }]
        }


def historical_priorities(*, date_combinations, **_):
    """Make SVO historically strongest while preserving an exploration option."""
    return [
        {
            **candidate,
            "historical_comparison_level": "exact_dates",
            "historical_observation_count": 5 if candidate["arrival_airport"] == "SVO" else 1,
            "historical_average_price": 50000 if candidate["arrival_airport"] == "SVO" else 90000,
            "historical_recency_days": 1,
        }
        for candidate in date_combinations
    ]


class MultiLegTests(unittest.TestCase):
    def test_candidates_enforce_buffers_and_four_day_domestic_trip(self):
        candidates = create_multi_leg_candidates("2027-01-20", "2027-02-13")
        first = candidates[0]
        last = candidates[-1]

        self.assertEqual("2027-01-21", first["domestic_departure_date"])
        self.assertEqual("2027-01-25", first["domestic_return_date"])
        self.assertEqual("2027-01-20", first["international_arrival_target"])
        self.assertEqual(["2027-01-20"], first["international_outbound_dates"])
        self.assertEqual("2027-01-26", first["international_return_date"])
        self.assertEqual("2027-02-08", last["domestic_departure_date"])

    def test_budgets_conversion_and_combined_ranking(self):
        domestic = FakeDomesticProvider()
        international = FakeInternationalProvider()
        report = search_multi_leg_itineraries(
            start_date="2027-01-20",
            end_date="2027-02-13",
            domestic_provider=domestic,
            international_provider=international,
            travelpayouts_budget=3,
            serpapi_budget=2,
            historical_priority_provider=historical_priorities,
        )

        self.assertEqual(3, report["travelpayouts_calls"])
        self.assertEqual(2, report["serpapi_calls"])
        self.assertLessEqual(len(domestic.calls), 3)
        self.assertLessEqual(len(international.calls), 2)
        self.assertEqual(2, len(report["itineraries"]))
        self.assertEqual(1.16, report["rub_to_inr"])
        self.assertGreater(report["itineraries"][0]["total_price_inr"], 50000)

    def test_late_moscow_arrival_is_excluded(self):
        report = search_multi_leg_itineraries(
            start_date="2027-01-20",
            end_date="2027-02-13",
            domestic_provider=FakeDomesticProvider(),
            international_provider=FakeInternationalProvider(late_arrival=True),
            travelpayouts_budget=1,
            serpapi_budget=1,
            historical_priority_provider=historical_priorities,
        )

        self.assertEqual([], report["itineraries"])

    def test_historical_priority_selects_svo_before_other_airports(self):
        report = search_multi_leg_itineraries(
            start_date="2027-01-20",
            end_date="2027-02-13",
            domestic_provider=FakeDomesticProvider(),
            international_provider=FakeInternationalProvider(),
            travelpayouts_budget=2,
            serpapi_budget=3,
            historical_priority_provider=historical_priorities,
        )

        airports = [item["international_arrival_airport"] for item in report["itineraries"]]
        self.assertEqual("SVO", airports[0])


if __name__ == "__main__":
    unittest.main()
