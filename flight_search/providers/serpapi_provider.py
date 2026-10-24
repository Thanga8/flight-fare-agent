import json
import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv
import serpapi

from flight_search.providers.base import FlightSearchProvider


load_dotenv()

CACHE_MAX_AGE_SECONDS = 24 * 60 * 60


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _read_fresh_cache(cache_path: Path, label: str) -> Dict[str, Any]:
    """Read a fresh cache response; stale or unverifiable files are never evidence."""
    if not cache_path.exists():
        return {"error": f"CACHE_MISS: no cached result for {label}", "_cache_hit": False, "_cache_status": "miss"}
    try:
        with cache_path.open("r", encoding="utf-8") as file:
            response = json.load(file)
    except (OSError, json.JSONDecodeError) as error:
        return {"error": f"STALE_CACHE: cached response cannot be read: {error}", "_cache_hit": False, "_cache_status": "stale", "_cache_age_seconds": None}
    if not isinstance(response, dict):
        return {"error": "STALE_CACHE: cached response has an invalid structure; cached result was not used",
                "_cache_hit": False, "_cache_status": "stale", "_cache_age_seconds": None}

    metadata = response.get("_serpapi_cache")
    fetched_at = None
    invalid_reason = None
    if metadata is None:
        try:
            fetched_at = datetime.fromtimestamp(cache_path.stat().st_mtime, timezone.utc)
        except (OSError, OverflowError, ValueError):
            invalid_reason = "cache file modification time is unavailable"
    elif not isinstance(metadata, dict) or not isinstance(metadata.get("fetched_at"), str):
        invalid_reason = "cache timestamp metadata is missing or malformed"
    else:
        try:
            fetched_at = datetime.fromisoformat(metadata["fetched_at"].replace("Z", "+00:00"))
            if fetched_at.tzinfo is None:
                invalid_reason = "cache timestamp has no timezone"
            else:
                fetched_at = fetched_at.astimezone(timezone.utc)
        except (TypeError, ValueError):
            invalid_reason = "cache timestamp metadata is malformed"

    now = _utc_now()
    age = (now - fetched_at).total_seconds() if fetched_at else None
    if invalid_reason is None and age is not None and age < 0:
        invalid_reason = "cache timestamp is in the future"
    elif invalid_reason is None and age is not None and age > CACHE_MAX_AGE_SECONDS:
        invalid_reason = "cache is older than 24 hours"
    if invalid_reason:
        return {
            "error": f"STALE_CACHE: {invalid_reason}; cached result was not used",
            "_cache_hit": False,
            "_cache_status": "stale",
            "_cache_age_seconds": age,
            "_source_fetched_at": _iso_utc(fetched_at) if fetched_at else None,
        }
    response["_cache_hit"] = True
    response["_cache_status"] = "hit"
    response["_cache_age_seconds"] = age
    response["_source_fetched_at"] = _iso_utc(fetched_at)
    return response


def _save_cached_response(cache_path: Path, response: Dict[str, Any]) -> Dict[str, Any]:
    fetched_at = _iso_utc(_utc_now())
    saved = dict(response)
    saved["_serpapi_cache"] = {"fetched_at": fetched_at}
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with cache_path.open("w", encoding="utf-8") as file:
        json.dump(saved, file, indent=2, ensure_ascii=False)
    response["_cache_hit"] = False
    response["_cache_status"] = "live"
    response["_source_fetched_at"] = fetched_at
    response["_cache_age_seconds"] = 0
    response["_serpapi_cache"] = saved["_serpapi_cache"]
    return response


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
            return _read_fresh_cache(
                cache_path, f"{departure_id} to {arrival_id} on {outbound_date}"
            )

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
        response = _save_cached_response(cache_path, response)
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
            return _read_fresh_cache(cache_path, "this multi-city query")
        if self.client is None:
            raise ValueError("SERPAPI_API_KEY is required for live searches.")
        response = dict(self.client.search(params))
        return _save_cached_response(cache_path, response)

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
