from datetime import datetime

from flight_search.database.db import (
    initialize_database,
    get_connection,
    create_search_run,
    save_flight_result,
)


# ==========================================
# TEST DATABASE PERSISTENCE
# ==========================================

def main():

    print("=" * 70)
    print("DATABASE PERSISTENCE TEST")
    print("=" * 70)

    # ==========================================
    # STEP 1 — INITIALIZE DATABASE
    # ==========================================

    initialize_database()

    print()
    print("Database initialized successfully.")

    # ==========================================
    # STEP 2 — CREATE SEARCH RUN
    # ==========================================

    search_run_id = create_search_run(
        searched_at=datetime.now().isoformat(
            timespec="seconds"
        ),
        origin="HYD",
        destination="SVO",
        start_date="2027-01-20",
        end_date="2027-02-13",
        min_trip_days=5,
        max_trip_days=6,
        api_budget=8,
    )

    print()
    print(f"Search run created successfully.")
    print(f"Search run ID: {search_run_id}")

    # ==========================================
    # STEP 3 — CREATE TEST FLIGHT RESULT
    # ==========================================

    test_result = {
        "departure_airport": "HYD",
        "arrival_airport": "SVO",
        "departure_date": "2027-02-08",
        "return_date": "2027-02-13",
        "price": 67680,
        "currency": "INR",
        "duration": 705,
        "stops": 1,
        "airline": "Qatar Airways",
    }

    flight_result_id = save_flight_result(
        search_run_id=search_run_id,
        result=test_result,
    )

    print()
    print("Flight result saved successfully.")
    print(f"Flight result ID: {flight_result_id}")

    # ==========================================
    # STEP 4 — READ DATA BACK
    # ==========================================

    connection = get_connection()

    try:

        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT *
            FROM search_runs
            WHERE id = ?
            """,
            (search_run_id,),
        )

        search_run = cursor.fetchone()

        cursor.execute(
            """
            SELECT *
            FROM flight_results
            WHERE id = ?
            """,
            (flight_result_id,),
        )

        flight_result = cursor.fetchone()

    finally:

        connection.close()

    # ==========================================
    # STEP 5 — DISPLAY SEARCH RUN
    # ==========================================

    print()
    print("=" * 70)
    print("SAVED SEARCH RUN")
    print("=" * 70)

    if search_run:

        print(f"ID: {search_run['id']}")
        print(
            f"Route: "
            f"{search_run['origin']} → "
            f"{search_run['destination']}"
        )
        print(
            f"Search window: "
            f"{search_run['start_date']} → "
            f"{search_run['end_date']}"
        )
        print(
            f"Trip duration: "
            f"{search_run['min_trip_days']}–"
            f"{search_run['max_trip_days']} days"
        )
        print(
            f"API budget: "
            f"{search_run['api_budget']}"
        )

    else:

        print("ERROR: Search run was not found.")

    # ==========================================
    # STEP 6 — DISPLAY FLIGHT RESULT
    # ==========================================

    print()
    print("=" * 70)
    print("SAVED FLIGHT RESULT")
    print("=" * 70)

    if flight_result:

        print(f"ID: {flight_result['id']}")
        print(
            f"Search run ID: "
            f"{flight_result['search_run_id']}"
        )
        print(
            f"Route: "
            f"{flight_result['departure_airport']} → "
            f"{flight_result['arrival_airport']}"
        )
        print(
            f"Dates: "
            f"{flight_result['departure_date']} → "
            f"{flight_result['return_date']}"
        )
        print(
            f"Price: "
            f"{flight_result['currency']} "
            f"{flight_result['price']:,.0f}"
        )
        print(
            f"Duration: "
            f"{flight_result['duration_minutes']} minutes"
        )
        print(
            f"Stops: "
            f"{flight_result['stops']}"
        )
        print(
            f"Airline: "
            f"{flight_result['airline']}"
        )

    else:

        print("ERROR: Flight result was not found.")

    # ==========================================
    # FINAL RESULT
    # ==========================================

    if search_run and flight_result:

        print()
        print("=" * 70)
        print("DATABASE PERSISTENCE TEST PASSED")
        print("=" * 70)

    else:

        print()
        print("=" * 70)
        print("DATABASE PERSISTENCE TEST FAILED")
        print("=" * 70)


# ==========================================
# SCRIPT ENTRY POINT
# ==========================================

if __name__ == "__main__":
    main()