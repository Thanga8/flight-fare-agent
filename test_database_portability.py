import sqlite3
import tempfile
import unittest
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from flight_search.database.migrate_sqlite_to_postgres import TABLES, _source_snapshot, main
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
