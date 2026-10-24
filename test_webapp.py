import unittest
from unittest.mock import patch

from webapp import _booking_links, app


class WebAppTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_landing_page_loads_without_searching(self):
        response = self.client.get("/")

        self.assertEqual(200, response.status_code)
        self.assertIn(b"Search possible itineraries", response.data)
        self.assertIn(b'name="viewport"', response.data)

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
