import sqlite3
from pathlib import Path

DB_PATH = Path("data") / "flights.db"

def reset_database():
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