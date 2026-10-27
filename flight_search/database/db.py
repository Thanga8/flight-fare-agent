import sqlite3
import os
from dotenv import load_dotenv
import math
import hashlib
import json
import re
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Optional, Dict, Any


# ==========================================
# DATABASE CONFIGURATION
# ==========================================

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
DATABASE_PATH = Path(os.getenv("FLIGHT_DATABASE_PATH", "data/flights.db"))
DATABASE_DIR = DATABASE_PATH.parent


class _PostgresConnection:
    """Small DB-API compatibility adapter for the application's SQLite SQL."""
    def __init__(self, raw):
        self.raw = raw

    def execute(self, sql, params=()):
        cursor = self.raw.cursor()
        cursor.execute(_postgres_sql(sql), params)
        return cursor

    def cursor(self):
        return _PostgresCursor(self.raw.cursor())

    def executescript(self, sql):
        for statement in sql.split(";"):
            if statement.strip():
                self.execute(statement)

    def commit(self): self.raw.commit()
    def rollback(self): self.raw.rollback()
    def close(self): self.raw.close()
    def __enter__(self):
        self.raw.__enter__()
        return self
    def __exit__(self, *args): return self.raw.__exit__(*args)


class _PostgresCursor:
    def __init__(self, raw): self.raw = raw
    def execute(self, sql, params=()): self.raw.execute(_postgres_sql(sql), params); return self
    def fetchone(self): return self.raw.fetchone()
    def fetchall(self): return self.raw.fetchall()
    @property
    def rowcount(self): return self.raw.rowcount
    @property
    def lastrowid(self): return None


def _postgres_sql(sql):
    sql = sql.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "BIGSERIAL PRIMARY KEY")
    sql = re.sub(r"\b((?:search_run|job|run)_id) INTEGER\b", r"\1 BIGINT", sql)
    ignore_conflict = "INSERT OR IGNORE INTO" in sql.upper()
    sql = sql.replace("INSERT OR IGNORE INTO", "INSERT INTO")
    if ignore_conflict and "ON CONFLICT" not in sql.upper():
        sql = sql.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"
    return sql.replace("?", "%s")


# ==========================================
# DATABASE CONNECTION
# ==========================================

def get_connection():
    """Open the configured PostgreSQL or SQLite connection."""

    if DATABASE_URL:
        import psycopg2
        from psycopg2.extras import DictCursor
        try:
            raw = psycopg2.connect(DATABASE_URL, connect_timeout=10, cursor_factory=DictCursor,
                                   application_name="flight-fare-agent")
        except Exception:
            raise RuntimeError("PostgreSQL connection failed; check local configuration and network access.") from None
        return _PostgresConnection(raw)

    DATABASE_DIR.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DATABASE_PATH, timeout=30)

    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    return connection


# ==========================================
# DATABASE INITIALIZATION
# ==========================================

