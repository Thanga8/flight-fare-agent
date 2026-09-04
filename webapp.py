"""Mobile-friendly web interface for the multi-leg fare search.

This module is deliberately thin: it collects search parameters and delegates all
fare selection to the existing multi-leg search engine.
"""

from __future__ import annotations

import os

from flask import Flask, render_template, request

from flight_search.config.settings import END_DATE, START_DATE
from flight_search.google_flights_url import build_google_flights_url
from flight_search.multi_leg import search_multi_leg_itineraries
from flight_search.providers.serpapi_provider import SerpApiProvider
from flight_search.providers.travelpayouts_provider import TravelpayoutsProvider


MAX_WEB_SERPAPI_BUDGET = 15

app = Flask(__name__)


def _booking_links(itinerary):
    """Provide route/date availability checks, not claimed exact-fare deep links."""

    return {
        "international": build_google_flights_url(
            "HYD",
            itinerary["international_arrival_airport"],
            itinerary["international"]["departure_date"],
            itinerary["international"]["return_date"],
        ),
        "domestic": build_google_flights_url(
            "MOW",
            "MMK",
            itinerary["domestic_departure_date"],
            itinerary["domestic_return_date"],
        ),
    }


@app.get("/")
def index():
    return render_template(
        "index.html",
        start_date=START_DATE,
        end_date=END_DATE,
        serpapi_budget=MAX_WEB_SERPAPI_BUDGET,
    )


@app.post("/search")
def search():
    start_date = request.form.get("start_date", START_DATE)
    end_date = request.form.get("end_date", END_DATE)

    if end_date < start_date:
        return render_template(
            "index.html",
            start_date=start_date,
            end_date=end_date,
            serpapi_budget=MAX_WEB_SERPAPI_BUDGET,
            error="The end date must be after the start date.",
        ), 400

    if not os.getenv("SERPAPI_API_KEY") or not os.getenv("TRAVELPAYOUTS_API_TOKEN"):
        return render_template(
            "index.html",
            start_date=start_date,
            end_date=end_date,
            serpapi_budget=MAX_WEB_SERPAPI_BUDGET,
            error="Missing SERPAPI_API_KEY or TRAVELPAYOUTS_API_TOKEN in .env.",
        ), 500

    try:
        report = search_multi_leg_itineraries(
            start_date=start_date,
            end_date=end_date,
            domestic_provider=TravelpayoutsProvider(),
            international_provider=SerpApiProvider(),
            serpapi_budget=MAX_WEB_SERPAPI_BUDGET,
        )
    except (RuntimeError, ValueError) as error:
        return render_template(
            "index.html",
            start_date=start_date,
            end_date=end_date,
            serpapi_budget=MAX_WEB_SERPAPI_BUDGET,
            error=f"Search could not complete: {error}",
        ), 502

    for itinerary in report["itineraries"]:
        itinerary["booking_links"] = _booking_links(itinerary)

    return render_template(
        "results.html",
        report=report,
        start_date=start_date,
        end_date=end_date,
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
