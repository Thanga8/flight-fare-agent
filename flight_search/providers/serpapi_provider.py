import os
from typing import Any, Dict

from dotenv import load_dotenv
import serpapi

from flight_search.providers.base import FlightSearchProvider


load_dotenv()


class SerpApiProvider(FlightSearchProvider):
    name = "serpapi"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("SERPAPI_API_KEY")

        if not self.api_key:
            raise ValueError("SERPAPI_API_KEY not found.")

        self.client = serpapi.Client(api_key=self.api_key)

    def search_round_trip(
        self,
        departure_id: str,
        arrival_id: str,
        outbound_date: str,
        return_date: str,
    ) -> Dict[str, Any]:
        params = {
            "engine": "google_flights",
            "departure_id": departure_id,
            "arrival_id": arrival_id,
            "outbound_date": outbound_date,
            "return_date": return_date,
            "currency": "INR",
            "hl": "en",
            "type": "1",
        }

        return self.client.search(params)

    def search_one_way(
    self,
    departure_id: str,
    arrival_id: str,
    outbound_date: str,
    ) -> Dict[str, Any]:
        params = {
            "engine": "google_flights",
            "departure_id": departure_id,
            "arrival_id": arrival_id,
            "outbound_date": outbound_date,
            "currency": "INR",
            "hl": "en",
            "type": "2",
        }

        return self.client.search(params)