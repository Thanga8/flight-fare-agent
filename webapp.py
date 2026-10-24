"""Configurable web interface for the multi-leg fare search."""

from __future__ import annotations

import os
from datetime import date

from flask import Flask, render_template, request

from flight_search.config.settings import (
    MULTI_LEG_COMBINED_CANDIDATE_LIMIT,
    MULTI_LEG_END_DATE,
    MULTI_LEG_LEG1_DESTINATION,
    MULTI_LEG_LEG1_ORIGIN,
    MULTI_LEG_LEG2_DESTINATION,
    MULTI_LEG_LEG2_ORIGIN,
    MULTI_LEG_NIGHTS_BETWEEN_DEPARTURES,
    MULTI_LEG_SERPAPI_BUDGET,
    MULTI_LEG_START_DATE,
)
from flight_search.google_flights_url import build_google_flights_url
from flight_search.multi_leg import search_multi_leg_itineraries
from flight_search.providers.serpapi_provider import SerpApiProvider


MAX_WEB_SERPAPI_BUDGET = MULTI_LEG_SERPAPI_BUDGET
app = Flask(__name__)


def _default_form_data():
    return {
        "start_date": MULTI_LEG_START_DATE,
        "end_date": MULTI_LEG_END_DATE,
        "leg1_origin": MULTI_LEG_LEG1_ORIGIN,
        "leg1_destination": MULTI_LEG_LEG1_DESTINATION,
        "leg2_origin": MULTI_LEG_LEG2_ORIGIN,
        "leg2_destination": MULTI_LEG_LEG2_DESTINATION,
        "nights_between_departures": str(MULTI_LEG_NIGHTS_BETWEEN_DEPARTURES),
        "serpapi_budget": str(MAX_WEB_SERPAPI_BUDGET),
        "combined_candidate_limit": str(MULTI_LEG_COMBINED_CANDIDATE_LIMIT),
        "leg1_cache_mode": "live",
        "leg2_cache_mode": "live",
        "combined_cache_mode": "live",
    }


def _render_index(form_data=None, error=None, status=200):
    return render_template(
        "index.html",
        form_data=form_data or _default_form_data(),
        serpapi_budget=MAX_WEB_SERPAPI_BUDGET,
        error=error,
    ), status


def _booking_links(itinerary, report):
    """Build route/date availability links for each displayed leg."""
    leg1_destination = (
        itinerary["leg1"].get("arrival_airport") or report["leg1_destination"]
    )
    return {
        "leg1": build_google_flights_url(
            report["leg1_origin"],
            leg1_destination,
            itinerary["leg1"]["departure_date"],
        ),
        "leg2": build_google_flights_url(
            itinerary["leg2"]["departure_airport"],
            report["leg2_destination"],
            itinerary["leg2"]["departure_date"],
        ),
    }


@app.get("/")
def index():
    return _render_index()


@app.post("/search")
def search():
    form_data = _default_form_data()
    for key in form_data:
        if key in request.form:
            form_data[key] = request.form.get(key, "").strip()

    try:
        start = date.fromisoformat(form_data["start_date"])
        end = date.fromisoformat(form_data["end_date"])
        if end < start:
            raise ValueError("The end date must be on or after the start date.")
        nights = int(form_data["nights_between_departures"])
        budget = int(form_data["serpapi_budget"])
        combined_limit = int(form_data["combined_candidate_limit"])
        if nights < 1 or nights > 60:
            raise ValueError("Nights between departures must be between 1 and 60.")
        if not 0 <= budget <= MAX_WEB_SERPAPI_BUDGET:
            raise ValueError(f"SerpApi budget must be between 0 and {MAX_WEB_SERPAPI_BUDGET}.")
        if not 0 <= combined_limit <= 50:
            raise ValueError("Combined candidates must be between 0 and 50.")
        for key in ("leg1_origin", "leg1_destination", "leg2_origin", "leg2_destination"):
            if not form_data[key]:
                raise ValueError("Enter an origin and destination for both legs.")
        for key in ("leg1_cache_mode", "leg2_cache_mode", "combined_cache_mode"):
            if form_data[key] not in {"live", "cache"}:
                raise ValueError("Each data mode must be Live search or Use cache only.")
    except (ValueError, TypeError) as error:
        return _render_index(form_data, str(error), 400)

    modes = (
        form_data["leg1_cache_mode"],
        form_data["leg2_cache_mode"],
        form_data["combined_cache_mode"],
    )
    needs_live_api = "live" in modes
    if needs_live_api and not os.getenv("SERPAPI_API_KEY"):
        return _render_index(
            form_data,
            "Missing SERPAPI_API_KEY in .env for the selected live searches.",
            500,
        )

    try:
        provider = SerpApiProvider(allow_cache_only=not needs_live_api)
        report = search_multi_leg_itineraries(
            start_date=form_data["start_date"],
            end_date=form_data["end_date"],
            international_provider=provider,
            serpapi_budget=budget,
            leg1_origin=form_data["leg1_origin"].upper(),
            leg1_destination=form_data["leg1_destination"].upper(),
            leg2_origin=form_data["leg2_origin"].upper(),
            leg2_destination=form_data["leg2_destination"].upper(),
            nights_between_departures=nights,
            leg1_cache_mode=form_data["leg1_cache_mode"],
            leg2_cache_mode=form_data["leg2_cache_mode"],
            combined_cache_mode=form_data["combined_cache_mode"],
            combined_candidate_limit=combined_limit,
        )
    except (RuntimeError, ValueError) as error:
        return _render_index(form_data, f"Search could not complete: {error}", 502)

    for itinerary in report["itineraries"]:
        itinerary["booking_links"] = _booking_links(itinerary, report)

    return render_template(
        "results.html",
        report=report,
        start_date=form_data["start_date"],
        end_date=form_data["end_date"],
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