def initialize_database():
    """
    Create all required database tables if they
    do not already exist.
    """

    connection = get_connection()

    if DATABASE_URL:
        # Serialize first-start schema creation/upgrades across web and Actions.
        connection.execute("SELECT pg_advisory_xact_lock(731204991)")

    cursor = connection.cursor()

    # ==========================================
    # SEARCH RUNS
    # ==========================================

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS search_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            searched_at TEXT NOT NULL,

            origin TEXT NOT NULL,

            destination TEXT NOT NULL,

            start_date TEXT NOT NULL,

            end_date TEXT NOT NULL,

            min_trip_days INTEGER NOT NULL,

            max_trip_days INTEGER NOT NULL,

            api_budget INTEGER NOT NULL,

            total_searches INTEGER,

            successful_api_searches INTEGER,

            priced_results INTEGER,

            no_price_searches INTEGER,

            failed_api_searches INTEGER
        )
        """
    )

    # ==========================================
    # FLIGHT RESULTS
    # ==========================================

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS flight_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            search_run_id INTEGER NOT NULL,

            departure_airport TEXT NOT NULL,

            arrival_airport TEXT NOT NULL,

            departure_date TEXT NOT NULL,

            return_date TEXT NOT NULL,

            price REAL NOT NULL,

            currency TEXT DEFAULT 'INR',

            duration_minutes INTEGER,

            stops INTEGER,

            airline TEXT,

            price_score REAL,

            duration_score REAL,

            stops_score REAL,

            convenience_score REAL,

            final_score REAL,

            FOREIGN KEY (search_run_id)
                REFERENCES search_runs(id)
        )
        """
    )

    # ==========================================
    # INDEXES
    # ==========================================

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_flight_results_search_run
        ON flight_results(search_run_id)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_flight_results_route_dates
        ON flight_results(
            departure_airport,
            arrival_airport,
            departure_date,
            return_date
        )
        """
    )

    # Isolated storage for the two-leg experimental search model.
    connection.executescript("""
        CREATE TABLE IF NOT EXISTS fare_monitor_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 0,
            start_date TEXT NOT NULL, end_date TEXT NOT NULL, nights INTEGER NOT NULL,
            leg1_origin TEXT NOT NULL, leg1_destination TEXT NOT NULL, leg2_origin TEXT NOT NULL, leg2_destination TEXT NOT NULL,
            interval_days INTEGER NOT NULL DEFAULT 2, timezone TEXT NOT NULL DEFAULT 'Asia/Kolkata',
            api_budget INTEGER NOT NULL DEFAULT 6, notify_telegram INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL, next_run_at TEXT, last_run_at TEXT, rotation_cursor INTEGER NOT NULL DEFAULT 0,
            running INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS fare_monitor_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, job_id INTEGER NOT NULL REFERENCES fare_monitor_jobs(id) ON DELETE CASCADE,
            status TEXT NOT NULL, started_at TEXT NOT NULL, finished_at TEXT, serpapi_calls INTEGER NOT NULL DEFAULT 0,
            serpapi_budget INTEGER NOT NULL, coverage_json TEXT NOT NULL DEFAULT '{}', result_json TEXT NOT NULL DEFAULT '{}',
            error TEXT, notification_sent INTEGER NOT NULL DEFAULT 0, notification_error TEXT,
            accounting_status TEXT NOT NULL DEFAULT 'exact', recovery_hold_until TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_fare_monitor_due ON fare_monitor_jobs(enabled,next_run_at);
        CREATE INDEX IF NOT EXISTS idx_fare_monitor_runs_job ON fare_monitor_runs(job_id,id DESC);
        CREATE TABLE IF NOT EXISTS fare_monitor_observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT, job_id INTEGER NOT NULL REFERENCES fare_monitor_jobs(id) ON DELETE CASCADE,
            run_id INTEGER NOT NULL REFERENCES fare_monitor_runs(id) ON DELETE CASCADE,
            identity_key TEXT NOT NULL, identity_json TEXT NOT NULL, route TEXT NOT NULL,
            itinerary_label TEXT NOT NULL DEFAULT '', leg1_date TEXT NOT NULL, leg2_date TEXT NOT NULL, fare REAL NOT NULL, currency TEXT NOT NULL,
            observed_at TEXT NOT NULL, itinerary_json TEXT NOT NULL,
            UNIQUE(job_id,run_id,identity_key)
        );
        CREATE INDEX IF NOT EXISTS idx_fare_monitor_observation_identity
        ON fare_monitor_observations(job_id,identity_key,observed_at);
        CREATE TABLE IF NOT EXISTS multi_leg_search_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            searched_at TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            nights_between_departures INTEGER NOT NULL,
            leg1_origin TEXT NOT NULL,
            leg1_destination TEXT NOT NULL,
            leg2_origin TEXT NOT NULL,
            leg2_destination TEXT NOT NULL,
            leg1_cache_mode TEXT NOT NULL,
            leg2_cache_mode TEXT NOT NULL,
            combined_cache_mode TEXT NOT NULL,
            serpapi_budget INTEGER NOT NULL,
            serpapi_calls INTEGER NOT NULL,
            budget_limited INTEGER NOT NULL,
            statistics_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS multi_leg_fare_observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            search_run_id INTEGER NOT NULL REFERENCES multi_leg_search_runs(id),
            leg_number INTEGER NOT NULL CHECK (leg_number IN (1, 2)),
            departure_date TEXT NOT NULL,
            departure_airport TEXT NOT NULL,
            arrival_airport TEXT NOT NULL,
            price REAL NOT NULL,
            currency TEXT NOT NULL,
            flight_json TEXT NOT NULL,
            data_source TEXT NOT NULL,
            source_fetched_at TEXT NOT NULL,
            recorded_at TEXT NOT NULL,
            observation_key TEXT NOT NULL UNIQUE
        );
        CREATE INDEX IF NOT EXISTS idx_multi_leg_fares_route_date_time
        ON multi_leg_fare_observations(departure_airport, arrival_airport, departure_date, source_fetched_at);
        CREATE TABLE IF NOT EXISTS multi_leg_search_outcomes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            search_run_id INTEGER NOT NULL REFERENCES multi_leg_search_runs(id),
            leg_number INTEGER NOT NULL CHECK (leg_number IN (1, 2)),
            departure_date TEXT NOT NULL,
            status TEXT NOT NULL,
            error TEXT,
            data_source TEXT NOT NULL,
            source_fetched_at TEXT,
            recorded_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS multi_leg_comparisons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            search_run_id INTEGER NOT NULL REFERENCES multi_leg_search_runs(id),
            leg1_departure_date TEXT NOT NULL,
            leg2_departure_date TEXT NOT NULL,
            separate_total REAL NOT NULL,
            combined_price REAL,
            difference REAL,
            status TEXT NOT NULL,
            details_json TEXT NOT NULL,
            data_source TEXT NOT NULL,
            source_fetched_at TEXT,
            recorded_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS multi_leg_google_insights (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            search_run_id INTEGER NOT NULL REFERENCES multi_leg_search_runs(id),
            leg_number INTEGER NOT NULL CHECK (leg_number IN (1, 2)),
            departure_id TEXT NOT NULL,
            arrival_id TEXT NOT NULL,
            departure_date TEXT NOT NULL,
            currency TEXT NOT NULL,
            insight_status TEXT NOT NULL,
            insights_json TEXT,
            data_source TEXT NOT NULL,
            source_fetched_at TEXT,
            recorded_at TEXT NOT NULL,
            snapshot_key TEXT NOT NULL UNIQUE
        );
        CREATE INDEX IF NOT EXISTS idx_multi_leg_google_insights_context
        ON multi_leg_google_insights(departure_date, departure_id, arrival_id, source_fetched_at);
    """)

    # Additive upgrade for databases created by an earlier monitoring preview.
    if DATABASE_URL:
        columns = {row["column_name"] for row in connection.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name=?", ("fare_monitor_runs",))}
    else:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(fare_monitor_runs)")}
    if "notification_error" not in columns:
        connection.execute("ALTER TABLE fare_monitor_runs ADD COLUMN notification_error TEXT")
    if "accounting_status" not in columns:
        connection.execute("ALTER TABLE fare_monitor_runs ADD COLUMN accounting_status TEXT NOT NULL DEFAULT 'exact'")
    if "recovery_hold_until" not in columns:
        connection.execute("ALTER TABLE fare_monitor_runs ADD COLUMN recovery_hold_until TEXT")
    if DATABASE_URL:
        observation_columns = {row["column_name"] for row in connection.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name=?", ("fare_monitor_observations",))}
    else:
        observation_columns = {row[1] for row in connection.execute("PRAGMA table_info(fare_monitor_observations)")}
    if "itinerary_label" not in observation_columns:
        connection.execute("ALTER TABLE fare_monitor_observations ADD COLUMN itinerary_label TEXT NOT NULL DEFAULT ''")

    # Keep the PostgreSQL advisory transaction lock through additive upgrades.
    connection.commit()

    connection.close()


def save_monitor_job(config, job_id=None):
    initialize_database()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    connection = get_connection()
    fields = (config["name"], config["enabled"], config["start_date"], config["end_date"], config["nights"],
              config["leg1_origin"], config["leg1_destination"], config["leg2_origin"], config["leg2_destination"],
              config["interval_days"], config["timezone"], config["api_budget"], config["notify_telegram"])
    try:
        with connection:
            if job_id:
                cur = connection.execute("""UPDATE fare_monitor_jobs SET name=?,enabled=?,start_date=?,end_date=?,nights=?,
                    leg1_origin=?,leg1_destination=?,leg2_origin=?,leg2_destination=?,interval_days=?,timezone=?,api_budget=?,notify_telegram=?,next_run_at=? WHERE id=?""",
                    (*fields, config.get("next_run_at"), job_id))
                if not cur.rowcount:
                    return None
            else:
                job_id = connection.execute("""INSERT INTO fare_monitor_jobs
                    (name,enabled,start_date,end_date,nights,leg1_origin,leg1_destination,leg2_origin,leg2_destination,
                     interval_days,timezone,api_budget,notify_telegram,created_at,next_run_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) RETURNING id""", (*fields, now, config.get("next_run_at"))).fetchone()[0]
        return get_monitor_job(job_id)
    finally:
        connection.close()


def get_monitor_job(job_id):
    initialize_database()
    connection = get_connection()
    try:
        row = connection.execute("SELECT * FROM fare_monitor_jobs WHERE id=?", (job_id,)).fetchone()
        return dict(row) if row else None
    finally:
        connection.close()


def list_monitor_jobs():
    initialize_database()
    connection = get_connection()
    try:
        return [dict(row) for row in connection.execute("SELECT * FROM fare_monitor_jobs ORDER BY id DESC")]
    finally:
        connection.close()


def delete_monitor_job(job_id):
    initialize_database()
    connection = get_connection()
    try:
        with connection:
            connection.execute("DELETE FROM fare_monitor_jobs WHERE id=?", (job_id,))
    finally:
        connection.close()


def monitor_daily_budget_limit():
    """Return a fail-closed daily ceiling, capped at the existing 50-call limit."""
    try:
        configured = int(os.getenv("MONITOR_MAX_DAILY_SERPAPI_BUDGET", "50"))
        if configured < 0:
            return 0
        return min(configured, 50)
    except (TypeError, ValueError):
        return 0


def get_monitor_daily_budget_status(now=None):
    """Return UTC-day monitor usage, counting running/uncertain jobs at their full reservation."""
    initialize_database()
    now = now or datetime.now(timezone.utc)
    start = now.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat(timespec="seconds")
    connection = get_connection()
    try:
        row = connection.execute("""SELECT COALESCE(SUM(CASE
            WHEN status='running' OR accounting_status='upper_bound' THEN serpapi_budget
            ELSE serpapi_calls END),0) AS used
            FROM fare_monitor_runs WHERE started_at>=? OR finished_at>=? OR status='running'""", (start, start)).fetchone()
        limit = monitor_daily_budget_limit()
        used = int(row["used"])
        return {"limit": limit, "used": used, "remaining": max(0, limit - used), "timezone": "UTC"}
    finally:
        connection.close()


def claim_monitor_run(job_id, due_only=False):
    """Atomically claim a manual or due run so two workers cannot overlap."""
    initialize_database()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    connection = get_connection()
    try:
        if not DATABASE_URL:
            connection.execute("BEGIN IMMEDIATE")
        with connection:
            if DATABASE_URL:
                # Serialize reservations across different jobs as well as within one job.
                connection.execute("SELECT pg_advisory_xact_lock(731204992)")
            stale = connection.execute("""SELECT r.id,j.interval_days,j.timezone,r.serpapi_budget FROM fare_monitor_runs r JOIN fare_monitor_jobs j ON j.id=r.job_id
                WHERE j.id=? AND j.running=1 AND r.status='running' AND r.started_at < ? ORDER BY r.id DESC LIMIT 1""",
                (job_id, (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat(timespec="seconds"))).fetchone()
            if stale:
                # A dead/timed-out worker may already have spent the provider
                # budget. Do not reclaim in this scheduler invocation; defer
                # the retry by a full interval and require the next poll.
                next_after_recovery = (datetime.now(ZoneInfo(stale["timezone"])) + timedelta(days=int(stale["interval_days"]))).astimezone(timezone.utc).isoformat(timespec="seconds")
                # Calls are not checkpointed durably while the external request
                # executes. Conservatively charge the entire reserved run budget.
                connection.execute("UPDATE fare_monitor_runs SET status='failed',finished_at=?,serpapi_calls=serpapi_budget,accounting_status='upper_bound',recovery_hold_until=?,coverage_json=?,result_json=?,error='Execution lease expired; provider usage is uncertain; maximum reserved budget charged.' WHERE id=?",
                                   (now, next_after_recovery, json.dumps({"api_calls_remaining": 0, "accounting_status": "upper_bound"}),
                                    json.dumps({"serpapi_calls": stale["serpapi_budget"], "serpapi_budget": stale["serpapi_budget"],
                                                "accounting_status": "upper_bound"}), stale["id"]))
                connection.execute("UPDATE fare_monitor_jobs SET running=0,last_run_at=?,next_run_at=? WHERE id=?",
                                   (now, next_after_recovery, job_id))
                return None
            recovery_hold = connection.execute("""SELECT r.recovery_hold_until FROM fare_monitor_runs r
                JOIN fare_monitor_jobs j ON j.id=r.job_id
                WHERE j.id=? AND r.status='failed'
                  AND r.accounting_status='upper_bound'
                ORDER BY r.id DESC LIMIT 1""", (job_id,)).fetchone()
            if recovery_hold and recovery_hold["recovery_hold_until"] and recovery_hold["recovery_hold_until"] > now:
                # Applies to manual and scheduled claims. A manual button must
                # not bypass the post-timeout cooldown and duplicate uncertain spend.
                return None
            clause = "id=? AND enabled=1 AND running=0 AND (next_run_at IS NULL OR next_run_at<=?)" if due_only else "id=? AND running=0"
            params = (job_id, now) if due_only else (job_id,)
            lock = " FOR UPDATE" if DATABASE_URL else ""
            row = connection.execute(f"SELECT * FROM fare_monitor_jobs WHERE {clause}{lock}", params).fetchone()
            if not row:
                return None
            daily_limit = monitor_daily_budget_limit()
            day_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat(timespec="seconds")
            daily_usage = connection.execute("""SELECT COALESCE(SUM(CASE
                WHEN status='running' OR accounting_status='upper_bound' THEN serpapi_budget
                ELSE serpapi_calls END),0) AS used
                FROM fare_monitor_runs WHERE started_at>=? OR finished_at>=? OR status='running'""", (day_start, day_start)).fetchone()["used"]
            if daily_limit <= 0 or int(daily_usage) + int(row["api_budget"]) > daily_limit:
                return None
            cursor = connection.execute("UPDATE fare_monitor_jobs SET running=1 WHERE id=? AND running=0", (job_id,))
            if cursor.rowcount != 1:
                return None
            run_id = connection.execute("INSERT INTO fare_monitor_runs(job_id,status,started_at,serpapi_budget) VALUES(?,?,?,?) RETURNING id",
                                        (job_id, "running", now, row["api_budget"])).fetchone()[0]
            return dict(row) | {"run_id": run_id}
    finally:
        connection.close()


def finish_monitor_run(job, status, report=None, error=None, next_run_at=None, accounting_status="exact"):
    initialize_database()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    report = report or {}
    if accounting_status == "upper_bound":
        report["serpapi_budget"] = int(job.get("api_budget", 0))
        report["serpapi_calls"] = int(job.get("api_budget", 0))
        report["accounting_status"] = "upper_bound"
    if status == "succeeded":
        from flight_search.monitoring import classify_fare_changes, normalize_run_itineraries
        current = normalize_run_itineraries(report, job)
    else:
        current = []
    connection = get_connection()
    try:
        with connection:
            changes = []
            if status == "succeeded":
                previous_run = connection.execute("SELECT id FROM fare_monitor_runs WHERE job_id=? AND status='succeeded' AND id<>? ORDER BY id DESC LIMIT 1",
                                                  (job["id"], job["run_id"])).fetchone()
                previous_run_observations = []
                if previous_run:
                    previous_run_observations = [dict(row) for row in connection.execute("SELECT * FROM fare_monitor_observations WHERE run_id=?", (previous_run["id"],))]
                latest_observations = [dict(row) for row in connection.execute("""SELECT o.* FROM fare_monitor_observations o
                    JOIN fare_monitor_runs r ON r.id=o.run_id WHERE o.job_id=? AND r.status='succeeded'
                    ORDER BY o.observed_at DESC,o.id DESC""", (job["id"],))]
                latest_by_identity = {}
                for observation in latest_observations:
                    latest_by_identity.setdefault(observation["identity_key"], observation)
                previous = list(latest_by_identity.values())
                for observation in current:
                    observation["observed_at"] = now
                def threshold(name, default):
                    try:
                        parsed = float(os.getenv(name, str(default)))
                        return parsed if math.isfinite(parsed) and parsed >= 0 else default
                    except (TypeError, ValueError):
                        return default
                changes = classify_fare_changes(current, previous,
                    previous_run=previous_run_observations,
                    min_absolute_inr=threshold("FARE_CHANGE_MIN_ABS_INR", 1000),
                    min_percent=threshold("FARE_CHANGE_MIN_PERCENT", 3))
                for observation in current:
                    connection.execute("""INSERT OR IGNORE INTO fare_monitor_observations
                        (job_id,run_id,identity_key,identity_json,route,itinerary_label,leg1_date,leg2_date,fare,currency,observed_at,itinerary_json)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (job["id"], job["run_id"], observation["identity_key"], json.dumps(observation["identity"], sort_keys=True),
                         observation["route"], observation["itinerary_label"], observation["leg1_date"], observation["leg2_date"], observation["fare"],
                         observation["currency"], now, json.dumps(observation["itinerary"], ensure_ascii=False, sort_keys=True)))
            report["fare_changes"] = changes
            report["fare_change_summary"] = {kind: sum(change["type"] == kind for change in changes)
                for kind in ("new_itinerary", "fare_decreased", "fare_increased", "no_material_change", "not_observed", "currency_mismatch")}
            report["fare_comparison_status"] = "compared" if status == "succeeded" else "unavailable: search did not complete successfully"
            report["api_calls_remaining"] = 0 if accounting_status == "upper_bound" else max(0, int(report.get("serpapi_budget", job["api_budget"])) - int(report.get("serpapi_calls", 0)))
            coverage = {key: report.get(key) for key in ("valid_date_pairs", "covered_date_pairs", "combined_searches", "planned_usage", "serpapi_budget", "api_calls_remaining", "fare_change_summary")}
            connection.execute("UPDATE fare_monitor_runs SET status=?,finished_at=?,serpapi_calls=?,accounting_status=?,coverage_json=?,result_json=?,error=? WHERE id=?",
                (status, now, report.get("serpapi_calls", 0), accounting_status, json.dumps(coverage), json.dumps(report, default=str), error, job["run_id"]))
            connection.execute("UPDATE fare_monitor_jobs SET running=0,last_run_at=?,next_run_at=?,rotation_cursor=rotation_cursor+1 WHERE id=?",
                               (now, next_run_at, job["id"]))
    finally:
        connection.close()


