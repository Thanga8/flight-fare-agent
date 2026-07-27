import sqlite3
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

    connection.commit()

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