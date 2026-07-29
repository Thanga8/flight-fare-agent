from flight_search.airports import (
    get_airports,
)

from utils.dates import (
    generate_date_combinations,
    sample_date_combinations,
)


_HISTORY_SCOPE_WEIGHTS = {
    "exact_dates": 1.0,
    "nearby_dates": 0.85,
    "same_month": 0.70,
    "airport_pair": 0.50,
    "none": 0.0,
}


def _historical_priority_score(candidate):
    """Return a simple, explainable score for historical evidence."""

    average_price = candidate.get("historical_average_price")
    observation_count = candidate.get("historical_observation_count", 0)

    if not average_price or observation_count <= 0:
        return 0.0

    confidence = min(observation_count, 5) / 5
    recency_days = candidate.get("historical_recency_days")
    recency = 1.0 if recency_days is None else max(0.25, 1 - recency_days / 365)
    scope = _HISTORY_SCOPE_WEIGHTS.get(
        candidate.get("historical_comparison_level"), 0.0
    )

    return (100000 / average_price) * confidence * recency * scope


def create_historical_initial_search_plan(
    historical_candidates,
    max_api_calls,
    exploration_reserve=1,
):
    """Plan Phase 1 using history while retaining explicit exploration.

    The best-supported candidates receive the non-exploration allocation.
    At least one lower-evidence candidate is retained whenever the budget and
    candidate pool permit it.  No API or database work occurs here.
    """

    if max_api_calls <= 0 or not historical_candidates:
        return []

    candidates = []
    for candidate in historical_candidates:
        item = dict(candidate)
        item["historical_priority_score"] = _historical_priority_score(item)
        candidates.append(item)

    target = min(max_api_calls, len(candidates))
    reserve = min(exploration_reserve, target)
    if target == 1:
        reserve = 1

    ranked = sorted(
        candidates,
        key=lambda item: (
            -item["historical_priority_score"],
            item["departure_airport"],
            item["arrival_airport"],
            item["departure_date"],
            item["return_date"],
        ),
    )
    supported_candidates = [
        item for item in ranked
        if item["historical_priority_score"] > 0
    ]
    # Do not label an arbitrary no-history candidate as historical merely
    # because budget remains after reserving exploration.
    historical_budget = min(target - reserve, len(supported_candidates))
    selected = ranked[:historical_budget]
    selected_keys = {
        (item["departure_airport"], item["arrival_airport"], item["departure_date"], item["return_date"])
        for item in selected
    }

    exploration_pool = [
        item for item in reversed(ranked)
        if (item["departure_airport"], item["arrival_airport"], item["departure_date"], item["return_date"])
        not in selected_keys
    ]
    selected.extend(exploration_pool[:target - historical_budget])

    plan = []
    for item in selected:
        is_exploration = item in exploration_pool[:target - historical_budget]
        plan.append(
            {
                "departure_airport": item["departure_airport"],
                "arrival_airport": item["arrival_airport"],
                "departure_date": item["departure_date"],
                "return_date": item["return_date"],
                "trip_days": item["trip_days"],
                "planning_priority": "exploration" if is_exploration else "historical",
                "planning_reason": (
                    "Reserved exploration candidate."
                    if is_exploration
                    else f"Historical {item['historical_comparison_level']} evidence."
                ),
                "historical_observation_count": item["historical_observation_count"],
                "historical_average_price": item["historical_average_price"],
            }
        )

    return plan


