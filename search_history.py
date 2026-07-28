import sqlite3

from flight_search.database.db import get_connection


# ==========================================
# SEARCH HISTORY
# ==========================================

def get_search_history():
    """
    Return all previous search runs.

    Results are ordered from newest
    search to oldest search.
    """

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            id,
            searched_at,
            origin,
            destination,
            start_date,
            end_date,
            min_trip_days,
            max_trip_days,
            api_budget,
            total_searches,
            successful_api_searches,
            priced_results,
            no_price_searches,
            failed_api_searches
        FROM search_runs
        ORDER BY searched_at DESC
        """
    )

    rows = cursor.fetchall()

    connection.close()

    return [dict(row) for row in rows]


# ==========================================
# FLIGHT RESULTS FOR A SEARCH
# ==========================================

def get_results_for_search(
    search_run_id: int,
):
    """
    Return all flight results belonging
    to a specific search run.
    """

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            id,
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
        FROM flight_results
        WHERE search_run_id = ?
        ORDER BY price ASC
        """,
        (search_run_id,),
    )

    rows = cursor.fetchall()

    connection.close()

    return [dict(row) for row in rows]


# ==========================================
# HISTORICAL CHEAPEST PRICE
# ==========================================

def get_historical_cheapest(
    origin: str,
    destination: str,
):
    """
    Find the cheapest flight ever recorded
    for a specific route.
    """

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            flight_results.*,
            search_runs.searched_at
        FROM flight_results
        JOIN search_runs
            ON flight_results.search_run_id
            = search_runs.id
        WHERE
            departure_airport = ?
            AND arrival_airport = ?
        ORDER BY price ASC
        LIMIT 1
        """,
        (
            origin,
            destination,
        ),
    )

    row = cursor.fetchone()

    connection.close()

    if row is None:
        return None

    return dict(row)


# ==========================================
# HISTORICAL PRICE FOR SPECIFIC DATES
# ==========================================

def get_historical_price_for_dates(
    origin: str,
    destination: str,
    departure_date: str,
    return_date: str,
):
    """
    Find all historical prices recorded for
    the exact same route and travel dates.
    """

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            flight_results.*,
            search_runs.searched_at
        FROM flight_results
        JOIN search_runs
            ON flight_results.search_run_id
            = search_runs.id
        WHERE
            departure_airport = ?
            AND arrival_airport = ?
            AND departure_date = ?
            AND return_date = ?
        ORDER BY
            searched_at ASC
        """,
        (
            origin,
            destination,
            departure_date,
            return_date,
        ),
    )

    rows = cursor.fetchall()

    connection.close()

    return [dict(row) for row in rows]


# ==========================================
# ROUTE PRICE HISTORY
# ==========================================

def get_route_price_history(
    origin: str,
    destination: str,
):
    """
    Return historical prices for a route.

    Useful for identifying whether prices
    are increasing or decreasing over time.
    """

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            flight_results.departure_date,
            flight_results.return_date,
            flight_results.price,
            flight_results.currency,
            flight_results.airline,
            flight_results.final_score,
            search_runs.searched_at
        FROM flight_results
        JOIN search_runs
            ON flight_results.search_run_id
            = search_runs.id
        WHERE
            flight_results.departure_airport = ?
            AND flight_results.arrival_airport = ?
        ORDER BY
            search_runs.searched_at ASC
        """,
        (
            origin,
            destination,
        ),
    )

    rows = cursor.fetchall()

    connection.close()

    return [dict(row) for row in rows]


# ==========================================
# LATEST SEARCH
# ==========================================

def get_latest_search():
    """
    Return the most recent search run.
    """

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM search_runs
        ORDER BY searched_at DESC
        LIMIT 1
        """
    )

    row = cursor.fetchone()

    connection.close()

    if row is None:
        return None

    return dict(row)

# ==========================================
# SEARCH ROUTE PRICE HISTORY
# ==========================================

