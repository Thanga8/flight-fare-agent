"""Configurable web interface for the multi-leg fare search."""

from __future__ import annotations

import os
import json
import math
import hmac
import secrets
from datetime import date, datetime, timezone, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from functools import wraps

from flask import Flask, render_template, request, session, redirect, url_for, jsonify, abort

from flight_search.config.settings import (
    MAX_WEB_SERPAPI_BUDGET,
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
    initialize_database, save_monitor_job, get_monitor_job, list_monitor_jobs,
    delete_monitor_job, claim_monitor_run, finish_monitor_run, list_monitor_runs,
    mark_monitor_notification,
    get_monitor_fare_history,
)
from flight_search.multi_leg import search_multi_leg_itineraries
from flight_search.providers.serpapi_provider import SerpApiProvider


app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "")
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                  SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE", "false").strip().lower() in {"1", "true", "yes", "on"})
try:
    MONITOR_MAX_BUDGET = min(MAX_WEB_SERPAPI_BUDGET, max(0, int(os.getenv("MONITOR_MAX_SERPAPI_BUDGET", str(MAX_WEB_SERPAPI_BUDGET)))))
    MONITOR_BUDGET_CONFIG_ERROR = None
except (TypeError, ValueError):
    MONITOR_MAX_BUDGET = 0
    MONITOR_BUDGET_CONFIG_ERROR = "MONITOR_MAX_SERPAPI_BUDGET must be an integer."
MONITOR_DEFAULT_BUDGET = min(6, MONITOR_MAX_BUDGET)
MONITOR_INTERVALS = {1, 2, 3, 7}
try:
    FARE_CHANGE_MIN_ABS_INR = max(0, float(os.getenv("FARE_CHANGE_MIN_ABS_INR", "1000")))
    FARE_CHANGE_MIN_PERCENT = max(0, float(os.getenv("FARE_CHANGE_MIN_PERCENT", "3")))
except (TypeError, ValueError):
    FARE_CHANGE_MIN_ABS_INR, FARE_CHANGE_MIN_PERCENT = 1000, 3


def _authorized():
    owner_password = os.getenv("MONITOR_OWNER_PASSWORD", "")
    return bool(len(owner_password) >= 12 and len(app.secret_key or "") >= 32 and session.get("monitor_owner"))


