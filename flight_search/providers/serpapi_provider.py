import os
from typing import Any, Dict

import json

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




    def search_open_jaw(
        self,
        outbound_departure_id: str,
        outbound_arrival_id: str,
        return_departure_id: str,
        return_arrival_id: str,
        outbound_date: str,
        return_date: str,
    ) -> Dict[str, Any]:
        """
        Search an explicit open-jaw itinerary using
        SerpApi Google Flights multi-city search.
    
        Example:
    
            Outbound:
                HYD → SVO
                2027-01-20
    
            Return:
                HEL → HYD
                2027-01-25
    
        The traveler independently travels from SVO to HEL.
        """
    
        multi_city_legs = [
            {
                "departure_id": outbound_departure_id,
                "arrival_id": outbound_arrival_id,
                "date": outbound_date,
            },
            {
                "departure_id": return_departure_id,
                "arrival_id": return_arrival_id,
                "date": return_date,
            },
        ]
    
        params = {
            "engine": "google_flights",
            "type": "3",
            "multi_city_json": json.dumps(
                multi_city_legs,
                separators=(",", ":"),
            ),
            "currency": "INR",
            "hl": "en",
        }
    
        return self.client.search(params)