def get_search_route_price_history(
    origin,
    destination,
    limit=10,
):
    """
    Return the most recent historical flight
    price observations for a requested search route.

    The requested route is matched against
    search_runs, allowing city-level destinations
    such as MOW to contain actual airport results
    such as SVO and DME.

    Results are ordered from newest search
    to oldest search.
    """

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            flight_results.departure_airport,
            flight_results.arrival_airport,
            flight_results.departure_date,
            flight_results.return_date,
            flight_results.price,
            flight_results.currency,
            flight_results.airline,
            flight_results.final_score,
            search_runs.searched_at

        FROM flight_results

        JOIN search_runs
            ON flight_results.search_run_id
            = search_runs.id

        WHERE
            search_runs.origin = ?
            AND search_runs.destination = ?

        ORDER BY
            search_runs.searched_at DESC,
            flight_results.price ASC

        LIMIT ?
        """,
        (
            origin,
            destination,
            limit,
        ),
    )

    rows = cursor.fetchall()

    connection.close()

    return [
        dict(row)
        for row in rows
    ]
# ==========================================
# PREVIOUS SEARCH CHEAPEST PRICE
# ==========================================

def get_previous_search_cheapest_price(
    origin,
    destination,
):
    """
    Return the cheapest recorded fare from
    the immediately previous search for the
    same search route.

    The current/latest search is excluded.

    Returns None if there is no previous search.
    """

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            sr.id AS search_run_id,
            sr.searched_at,
            MIN(fr.price) AS cheapest_price

        FROM search_runs sr

        JOIN flight_results fr
            ON fr.search_run_id = sr.id

        WHERE
            sr.origin = ?
            AND sr.destination = ?

        GROUP BY
            sr.id,
            sr.searched_at

        ORDER BY
            sr.searched_at DESC

        LIMIT 2
        """,
        (
            origin,
            destination,
        ),
    )

    rows = cursor.fetchall()

    connection.close()

    # ==========================================
    # NEED AT LEAST TWO SEARCHES
    # ==========================================

    if len(rows) < 2:
        return None

    # First row = current/latest search
    # Second row = previous search

    previous_search = rows[1]

    return {
        "search_run_id":
            previous_search["search_run_id"],

        "searched_at":
            previous_search["searched_at"],

        "cheapest_price":
            previous_search["cheapest_price"],
    }

# ==========================================
# COMPARE WITH PREVIOUS SEARCH
# ==========================================

def compare_with_previous_search(
    origin,
    destination,
    current_price,
):
    """
    Compare the current cheapest fare with
    the cheapest fare from the immediately
    previous search for the same route.
    """

    previous_search = (
        get_previous_search_cheapest_price(
            origin=origin,
            destination=destination,
        )
    )

    # ==========================================
    # NO PREVIOUS SEARCH
    # ==========================================

    if previous_search is None:

        return {
            "comparison_available": False,

            "current_price":
                current_price,

            "previous_price":
                None,

            "price_difference":
                None,

            "price_difference_percent":
                None,

            "price_direction":
                "NO_PREVIOUS_SEARCH",

            "previous_searched_at":
                None,

            "previous_search_run_id":
                None,
        }

    previous_price = (
        previous_search["cheapest_price"]
    )

    # ==========================================
    # CALCULATE PRICE DIFFERENCE
    # ==========================================

    price_difference = (
        current_price
        - previous_price
    )

    price_difference_percent = (
        price_difference
        / previous_price
        * 100
    )

    # ==========================================
    # DETERMINE PRICE DIRECTION
    # ==========================================

    if current_price < previous_price:

        price_direction = "CHEAPER"

    elif current_price > previous_price:

        price_direction = "EXPENSIVE"

    else:

        price_direction = "UNCHANGED"

    # ==========================================
    # RETURN COMPARISON
    # ==========================================

    return {

        "comparison_available":
            True,

        "current_price":
            current_price,

        "previous_price":
            previous_price,

        "price_difference":
            price_difference,

        "price_difference_percent":
            round(
                price_difference_percent,
                2,
            ),

        "price_direction":
            price_direction,

        "previous_searched_at":
            previous_search["searched_at"],

        "previous_search_run_id":
            previous_search["search_run_id"],
    }

# ==========================================
# CHEAPEST FARE FOR SEARCH ROUTE
# ==========================================

