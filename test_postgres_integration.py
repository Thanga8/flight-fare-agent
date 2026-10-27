"""Destructive integration tests for an explicitly disposable PostgreSQL database.

Run only with TEST_POSTGRES_URL pointing to a database whose name contains
"test" or "disposable". The suite refuses DATABASE_URL fallback and checks
the server identity and public table allowlist before clearing app test data.
"""
import os
import re
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from flight_search.database import db


def _test_url():
    url = os.getenv("TEST_POSTGRES_URL", "").strip()
    if not url:
        raise unittest.SkipTest("Set TEST_POSTGRES_URL to an explicitly disposable PostgreSQL database.")
    if not re.search(r"(?:/|\b)(?:test|disposable)[\w-]*(?:\?|$)", url, re.IGNORECASE):
        raise unittest.SkipTest("TEST_POSTGRES_URL database name must include 'test' or 'disposable'.")
    return url


class PostgreSQLIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.url = _test_url()
        import psycopg2
        from psycopg2.extras import DictCursor
        try:
            connection = psycopg2.connect(cls.url, connect_timeout=5, cursor_factory=DictCursor,
                                          application_name="flight-fare-agent-disposable-tests")
            identity = connection.cursor()
            identity.execute("SELECT current_database(), current_user, inet_server_addr()::text")
            dbname, _user, _address = identity.fetchone()
            if not re.search(r"(?:test|disposable)", dbname, re.IGNORECASE):
                raise RuntimeError("Refusing PostgreSQL integration tests: server database name is not disposable.")
            identity.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'")
            tables = [row[0] for row in identity.fetchall()]
            from flight_search.database.migrate_sqlite_to_postgres import TABLES
            known_app_tables = set(TABLES)
            unexpected_tables = set(tables) - known_app_tables
            if unexpected_tables:
                raise RuntimeError("Refusing PostgreSQL integration tests: public schema contains unexpected tables.")
            if tables:
                quoted = ",".join('"' + name.replace('"', '""') + '"' for name in tables)
                identity.execute(f"TRUNCATE TABLE {quoted} RESTART IDENTITY CASCADE")
                connection.commit()
            connection.close()
        except Exception as exc:
            try:
                connection.close()
            except Exception:
                pass
            if isinstance(exc, RuntimeError) and str(exc).startswith("Refusing PostgreSQL integration tests"):
                raise
            raise RuntimeError("Could not safely verify TEST_POSTGRES_URL; integration database was not modified.") from None
        cls._db_url_patch = patch.object(db, "DATABASE_URL", cls.url)
        cls._db_url_patch.start()
        db.initialize_database()

    def setUp(self):
        connection = db.get_connection()
        try:
            tables = [row[0] for row in connection.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname='public'").fetchall()]
            if tables:
                quoted = ",".join('"' + name.replace('"', '""') + '"' for name in tables)
                connection.execute(f"TRUNCATE TABLE {quoted} RESTART IDENTITY CASCADE")
                connection.commit()
        finally:
            connection.close()

    def create_monitor_job(self, name="Disposable integration"):
        return db.save_monitor_job({
            "name": name, "enabled": 1, "start_date": "2027-01-01", "end_date": "2027-01-20",
            "nights": 5, "leg1_origin": "HYD", "leg1_destination": "MOW",
            "leg2_origin": "MOW", "leg2_destination": "HYD", "interval_days": 2,
            "timezone": "Asia/Kolkata", "api_budget": 2, "notify_telegram": 0,
            "next_run_at": None,
        })

    @classmethod
    def tearDownClass(cls):
        try:
            connection = db.get_connection()
            try:
                tables = [row[0] for row in connection.execute(
                    "SELECT tablename FROM pg_tables WHERE schemaname='public'").fetchall()]
                from flight_search.database.migrate_sqlite_to_postgres import TABLES
                unexpected = set(tables) - set(TABLES)
                if unexpected:
                    raise RuntimeError("Refusing integration cleanup: unexpected public tables were found.")
                if tables:
                    quoted = ",".join('"' + name.replace('"', '""') + '"' for name in tables)
                    connection.execute(f"TRUNCATE TABLE {quoted} RESTART IDENTITY CASCADE")
                    connection.commit()
            finally:
                connection.close()
        finally:
            cls._db_url_patch.stop()

    def test_schema_search_multi_leg_and_monitor_lifecycle(self):
        run_id = db.create_search_run("HYD", "MOW", "2027-01-01", "2027-02-01", 5, 6, 4)
        flight_id = db.save_flight_result(run_id, {
            "departure_airport": "HYD", "arrival_airport": "MOW", "departure_date": "2027-01-10",
            "return_date": "2027-01-15", "price": 42000, "currency": "INR",
        })
        self.assertGreater(flight_id, 0)
        multi_id = db.persist_multi_leg_search(
            run={"start_date": "2027-01-01", "end_date": "2027-01-20", "nights": 7,
                 "leg1_origin": "HYD", "leg1_destination": "MOW", "leg2_origin": "MOW", "leg2_destination": "HYD",
                 "leg1_cache_mode": "cache", "leg2_cache_mode": "cache", "combined_cache_mode": "cache",
                 "serpapi_budget": 0, "serpapi_calls": 0, "budget_limited": False, "statistics": {}},
            fares=[], outcomes=[], comparisons=[])
        self.assertGreater(multi_id, 0)
        job = self.create_monitor_job()
        claimed = db.claim_monitor_run(job["id"])
        self.assertIsNotNone(claimed)
        db.finish_monitor_run(claimed, "failed", {"serpapi_calls": 0, "serpapi_budget": 2}, error="mock failure")
        self.assertEqual("failed", db.list_monitor_runs(job["id"])[0]["status"])

    def test_concurrent_claiming_only_creates_one_run(self):
        job = self.create_monitor_job()
        with ThreadPoolExecutor(max_workers=8) as pool:
            claims = list(pool.map(lambda _i: db.claim_monitor_run(job["id"]), range(8)))
        self.assertEqual(1, sum(claim is not None for claim in claims))

    def test_interrupted_run_recovery_charges_upper_bound_and_holds_retry(self):
        job = self.create_monitor_job()
        claim = db.claim_monitor_run(job["id"])
        connection = db.get_connection()
        try:
            with connection:
                connection.execute("UPDATE fare_monitor_runs SET started_at=? WHERE id=?",
                                   ("2000-01-01T00:00:00+00:00", claim["run_id"]))
        finally:
            connection.close()
        self.assertIsNone(db.claim_monitor_run(job["id"], due_only=True))
        run = db.list_monitor_runs(job["id"])[0]
        self.assertEqual("upper_bound", run["accounting_status"])
        self.assertEqual(job["api_budget"], run["serpapi_calls"])

    def test_populated_legacy_migration_and_sequence_preservation(self):
        from flight_search.database.migrate_sqlite_to_postgres import migrate
        with tempfile.TemporaryDirectory() as directory:
            source_path = Path(directory) / "legacy.db"
            source = sqlite3.connect(source_path)
            source.executescript("""
                CREATE TABLE search_runs (id INTEGER PRIMARY KEY AUTOINCREMENT, searched_at TEXT NOT NULL, origin TEXT NOT NULL, destination TEXT NOT NULL, start_date TEXT NOT NULL, end_date TEXT NOT NULL, min_trip_days INTEGER NOT NULL, max_trip_days INTEGER NOT NULL, api_budget INTEGER NOT NULL);
                CREATE TABLE flight_results (id INTEGER PRIMARY KEY AUTOINCREMENT, search_run_id INTEGER NOT NULL REFERENCES search_runs(id), departure_airport TEXT NOT NULL, arrival_airport TEXT NOT NULL, departure_date TEXT NOT NULL, return_date TEXT NOT NULL, price REAL NOT NULL);
            """)
            source.execute("INSERT INTO search_runs VALUES (7,'then','HYD','MOW','2027-01-01','2027-02-01',5,6,4)")
            source.execute("INSERT INTO flight_results VALUES (11,7,'HYD','MOW','2027-01-10','2027-01-15',42000)")
            source.execute("INSERT INTO sqlite_sequence(name,seq) VALUES ('search_runs',29)")
            source.commit()
            source.close()
            result = migrate(source_path, self.url)
            self.assertEqual("migrated", result["mode"])
            connection = db.get_connection()
            try:
                self.assertEqual(1, connection.execute("SELECT COUNT(*) FROM flight_results WHERE id=11 AND search_run_id=7").fetchone()[0])
                self.assertEqual(29, connection.execute("SELECT last_value FROM search_runs_id_seq").fetchone()[0])
            finally:
                connection.close()

    def test_repeated_migration_is_refused_without_overwriting_existing_data(self):
        from flight_search.database.migrate_sqlite_to_postgres import migrate
        with tempfile.TemporaryDirectory() as directory:
            source_path = Path(directory) / "legacy.db"
            source = sqlite3.connect(source_path)
            source.executescript("""
                CREATE TABLE search_runs (id INTEGER PRIMARY KEY AUTOINCREMENT, searched_at TEXT NOT NULL, origin TEXT NOT NULL, destination TEXT NOT NULL, start_date TEXT NOT NULL, end_date TEXT NOT NULL, min_trip_days INTEGER NOT NULL, max_trip_days INTEGER NOT NULL, api_budget INTEGER NOT NULL);
                CREATE TABLE flight_results (id INTEGER PRIMARY KEY AUTOINCREMENT, search_run_id INTEGER NOT NULL REFERENCES search_runs(id), departure_airport TEXT NOT NULL, arrival_airport TEXT NOT NULL, departure_date TEXT NOT NULL, return_date TEXT NOT NULL, price REAL NOT NULL);
            """)
            source.execute("INSERT INTO search_runs VALUES (23,'then','HYD','MOW','2027-01-01','2027-02-01',5,6,4)")
            source.commit()
            source.close()
            migrate(source_path, self.url)
            with self.assertRaisesRegex(ValueError, "target contains data"):
                migrate(source_path, self.url)
            connection = db.get_connection()
            try:
                self.assertEqual(1, connection.execute("SELECT COUNT(*) FROM search_runs WHERE id=23").fetchone()[0])
            finally:
                connection.close()

    def test_injected_migration_failure_rolls_back_rows(self):
        from flight_search.database.migrate_sqlite_to_postgres import migrate
        with tempfile.TemporaryDirectory() as directory:
            source_path = Path(directory) / "legacy.db"
            source = sqlite3.connect(source_path)
            source.executescript("""
                CREATE TABLE search_runs (id INTEGER PRIMARY KEY AUTOINCREMENT, searched_at TEXT NOT NULL, origin TEXT NOT NULL, destination TEXT NOT NULL, start_date TEXT NOT NULL, end_date TEXT NOT NULL, min_trip_days INTEGER NOT NULL, max_trip_days INTEGER NOT NULL, api_budget INTEGER NOT NULL);
                CREATE TABLE flight_results (id INTEGER PRIMARY KEY AUTOINCREMENT, search_run_id INTEGER NOT NULL REFERENCES search_runs(id), departure_airport TEXT NOT NULL, arrival_airport TEXT NOT NULL, departure_date TEXT NOT NULL, return_date TEXT NOT NULL, price REAL NOT NULL);
            """)
            source.execute("INSERT INTO search_runs VALUES (101,'then','HYD','MOW','2027-01-01','2027-02-01',5,6,4)")
            source.commit()
            source.close()
            with self.assertRaisesRegex(RuntimeError, "Injected migration failure"):
                migrate(source_path, self.url, fail_after_rows=1)
            connection = db.get_connection()
            try:
                self.assertEqual(0, connection.execute("SELECT COUNT(*) FROM search_runs").fetchone()[0])
            finally:
                connection.close()

    def test_absent_database_url_does_not_select_postgres(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sqlite.db"
            with patch.object(db, "DATABASE_URL", ""), patch.object(db, "DATABASE_PATH", path), patch.object(db, "DATABASE_DIR", path.parent):
                connection = db.get_connection()
                try:
                    self.assertTrue(path.exists())
                    self.assertIsInstance(connection, sqlite3.Connection)
                finally:
                    connection.close()


if __name__ == "__main__":
    unittest.main()