def list_monitor_runs(job_id, limit=30):
    initialize_database()
    connection = get_connection()
    try:
        return [dict(row) for row in connection.execute("SELECT * FROM fare_monitor_runs WHERE job_id=? ORDER BY id DESC LIMIT ?", (job_id, limit))]
    finally:
        connection.close()


def mark_monitor_notification(run_id, *, sent, error=None):
    initialize_database()
    connection = get_connection()
    try:
        with connection:
            connection.execute("UPDATE fare_monitor_runs SET notification_sent=?,notification_error=? WHERE id=?",
                               (int(sent), error, run_id))
    finally:
        connection.close()


def get_monitor_fare_history(job_id, limit=100):
    initialize_database()
    connection = get_connection()
    try:
        return [dict(row) for row in connection.execute("""SELECT o.*,r.status AS run_status FROM fare_monitor_observations o
            JOIN fare_monitor_runs r ON r.id=o.run_id WHERE o.job_id=? ORDER BY o.observed_at DESC,o.id DESC LIMIT ?""",
            (job_id, limit))]
    finally:
        connection.close()


def check_database_readiness():
    """Check access to the configured DB without leaving any writes behind."""
    connection = get_connection()
    try:
        connection.execute("SELECT 1")
        connection.rollback()
    finally:
        connection.close()


