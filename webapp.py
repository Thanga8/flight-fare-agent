"""Configurable web interface for the multi-leg fare search."""

from __future__ import annotations

import os
import json
import math
from datetime import date, datetime, timezone

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
from flight_search.database.db import (
    get_multi_leg_google_insights,
    get_multi_leg_historical_prices,
)
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
    report["google_insights"] = _insight_views(report.get("google_insights", []))

    return render_template(
        "results.html",
        report=report,
        start_date=form_data["start_date"],
        end_date=form_data["end_date"],
    )


def _plot_points(points):
    """Map real timestamp/price samples to an SVG without synthesizing data."""
    if not points:
        return {"polyline": "", "points": []}
    times = [point["timestamp"] for point in points]
    prices = [point["price"] for point in points]
    min_time, max_time = min(times), max(times)
    min_price, max_price = min(prices), max(prices)
    plotted = []
    for point in points:
        x = 300 if max_time == min_time else 24 + (point["timestamp"] - min_time) * 552 / (max_time - min_time)
        y = 100 if max_price == min_price else 180 - (point["price"] - min_price) * 160 / (max_price - min_price)
        plotted.append({"x": round(x, 2), "y": round(y, 2), "label": point["label"]})
    return {
        "polyline": " ".join(f"{point['x']},{point['y']}" for point in plotted),
        "points": plotted,
    }


def _history_groups(rows):
    grouped = {}
    for original in rows:
        row = dict(original)
        currency = row.get("currency") or "Unknown currency"
        try:
            flight = json.loads(row.get("flight_json") or "{}")
        except (TypeError, json.JSONDecodeError):
            flight = {}
        segments = flight.get("flights") or []
        carriers = []
        signature_segments = []
        for segment in segments:
            carrier = segment.get("airline") or segment.get("airline_code")
            flight_no = segment.get("flight_number")
            start = segment.get("departure_airport", {})
            end = segment.get("arrival_airport", {})
            segment_route = f"{start.get('id', '?')} {start.get('time', '')} → {end.get('id', '?')} {end.get('time', '')}"
            segment_label = f"{carrier or 'Carrier unavailable'} {flight_no or ''} · {segment_route}"
            carriers.append(segment_label.strip())
            signature_segments.append((start.get("id"), end.get("id"), carrier, flight_no))
        row["itinerary_detail"] = " · ".join(carriers) if carriers else f"{max(0, len(segments) - 1)} stop(s) · {flight.get('total_duration', 'duration unavailable')} min"
        row["itinerary_signature"] = json.dumps({
            "segments": signature_segments,
            "extensions": flight.get("extensions", []),
            "ticket_also_sold_by": flight.get("ticket_also_sold_by", []),
        }, ensure_ascii=False, sort_keys=True)
        row["observation_time"] = row.get("source_fetched_at") or row.get("recorded_at")
        grouped.setdefault((currency, row["itinerary_signature"]), []).append(row)
    result = []
    for (currency, signature), observations in sorted(grouped.items()):
        observations.sort(key=lambda item: (item.get("source_fetched_at") or item.get("recorded_at") or "", item.get("id", 0)))
        values = [float(item["price"]) for item in observations]
        plot_input = []
        for item in observations:
            raw_time = item.get("source_fetched_at") or item.get("recorded_at")
            try:
                parsed = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                timestamp = parsed.timestamp()
                plot_input.append({"timestamp": timestamp, "price": float(item["price"]), "label": f"{raw_time} · {item['price']} {currency}"})
            except (ValueError, TypeError, AttributeError):
                pass
        result.append({
            "currency": currency,
            "itinerary_signature": observations[0]["itinerary_detail"],
            "observations": observations,
            "latest": observations[-1],
            "lowest": min(values),
            "highest": max(values),
            "chart": _plot_points(plot_input),
            "enough_for_trend": len(plot_input) >= 2,
        })
    return result


