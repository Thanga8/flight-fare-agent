"""Opt-in probe for cached Aviasales fares on Moscow to Murmansk.

This is research code for Phase 6. It is intentionally separate from the
provider architecture and does not write to SQLite. It makes one HTTPS request
only when TRAVELPAYOUTS_API_TOKEN is supplied.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_URL = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"


def get_api_token():
    """Read the token from the environment or the project's local .env file."""

    token = os.getenv("TRAVELPAYOUTS_API_TOKEN")
    if token:
        return token

    env_path = Path(__file__).with_name(".env")
    if not env_path.is_file():
        return None

    for line in env_path.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if separator and key.strip() == "TRAVELPAYOUTS_API_TOKEN":
            return value.strip().strip("\"'") or None

    return None


def fetch_mow_to_mmk_fares(token, departure_date, limit=30):
    """Fetch cached one-way offers for MOW to MMK in Russian rubles."""

    query = urlencode(
        {
            "origin": "MOW",
            "destination": "MMK",
            "departure_at": departure_date,
            "one_way": "true",
            "unique": "false",
            "sorting": "price",
            "direct": "false",
            "currency": "RUB",
            "limit": limit,
            "page": 1,
        }
    )
    request = Request(
        f"{API_URL}?{query}",
        headers={"X-Access-Token": token},
    )

    with urlopen(request, timeout=30) as response:
        return json.load(response)


def format_offer(offer):
    price = offer.get("price", offer.get("value", "unknown"))
    airline = offer.get("airline", "unknown")
    flight_number = offer.get("flight_number", "unknown")
    departure_at = offer.get("departure_at", offer.get("depart_date", "unknown"))
    duration = offer.get("duration", offer.get("duration_to", "unknown"))
    expires_at = offer.get("expires_at", "unknown")

    return (
        f"{price} RUB | airline={airline} | flight={flight_number} | "
        f"departure={departure_at} | duration={duration} min | "
        f"expires={expires_at}"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Check Aviasales cached MOW → MMK fare coverage."
    )
    parser.add_argument(
        "--departure",
        default="2027-01-25",
        help="One-way departure date (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=30,
        help="Maximum cached offers to request (1-30).",
    )
    args = parser.parse_args()

    token = get_api_token()
    if not token:
        print("TRAVELPAYOUTS_API_TOKEN is not set; no request was made.")
        print(
            "Create a Travelpayouts account, export its API token, then run "
            "this script again."
        )
        return 2

    if not 1 <= args.limit <= 30:
        parser.error("--limit must be between 1 and 30")

    try:
        payload = fetch_mow_to_mmk_fares(
            token=token,
            departure_date=args.departure,
            limit=args.limit,
        )
    except (HTTPError, URLError, TimeoutError) as error:
        print(f"Travelpayouts request failed: {error}")
        return 1

    if not payload.get("success"):
        print(f"Travelpayouts returned an error: {payload.get('error')}")
        return 1

    offers = payload.get("data") or []
    if isinstance(offers, dict):
        offers = list(offers.values())

    print(f"MOW -> MMK cached fare probe for {args.departure}")
    print(f"Offers returned: {len(offers)}")

    if not offers:
        print("No cached fare was returned. This does not prove the route is unavailable.")
        return 1

    for index, offer in enumerate(offers[:10], start=1):
        print(f"{index}. {format_offer(offer)}")

    print("Coverage verified: cached fare data includes a Russian domestic route.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
