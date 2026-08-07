"""Cached Aviasales fare access for Russian domestic itinerary planning."""

from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_URL = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"


def get_travelpayouts_token():
    token = os.getenv("TRAVELPAYOUTS_API_TOKEN")
    if token:
        return token

    env_path = Path(".env")
    if not env_path.is_file():
        return None

    for line in env_path.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if separator and key.strip() == "TRAVELPAYOUTS_API_TOKEN":
            return value.strip().strip("\"'") or None

    return None


class TravelpayoutsProvider:
    """Read cached round-trip offers without altering the default provider."""

    name = "travelpayouts_cached"

    def __init__(self, api_token=None):
        self.api_token = api_token or get_travelpayouts_token()
        if not self.api_token:
            raise ValueError("TRAVELPAYOUTS_API_TOKEN not found.")

    def search_round_trip(
        self,
        departure_id,
        arrival_id,
        outbound_date,
        return_date,
    ):
        query = urlencode(
            {
                "origin": departure_id,
                "destination": arrival_id,
                "departure_at": outbound_date,
                "return_at": return_date,
                "one_way": "false",
                "unique": "false",
                "sorting": "price",
                "direct": "false",
                "currency": "RUB",
                "limit": 30,
                "page": 1,
                "market": "ru",
            }
        )
        request = Request(
            f"{API_URL}?{query}",
            headers={"X-Access-Token": self.api_token},
        )

        try:
            with urlopen(request, timeout=30) as response:
                return json.load(response)
        except (HTTPError, URLError, TimeoutError) as error:
            raise RuntimeError(f"Travelpayouts request failed: {error}") from error

    @staticmethod
    def extract_cheapest_offer(payload):
        if not payload.get("success"):
            return None

        offers = payload.get("data") or []
        if isinstance(offers, dict):
            offers = list(offers.values())

        priced_offers = [
            offer for offer in offers
            if offer.get("price", offer.get("value")) is not None
        ]
        if not priced_offers:
            return None

        cheapest = min(
            priced_offers,
            key=lambda offer: offer.get("price", offer.get("value")),
        )
        return {
            "price": cheapest.get("price", cheapest.get("value")),
            "currency": cheapest.get("currency", "RUB"),
            "airline": cheapest.get("airline"),
            "flight_number": cheapest.get("flight_number"),
            "departure_at": cheapest.get("departure_at", cheapest.get("depart_date")),
            "return_at": cheapest.get("return_at", cheapest.get("return_date")),
            "duration": cheapest.get("duration"),
            "raw": cheapest,
        }