def _insight_views(rows):
    result = []
    for row in rows:
        item = dict(row)
        if "price_insights" in item:
            insights = item["price_insights"]
        else:
            try:
                insights = json.loads(item["insights_json"]) if item.get("insights_json") is not None else None
            except (TypeError, json.JSONDecodeError):
                insights = None
        source_status = item.get("status", item.get("insight_status", "present"))
        if source_status == "absent":
            item["status"] = "absent"
        elif source_status in {"failed", "budget_skipped", "cache_miss", "stale_cache", "cache_error"}:
            item["status"] = source_status
        elif source_status in {"null", "empty"} or insights is None or insights == {} or insights == []:
            item["status"] = "no_usable_insights"
        elif not isinstance(insights, dict):
            item["status"] = "no_usable_insights"
            insights = {}
        else:
            item["status"] = "present"

        raw_range = insights.get("typical_price_range") if isinstance(insights, dict) else None
        def valid_number(value, *, allow_negative=False):
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                return False
            try:
                return math.isfinite(float(value)) and (allow_negative or value >= 0)
            except (OverflowError, TypeError, ValueError):
                return False
        item["typical_price_range"] = (
            raw_range if isinstance(raw_range, (tuple, list)) and len(raw_range) == 2
            and all(valid_number(value) for value in raw_range)
            and raw_range[0] <= raw_range[1]
            else None
        )
        item["insights"] = {}
        raw_lowest = insights.get("lowest_price") if isinstance(insights, dict) else None
        if valid_number(raw_lowest):
            item["insights"]["lowest_price"] = raw_lowest
        raw_level = insights.get("price_level") if isinstance(insights, dict) else None
        if isinstance(raw_level, str) and raw_level.strip():
            item["insights"]["price_level"] = raw_level
        item["price_points"] = []
        raw_series = insights.get("price_history") if isinstance(insights, dict) else None
        if isinstance(raw_series, list):
            for pair in raw_series:
                if not isinstance(pair, (tuple, list)) or len(pair) < 2:
                    continue
                timestamp, price = pair[0], pair[1]
                if not valid_number(timestamp, allow_negative=True) or not valid_number(price):
                    continue
                try:
                    label = datetime.fromtimestamp(timestamp, timezone.utc).isoformat()
                except (OverflowError, OSError, ValueError):
                    continue
                item["price_points"].append({"timestamp": float(timestamp), "price": float(price), "label": f"{label} · {price} {item['currency']}"})
        item["price_points"].sort(key=lambda point: point["timestamp"])
        item["chart"] = _plot_points(item["price_points"])
        item["retrieval_time"] = item.get("recorded_at")
        item["has_other_insights"] = bool(item["insights"] or item["price_points"])
        result.append(item)
    return result


@app.get("/history")
def fare_history():
    departure_airport = request.args.get("departure_airport", "").strip().upper()
    arrival_airport = request.args.get("arrival_airport", "").strip().upper()
    departure_date = request.args.get("departure_date", "").strip()
    error = None
    fare_groups = []
    insight_rows = []
    if any((departure_airport, arrival_airport, departure_date)):
        try:
            if not departure_airport or not arrival_airport or not departure_date:
                raise ValueError("Enter origin, destination, and departure date.")
            parsed_date = date.fromisoformat(departure_date)
            if parsed_date.isoformat() != departure_date:
                raise ValueError("Enter the departure date in YYYY-MM-DD format.")
            observations = get_multi_leg_historical_prices(
                departure_airport, arrival_airport, departure_date
            )
            insight_rows = get_multi_leg_google_insights(
                departure_airport, arrival_airport, departure_date
            )
            fare_groups = _history_groups(observations)
        except ValueError as exception:
            error = str(exception)
    return render_template(
        "history.html",
        departure_airport=departure_airport,
        arrival_airport=arrival_airport,
        departure_date=departure_date,
        fare_groups=fare_groups,
        insight_rows=_insight_views(insight_rows),
        error=error,
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