def create_search_plan(
    departure_id: str,
    arrival_id: str,
    start_date: str,
    end_date: str,
    min_trip_days: int,
    max_trip_days: int,
    max_api_calls: int,
):
    """
    Create a search plan that respects
    the total API call budget.

    The returned plan contains no API calls.
    It only determines what should be searched.
    """

    if max_api_calls <= 0:
        return []

    # ==========================================
    # GET AIRPORTS
    # ==========================================

    departure_airports = get_airports(
        departure_id
    )

    arrival_airports = get_airports(
        arrival_id
    )

    # ==========================================
    # GENERATE DATE COMBINATIONS
    # ==========================================

    date_combinations = (
        generate_date_combinations(

            start_date=start_date,

            end_date=end_date,

            min_trip_days=min_trip_days,

            max_trip_days=max_trip_days,
        )
    )

    if not date_combinations:
        return []

    # ==========================================
    # CREATE AIRPORT PAIRS
    # ==========================================

    airport_pairs = []

    for departure_airport in (
        departure_airports
    ):

        for arrival_airport in (
            arrival_airports
        ):

            airport_pairs.append(
                {
                    "departure_airport":
                        departure_airport,

                    "arrival_airport":
                        arrival_airport,
                }
            )

    if not airport_pairs:
        return []

    # ==========================================
    # DETERMINE SEARCH ALLOCATION
    # ==========================================

    number_of_pairs = len(
        airport_pairs
    )

    base_allocation = (
        max_api_calls
        // number_of_pairs
    )

    remainder = (
        max_api_calls
        % number_of_pairs
    )

    search_plan = []

    # ==========================================
    # ALLOCATE SEARCHES
    # ==========================================

    for index, pair in enumerate(
        airport_pairs
    ):

        allocation = base_allocation

        # Distribute leftover searches
        # to the first few airport pairs.
        if index < remainder:
            allocation += 1

        # Don't request more dates than
        # actually exist.
        allocation = min(
            allocation,
            len(date_combinations),
        )

        selected_dates = (
            sample_date_combinations(

                combinations=(
                    date_combinations
                ),

                sample_size=allocation,
            )
        )

        for combination in (
            selected_dates
        ):

            search_plan.append(
                {
                    "departure_airport":
                        pair[
                            "departure_airport"
                        ],

                    "arrival_airport":
                        pair[
                            "arrival_airport"
                        ],

                    "departure_date":
                        combination[
                            "departure_date"
                        ],

                    "return_date":
                        combination[
                            "return_date"
                        ],

                    "trip_days":
                        combination[
                            "trip_days"
                        ],
                }
            )

    return search_plan

def create_initial_search_plan(
    departure_id: str,
    arrival_id: str,
    start_date: str,
    end_date: str,
    min_trip_days: int,
    max_trip_days: int,
    max_api_calls: int,
):
    """
    Create the first exploration batch.

    The initial budget is distributed evenly
    across available airport pairs.
    """

    if max_api_calls <= 0:
        return []

    departure_airports = get_airports(
        departure_id
    )

    arrival_airports = get_airports(
        arrival_id
    )

    date_combinations = (
        generate_date_combinations(
            start_date=start_date,
            end_date=end_date,
            min_trip_days=min_trip_days,
            max_trip_days=max_trip_days,
        )
    )

    if not date_combinations:
        return []

    airport_pairs = []

    for departure_airport in departure_airports:

        for arrival_airport in arrival_airports:

            airport_pairs.append(
                {
                    "departure_airport":
                        departure_airport,

                    "arrival_airport":
                        arrival_airport,
                }
            )

    if not airport_pairs:
        return []

    number_of_pairs = len(
        airport_pairs
    )

    allocation = max(
        1,
        max_api_calls
        // number_of_pairs,
    )

    search_plan = []

    for pair in airport_pairs:

        selected_dates = (
            sample_date_combinations(
                combinations=date_combinations,
                sample_size=allocation,
            )
        )

        for combination in selected_dates:

            search_plan.append(
                {
                    "departure_airport":
                        pair[
                            "departure_airport"
                        ],

                    "arrival_airport":
                        pair[
                            "arrival_airport"
                        ],

                    "departure_date":
                        combination[
                            "departure_date"
                        ],

                    "return_date":
                        combination[
                            "return_date"
                        ],

                    "trip_days":
                        combination[
                            "trip_days"
                        ],
                }
            )

            if len(search_plan) >= max_api_calls:
                return search_plan

    return search_plan

