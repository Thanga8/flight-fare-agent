import json
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
    ):
        self.api_key = (
            api_key
            or os.getenv("SERPAPI_API_KEY")
        )

        if not self.api_key:
            raise ValueError(
                "SERPAPI_API_KEY not found."
            )

        self.client = serpapi.Client(
            api_key=self.api_key
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