def list_database_tables():
    """Return public/application table names for the local diagnostic utility."""
    connection = get_connection()
    try:
        if DATABASE_URL:
            rows = connection.execute("""SELECT table_name FROM information_schema.tables
                WHERE table_schema='public' AND table_type='BASE TABLE' ORDER BY table_name""").fetchall()
            return [row[0] for row in rows]
        return [row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()]
    finally:
        connection.close()


def persist_multi_leg_search(*, run: Dict[str, Any], fares: list[Dict[str, Any]],
                             outcomes: list[Dict[str, Any]], comparisons: list[Dict[str, Any]],
                             google_insights: Optional[list[Dict[str, Any]]] = None) -> int:
    """Persist one multi-leg run atomically; cached observation keys deduplicate reuse."""
    initialize_database()
    recorded_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    connection = get_connection()
    try:
        with connection:
            cursor = connection.execute(
                """INSERT INTO multi_leg_search_runs (
                    searched_at,start_date,end_date,nights_between_departures,
                    leg1_origin,leg1_destination,leg2_origin,leg2_destination,
                    leg1_cache_mode,leg2_cache_mode,combined_cache_mode,
                    serpapi_budget,serpapi_calls,budget_limited,statistics_json
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) RETURNING id""",
                (recorded_at, run["start_date"], run["end_date"], run["nights"],
                 run["leg1_origin"], run["leg1_destination"], run["leg2_origin"], run["leg2_destination"],
                 run["leg1_cache_mode"], run["leg2_cache_mode"], run["combined_cache_mode"],
                 run["serpapi_budget"], run["serpapi_calls"], int(run["budget_limited"]),
                 json.dumps(run["statistics"], ensure_ascii=False, sort_keys=True)),
            )
            run_id = cursor.fetchone()[0]
            for fare in fares:
                source_time = fare.get("source_fetched_at") or recorded_at
                identity = {key: fare.get(key) for key in (
                    "departure_date", "departure_airport", "arrival_airport", "price", "currency"
                )}
                identity["source_fetched_at"] = source_time
                if fare.get("data_source") == "live":
                    identity["live_run_id"] = run_id
                key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode("utf-8")).hexdigest()
                connection.execute(
                    """INSERT OR IGNORE INTO multi_leg_fare_observations (
                        search_run_id,leg_number,departure_date,departure_airport,arrival_airport,
                        price,currency,flight_json,data_source,source_fetched_at,recorded_at,observation_key
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (run_id, fare["leg_number"], fare["departure_date"], fare["departure_airport"],
                     fare["arrival_airport"], fare["price"], fare.get("currency", "INR"),
                     json.dumps(fare.get("flight", {}), ensure_ascii=False, sort_keys=True),
                     fare.get("data_source", "live"), source_time, recorded_at, key),
                )
            for outcome in outcomes:
                connection.execute(
                    """INSERT INTO multi_leg_search_outcomes (
                        search_run_id,leg_number,departure_date,status,error,data_source,source_fetched_at,recorded_at
                    ) VALUES (?,?,?,?,?,?,?,?)""",
                    (run_id, outcome["leg_number"], outcome["departure_date"], outcome["status"],
                     outcome.get("error"), outcome.get("data_source", "live"),
                     outcome.get("source_fetched_at"), recorded_at),
                )
            for comparison in comparisons:
                connection.execute(
                    """INSERT INTO multi_leg_comparisons (
                        search_run_id,leg1_departure_date,leg2_departure_date,separate_total,
                        combined_price,difference,status,details_json,data_source,source_fetched_at,recorded_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (run_id, comparison["leg1_departure_date"], comparison["leg2_departure_date"],
                     comparison["separate_total"], comparison.get("combined_price"), comparison.get("difference"),
                     comparison["status"], json.dumps(comparison.get("details", {}), ensure_ascii=False, sort_keys=True),
                     comparison.get("data_source", "live"), comparison.get("source_fetched_at"), recorded_at),
                )
            for insight in google_insights or []:
                source_time = insight.get("source_fetched_at")
                identity = {
                    "leg_number": insight["leg_number"],
                    "departure_id": insight["departure_id"],
                    "arrival_id": insight["arrival_id"],
                    "departure_date": insight["departure_date"],
                    "currency": insight.get("currency", "INR"),
                    "insight_status": insight["insight_status"],
                    "insights_json": insight.get("insights_json"),
                    "source_fetched_at": source_time,
                }
                snapshot_key = hashlib.sha256(
                    json.dumps(identity, sort_keys=True, ensure_ascii=False).encode("utf-8")
                ).hexdigest()
                connection.execute(
                    """INSERT OR IGNORE INTO multi_leg_google_insights (
                        search_run_id,leg_number,departure_id,arrival_id,departure_date,currency,
                        insight_status,insights_json,data_source,source_fetched_at,recorded_at,snapshot_key
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (run_id, insight["leg_number"], insight["departure_id"], insight["arrival_id"],
                     insight["departure_date"], insight.get("currency", "INR"), insight["insight_status"],
                     insight.get("insights_json"), insight.get("data_source", "live"), source_time,
                     recorded_at, snapshot_key),
                )
        return run_id
    finally:
        connection.close()


def get_multi_leg_historical_prices(departure_airport: str, arrival_airport: str,
                                    departure_date: str) -> list[Dict[str, Any]]:
    """Return distinct fare observations ordered by their source observation time."""
    initialize_database()
    connection = get_connection()
    try:
        rows = connection.execute(
            """SELECT * FROM multi_leg_fare_observations
               WHERE departure_airport=? AND arrival_airport=? AND departure_date=?
               ORDER BY source_fetched_at ASC, id ASC""",
            (departure_airport, arrival_airport, departure_date),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def get_multi_leg_google_insights(departure_airport: str, arrival_airport: str,
                                  departure_date: str) -> list[Dict[str, Any]]:
    """Return snapshots whose queried airport groups include this exact route."""
    initialize_database()
    connection = get_connection()
    try:
        rows = connection.execute(
            """SELECT * FROM multi_leg_google_insights WHERE departure_date=?
               ORDER BY COALESCE(source_fetched_at, recorded_at), id""",
            (departure_date,),
        ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            if (departure_airport in item["departure_id"].split(",") and
                    arrival_airport in item["arrival_id"].split(",")):
                result.append(item)
        return result
    finally:
        connection.close()


# ==========================================
# CREATE SEARCH RUN
# ==========================================

def create_search_run(
    origin: str,
    destination: str,
    start_date: str,
    end_date: str,
    min_trip_days: int,
    max_trip_days: int,
    api_budget: int,
) -> int:
    """
    Create a new search run record.

    Returns:
        The database ID of the newly created search run.
    """

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO search_runs (
                searched_at,
                origin,
                destination,
                start_date,
                end_date,
                min_trip_days,
                max_trip_days,
                api_budget
            )
            VALUES (
                CURRENT_TIMESTAMP,
                ?, ?, ?, ?, ?, ?, ?
            ) RETURNING id
            """,
            (
                origin,
                destination,
                start_date,
                end_date,
                min_trip_days,
                max_trip_days,
                api_budget,
            ),
        )

        run_id = cursor.fetchone()[0]
        connection.commit()

        return run_id

    finally:
        connection.close()


# ==========================================
# SAVE FLIGHT RESULT
# ==========================================

def save_flight_result(
    search_run_id: int,
    result: Dict[str, Any],
) -> int:
    """
    Save one normalized flight result.

    Returns:
        The database ID of the newly created flight result.
    """

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO flight_results (
                search_run_id,
                departure_airport,
                arrival_airport,
                departure_date,
                return_date,
                price,
                currency,
                duration_minutes,
                stops,
                airline,
                price_score,
                duration_score,
                stops_score,
                convenience_score,
                final_score
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id
            """,
            (
                search_run_id,
                result.get("departure_airport"),
                result.get("arrival_airport"),
                result.get("departure_date"),
                result.get("return_date"),
                result.get("price"),
                result.get("currency", "INR"),
                result.get("duration"),
                result.get("stops"),
                result.get("airline"),
                result.get("price_score"),
                result.get("duration_score"),
                result.get("stops_score"),
                result.get("convenience_score"),
                result.get("final_score"),
            ),
        )

        result_id = cursor.fetchone()[0]
        connection.commit()

        return result_id

    finally:
        connection.close()


# ==========================================
# UPDATE SEARCH RUN STATISTICS
# ==========================================

def update_search_run_statistics(
    search_run_id: int,
    statistics: Dict[str, Any],
) -> None:
    """
    Update a search run with final search statistics.
    """

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            UPDATE search_runs
            SET
                total_searches = ?,
                successful_api_searches = ?,
                priced_results = ?,
                no_price_searches = ?,
                failed_api_searches = ?
            WHERE id = ?
            """,
            (
                statistics.get("total_searches"),
                statistics.get("successful_api_searches"),
                statistics.get("priced_results"),
                statistics.get("no_price_searches"),
                statistics.get("failed_api_searches"),
                search_run_id,
            ),
        )

        connection.commit()

    finally:
        connection.close()

def get_latest_search_run():
    """
    Return the most recent search run, or None if the table is empty.
    """

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT *
            FROM search_runs
            ORDER BY id DESC
            LIMIT 1
            """
        )

        row = cursor.fetchone()

        return dict(row) if row else None

    finally:
        connection.close()


def get_flight_results_for_search_run(search_run_id: int):
    """
    Return all flight results for a given search run.
    """

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT *
            FROM flight_results
            WHERE search_run_id = ?
            ORDER BY id ASC
            """,
            (search_run_id,),
        )

        rows = cursor.fetchall()

        return [dict(row) for row in rows]

    finally:
        connection.close()

def update_flight_result_scores(
    flight_result_id: int,
    scores: dict,
) -> None:
    """
    Update score columns for one saved flight result.
    """

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            UPDATE flight_results
            SET
                price_score = ?,
                duration_score = ?,
                stops_score = ?,
                convenience_score = ?,
                final_score = ?
            WHERE id = ?
            """,
            (
                scores.get("price_score"),
                scores.get("duration_score"),
                scores.get("stops_score"),
                scores.get("convenience_score"),
                scores.get("final_score"),
                flight_result_id,
            ),
        )

        connection.commit()

    finally:
        connection.close()

# ==========================================
# SCRIPT ENTRY POINT
# ==========================================

if __name__ == "__main__":

    initialize_database()

    print("=" * 70)
    print("DATABASE INITIALIZED")
    print("=" * 70)
    print(f"Database: {DATABASE_PATH}")
    print("Tables created:")
    print("  - search_runs")
    print("  - flight_results")
    print("=" * 70)
