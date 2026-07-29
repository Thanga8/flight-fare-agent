import unittest
from unittest.mock import Mock, patch

from flight_search.planner import create_historical_initial_search_plan
from search_history import get_historical_search_priorities


def candidate(arrival_airport, departure_date, average_price=None, count=0):
    return {
        "departure_airport": "HYD",
        "arrival_airport": arrival_airport,
        "departure_date": departure_date,
        "return_date": "2027-01-26",
        "trip_days": 5,
        "historical_comparison_level": "exact_dates" if count else "none",
        "historical_observation_count": count,
        "historical_average_price": average_price,
        "historical_recency_days": 1 if count else None,
    }


class HistoricalPrioritizationTests(unittest.TestCase):
    def test_history_gets_priority_and_exploration_is_retained(self):
        plan = create_historical_initial_search_plan(
            [
                candidate("SVO", "2027-01-20", 50000, 5),
                candidate("DME", "2027-01-21", 70000, 5),
                candidate("VKO", "2027-01-22"),
            ],
            max_api_calls=2,
        )

        self.assertEqual(2, len(plan))
        self.assertEqual("SVO", plan[0]["arrival_airport"])
        self.assertEqual("historical", plan[0]["planning_priority"])
        self.assertEqual("VKO", plan[1]["arrival_airport"])
        self.assertEqual("exploration", plan[1]["planning_priority"])

    def test_budget_and_candidate_uniqueness_are_preserved(self):
        candidates = [
            candidate("SVO", "2027-01-20", 50000, 3),
            candidate("DME", "2027-01-21", 60000, 2),
        ]
        plan = create_historical_initial_search_plan(candidates, max_api_calls=10)

        keys = {
            (item["departure_airport"], item["arrival_airport"], item["departure_date"], item["return_date"])
            for item in plan
        }
        self.assertEqual(2, len(plan))
        self.assertEqual(2, len(keys))

    def test_one_call_is_exploration_when_history_is_insufficient(self):
        plan = create_historical_initial_search_plan(
            [candidate("VKO", "2027-01-22")],
            max_api_calls=1,
        )

        self.assertEqual("exploration", plan[0]["planning_priority"])

    def test_no_history_uses_only_exploration_candidates(self):
        plan = create_historical_initial_search_plan(
            [
                candidate("SVO", "2027-01-20"),
                candidate("VKO", "2027-01-22"),
            ],
            max_api_calls=2,
        )

        self.assertEqual(2, len(plan))
        self.assertTrue(
            all(item["planning_priority"] == "exploration" for item in plan)
        )

    def test_history_helper_prefers_exact_dates_and_calculates_recency(self):
        connection = Mock()
        connection.execute.return_value.fetchall.return_value = [
            {
                "departure_airport": "HYD",
                "arrival_airport": "SVO",
                "departure_date": "2027-01-20",
                "return_date": "2027-01-25",
                "price": 50000,
                "searched_at": "2026-07-20 10:00:00",
            },
            {
                "departure_airport": "HYD",
                "arrival_airport": "SVO",
                "departure_date": "2027-01-21",
                "return_date": "2027-01-26",
                "price": 60000,
                "searched_at": "2026-07-01 10:00:00",
            },
        ]

        with patch("search_history.get_connection", return_value=connection):
            summaries = get_historical_search_priorities(
                "HYD",
                "MOW",
                [{
                    "departure_airport": "HYD",
                    "arrival_airport": "SVO",
                    "departure_date": "2027-01-20",
                    "return_date": "2027-01-25",
                    "trip_days": 5,
                }],
                reference_date="2026-07-29",
            )

        self.assertEqual("exact_dates", summaries[0]["historical_comparison_level"])
        self.assertEqual(1, summaries[0]["historical_observation_count"])
        self.assertEqual(50000, summaries[0]["historical_low_price"])
        self.assertEqual(9, summaries[0]["historical_recency_days"])
        connection.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