def create_adaptive_search_plan(
    date_combinations,
    airport_rankings,
    already_searched,
    remaining_api_calls,
):
    """
    Create the second-stage adaptive search plan.

    The remaining API budget is distributed across
    airport pairs based on their observed prices.

    Cheaper airport pairs receive priority.

    The function guarantees that:
    - Already searched date combinations are excluded.
    - The API budget is never exceeded.
    - The available budget is used whenever enough
      unique search combinations exist.
    """

    if (
        remaining_api_calls <= 0
        or not date_combinations
    ):
        return []

    search_plan = []

    # ==========================================
    # TRACK ALREADY SEARCHED COMBINATIONS
    # ==========================================

    searched_dates = {}

    for search in already_searched:

        pair = (
            search["departure_airport"],
            search["arrival_airport"],
        )

        date_key = (
            search["departure_date"],
            search["return_date"],
        )

        if pair not in searched_dates:

            searched_dates[pair] = set()

        searched_dates[pair].add(
            date_key
        )

    # ==========================================
    # BUILD AIRPORT PAIR LIST
    # ==========================================

    airport_pairs = []

    for ranking in airport_rankings:

        pair = (
            ranking["departure_airport"],
            ranking["arrival_airport"],
        )

        airport_pairs.append(
            {
                "departure_airport":
                    ranking[
                        "departure_airport"
                    ],

                "arrival_airport":
                    ranking[
                        "arrival_airport"
                    ],

                "price":
                    ranking["price"],
            }
        )

    # ==========================================
    # BUILD AVAILABLE DATES PER AIRPORT
    # ==========================================

    available_by_pair = {}

    for airport_pair in airport_pairs:

        departure_airport = (
            airport_pair[
                "departure_airport"
            ]
        )

        arrival_airport = (
            airport_pair[
                "arrival_airport"
            ]
        )

        pair = (
            departure_airport,
            arrival_airport,
        )

        already_searched_dates = (
            searched_dates.get(
                pair,
                set(),
            )
        )

        available_dates = [

            combination

            for combination
            in date_combinations

            if (
                combination[
                    "departure_date"
                ],
                combination[
                    "return_date"
                ],
            )
            not in already_searched_dates

        ]

        if available_dates:

            available_by_pair[pair] = (
                available_dates
            )

    if not available_by_pair:
        return []

    # ==========================================
    # DETERMINE TOTAL AVAILABLE SEARCHES
    # ==========================================

    total_available_searches = sum(

        len(dates)

        for dates
        in available_by_pair.values()

    )

    target_searches = min(
        remaining_api_calls,
        total_available_searches,
    )

    if target_searches <= 0:
        return []

    # ==========================================
    # ADAPTIVE ALLOCATION
    # ==========================================
    #
    # Give more budget to cheaper airports.
    #
    # Example:
    #
    # DME = £40,000
    # SVO = £45,000
    # VKO = £50,000
    #
    # DME receives the largest share.
    #
    # ==========================================

    number_of_pairs = len(
        available_by_pair
    )

    # Base allocation ensures that each
    # promising airport gets a chance.
    base_allocation = (
        target_searches
        // number_of_pairs
    )

    remainder = (
        target_searches
        % number_of_pairs
    )

    allocated = {}

    for index, airport_pair in enumerate(
        airport_pairs
    ):

        pair = (
            airport_pair[
                "departure_airport"
            ],
            airport_pair[
                "arrival_airport"
            ],
        )

        if pair not in available_by_pair:
            continue

        allocation = base_allocation

        if index < remainder:

            allocation += 1

        allocation = min(
            allocation,
            len(
                available_by_pair[
                    pair
                ]
            ),
        )

        allocated[pair] = allocation

    # ==========================================
    # REDISTRIBUTE UNUSED BUDGET
    # ==========================================
    #
    # Some airport pairs may not have enough
    # unique dates for their allocation.
    #
    # Give unused calls to other promising
    # airport pairs.
    #
    # ==========================================

    allocated_total = sum(
        allocated.values()
    )

    remaining_to_allocate = (
        target_searches
        - allocated_total
    )

    while remaining_to_allocate > 0:

        allocation_made = False

        for airport_pair in airport_pairs:

            pair = (
                airport_pair[
                    "departure_airport"
                ],
                airport_pair[
                    "arrival_airport"
                ],
            )

            if pair not in available_by_pair:
                continue

            current_allocation = (
                allocated.get(
                    pair,
                    0,
                )
            )

            available_count = len(
                available_by_pair[
                    pair
                ]
            )

            if (
                current_allocation
                >= available_count
            ):
                continue

            allocated[pair] = (
                current_allocation
                + 1
            )

            remaining_to_allocate -= 1

            allocation_made = True

            if remaining_to_allocate <= 0:
                break

        if not allocation_made:
            break

    # ==========================================
    # CREATE FINAL SEARCH PLAN
    # ==========================================

    for airport_pair in airport_pairs:

        pair = (
            airport_pair[
                "departure_airport"
            ],
            airport_pair[
                "arrival_airport"
            ],
        )

        allocation = allocated.get(
            pair,
            0,
        )

        if allocation <= 0:
            continue

        available_dates = (
            available_by_pair[
                pair
            ]
        )

        selected_dates = (
            sample_date_combinations(
                combinations=(
                    available_dates
                ),
                sample_size=allocation,
            )
        )

        for combination in selected_dates:

            search_plan.append(
                {
                    "departure_airport":
                        pair[0],

                    "arrival_airport":
                        pair[1],

                    "departure_date":
                        combination[
                            "departure_date"
                        ],

                    "return_date":
                        combination[
                            "return_date"
                        ],

                    "trip_days":
                        combination[
                            "trip_days"
                        ],
                }
            )

    # ==========================================
    # FINAL SAFETY CHECK
    # ==========================================

    assert (
        len(search_plan)
        <= remaining_api_calls
    ), (
        "Adaptive search plan exceeds "
        "remaining API budget."
    )

    return search_plan