def get_cheapest_for_search_route(
    origin,
    destination,
):
    """
    Find the cheapest flight ever recorded
    for a requested search route.

    The requested route is matched against
    search_runs, allowing city-level destinations
    such as MOW to contain actual airport results
    such as SVO and DME.
    """

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            flight_results.*,
            search_runs.searched_at,
            search_runs.origin AS search_origin,
            search_runs.destination AS search_destination

        FROM flight_results

        JOIN search_runs
            ON flight_results.search_run_id
            = search_runs.id

        WHERE
            search_runs.origin = ?
            AND search_runs.destination = ?

        ORDER BY
            flight_results.price ASC

        LIMIT 1
        """,
        (
            origin,
            destination,
        ),
    )

    row = cursor.fetchone()

    connection.close()

    if row is None:
        return None

    return dict(row)

# ==========================================
# LATEST FLIGHT RESULTS
# ==========================================

def get_latest_results():
    """
    Return flight results from the latest
    search run.
    """

    latest_search = get_latest_search()

    if latest_search is None:
        return []

    return get_results_for_search(
        search_run_id=latest_search["id"]
    )

def get_historical_price_statistics(
    origin,
    destination,
):
    """
    Calculate historical price statistics
    for a specific airport route.
    """

    history = get_route_price_history(
        origin=origin,
        destination=destination,
    )

    if not history:
        return None

    prices = [
        result["price"]
        for result in history
        if result.get("price") is not None
    ]

    if not prices:
        return None

    prices.sort()

    count = len(prices)

    lowest_price = min(prices)

    highest_price = max(prices)

    average_price = (
        sum(prices) / count
    )

    # Calculate median
    middle = count // 2

    if count % 2 == 0:

        median_price = (
            prices[middle - 1]
            + prices[middle]
        ) / 2

    else:

        median_price = prices[middle]

    return {
        "origin": origin,

        "destination": destination,

        "observation_count": count,

        "lowest_price": lowest_price,

        "highest_price": highest_price,

        "average_price": average_price,

        "median_price": median_price,

    }

def get_comparable_historical_prices(
    origin,
    destination,
    departure_date,
    return_date,
):
    """
    Find historical flight prices that are
    comparable to the requested travel dates.

    Comparison priority:

    1. Exact departure + return date
    2. Departure within +/- 3 days
       and trip duration within +/- 1 day
    3. Same departure month
       and trip duration within +/- 1 day
    4. Route-wide historical data
    """

    from datetime import datetime, timedelta

    connection = get_connection()

    # ==========================================
    # CONVERT REQUESTED DATES
    # ==========================================

    requested_departure = datetime.strptime(
        departure_date,
        "%Y-%m-%d",
    )

    requested_return = datetime.strptime(
        return_date,
        "%Y-%m-%d",
    )

    requested_trip_days = (
        requested_return
        - requested_departure
    ).days

    requested_month = (
        requested_departure.month
    )

    # ==========================================
    # GET HISTORICAL RESULTS
    # ==========================================

    cursor = connection.execute(
        """
        SELECT
            flight_results.*,
            search_runs.searched_at

        FROM flight_results

        JOIN search_runs
            ON flight_results.search_run_id =
               search_runs.id

        WHERE
            flight_results.departure_airport = ?

            AND

            flight_results.arrival_airport = ?

        ORDER BY
            search_runs.searched_at DESC
        """,
        (
            origin,
            destination,
        ),
    )

    rows = cursor.fetchall()

    connection.close()

    if not rows:

        return {
            "comparison_level": "none",
            "results": [],
        }

    # ==========================================
    # CONVERT SQLITE ROWS
    # ==========================================

    historical_results = [
        dict(row)
        for row in rows
    ]

    # ==========================================
    # LEVEL 1
    # EXACT DATE MATCH
    # ==========================================

    exact_matches = [

        result

        for result in historical_results

        if (
            result["departure_date"]
            == departure_date
        )

        and

        (
            result["return_date"]
            == return_date
        )
    ]

    if exact_matches:

        return {
            "comparison_level":
                "exact_dates",

            "results":
                exact_matches,
        }

    # ==========================================
    # PREPARE HISTORICAL DATE DATA
    # ==========================================

    for result in historical_results:

        historical_departure = (
            datetime.strptime(
                result["departure_date"],
                "%Y-%m-%d",
            )
        )

        historical_return = (
            datetime.strptime(
                result["return_date"],
                "%Y-%m-%d",
            )
        )

        historical_trip_days = (
            historical_return
            - historical_departure
        ).days

        result[
            "_departure_date_obj"
        ] = historical_departure

        result[
            "_return_date_obj"
        ] = historical_return

        result[
            "_trip_days"
        ] = historical_trip_days

    # ==========================================
    # LEVEL 2
    # NEARBY DEPARTURE
    # + SIMILAR TRIP DURATION
    # ==========================================

    nearby_start = (
        requested_departure
        - timedelta(days=3)
    )

    nearby_end = (
        requested_departure
        + timedelta(days=3)
    )

    nearby_matches = [

        result

        for result in historical_results

        if (

            nearby_start
            <= result[
                "_departure_date_obj"
            ]
            <= nearby_end

        )

        and (

            abs(
                result[
                    "_trip_days"
                ]
                -
                requested_trip_days
            )
            <= 1

        )
    ]

    if nearby_matches:

        return {
            "comparison_level":
                "nearby_dates_similar_duration",

            "results":
                nearby_matches,
        }

    # ==========================================
    # LEVEL 3
    # SAME MONTH
    # + SIMILAR TRIP DURATION
    # ==========================================

    same_month_matches = [

        result

        for result in historical_results

        if (

            result[
                "_departure_date_obj"
            ].month

            == requested_month

        )

        and (

            abs(
                result[
                    "_trip_days"
                ]
                -
                requested_trip_days
            )
            <= 1

        )
    ]

    if same_month_matches:

        return {
            "comparison_level":
                "same_month_similar_duration",

            "results":
                same_month_matches,
        }

    # ==========================================
    # LEVEL 4
    # ROUTE-WIDE HISTORY
    # ==========================================

    return {
        "comparison_level":
            "route_wide",

        "results":
            historical_results,
    }

# ==========================================
# COMPARE PRICE WITH COMPARABLE HISTORY
# ==========================================

def compare_price_with_comparable_history(
    origin,
    destination,
    departure_date,
    return_date,
    current_price,
):
    """
    Compare the current flight price against
    the best available level of historical data.

    Comparison hierarchy:

    1. Exact travel dates
    2. Nearby departure dates + similar trip duration
    3. Same departure month + similar trip duration
    4. Route-wide historical data

    Returns the comparison level used so the
    caller knows how relevant the historical
    comparison is.
    """

    from datetime import datetime

    # ==========================================
    # CALCULATE TRIP DURATION
    # ==========================================

    departure = datetime.strptime(
        departure_date,
        "%Y-%m-%d",
    )

    return_date_obj = datetime.strptime(
        return_date,
        "%Y-%m-%d",
    )

    trip_days = (
        return_date_obj - departure
    ).days

    # ==========================================
    # GET COMPARABLE HISTORICAL RESULTS
    # ==========================================

    comparable_history = (
        get_comparable_historical_prices(

            origin=origin,

            destination=destination,

            departure_date=departure_date,

            return_date=return_date,

        )
    )

    comparison_level = (
        comparable_history[
            "comparison_level"
        ]
    )

    historical_results = (
        comparable_history[
            "results"
        ]
    )

    # ==========================================
    # NO HISTORICAL DATA
    # ==========================================

    if not historical_results:

        return {

            "origin":
                origin,

            "destination":
                destination,

            "departure_date":
                departure_date,

            "return_date":
                return_date,

            "trip_days":
                trip_days,

            "current_price":
                current_price,

            "comparison_level":
                "none",

            "historical_low":
                None,

            "historical_high":
                None,

            "historical_average":
                None,

            "historical_count":
                0,

            "difference_from_low_percent":
                None,

            "difference_from_average_percent":
                None,

            "assessment":
                "NO_HISTORICAL_DATA",

            "confidence":
                "NONE",

        }

    # ==========================================
    # EXTRACT HISTORICAL PRICES
    # ==========================================

    prices = [

        result["price"]

        for result in historical_results

        if result.get("price") is not None

    ]

    if not prices:

        return {

            "comparison_level":
                comparison_level,

            "historical_count":
                0,

            "assessment":
                "NO_HISTORICAL_DATA",

            "confidence":
                "NONE",

        }

    # ==========================================
    # CALCULATE STATISTICS
    # ==========================================

    historical_low = min(prices)

    historical_high = max(prices)

    historical_average = (
        sum(prices)
        / len(prices)
    )

    historical_count = len(prices)

    # ==========================================
    # PRICE DIFFERENCES
    # ==========================================

    difference_from_low_percent = (

        (
            current_price
            - historical_low
        )

        / historical_low

        * 100

    )

    difference_from_average_percent = (

        (
            current_price
            - historical_average
        )

        / historical_average

        * 100

    )

    # ==========================================
    # PRICE ASSESSMENT
    # ==========================================

    if current_price <= historical_low:

        assessment = (
            "NEW_HISTORICAL_LOW"
        )

    elif (
        current_price
        <= historical_average * 0.95
    ):

        assessment = (
            "VERY_GOOD_PRICE"
        )

    elif (
        current_price
        <= historical_average
    ):

        assessment = (
            "GOOD_PRICE"
        )

    elif (
        current_price
        <= historical_average * 1.10
    ):

        assessment = (
            "ABOVE_AVERAGE"
        )

    else:

        assessment = (
            "EXPENSIVE"
        )

    # ==========================================
    # CONFIDENCE
    # ==========================================

    if historical_count >= 10:

        confidence = "HIGH"

    elif historical_count >= 5:

        confidence = "MEDIUM"

    elif historical_count >= 2:

        confidence = "LOW"

    else:

        confidence = "VERY_LOW"

    # ==========================================
    # RETURN RESULT
    # ==========================================

    return {

        "origin":
            origin,

        "destination":
            destination,

        "departure_date":
            departure_date,

        "return_date":
            return_date,

        "trip_days":
            trip_days,

        "current_price":
            current_price,

        "comparison_level":
            comparison_level,

        "historical_low":
            historical_low,

        "historical_high":
            historical_high,

        "historical_average":
            round(
                historical_average,
                2,
            ),

        "historical_count":
            historical_count,

        "difference_from_low_percent":
            round(
                difference_from_low_percent,
                2,
            ),

        "difference_from_average_percent":
            round(
                difference_from_average_percent,
                2,
            ),

        "assessment":
            assessment,

        "confidence":
            confidence,

    }

def compare_price_with_history(
    origin,
    destination,
    departure_date,
    return_date,
    current_price,
):
    """
    Compare the current flight price with
    previously observed prices for the
    same airport pair and exact travel dates.
    """

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            MIN(price) AS historical_low,
            MAX(price) AS historical_high,
            AVG(price) AS historical_average,
            COUNT(*) AS historical_count
        FROM flight_results
        WHERE
            departure_airport = ?
            AND arrival_airport = ?
            AND departure_date = ?
            AND return_date = ?
        """,
        (
            origin,
            destination,
            departure_date,
            return_date,
        ),
    )

    row = cursor.fetchone()

    connection.close()

    # ==========================================
    # NO HISTORICAL DATA
    # ==========================================

    if (
        not row
        or row["historical_count"] == 0
    ):
        return {
            "historical_low": None,
            "historical_high": None,
            "historical_average": None,
            "historical_count": 0,
            "difference_from_low_percent": None,
            "difference_from_average_percent": None,
            "assessment": "NO_HISTORICAL_DATA",
        }

    historical_low = (
        row["historical_low"]
    )

    historical_high = (
        row["historical_high"]
    )

    historical_average = (
        row["historical_average"]
    )

    historical_count = (
        row["historical_count"]
    )

    # ==========================================
    # PRICE DIFFERENCES
    # ==========================================

    difference_from_low_percent = (
        (
            current_price
            - historical_low
        )
        / historical_low
        * 100
    )

    difference_from_average_percent = (
        (
            current_price
            - historical_average
        )
        / historical_average
        * 100
    )

    # ==========================================
    # PRICE ASSESSMENT
    # ==========================================

    if current_price <= historical_low:

        assessment = (
            "NEW_HISTORICAL_LOW"
        )

    elif (
        current_price
        <= historical_average * 0.95
    ):

        assessment = (
            "VERY_GOOD_PRICE"
        )

    elif (
        current_price
        <= historical_average
    ):

        assessment = (
            "GOOD_PRICE"
        )

    elif (
        current_price
        <= historical_average * 1.10
    ):

        assessment = (
            "ABOVE_AVERAGE"
        )

    else:

        assessment = (
            "EXPENSIVE"
        )

    # ==========================================
    # RETURN RESULT
    # ==========================================

    return {
        "historical_low":
            historical_low,

        "historical_high":
            historical_high,

        "historical_average":
            historical_average,

        "historical_count":
            historical_count,

        "difference_from_low_percent":
            round(
                difference_from_low_percent,
                2,
            ),

        "difference_from_average_percent":
            round(
                difference_from_average_percent,
                2,
            ),

        "assessment":
            assessment,
    }

