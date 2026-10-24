from __future__ import annotations

import json
from pathlib import Path
from typing import Any


# ============================================================
# CONFIGURATION
# ============================================================

RAW_SEARCH_DIR = Path("data/raw_searches")

# Replace these with the exact filenames from data/raw_searches.
#
# Example:
#
# EARLIER_FILE = (
#     "raw_HYD_SVO_2027-01-20_2027-01-25_20260728_152350_123456.json"
# )
#
# LATEST_FILE = (
#     "raw_HYD_SVO_2027-01-20_2027-01-25_20260731_112233_123456.json"
# )

EARLIER_FILE = "raw_HYD_SVO_2027-01-20_2027-01-25.json"
LATEST_FILE = "raw_HYD_SVO_2027-01-20_2027-01-25_20260730_220940_189179.json"


# ============================================================
# BASIC HELPERS
# ============================================================

def load_json(filename: str) -> dict[str, Any]:
    """
    Load a raw SerpApi JSON file from data/raw_searches/.
    """

    path = RAW_SEARCH_DIR / filename

    if not path.exists():
        raise FileNotFoundError(
            f"JSON file not found:\n{path}"
        )

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def print_section(title: str) -> None:
    """
    Print a formatted section heading.
    """

    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


def print_subsection(title: str) -> None:
    """
    Print a formatted subsection heading.
    """

    print()
    print("-" * 70)
    print(title)
    print("-" * 70)


def yes_no(value: bool) -> str:
    """
    Convert boolean to readable output.
    """

    return "YES" if value else "NO"


def get_first_result(
    data: dict[str, Any],
) -> dict[str, Any] | None:
    """
    Get the first result from best_flights.

    Google Flights responses normally put the
    cheapest/recommended result in best_flights,
    but this function safely handles missing data.
    """

    best_flights = data.get(
        "best_flights",
        [],
    )

    if not best_flights:
        return None

    return best_flights[0]


