import json
import hashlib
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv
import serpapi

from flight_search.providers.base import FlightSearchProvider


load_dotenv()


class SerpApiProvider(FlightSearchProvider):
    name = "serpapi"

    def __init__(
        self,
        api_key: str | None = None,
        save_raw_responses: bool | None = None,
        allow_cache_only: bool = False,
    ):
        self.api_key = (
            api_key
            or os.getenv("SERPAPI_API_KEY")
        )

        if not self.api_key and not allow_cache_only:
            raise ValueError(
                "SERPAPI_API_KEY not found."
            )

        self.client = (
            serpapi.Client(api_key=self.api_key)
            if self.api_key else None
        )

        if save_raw_responses is None:
            save_raw_responses = os.getenv(
                "SAVE_RAW_SERPAPI_RESPONSES",
                "false",
            ).strip().lower() in {"1", "true", "yes", "on"}

        self.save_raw_responses = save_raw_responses

    def search_round_trip(
        self,
        departure_id: str,
        arrival_id: str,
        outbound_date: str,
        return_date: str,
    ) -> Dict[str, Any]:
        """
        Search Google Flights through SerpApi
        and save the complete raw response.

        The raw response is saved for later
        debugging and fare verification.
        """

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

        # ==========================================
        # CALL SERPAPI
        # ==========================================

        response = self.client.search(
            params
        )

        if self.save_raw_responses:
            self._save_raw_response(
                response=dict(response),
                departure_id=departure_id,
                arrival_id=arrival_id,
                outbound_date=outbound_date,
                return_date=return_date,
            )

        # ==========================================
        # RETURN RESPONSE TO EXISTING SEARCH FLOW
        # ==========================================

        return response

    def search_one_way(
        self,
        departure_id: str,
        arrival_id: str,
        outbound_date: str,
        cache_mode: str = "live",
    ) -> Dict[str, Any]:
        """Search a one-way leg, or read/write its exact-query local cache."""
        if cache_mode not in {"live", "cache"}:
            raise ValueError("cache_mode must be 'live' or 'cache'.")
        cache_path = self._one_way_cache_path(
            departure_id, arrival_id, outbound_date
        )
        if cache_mode == "cache":
            if not cache_path.exists():
                return {
                    "error": f"CACHE_MISS: no cached result for {departure_id} "
                    f"to {arrival_id} on {outbound_date}",
                    "_cache_hit": False,
                }
            with cache_path.open("r", encoding="utf-8") as file:
                response = json.load(file)
            response["_cache_hit"] = True
            return response

        if self.client is None:
            raise ValueError("SERPAPI_API_KEY is required for live searches.")
        params = {
            "engine": "google_flights",
            "departure_id": departure_id,
            "arrival_id": arrival_id,
            "outbound_date": outbound_date,
            "currency": "INR",
            "hl": "en",
            "type": "2",
        }
        response = dict(self.client.search(params))
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with cache_path.open("w", encoding="utf-8") as file:
            json.dump(dict(response), file, indent=2, ensure_ascii=False)
        response["_cache_hit"] = False
        if self.save_raw_responses:
            self._save_raw_response(
                response=dict(response),
                departure_id=departure_id,
                arrival_id=arrival_id,
                outbound_date=outbound_date,
                return_date="one-way",
            )
        return response

    def search_multi_city(
        self,
        legs: list[dict[str, str]],
        cache_mode: str = "live",
    ) -> Dict[str, Any]:
        """Search a linked multi-city itinerary through Google Flights."""
        if cache_mode not in {"live", "cache"}:
            raise ValueError("cache_mode must be 'live' or 'cache'.")
        multi_city_json = json.dumps(legs, separators=(",", ":"))
        params = {
            "engine": "google_flights",
            "type": "3",
            "multi_city_json": multi_city_json,
            "currency": "INR",
            "hl": "en",
        }
        cache_path = self._query_cache_path(params, "multi_city")
        if cache_mode == "cache":
            if not cache_path.exists():
                return {
                    "error": "CACHE_MISS: no cached result for this multi-city query",
                    "_cache_hit": False,
                }
            with cache_path.open("r", encoding="utf-8") as file:
                response = json.load(file)
            response["_cache_hit"] = True
            return response
        if self.client is None:
            raise ValueError("SERPAPI_API_KEY is required for live searches.")
        response = dict(self.client.search(params))
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with cache_path.open("w", encoding="utf-8") as file:
            json.dump(response, file, indent=2, ensure_ascii=False)
        response["_cache_hit"] = False
        return response

    @staticmethod
    def _one_way_cache_path(
        departure_id: str, arrival_id: str, outbound_date: str
    ) -> Path:
        """Return a stable path keyed by every parameter affecting this query."""
        key = json.dumps(
            {
                "departure_id": departure_id,
                "arrival_id": arrival_id,
                "outbound_date": outbound_date,
                "currency": "INR",
                "hl": "en",
                "type": "2",
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
        safe_departure = departure_id.replace(",", "-")
        safe_arrival = arrival_id.replace(",", "-")
        filename = f"{safe_departure}_{safe_arrival}_{outbound_date}_{digest}.json"
        return Path("data/cache/serpapi_one_way") / filename

    @staticmethod
    def _query_cache_path(params: dict, query_type: str) -> Path:
        key = json.dumps(params, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
        filename = f"{query_type}_{digest}.json"
        return Path("data/cache") / f"serpapi_{query_type}" / filename

    @staticmethod
    def _save_raw_response(
        response: Dict[str, Any],
        departure_id: str,
        arrival_id: str,
        outbound_date: str,
        return_date: str,
    ) -> None:
        """
        Save the complete raw SerpApi response
        to data/raw_searches/.

        A timestamp is added to the filename
        so previous responses are never overwritten.
        """

        output_dir = Path(
            "data/raw_searches"
        )

        output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        timestamp = (
            datetime.now().strftime(
                "%Y%m%d_%H%M%S_%f"
            )
        )

        filename = (
            f"raw_"
            f"{departure_id}_"
            f"{arrival_id}_"
            f"{outbound_date}_"
            f"{return_date}_"
            f"{timestamp}.json"
        )

        output_path = (
            output_dir / filename
        )

        with output_path.open(
            "w",
            encoding="utf-8",
        ) as file:

            json.dump(
                response,
                file,
                indent=2,
                ensure_ascii=False,
            )

        print(
            f"    Raw SerpApi response saved: "
            f"{output_path}"
        )
