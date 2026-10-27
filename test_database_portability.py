import sqlite3
import tempfile
import unittest
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from flight_search.database.migrate_sqlite_to_postgres import TABLES, OPTIONAL_TABLES, _source_snapshot, main
from flight_search.database import db
from flight_search.database.db import _postgres_sql


class DatabasePortabilityTests(unittest.TestCase):
    def make_source(self, path):
        connection = sqlite3.connect(path)
        connection.execute("PRAGMA foreign_keys=ON")
        for table in TABLES:
            if table == "search_runs":
                connection.execute('CREATE TABLE search_runs (id INTEGER PRIMARY KEY AUTOINCREMENT)')
            elif table == "flight_results":
                connection.execute('CREATE TABLE flight_results (id INTEGER PRIMARY KEY, search_run_id INTEGER REFERENCES search_runs(id))')
            elif table == "fare_monitor_runs":
                connection.execute('CREATE TABLE fare_monitor_runs (id INTEGER PRIMARY KEY, job_id INTEGER REFERENCES fare_monitor_jobs(id))')
            elif table == "fare_monitor_observations":
                connection.execute('CREATE TABLE fare_monitor_observations (id INTEGER PRIMARY KEY, job_id INTEGER REFERENCES fare_monitor_jobs(id), run_id INTEGER REFERENCES fare_monitor_runs(id))')
            else:
                connection.execute(f'CREATE TABLE "{table}" (id INTEGER PRIMARY KEY)')
        connection.commit()
        return connection

    def test_empty_initialized_source_has_zero_counts(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.db"
            connection = self.make_source(path)
            connection.close()
            source, counts = _source_snapshot(path)
            try:
                self.assertEqual(set(counts), set(TABLES))
                self.assertTrue(all(count == 0 for count in counts.values()))
            finally:
                source.close()

    def test_source_sequence_high_watermark_includes_deleted_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.db"
            connection = self.make_source(path)
            connection.execute("INSERT INTO search_runs(id) VALUES (19)")
            connection.execute("DELETE FROM search_runs")
            connection.commit()
            connection.close()
            source, _ = _source_snapshot(path)
            try:
                from flight_search.database.migrate_sqlite_to_postgres import _source_sequences
                self.assertEqual(19, _source_sequences(source)["search_runs"])
            finally:
                source.close()

    def test_empty_database_is_reported_as_zero_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.db"
            sqlite3.connect(path).close()
            source, counts = _source_snapshot(path)
            try:
                self.assertTrue(all(count == 0 for count in counts.values()))
            finally:
                source.close()

    def test_populated_legacy_schema_without_monitor_tables_is_supported_read_only(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "legacy.db"
            connection = sqlite3.connect(path)
            connection.executescript("""
                CREATE TABLE search_runs (id INTEGER PRIMARY KEY AUTOINCREMENT, searched_at TEXT NOT NULL, origin TEXT NOT NULL, destination TEXT NOT NULL, start_date TEXT NOT NULL, end_date TEXT NOT NULL, min_trip_days INTEGER NOT NULL, max_trip_days INTEGER NOT NULL, api_budget INTEGER NOT NULL);
                CREATE TABLE flight_results (id INTEGER PRIMARY KEY AUTOINCREMENT, search_run_id INTEGER NOT NULL REFERENCES search_runs(id), departure_airport TEXT NOT NULL, arrival_airport TEXT NOT NULL, departure_date TEXT NOT NULL, return_date TEXT NOT NULL, price REAL NOT NULL);
            """)
            connection.execute("INSERT INTO search_runs VALUES (41,'then','HYD','MOW','2027-01-01','2027-02-01',5,6,4)")
            connection.execute("INSERT INTO flight_results VALUES (83,41,'HYD','MOW','2027-01-10','2027-01-15',50000)")
            connection.execute("INSERT INTO sqlite_sequence(name,seq) VALUES ('search_runs',99)")
            connection.commit()
            connection.close()
            before = path.read_bytes()
            source, counts = _source_snapshot(path)
            try:
                self.assertEqual(1, counts["search_runs"])
                self.assertEqual(1, counts["flight_results"])
                for table in OPTIONAL_TABLES:
                    self.assertEqual(0, counts[table])
            finally:
                source.close()
            self.assertEqual(before, path.read_bytes(), "migration preflight must not mutate the user's source")

    def test_partial_legacy_schema_missing_required_table_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "incomplete.db"
            connection = sqlite3.connect(path)
            connection.execute("CREATE TABLE search_runs(id INTEGER PRIMARY KEY)")
            connection.close()
            with self.assertRaisesRegex(ValueError, "missing required application tables"):
                _source_snapshot(path)

    def test_sqlite_intended_test_cannot_be_redirected_by_environment_url(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "isolated.db"
            with patch.dict("os.environ", {"DATABASE_URL": "postgresql://user:secret@shared.example/db"}), \
                 patch.object(db, "DATABASE_URL", ""), \
                 patch.object(db, "DATABASE_PATH", path), \
                 patch.object(db, "DATABASE_DIR", path.parent):
                db.initialize_database()
                self.assertTrue(path.exists())
                connection = db.get_connection()
                try:
                    self.assertIsInstance(connection, sqlite3.Connection)
                finally:
                    connection.close()

    def test_source_foreign_key_violations_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.db"
            connection = self.make_source(path)
            connection.execute("PRAGMA foreign_keys=OFF")
            connection.execute("INSERT INTO flight_results(id,search_run_id) VALUES (1,999)")
            connection.commit()
            connection.close()
            with self.assertRaisesRegex(ValueError, "foreign-key integrity"):
                _source_snapshot(path)

    def test_legacy_optional_tables_may_be_empty_or_populated_when_present(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "monitor.db"
            connection = self.make_source(path)
            connection.execute("INSERT INTO search_runs(id) VALUES(1)")
            connection.execute("INSERT INTO fare_monitor_jobs(id) VALUES(5)")
            connection.execute("INSERT INTO fare_monitor_runs(id,job_id) VALUES(8,5)")
            connection.execute("INSERT INTO fare_monitor_observations(id,job_id,run_id) VALUES(13,5,8)")
            connection.commit()
            connection.close()
            source, counts = _source_snapshot(path)
            try:
                self.assertEqual(1, counts["fare_monitor_jobs"])
                self.assertEqual(1, counts["fare_monitor_runs"])
                self.assertEqual(1, counts["fare_monitor_observations"])
            finally:
                source.close()

    def test_postgres_sql_translation_is_narrow(self):
        self.assertIn("BIGSERIAL PRIMARY KEY", _postgres_sql("id INTEGER PRIMARY KEY AUTOINCREMENT"))
        self.assertIn("search_run_id BIGINT", _postgres_sql("search_run_id INTEGER NOT NULL"))
        self.assertIn("ON CONFLICT DO NOTHING", _postgres_sql("INSERT OR IGNORE INTO t VALUES (?)"))
        self.assertEqual("SELECT %s", _postgres_sql("SELECT ?"))
        self.assertEqual("INSERT INTO t VALUES (%s)", _postgres_sql("INSERT INTO t VALUES (?)"))

    def test_connection_errors_do_not_expose_connection_url(self):
        with patch.object(db, "DATABASE_URL", "postgresql://user:secret@host/db"), \
             patch("psycopg2.connect", side_effect=RuntimeError("postgresql://user:secret@host/db")):
            with self.assertRaisesRegex(RuntimeError, "PostgreSQL connection failed") as raised:
                db.get_connection()
        self.assertNotIn("secret", str(raised.exception))

    def test_migration_connection_error_is_redacted_and_source_is_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.db"
            source = self.make_source(path)
            source.execute("INSERT INTO search_runs(id) VALUES (7)")
            source.commit()
            source.close()
            verify = sqlite3.connect(path)
            before = verify.execute("SELECT COUNT(*) FROM search_runs").fetchone()[0]
            verify.close()
            stderr = StringIO()
            with patch.object(db, "get_connection", side_effect=RuntimeError("connection postgresql://user:secret@host/db failed")), \
                 patch.object(db, "DATABASE_URL", ""), \
                 patch.dict("os.environ", {"DATABASE_URL": "postgresql://user:secret@host/db"}), \
                 redirect_stderr(stderr):
                result = main(["--source", str(path)])
            self.assertEqual(1, result)
            self.assertNotIn("secret", stderr.getvalue())
            verify = sqlite3.connect(path)
            after = verify.execute("SELECT COUNT(*) FROM search_runs").fetchone()[0]
            verify.close()
            self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
