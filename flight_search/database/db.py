import sqlite3
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any


# ==========================================
# DATABASE CONFIGURATION
# ==========================================

DATABASE_DIR = Path("data")
DATABASE_PATH = DATABASE_DIR / "flights.db"


# ==========================================
# DATABASE CONNECTION
# ==========================================

def get_connection():
    """
    Create and return a SQLite database connection.
    """

    DATABASE_DIR.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DATABASE_PATH)

    connection.row_factory = sqlite3.Row

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
    cursor.executescript("""
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
    """)

    connection.commit()

    connection.close()


def persist_multi_leg_search(*, run: Dict[str, Any], fares: list[Dict[str, Any]],
                             outcomes: list[Dict[str, Any]], comparisons: list[Dict[str, Any]]) -> int:
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
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (recorded_at, run["start_date"], run["end_date"], run["nights"],
                 run["leg1_origin"], run["leg1_destination"], run["leg2_origin"], run["leg2_destination"],
                 run["leg1_cache_mode"], run["leg2_cache_mode"], run["combined_cache_mode"],
                 run["serpapi_budget"], run["serpapi_calls"], int(run["budget_limited"]),
                 json.dumps(run["statistics"], ensure_ascii=False, sort_keys=True)),
            )
            run_id = cursor.lastrowid
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
        return run_id
    finally:
        connection.close()


def get_multi_leg_historical_prices(departure_airport: str, arrival_airport: str,
                                    departure_date: str) -> list[Dict[str, Any]]:
    """Return distinct fare observations ordered by their source observation time."""
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
            )
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

        connection.commit()

        return cursor.lastrowid

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
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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

        connection.commit()

        return cursor.lastrowid

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
