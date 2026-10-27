import sqlite3

from flight_search.database.db import DATABASE_PATH, DATABASE_URL

DB_PATH = DATABASE_PATH

def reset_database():
    if DATABASE_URL:
        print("This legacy reset utility is SQLite-only; it refuses to modify PostgreSQL.")
        return
    if not DB_PATH.exists():
        print(f"Database not found: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()

        cur.execute("DROP TABLE IF EXISTS flight_results;")
        cur.execute("DROP TABLE IF EXISTS search_runs;")

        conn.commit()
        print("Dropped tables: flight_results, search_runs")

    finally:
        conn.close()

if __name__ == "__main__":
    reset_database()
