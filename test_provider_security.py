import unittest
from unittest.mock import Mock

import requests

from flight_search.providers.flightapi_provider import FlightApiProvider


class FlightApiSecurityTests(unittest.TestCase):
    def test_request_exception_does_not_expose_api_key_embedded_in_url(self):
        secret = "test-key-never-log-this"
        provider = FlightApiProvider(api_key=secret)
        provider.session = Mock()
        provider.session.get.side_effect = requests.Timeout(
            f"request to https://api.flightapi.io/roundtrip/{secret}/HYD/SVO timed out")
        with self.assertRaisesRegex(RuntimeError, "response details were suppressed") as raised:
            provider.search_round_trip("HYD", "SVO", "2027-01-20", "2027-01-25")
        self.assertNotIn(secret, str(raised.exception))

    def test_invalid_json_and_non_object_responses_are_rejected_safely(self):
        provider = FlightApiProvider(api_key="test-only")
        provider.session = Mock()
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.side_effect = ValueError("bad JSON")
        provider.session.get.return_value = response
        with self.assertRaisesRegex(RuntimeError, "invalid JSON"):
            provider.search_round_trip("HYD", "SVO", "2027-01-20", "2027-01-25")
        response.json.side_effect = None
        response.json.return_value = []
        with self.assertRaisesRegex(RuntimeError, "unexpected response format"):
            provider.search_round_trip("HYD", "SVO", "2027-01-20", "2027-01-25")


if __name__ == "__main__":
    unittest.main()
