"""Copy an initialized SQLite database into an empty PostgreSQL database.

The source is opened read-only. Copy operations and sequence adjustments share
one PostgreSQL transaction, so an interrupted copy can be safely retried after
the server rolls the transaction back.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path
from dotenv import load_dotenv

TABLES = (
    "search_runs", "flight_results", "fare_monitor_jobs", "fare_monitor_runs",
    "fare_monitor_observations", "multi_leg_search_runs",
    "multi_leg_fare_observations", "multi_leg_search_outcomes",
    "multi_leg_comparisons", "multi_leg_google_insights",
)
OPTIONAL_TABLES = frozenset({
    "fare_monitor_jobs", "fare_monitor_runs", "fare_monitor_observations",
    "multi_leg_search_runs", "multi_leg_fare_observations", "multi_leg_search_outcomes",
    "multi_leg_comparisons", "multi_leg_google_insights",
})
REQUIRED_TABLES = frozenset({"search_runs", "flight_results"})


def _source_snapshot(path):
    if not path.is_file():
        raise ValueError("SQLite source file does not exist.")
    source = sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True)
    source.row_factory = sqlite3.Row
    names = {row[0] for row in source.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not names:
        return source, {table: 0 for table in TABLES}
    missing_required = REQUIRED_TABLES - names
    if missing_required:
        source.close()
        raise ValueError("Source database schema is missing required application tables: " + ", ".join(sorted(missing_required)))
    counts = {table: source.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
              if table in names else 0 for table in TABLES}
    violations = source.execute("PRAGMA foreign_key_check").fetchall()
    if violations:
        source.close()
        raise ValueError("Source database has foreign-key integrity violations.")
    return source, counts


def _source_sequences(source):
    """Read SQLite AUTOINCREMENT high-water marks, including deleted max IDs."""
    names = {row[0] for row in source.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "sqlite_sequence" not in names:
        return {}
    return {row[0]: int(row[1]) for row in source.execute("SELECT name, seq FROM sqlite_sequence")
            if row[0] in TABLES}


def migrate(source_path: Path, database_url: str, *, dry_run=False, fail_after_rows=None):
    if not database_url:
        raise ValueError("DATABASE_URL is required; no credential-bearing URL is printed.")
    source, source_counts = _source_snapshot(source_path)
    db = None
    previous_database_url = None
    try:
        source_sequences = _source_sequences(source)
        source_tables = {row[0] for row in source.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        # Import after setting selection so the shared persistence module targets PostgreSQL.
        from flight_search.database import db
        previous_database_url = db.DATABASE_URL
        db.DATABASE_URL = database_url
        target = db.get_connection()
        try:
            public_tables = target.execute("""SELECT tablename FROM pg_tables WHERE schemaname='public'""").fetchall()
            target_names = {row[0] for row in public_tables}
            target_counts = {}
            for table in target_names:
                safe_name = table.replace('"', '""')
                target_counts[table] = target.execute(f'SELECT COUNT(*) FROM public."{safe_name}"').fetchone()[0]
            nonempty = {table: count for table, count in target_counts.items() if count}
            if nonempty:
                raise ValueError("PostgreSQL target contains data; migration requires an empty public schema.")
            if dry_run:
                return {"mode": "dry-run", "source_counts": source_counts,
                        "target_public_tables": len(target_names), "target_data_rows": 0}

            target.close()
            db.initialize_database()
            target = db.get_connection()
            try:
                copied_rows = 0
                with target:
                    for table in TABLES:
                        if table not in source_tables:
                            continue
                        columns = [row[1] for row in source.execute(f'PRAGMA table_info("{table}")')]
                        if not columns:
                            if source_counts[table] == 0:
                                continue
                            raise ValueError(f"Source table {table} has no columns.")
                        cols_sql = ",".join('"' + col.replace('"', '""') + '"' for col in columns)
                        placeholders = ",".join("?" for _ in columns)
                        insert_sql = f'INSERT INTO "{table}" ({cols_sql}) VALUES ({placeholders})'
                        rows = source.execute(f'SELECT {cols_sql} FROM "{table}"').fetchall()
                        for row in rows:
                            target.execute(insert_sql, tuple(row))
                            copied_rows += 1
                            if fail_after_rows is not None and copied_rows >= fail_after_rows:
                                raise RuntimeError("Injected migration failure for rollback verification.")
                    for table in TABLES:
                        max_id = target.execute(f'SELECT MAX(id) FROM "{table}"').fetchone()[0] or 0
                        high_water = max(int(max_id), source_sequences.get(table, 0))
                        target.execute("SELECT setval(pg_get_serial_sequence(%s,'id'),%s,%s)",
                                       (f"public.{table}", max(high_water, 1), high_water > 0))
                    verified = {table: target.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
                                for table in TABLES}
                    if verified != source_counts:
                        raise ValueError("PostgreSQL row counts did not match the SQLite source.")
                    fk_issues = target.execute("""SELECT COUNT(*) FROM (
                        SELECT 1 FROM flight_results f LEFT JOIN search_runs s ON s.id=f.search_run_id WHERE s.id IS NULL
                        UNION ALL SELECT 1 FROM fare_monitor_runs r LEFT JOIN fare_monitor_jobs j ON j.id=r.job_id WHERE j.id IS NULL
                        UNION ALL SELECT 1 FROM fare_monitor_observations o
                          LEFT JOIN fare_monitor_jobs j ON j.id=o.job_id LEFT JOIN fare_monitor_runs r ON r.id=o.run_id
                          WHERE j.id IS NULL OR r.id IS NULL
                        UNION ALL SELECT 1 FROM multi_leg_fare_observations f
                          LEFT JOIN multi_leg_search_runs s ON s.id=f.search_run_id WHERE s.id IS NULL
                        UNION ALL SELECT 1 FROM multi_leg_search_outcomes o
                          LEFT JOIN multi_leg_search_runs s ON s.id=o.search_run_id WHERE s.id IS NULL
                        UNION ALL SELECT 1 FROM multi_leg_comparisons c
                          LEFT JOIN multi_leg_search_runs s ON s.id=c.search_run_id WHERE s.id IS NULL
                        UNION ALL SELECT 1 FROM multi_leg_google_insights i
                          LEFT JOIN multi_leg_search_runs s ON s.id=i.search_run_id WHERE s.id IS NULL
                    ) integrity""").fetchone()[0]
                    if fk_issues:
                        raise ValueError("PostgreSQL relationship validation failed.")
                return {"mode": "migrated", "source_counts": source_counts,
                        "target_counts": verified, "relationships": "valid"}
            finally:
                target.close()
        finally:
            target.close()
    finally:
        source.close()
        if db is not None:
            db.DATABASE_URL = previous_database_url


def main(argv=None):
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path, help="SQLite database path")
    parser.add_argument("--dry-run", action="store_true", help="Check source and empty target without creating schema or copying")
    args = parser.parse_args(argv)
    url = os.getenv("DATABASE_URL", "").strip()
    try:
        print(json.dumps(migrate(args.source, url, dry_run=args.dry_run), indent=2, sort_keys=True))
    except Exception as error:
        # Driver exceptions may include the connection string: never print them.
        safe = error if isinstance(error, (ValueError,)) else "Database operation failed; check connectivity and credentials locally."
        print(f"Migration failed: {safe}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
