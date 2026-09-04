import unittest

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
        response = self.client.post(
            "/search",
            data={"start_date": "2027-02-13", "end_date": "2027-01-20"},
        )

        self.assertEqual(400, response.status_code)
        self.assertIn(b"end date must be after", response.data)

    def test_availability_links_include_the_specific_dates(self):
        links = _booking_links(
            {
                "international_arrival_airport": "SVO",
                "international": {
                    "departure_date": "2027-01-24",
                    "return_date": "2027-01-30",
                },
                "domestic_departure_date": "2027-01-25",
                "domestic_return_date": "2027-01-29",
            }
        )

        self.assertIn("HYD", links["international"])
        self.assertIn("2027-01-25", links["domestic"])


if __name__ == "__main__":
    unittest.main()
