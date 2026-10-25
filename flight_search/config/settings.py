# ==========================================
# SEARCH CONFIGURATION
# ==========================================

import os

from dotenv import load_dotenv

ORIGIN = "HYD"
DESTINATION = "MOW"

START_DATE = "2027-01-20"
END_DATE = "2027-02-13"

MIN_TRIP_DAYS = 5
MAX_TRIP_DAYS = 6

MAX_SEARCHES = 4


# ==========================================
# EXPERIMENTAL MULTI-CITY ITINERARY
# ==========================================

load_dotenv()

DEFAULT_MULTI_LEG_SERPAPI_BUDGET = 50


def _read_max_web_serpapi_budget(value=None):
    """Read a non-negative web search budget ceiling from the environment value."""
    if value is None:
        value = os.getenv("MAX_WEB_SERPAPI_BUDGET")
    if value is None:
        return 250
    try:
        maximum = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(
            "MAX_WEB_SERPAPI_BUDGET must be a non-negative integer; "
            f"received {value!r}."
        ) from error
    if maximum < 0:
        raise ValueError(
            "MAX_WEB_SERPAPI_BUDGET must be a non-negative integer; "
            f"received {value!r}."
        )
    return maximum


MAX_WEB_SERPAPI_BUDGET = _read_max_web_serpapi_budget()
MULTI_LEG_SERPAPI_BUDGET = min(
    DEFAULT_MULTI_LEG_SERPAPI_BUDGET,
    MAX_WEB_SERPAPI_BUDGET,
)
MULTI_LEG_START_DATE = "2027-02-03"
MULTI_LEG_END_DATE = "2027-03-15"
MULTI_LEG_NIGHTS_BETWEEN_DEPARTURES = 7
MULTI_LEG_LEG1_ORIGIN = "HYD"
MULTI_LEG_LEG1_DESTINATION = "PAR"
MULTI_LEG_LEG2_ORIGIN = "HEL"
MULTI_LEG_LEG2_DESTINATION = "HYD"
MULTI_LEG_COMBINED_CANDIDATE_LIMIT = 3


# ==========================================
# REPORTING
# ==========================================

TOP_RESULTS_TO_SHOW = 10

VERIFY_TOP_RESULTS = 3


# ==========================================
# PRICE INTELLIGENCE
# ==========================================

DEFAULT_HISTORY_WINDOW = 5