def compare_price_with_route_history(
    origin,
    destination,
    trip_days,
    current_price,
    min_trip_days=None,
    max_trip_days=None,
):
    """
    Compare the current flight price with
    historical prices observed for the same route.

    Historical results are filtered by:

    1. Origin airport/city
    2. Destination airport/city
    3. Trip duration

    If min_trip_days and max_trip_days are provided,
    the historical search will use that duration range.

    This comparison is broader than exact-date history.
    """

    connection = get_connection()

    cursor = connection.cursor()

    # ==========================================
    # DETERMINE TRIP DURATION RANGE
    # ==========================================

    if min_trip_days is None:
        min_trip_days = trip_days

    if max_trip_days is None:
        max_trip_days = trip_days

    # ==========================================
    # ROUTE-LEVEL HISTORICAL SEARCH
    # ==========================================

    cursor.execute(
        """
        SELECT
            MIN(fr.price) AS historical_low,
            MAX(fr.price) AS historical_high,
            AVG(fr.price) AS historical_average,
            COUNT(*) AS historical_count
        FROM flight_results fr
        JOIN search_runs sr
            ON fr.search_run_id = sr.id
        WHERE
            sr.origin = ?
            AND sr.destination = ?
            AND (
                julianday(fr.return_date)
                - julianday(fr.departure_date)
            ) BETWEEN ? AND ?
        """,
        (
            origin,
            destination,
            min_trip_days,
            max_trip_days,
        ),
    )

    row = cursor.fetchone()

    connection.close()

    # ==========================================
    # NO HISTORICAL DATA
    # ==========================================

    if not row or row["historical_count"] == 0:

        return {
            "origin": origin,
            "destination": destination,
            "trip_days": trip_days,

            "historical_low": None,
            "historical_high": None,
            "historical_average": None,
            "historical_count": 0,

            "difference_from_low_percent": None,
            "difference_from_average_percent": None,

            "assessment": "NO_HISTORICAL_DATA",

            "confidence": "NONE",
        }

    # ==========================================
    # EXTRACT HISTORICAL VALUES
    # ==========================================

    historical_low = row["historical_low"]

    historical_high = row["historical_high"]

    historical_average = (
        row["historical_average"]
    )

    historical_count = (
        row["historical_count"]
    )

    # ==========================================
    # CALCULATE PRICE DIFFERENCES
    # ==========================================

    difference_from_low_percent = (
        (
            current_price
            - historical_low
        )
        / historical_low
        * 100
    )

    difference_from_average_percent = (
        (
            current_price
            - historical_average
        )
        / historical_average
        * 100
    )

    # ==========================================
    # PRICE ASSESSMENT
    # ==========================================

    if current_price <= historical_low:

        assessment = (
            "NEW_HISTORICAL_LOW"
        )

    elif (
        current_price
        <= historical_average * 0.95
    ):

        assessment = (
            "VERY_GOOD_PRICE"
        )

    elif (
        current_price
        <= historical_average
    ):

        assessment = (
            "GOOD_PRICE"
        )

    elif (
        current_price
        <= historical_average * 1.10
    ):

        assessment = (
            "ABOVE_AVERAGE"
        )

    else:

        assessment = (
            "EXPENSIVE"
        )

    # ==========================================
    # CONFIDENCE LEVEL
    # ==========================================

    if historical_count >= 10:

        confidence = "HIGH"

    elif historical_count >= 5:

        confidence = "MEDIUM"

    elif historical_count >= 2:

        confidence = "LOW"

    else:

        confidence = "VERY_LOW"

    # ==========================================
    # RETURN ANALYSIS
    # ==========================================

    return {

        "origin":
            origin,

        "destination":
            destination,

        "trip_days":
            trip_days,

        "historical_low":
            historical_low,

        "historical_high":
            historical_high,

        "historical_average":
            round(
                historical_average,
                2,
            ),

        "historical_count":
            historical_count,

        "difference_from_low_percent":
            round(
                difference_from_low_percent,
                2,
            ),

        "difference_from_average_percent":
            round(
                difference_from_average_percent,
                2,
            ),

        "assessment":
            assessment,

        "confidence":
            confidence,
    }

# ==========================================
# COMPLETE PRICE INTELLIGENCE
# ==========================================

def analyze_price_intelligence(
    origin,
    destination,
    departure_date,
    return_date,
    current_price,
):
    """
    Perform complete historical price analysis.

    The system automatically selects the best
    available historical comparison:

    1. Exact travel dates
    2. Nearby dates + similar duration
    3. Same month + similar duration
    4. Route-wide history
    """

    # ==========================================
    # COMPARABLE HISTORY ANALYSIS
    # ==========================================

    historical_analysis = (
        compare_price_with_comparable_history(

            origin=origin,

            destination=destination,

            departure_date=departure_date,

            return_date=return_date,

            current_price=current_price,

        )
    )

    # ==========================================
    # RETURN UNIFIED PRICE INTELLIGENCE
    # ==========================================

    return {

        "route": {

            "origin":
                origin,

            "destination":
                destination,

        },

        "travel": {

            "departure_date":
                departure_date,

            "return_date":
                return_date,

            "trip_days":
                historical_analysis[
                    "trip_days"
                ],

        },

        "current_price":
            current_price,

        "historical_analysis":
            historical_analysis,

    }