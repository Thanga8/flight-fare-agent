import unittest
from unittest.mock import patch

from test_postgres_integration import _test_url


class PostgreSQLTargetSafetyTests(unittest.TestCase):
    def test_accepts_only_loopback_test_database_urls(self):
        with patch.dict("os.environ", {"TEST_POSTGRES_URL": "postgresql://user:pass@127.0.0.1:5432/disposable_flight_fare_test"}):
            self.assertEqual(
                "postgresql://user:pass@127.0.0.1:5432/disposable_flight_fare_test",
                _test_url(),
            )

    def test_rejects_remote_database_even_when_name_looks_disposable(self):
        with patch.dict("os.environ", {"TEST_POSTGRES_URL": "postgresql://user:pass@db.example.test:5432/disposable_test"}):
            with self.assertRaisesRegex(unittest.SkipTest, "loopback"):
                _test_url()

    def test_rejects_loopback_database_without_disposable_name_prefix(self):
        with patch.dict("os.environ", {"TEST_POSTGRES_URL": "postgresql://user:pass@localhost:5432/production_test"}):
            with self.assertRaisesRegex(unittest.SkipTest, "start with"):
                _test_url()


if __name__ == "__main__":
    unittest.main()