def monitor_auth_required(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        if not _authorized():
            if request.path.startswith("/api/"):
                return jsonify(error="Monitoring login required."), 401
            return redirect(url_for("monitor_login", next=request.path))
        if request.method == "POST" and not _valid_csrf():
            return jsonify(error="Request validation failed. Reload the page and try again."), 400
        return function(*args, **kwargs)
    return wrapped


def _valid_csrf():
    expected = session.get("csrf_token", "")
    supplied = request.headers.get("X-CSRF-Token") or request.form.get("_csrf_token", "")
    return bool(expected and supplied and hmac.compare_digest(expected, supplied))


def _serpapi_key_configured():
    value = os.getenv("SERPAPI_API_KEY", "").strip()
    return bool(value and value.lower() not in {"none", "null", "changeme", "your_api_key", "your_serpapi_api_key"})


def _next_run(interval_days, timezone_name):
    now = datetime.now(ZoneInfo(timezone_name))
    return (now + timedelta(days=interval_days)).astimezone(timezone.utc).isoformat(timespec="seconds")


def _monitor_config(data, current=None):
    def value(key, default=""):
        return data.get(key, current.get(key, default) if current else default)
    name = str(value("name", "Fare watch")).strip()[:80]
    if not name:
        raise ValueError("Enter a monitoring job name.")
    start_date, end_date = str(value("start_date")), str(value("end_date"))
    start, end = date.fromisoformat(start_date), date.fromisoformat(end_date)
    if end < start:
        raise ValueError("End date must be on or after start date.")
    nights, interval, budget = int(value("nights", 7)), int(value("interval_days", 2)), int(value("api_budget", MONITOR_DEFAULT_BUDGET))
    if not 1 <= nights <= 60:
        raise ValueError("Nights must be between 1 and 60.")
    if interval not in MONITOR_INTERVALS:
        raise ValueError("Choose a 1, 2, 3, or 7 day interval.")
    if not 2 <= budget <= MONITOR_MAX_BUDGET:
        raise ValueError(f"Per-run budget must be between 2 and {MONITOR_MAX_BUDGET} calls.")
    timezone_name = str(value("timezone", "Asia/Kolkata"))
    try:
        ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as error:
        raise ValueError("Choose a valid IANA timezone.") from error
    codes = {}
    for key in ("leg1_origin", "leg1_destination", "leg2_origin", "leg2_destination"):
        code = str(value(key)).strip().upper()
        if not code or len(code) > 100 or any(ord(c) < 32 for c in code):
            raise ValueError("Each leg needs a valid airport code or supported airport group.")
        codes[key] = code
    # Create and update forms submit the complete configuration. An omitted
    # checkbox therefore means explicitly paused in either operation.
    enabled = str(data.get("enabled", "0")).lower() in {"1", "true", "on", "yes"}
    config = {"name": name, "enabled": int(enabled), "start_date": start.isoformat(), "end_date": end.isoformat(),
              "nights": nights, "interval_days": interval, "timezone": timezone_name, "api_budget": budget,
              "notify_telegram": int(str(value("notify_telegram", "0")).lower() in {"1", "true", "on", "yes"}), **codes}
    config["next_run_at"] = _next_run(interval, timezone_name) if enabled else None
    return config


def _execute_monitor(job):
    if not _serpapi_key_configured():
        error = "SERPAPI_API_KEY is missing or contains a placeholder value. Configure the provider credential before running a search."
        finish_monitor_run(job, "failed", error=error)
        return {"status": "failed", "error": error}
    try:
        run_budget = int(job["api_budget"])
    except (KeyError, TypeError, ValueError):
        run_budget = -1
    if run_budget < 2 or run_budget > MONITOR_MAX_BUDGET or run_budget > MAX_WEB_SERPAPI_BUDGET:
        error = f"Saved job budget is outside the current server limit (2–{MONITOR_MAX_BUDGET} calls). Update the job before running."
        finish_monitor_run(job, "failed", error=error)
        return {"status": "failed", "error": error}
    cursor = int(job.get("rotation_cursor", 0))
    try:
        provider = SerpApiProvider()
        report = search_multi_leg_itineraries(start_date=job["start_date"], end_date=job["end_date"],
            international_provider=provider, serpapi_budget=run_budget, leg1_origin=job["leg1_origin"],
            leg1_destination=job["leg1_destination"], leg2_origin=job["leg2_origin"], leg2_destination=job["leg2_destination"],
            nights_between_departures=int(job["nights"]), combined_candidate_limit=2, rotation_cursor=cursor)
        query_errors = any(leg.get("response_errors") for leg in report.get("leg_stats", []))
        # Budget-based date sampling is the designed search plan. A run is
        # incomplete only when a provider call failed or a planned stage was
        # actually skipped after planning, not merely because the full window
        # is larger than this run's conservative sample.
        incomplete_stage = bool(report.get("incomplete_reason"))
        status = "failed" if not report.get("serpapi_calls") else ("partially_succeeded" if query_errors or incomplete_stage else "succeeded")
        error = report.get("incomplete_reason") or ("Some provider searches failed." if query_errors else None)
        finish_monitor_run(job, status, report, error, _next_run(int(job["interval_days"]), job["timezone"]) if job["enabled"] else None)
        if job.get("notify_telegram"):
            if status != "succeeded":
                mark_monitor_notification(job["run_id"], sent=False, error="Notification skipped because the search was failed or incomplete.")
                return {"status": status, "report": report, "error": error}
            useful_change = any(change.get("type") in {"new_itinerary", "fare_decreased", "fare_increased"}
                                for change in report.get("fare_changes", []))
            if report.get("itineraries") and not useful_change:
                mark_monitor_notification(job["run_id"], sent=False, error="Notification skipped: no new itinerary or material fare change.")
                return {"status": status, "report": report, "error": error}
            try:
                sent = _send_monitor_notification(job, report, status)
                mark_monitor_notification(job["run_id"], sent=sent,
                    error=None if sent else "Telegram bot token or chat ID is not configured.")
            except Exception as notification_error:
                safe_notification_error = str(notification_error)
                for secret in (os.getenv("TELEGRAM_BOT_TOKEN", ""), os.getenv("TELEGRAM_CHAT_ID", "")):
                    if secret:
                        safe_notification_error = safe_notification_error.replace(secret, "[redacted]")
                mark_monitor_notification(job["run_id"], sent=False, error=f"Telegram delivery failed: {safe_notification_error}")
        return {"status": status, "report": report, "error": error}
    except Exception as error:
        safe_error = str(error)
        for secret_name in ("SERPAPI_API_KEY", "TELEGRAM_BOT_TOKEN", "MONITOR_OWNER_PASSWORD", "FLASK_SECRET_KEY"):
            secret = os.getenv(secret_name, "")
            if secret:
                safe_error = safe_error.replace(secret, "[redacted]")
        finish_monitor_run(job, "failed", error=safe_error, next_run_at=_next_run(int(job["interval_days"]), job["timezone"]) if job["enabled"] else None)
        return {"status": "failed", "error": safe_error}


def _send_monitor_notification(job, report, status):
    token, chat_id = os.getenv("TELEGRAM_BOT_TOKEN", "").strip(), os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id or token.lower() in {"none", "null", "changeme", "your_bot_token"}:
        return False
    import requests
    best = min(report.get("itineraries", []), key=lambda item: item.get("total_price_inr", float("inf")), default=None)
    changes = report.get("fare_changes", [])
    combined = report.get("combined_results", [])
    verified = sum(result.get("status") == "priced" for result in combined)
    combined_status = f"{verified}/{len(combined)} combined checks priced" if combined else "no combined checks completed"
    message = (f"Fare check: {job['name']} · {job['leg1_origin']}–{job['leg1_destination']} / "
               f"{job['leg2_origin']}–{job['leg2_destination']}\nStatus: {status}\n"
               f"Window: {job['start_date']} to {job['end_date']} · completed {datetime.now(ZoneInfo(job['timezone'])).isoformat(timespec='minutes')}\n"
               f"Best observed: INR {best['total_price_inr']:,.0f}" if best else
               f"Fare check: {job['name']}\nStatus: {status} · no newly priced itinerary\nWindow: {job['start_date']} to {job['end_date']} · completed {datetime.now(ZoneInfo(job['timezone'])).isoformat(timespec='minutes')}")
    message += (f"\nCoverage: {report.get('covered_date_pairs', 0)}/{report.get('valid_date_pairs', 0)} date pairs; "
                f"{combined_status}\nSerpApi calls: {report.get('serpapi_calls', 0)}/{job['api_budget']}")
    summary = report.get("fare_change_summary", {})
    message += (f"\nFare changes: {summary.get('new_itinerary', 0)} new, "
                f"{summary.get('fare_decreased', 0)} decreased, {summary.get('fare_increased', 0)} increased, "
                f"{summary.get('no_material_change', 0)} unchanged, {summary.get('not_observed', 0)} not observed")
    shown_changes = 0
    for change in changes:
        if change["type"] in {"fare_decreased", "fare_increased"}:
            if shown_changes >= 5:
                break
            message += (f"\n{change['type'].replace('_', ' ').title()}: {change['route']} "
                        f"({change['leg1_date']} / {change['leg2_date']}) · {change['currency']} {change['previous_fare']:,.0f} → "
                        f"{change['currency']} {change['current_fare']:,.0f} (Δ {change['currency']} {change['absolute_change']:,.0f}; "
                        f"{change['percentage_change']:+.2f}%)")
            shown_changes += 1
        elif change["type"] == "new_itinerary":
            if shown_changes >= 5:
                break
            message += f"\nNew itinerary: {change['route']} ({change['leg1_date']} / {change['leg2_date']}) · {change['currency']} {change['fare']:,.0f}"
            shown_changes += 1
    total_alertable = sum(change.get("type") in {"new_itinerary", "fare_decreased", "fare_increased"} for change in changes)
    if total_alertable > shown_changes:
        message += f"\n{total_alertable - shown_changes} additional new/material changes are in the dashboard."
    if report.get("incomplete_reason"):
        message += f"\nLimit: {report['incomplete_reason']}"
    message += "\nObserved fares may change before booking."
    response = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": message}, timeout=10)
    response.raise_for_status()
    return True


@app.get("/monitor/login")
def monitor_login():
    session.setdefault("csrf_token", secrets.token_urlsafe(32))
    return render_template("monitor_login.html", error=None, csrf_token=session["csrf_token"])


@app.post("/monitor/login")
def monitor_login_post():
    expected = os.getenv("MONITOR_OWNER_PASSWORD", "")
    if len(expected) < 12 or len(app.secret_key or "") < 32:
        return render_template("monitor_login.html", error="Configure MONITOR_OWNER_PASSWORD (at least 12 characters) and FLASK_SECRET_KEY (at least 32 characters) on the web service.", csrf_token=session.setdefault("csrf_token", secrets.token_urlsafe(32))), 503
    if not _valid_csrf():
        return render_template("monitor_login.html", error="Request validation failed. Reload the page and try again.", csrf_token=session.setdefault("csrf_token", secrets.token_urlsafe(32))), 400
    if not hmac.compare_digest(request.form.get("password", ""), expected):
        return render_template("monitor_login.html", error="Password was not accepted.", csrf_token=session["csrf_token"]), 401
    session["monitor_owner"] = True
    session["csrf_token"] = secrets.token_urlsafe(32)
    return redirect(url_for("monitor_dashboard"))


@app.post("/monitor/logout")
@monitor_auth_required
def monitor_logout():
    session.clear()
    return redirect(url_for("index"))


@app.get("/monitor")
@monitor_auth_required
def monitor_dashboard():
    initialize_database()
    jobs = list_monitor_jobs()
    runs = {str(job["id"]): list_monitor_runs(job["id"]) for job in jobs}
    histories = {str(job["id"]): get_monitor_fare_history(job["id"]) for job in jobs}
    for job_runs in runs.values():
        for run in job_runs:
            try:
                run["result"] = json.loads(run["result_json"] or "{}")
            except (TypeError, json.JSONDecodeError):
                run["result"] = {}
    session.setdefault("csrf_token", secrets.token_urlsafe(32))
    return render_template("monitor.html", jobs=jobs, runs=runs, histories=histories, csrf_token=session["csrf_token"],
                           max_budget=MONITOR_MAX_BUDGET, default_budget=MONITOR_DEFAULT_BUDGET,
                           readiness=_monitor_readiness())


def _monitor_readiness():
    checks = {
        "owner_auth": (len(os.getenv("FLASK_SECRET_KEY", "")) >= 32 and len(os.getenv("MONITOR_OWNER_PASSWORD", "")) >= 12, "Set FLASK_SECRET_KEY (at least 32 characters) and MONITOR_OWNER_PASSWORD (at least 12 characters) on the web service."),
        "search_provider": (_serpapi_key_configured(), "Set SERPAPI_API_KEY on the web service and scheduler host. Presence is checked locally; provider acceptance requires a live request."),
        "database_configuration": (True, "DATABASE_URL selects shared PostgreSQL when present; otherwise FLIGHT_DATABASE_PATH (default data/flights.db) selects local SQLite."),
        "request_budget": (MONITOR_BUDGET_CONFIG_ERROR is None and MONITOR_MAX_BUDGET >= 2, MONITOR_BUDGET_CONFIG_ERROR or "Set MONITOR_MAX_SERPAPI_BUDGET and MAX_WEB_SERPAPI_BUDGET to allow at least 2 calls."),
        "scheduler_gate": (os.getenv("FARE_MONITOR_ENABLED", "").lower() == "true", "Set repository variable FARE_MONITOR_ENABLED=true only after runner and shared storage are ready."),
        "telegram": (bool(os.getenv("TELEGRAM_BOT_TOKEN", "").strip() and os.getenv("TELEGRAM_CHAT_ID", "").strip()), "Telegram is optional; configure both TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID if notifications are enabled."),
    }
    try:
        initialize_database()
        from flight_search.database.db import check_database_readiness
        check_database_readiness()
        database = {"status": "ready", "message": "Database is reachable."}
    except Exception:
        database = {"status": "missing", "message": "Database is unavailable; verify the configured database connection and network access."}
    return {"monitoring_enabled": os.getenv("FARE_MONITOR_ENABLED", "").lower() == "true",
            "checks": {name: {"status": "ready" if ok else "missing", "message": note} for name, (ok, note) in checks.items()},
            "database": database,
            "scheduler": {"status": "configured" if os.getenv("GITHUB_ACTIONS") == "true" and os.getenv("RUNNER_NAME") else "not_verified",
                          "message": "GitHub-hosted runner environment detected; this does not verify the workflow schedule or a successful run." if os.getenv("GITHUB_ACTIONS") == "true" else "GitHub Actions must be deliberately configured; scheduled events use the workflow on the repository default branch."}}


@app.get("/healthz")
def healthz():
    """Non-secret connectivity check for local startup and workflow preflight."""
    try:
        from flight_search.database.db import check_database_readiness
        check_database_readiness()
        return jsonify(status="ready", database="reachable"), 200
    except Exception:
        return jsonify(status="unavailable", database="unreachable"), 503


@app.get("/api/monitor/readiness")
@monitor_auth_required
def monitor_readiness():
    return jsonify(_monitor_readiness())


@app.post("/api/monitor/jobs")
@monitor_auth_required
def monitor_create():
    try:
        config = _monitor_config(request.form)
        return redirect(url_for("monitor_dashboard", saved=save_monitor_job(config)["id"]))
    except (ValueError, TypeError) as error:
        return jsonify(error=str(error)), 400


@app.post("/api/monitor/jobs/<int:job_id>")
@monitor_auth_required
def monitor_update(job_id):
    current = get_monitor_job(job_id)
    if not current:
        abort(404)
    try:
        config = _monitor_config(request.form, current)
        save_monitor_job(config, job_id)
        return redirect(url_for("monitor_dashboard", saved=job_id))
    except (ValueError, TypeError) as error:
        return jsonify(error=str(error)), 400


@app.post("/api/monitor/jobs/<int:job_id>/run")
@monitor_auth_required
def monitor_run(job_id):
    job = claim_monitor_run(job_id)
    if not job:
        return jsonify(error="Job is missing or already running."), 409
    outcome = _execute_monitor(job)
    return jsonify(outcome or {"status": "failed"}), 200 if outcome and outcome["status"] != "failed" else 502


@app.post("/api/monitor/jobs/<int:job_id>/delete")
@monitor_auth_required
def monitor_delete(job_id):
    delete_monitor_job(job_id)
    return redirect(url_for("monitor_dashboard"))


@app.cli.command("run-due-monitors")
def run_due_monitors():
    """Run due jobs once; invoke from a persistent scheduled worker."""
    if os.getenv("FARE_MONITOR_ENABLED", "").lower() != "true":
        print("Fare monitoring scheduler gate is disabled; no jobs were run.")
        return
    initialize_database()
    for job in list_monitor_jobs():
        claimed = claim_monitor_run(job["id"], due_only=True)
        if claimed:
            outcome = _execute_monitor(claimed)
            print(f"monitor {job['id']}: {(outcome or {}).get('status', 'failed')}")


@app.cli.command("db-ready")
def db_ready():
    """Initialize the schema and check connectivity without fare searches."""
    try:
        initialize_database()
        from flight_search.database.db import check_database_readiness
        check_database_readiness()
    except Exception:
        print("Database unavailable; check local configuration and network access.")
        raise SystemExit(1)
    print("Database ready.")


def _default_form_data():
    return {
        "start_date": MULTI_LEG_START_DATE,
        "end_date": MULTI_LEG_END_DATE,
        "leg1_origin": MULTI_LEG_LEG1_ORIGIN,
        "leg1_destination": MULTI_LEG_LEG1_DESTINATION,
        "leg2_origin": MULTI_LEG_LEG2_ORIGIN,
        "leg2_destination": MULTI_LEG_LEG2_DESTINATION,
        "nights_between_departures": str(MULTI_LEG_NIGHTS_BETWEEN_DEPARTURES),
        "serpapi_budget": str(MULTI_LEG_SERPAPI_BUDGET),
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
    if needs_live_api and not _serpapi_key_configured():
        return _render_index(
            form_data,
            "Missing SERPAPI_API_KEY in .env for the selected live searches.",
            500,
        )

    try:
        initialize_database()
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
    """Map original timestamp/price samples to an SVG with labeled date and fare axes."""
    if not points:
        return {"polyline": "", "points": [], "x_ticks": [], "y_ticks": []}

    points = sorted(points, key=lambda point: point["timestamp"])
    times = [point["timestamp"] for point in points]
    prices = [point["price"] for point in points]
    min_time, max_time = min(times), max(times)
    raw_min_price, raw_max_price = min(prices), max(prices)

    # Add a little vertical breathing room without inventing any observations.
    if raw_min_price == raw_max_price:
        padding = max(abs(raw_min_price) * 0.05, 1)
    else:
        padding = (raw_max_price - raw_min_price) * 0.08
    scale_min = max(0, raw_min_price - padding)
    scale_max = raw_max_price + padding
    if scale_max <= scale_min:
        scale_max = scale_min + 1

    left, right, top, bottom = 76, 580, 24, 190
    plotted = []
    for point in points:
        x = (left + right) / 2 if max_time == min_time else left + (point["timestamp"] - min_time) * (right - left) / (max_time - min_time)
        y = bottom - (point["price"] - scale_min) * (bottom - top) / (scale_max - scale_min)
        plotted.append({"x": round(x, 2), "y": round(y, 2), "label": point["label"]})

    tick_times = sorted({times[0], times[len(times) // 2], times[-1]})
    x_ticks = [
        {
            "x": round((left + right) / 2 if max_time == min_time else left + (timestamp - min_time) * (right - left) / (max_time - min_time), 2),
            "label": datetime.fromtimestamp(timestamp, timezone.utc).strftime("%d %b %y"),
        }
        for timestamp in tick_times
    ]
    y_ticks = []
    for index in range(5):
        value = scale_min + (scale_max - scale_min) * index / 4
        y = bottom - (value - scale_min) * (bottom - top) / (scale_max - scale_min)
        label = f"{value:,.0f}" if abs(value - round(value)) < 0.01 else f"{value:,.1f}"
        y_ticks.append({"y": round(y, 2), "value": value, "label": label})

    return {
        "polyline": " ".join(f"{point['x']},{point['y']}" for point in plotted),
        "points": plotted,
        "x_ticks": x_ticks,
        "y_ticks": y_ticks,
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
    # Development convenience only. Production must use a WSGI server.
    app.run(host="127.0.0.1", port=5000, debug=False)