def get_all_results(
    data: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Combine best_flights and other_flights
    into one list.

    This is useful for comparing all visible
    itineraries returned by Google Flights.
    """

    results = []

    for key in (
        "best_flights",
        "other_flights",
    ):
        flights = data.get(
            key,
            [],
        )

        if isinstance(flights, list):
            results.extend(
                item
                for item in flights
                if isinstance(item, dict)
            )

    return results


def get_price(
    result: dict[str, Any] | None,
) -> int | float | None:
    """
    Extract itinerary price.
    """

    if not result:
        return None

    price = result.get("price")

    if isinstance(price, (int, float)):
        return price

    return None


# ============================================================
# ITINERARY EXTRACTION
# ============================================================

def extract_segments(
    result: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """
    Extract all flight segments from an itinerary.
    """

    if not result:
        return []

    segments = result.get(
        "flights",
        [],
    )

    if not isinstance(segments, list):
        return []

    return [
        segment
        for segment in segments
        if isinstance(segment, dict)
    ]


def normalize_segment(
    segment: dict[str, Any],
) -> dict[str, Any]:
    """
    Extract only the important fields from
    one flight segment.
    """

    departure = segment.get(
        "departure_airport",
        {},
    )

    arrival = segment.get(
        "arrival_airport",
        {},
    )

    return {
        "airline": segment.get(
            "airline"
        ),
        "flight_number": segment.get(
            "flight_number"
        ),
        "airplane": segment.get(
            "airplane"
        ),
        "departure_id": departure.get(
            "id"
        ),
        "departure_name": departure.get(
            "name"
        ),
        "departure_time": departure.get(
            "time"
        ),
        "arrival_id": arrival.get(
            "id"
        ),
        "arrival_name": arrival.get(
            "name"
        ),
        "arrival_time": arrival.get(
            "time"
        ),
        "duration": segment.get(
            "duration"
        ),
        "overnight": segment.get(
            "overnight"
        ),
    }


def get_normalized_segments(
    result: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """
    Return normalized flight segments.
    """

    return [
        normalize_segment(segment)
        for segment in extract_segments(result)
    ]


def get_layovers(
    result: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """
    Extract layover information.
    """

    if not result:
        return []

    layovers = result.get(
        "layovers",
        [],
    )

    if not isinstance(layovers, list):
        return []

    return [
        {
            "name": layover.get(
                "name"
            ),
            "id": layover.get(
                "id"
            ),
            "duration": layover.get(
                "duration"
            ),
        }
        for layover in layovers
        if isinstance(layover, dict)
    ]


# ============================================================
# ITINERARY DISPLAY
# ============================================================

def print_itinerary(
    label: str,
    result: dict[str, Any] | None,
) -> None:
    """
    Print a readable itinerary summary.
    """

    print_subsection(label)

    if not result:
        print("No itinerary found.")
        return

    print(
        f"Price: ₹{result.get('price', 'Unknown'):,}"
        if isinstance(
            result.get("price"),
            (int, float),
        )
        else f"Price: {result.get('price', 'Unknown')}"
    )

    print(
        f"Type: "
        f"{result.get('type', 'Unknown')}"
    )

    print(
        f"Total duration: "
        f"{result.get('total_duration', 'Unknown')} minutes"
    )

    segments = get_normalized_segments(
        result
    )

    if not segments:
        print("No flight segments found.")
    else:
        print()
        print("Flight segments:")

        for index, segment in enumerate(
            segments,
            start=1,
        ):
            print(
                f"  {index}. "
                f"{segment['departure_id']} "
                f"→ "
                f"{segment['arrival_id']}"
            )

            print(
                f"     Airline: "
                f"{segment['airline']}"
            )

            print(
                f"     Flight: "
                f"{segment['flight_number']}"
            )

            print(
                f"     Departure: "
                f"{segment['departure_time']}"
            )

            print(
                f"     Arrival: "
                f"{segment['arrival_time']}"
            )

            print(
                f"     Aircraft: "
                f"{segment['airplane']}"
            )

            print(
                f"     Duration: "
                f"{segment['duration']} minutes"
            )

    layovers = get_layovers(
        result
    )

    if layovers:
        print()
        print("Layovers:")

        for index, layover in enumerate(
            layovers,
            start=1,
        ):
            print(
                f"  {index}. "
                f"{layover['id']} "
                f"({layover['name']})"
            )

            print(
                f"     Duration: "
                f"{layover['duration']} minutes"
            )
    else:
        print()
        print("Layovers: None")


# ============================================================
# SEARCH PARAMETER COMPARISON
# ============================================================

def compare_search_parameters(
    earlier: dict[str, Any],
    latest: dict[str, Any],
) -> None:
    """
    Compare SerpApi search parameters.
    """

    print_section(
        "SEARCH PARAMETERS"
    )

    earlier_params = earlier.get(
        "search_parameters",
        {},
    )

    latest_params = latest.get(
        "search_parameters",
        {},
    )

    fields = [
        "departure_id",
        "arrival_id",
        "outbound_date",
        "return_date",
        "currency",
        "hl",
        "type",
    ]

    all_same = True

    for field in fields:
        earlier_value = earlier_params.get(
            field
        )

        latest_value = latest_params.get(
            field
        )

        same = (
            earlier_value
            == latest_value
        )

        if not same:
            all_same = False

        print(
            f"{field}:"
        )

        print(
            f"  Earlier: {earlier_value}"
        )

        print(
            f"  Latest:  {latest_value}"
        )

        print(
            f"  Same:    {yes_no(same)}"
        )

    print()

    print(
        "Same search parameters: "
        f"{yes_no(all_same)}"
    )


# ============================================================
# PRICE COMPARISON
# ============================================================

def compare_prices(
    earlier_result: dict[str, Any] | None,
    latest_result: dict[str, Any] | None,
) -> None:
    """
    Compare prices of the selected best itineraries.
    """

    print_section(
        "PRICE COMPARISON"
    )

    earlier_price = get_price(
        earlier_result
    )

    latest_price = get_price(
        latest_result
    )

    print(
        f"Earlier price: "
        f"₹{earlier_price:,}"
        if earlier_price is not None
        else "Earlier price: Unknown"
    )

    print(
        f"Latest price:  "
        f"₹{latest_price:,}"
        if latest_price is not None
        else "Latest price: Unknown"
    )

    if (
        earlier_price is None
        or latest_price is None
    ):
        print(
            "Could not calculate price difference."
        )
        return

    difference = (
        latest_price
        - earlier_price
    )

    percentage = (
        difference
        / earlier_price
        * 100
    )

    print()

    print(
        f"Difference: "
        f"₹{difference:,.0f}"
    )

    print(
        f"Percentage change: "
        f"{percentage:.2f}%"
    )

    if difference > 0:
        print(
            "Result: "
            "Latest fare is HIGHER."
        )

    elif difference < 0:
        print(
            "Result: "
            "Latest fare is LOWER."
        )

    else:
        print(
            "Result: "
            "Fare is UNCHANGED."
        )


# ============================================================
# TOKEN COMPARISON
# ============================================================

def compare_tokens(
    earlier_result: dict[str, Any] | None,
    latest_result: dict[str, Any] | None,
) -> None:
    """
    Compare departure tokens.
    """

    print_section(
        "DEPARTURE TOKEN COMPARISON"
    )

    earlier_token = (
        earlier_result.get(
            "departure_token"
        )
        if earlier_result
        else None
    )

    latest_token = (
        latest_result.get(
            "departure_token"
        )
        if latest_result
        else None
    )

    print(
        "Earlier token available: "
        f"{yes_no(bool(earlier_token))}"
    )

    print(
        "Latest token available:  "
        f"{yes_no(bool(latest_token))}"
    )

    if (
        earlier_token
        and latest_token
    ):
        print()

        print(
            "Tokens identical: "
            f"{yes_no(earlier_token == latest_token)}"
        )

        if earlier_token != latest_token:
            print(
                "Interpretation: "
                "Google Flights generated "
                "different itinerary tokens "
                "for the two searches."
            )


# ============================================================
# ITINERARY COMPARISON
# ============================================================

def compare_itineraries(
    earlier_result: dict[str, Any] | None,
    latest_result: dict[str, Any] | None,
) -> bool:
    """
    Compare visible flight itinerary details.

    Returns True if the visible itineraries
    are exactly identical.
    """

    print_section(
        "BEST ITINERARY COMPARISON"
    )

    earlier_segments = (
        get_normalized_segments(
            earlier_result
        )
    )

    latest_segments = (
        get_normalized_segments(
            latest_result
        )
    )

    earlier_layovers = (
        get_layovers(
            earlier_result
        )
    )

    latest_layovers = (
        get_layovers(
            latest_result
        )
    )

    same_segments = (
        earlier_segments
        == latest_segments
    )

    same_layovers = (
        earlier_layovers
        == latest_layovers
    )

    earlier_duration = (
        earlier_result.get(
            "total_duration"
        )
        if earlier_result
        else None
    )

    latest_duration = (
        latest_result.get(
            "total_duration"
        )
        if latest_result
        else None
    )

    same_duration = (
        earlier_duration
        == latest_duration
    )

    print(
        "Same number of segments: "
        f"{yes_no(len(earlier_segments) == len(latest_segments))}"
    )

    print(
        "Same flight segments: "
        f"{yes_no(same_segments)}"
    )

    print(
        "Same layovers: "
        f"{yes_no(same_layovers)}"
    )

    print(
        "Same total duration: "
        f"{yes_no(same_duration)}"
    )

    if not same_segments:
        print()
        print(
            "Segment differences detected."
        )

        print()
        print(
            "Earlier segments:"
        )

        for segment in earlier_segments:
            print(
                f"  {segment['departure_id']} "
                f"→ "
                f"{segment['arrival_id']} | "
                f"{segment['airline']} "
                f"{segment['flight_number']} | "
                f"{segment['departure_time']} "
                f"→ "
                f"{segment['arrival_time']}"
            )

        print()
        print(
            "Latest segments:"
        )

        for segment in latest_segments:
            print(
                f"  {segment['departure_id']} "
                f"→ "
                f"{segment['arrival_id']} | "
                f"{segment['airline']} "
                f"{segment['flight_number']} | "
                f"{segment['departure_time']} "
                f"→ "
                f"{segment['arrival_time']}"
            )

    same_itinerary = (
        same_segments
        and same_layovers
        and same_duration
    )

    print()

    print(
        "Same visible itinerary: "
        f"{yes_no(same_itinerary)}"
    )

    return same_itinerary


# ============================================================
# PRICE INSIGHTS
# ============================================================

def compare_price_insights(
    earlier: dict[str, Any],
    latest: dict[str, Any],
) -> None:
    """
    Compare Google Flights price insights.
    """

    print_section(
        "PRICE INSIGHTS COMPARISON"
    )

    earlier_insights = earlier.get(
        "price_insights",
        {},
    )

    latest_insights = latest.get(
        "price_insights",
        {},
    )

    fields = [
        "lowest_price",
        "price_level",
        "typical_price_range",
        "price_history",
    ]

    for field in fields:
        earlier_value = earlier_insights.get(
            field
        )

        latest_value = latest_insights.get(
            field
        )

        print(
            f"{field}:"
        )

        print(
            f"  Earlier: {earlier_value}"
        )

        print(
            f"  Latest:  {latest_value}"
        )

        print(
            f"  Same:    "
            f"{yes_no(earlier_value == latest_value)}"
        )


# ============================================================
# OTHER FLIGHTS COMPARISON
# ============================================================

def get_result_signature(
    result: dict[str, Any],
) -> tuple:
    """
    Create a signature for comparing visible itineraries.
    """

    segments = (
        get_normalized_segments(
            result
        )
    )

    return tuple(
        (
            segment["airline"],
            segment["flight_number"],
            segment["departure_id"],
            segment["arrival_id"],
            segment["departure_time"],
            segment["arrival_time"],
        )
        for segment in segments
    )


def compare_all_visible_flights(
    earlier: dict[str, Any],
    latest: dict[str, Any],
) -> None:
    """
    Compare all visible Google Flights results.

    This helps determine whether the earlier
    ₹63,264 fare disappeared from the result set.
    """

    print_section(
        "OTHER FLIGHTS / ALL VISIBLE RESULTS"
    )

    earlier_results = get_all_results(
        earlier
    )

    latest_results = get_all_results(
        latest
    )

    print(
        f"Earlier visible itineraries: "
        f"{len(earlier_results)}"
    )

    print(
        f"Latest visible itineraries:  "
        f"{len(latest_results)}"
    )

    print_subsection(
        "EARLIER SEARCH RESULTS"
    )

    for index, result in enumerate(
        earlier_results,
        start=1,
    ):
        price = result.get(
            "price",
            "Unknown",
        )

        signature = get_result_signature(
            result
        )

        print(
            f"{index}. "
            f"₹{price:,}"
            if isinstance(
                price,
                (int, float),
            )
            else f"{index}. Price: {price}"
        )

        print(
            f"   Segments: "
            f"{len(signature)}"
        )

        for segment in signature:
            print(
                f"   {segment[0]} "
                f"{segment[1]} | "
                f"{segment[2]} → "
                f"{segment[3]} | "
                f"{segment[4]} → "
                f"{segment[5]}"
            )

    print_subsection(
        "LATEST SEARCH RESULTS"
    )

    for index, result in enumerate(
        latest_results,
        start=1,
    ):
        price = result.get(
            "price",
            "Unknown",
        )

        signature = get_result_signature(
            result
        )

        print(
            f"{index}. "
            f"₹{price:,}"
            if isinstance(
                price,
                (int, float),
            )
            else f"{index}. Price: {price}"
        )

        print(
            f"   Segments: "
            f"{len(signature)}"
        )

        for segment in signature:
            print(
                f"   {segment[0]} "
                f"{segment[1]} | "
                f"{segment[2]} → "
                f"{segment[3]} | "
                f"{segment[4]} → "
                f"{segment[5]}"
            )

    # --------------------------------------------------------
    # Check whether the earlier exact itinerary still exists
    # --------------------------------------------------------

    earlier_signatures = {
        get_result_signature(result)
        for result in earlier_results
    }

    latest_signatures = {
        get_result_signature(result)
        for result in latest_results
    }

    missing_from_latest = (
        earlier_signatures
        - latest_signatures
    )

    new_in_latest = (
        latest_signatures
        - earlier_signatures
    )

    print_subsection(
        "ITINERARY AVAILABILITY CHANGES"
    )

    print(
        "Earlier itineraries missing "
        "from latest search: "
        f"{len(missing_from_latest)}"
    )

    print(
        "New itineraries appearing "
        "in latest search: "
        f"{len(new_in_latest)}"
    )

    if missing_from_latest:
        print()

        print(
            "IMPORTANT:"
        )

        print(
            "At least one itinerary that "
            "was visible in the earlier "
            "search is no longer visible "
            "in the latest search."
        )

        print(
            "This could indicate a change "
            "in availability or fare inventory."
        )


# ============================================================
# FINAL INTERPRETATION
# ============================================================

def generate_conclusion(
    earlier: dict[str, Any],
    latest: dict[str, Any],
    earlier_result: dict[str, Any] | None,
    latest_result: dict[str, Any] | None,
    same_itinerary: bool,
) -> None:
    """
    Generate a high-level interpretation.
    """

    print_section(
        "FINAL INTERPRETATION"
    )

    earlier_price = get_price(
        earlier_result
    )

    latest_price = get_price(
        latest_result
    )

    if (
        earlier_price is None
        or latest_price is None
    ):
        print(
            "Unable to determine a final "
            "interpretation because one or "
            "both prices are unavailable."
        )
        return

    all_earlier_results = (
        get_all_results(
            earlier
        )
    )

    all_latest_results = (
        get_all_results(
            latest
        )
    )

    earlier_signatures = {
        get_result_signature(result)
        for result in all_earlier_results
    }

    latest_signatures = {
        get_result_signature(result)
        for result in all_latest_results
    }

    earlier_itinerary_missing = (
        get_result_signature(
            earlier_result
        )
        not in latest_signatures
        if earlier_result
        else False
    )

    # --------------------------------------------------------
    # CASE 1
    # Same visible itinerary, higher price
    # --------------------------------------------------------

    if (
        same_itinerary
        and latest_price > earlier_price
    ):
        print(
            "LIKELY EXPLANATION:"
        )

        print()

        print(
            "The visible itinerary is identical "
            "in both searches, but the latest "
            "search returned a higher fare."
        )

        print()

        print(
            "This strongly suggests that the "
            "same physical flight itinerary "
            "was repriced between the two "
            "searches."
        )

        print()

        print(
            "Possible causes include:"
        )

        print(
            "  • Airline fare inventory changed"
        )

        print(
            "  • Lower fare bucket sold out"
        )

        print(
            "  • Google Flights refreshed its "
            "live pricing data"
        )

        print(
            "  • The fare was revalidated at "
            "a different price"
        )

        print()

        print(
            "Conclusion:"
        )

        print(
            "The ₹63,264 fare appears to have "
            "been a legitimate lower fare that "
            "was no longer available at the "
            "time of the latest search."
        )

        return

    # --------------------------------------------------------
    # CASE 2
    # Different itinerary
    # --------------------------------------------------------

    if not same_itinerary:
        print(
            "LIKELY EXPLANATION:"
        )

        print()

        print(
            "The best visible itinerary changed "
            "between the two searches."
        )

        print()

        print(
            "Therefore the price difference "
            "cannot be attributed solely to "
            "fare movement."
        )

        print(
            "The underlying itinerary or "
            "availability changed as well."
        )

        return

    # --------------------------------------------------------
    # CASE 3
    # Lower latest fare
    # --------------------------------------------------------

    if latest_price < earlier_price:
        print(
            "LIKELY EXPLANATION:"
        )

        print()

        print(
            "The same visible itinerary is now "
            "available at a lower price."
        )

        print(
            "This suggests the fare decreased "
            "or a cheaper fare bucket became "
            "available."
        )

        return

    # --------------------------------------------------------
    # CASE 4
    # Same price
    # --------------------------------------------------------

    print(
        "No meaningful fare difference "
        "was detected."
    )


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    """
    Main comparison workflow.
    """

    print()
    print("=" * 70)
    print(
        "GOOGLE FLIGHTS RAW SEARCH COMPARISON"
    )
    print("=" * 70)

    print()
    print(
        f"Raw search directory:"
    )

    print(
        f"{RAW_SEARCH_DIR.resolve()}"
    )

    print()
    print(
        f"Earlier JSON:"
    )

    print(
        f"{EARLIER_FILE}"
    )

    print()
    print(
        f"Latest JSON:"
    )

    print(
        f"{LATEST_FILE}"
    )

    # --------------------------------------------------------
    # LOAD FILES
    # --------------------------------------------------------

    earlier = load_json(
        EARLIER_FILE
    )

    latest = load_json(
        LATEST_FILE
    )

    # --------------------------------------------------------
    # GET BEST ITINERARIES
    # --------------------------------------------------------

    earlier_result = get_first_result(
        earlier
    )

    latest_result = get_first_result(
        latest
    )

    # --------------------------------------------------------
    # PRINT BASIC FILE INFORMATION
    # --------------------------------------------------------

    print_section(
        "FILES BEING COMPARED"
    )

    print(
        f"Earlier file: "
        f"{EARLIER_FILE}"
    )

    print(
        f"Latest file:  "
        f"{LATEST_FILE}"
    )

    # --------------------------------------------------------
    # PRINT BEST ITINERARIES
    # --------------------------------------------------------

    print_itinerary(
        "EARLIER SEARCH — BEST ITINERARY",
        earlier_result,
    )

    print_itinerary(
        "LATEST SEARCH — BEST ITINERARY",
        latest_result,
    )

    # --------------------------------------------------------
    # COMPARE SEARCH PARAMETERS
    # --------------------------------------------------------

    compare_search_parameters(
        earlier,
        latest,
    )

    # --------------------------------------------------------
    # COMPARE PRICES
    # --------------------------------------------------------

    compare_prices(
        earlier_result,
        latest_result,
    )

    # --------------------------------------------------------
    # COMPARE ITINERARIES
    # --------------------------------------------------------

    same_itinerary = compare_itineraries(
        earlier_result,
        latest_result,
    )

    # --------------------------------------------------------
    # COMPARE DEPARTURE TOKENS
    # --------------------------------------------------------

    compare_tokens(
        earlier_result,
        latest_result,
    )

    # --------------------------------------------------------
    # COMPARE PRICE INSIGHTS
    # --------------------------------------------------------

    compare_price_insights(
        earlier,
        latest,
    )

    # --------------------------------------------------------
    # COMPARE ALL VISIBLE RESULTS
    # --------------------------------------------------------

    compare_all_visible_flights(
        earlier,
        latest,
    )

    # --------------------------------------------------------
    # FINAL INTERPRETATION
    # --------------------------------------------------------

    generate_conclusion(
        earlier=earlier,
        latest=latest,
        earlier_result=earlier_result,
        latest_result=latest_result,
        same_itinerary=same_itinerary,
    )

    # --------------------------------------------------------
    # FINISHED
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print(
        "COMPARISON COMPLETE"
    )
    print("=" * 70)


if __name__ == "__main__":
    main()