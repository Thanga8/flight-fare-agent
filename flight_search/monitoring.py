"""Stable itinerary identity and comparable fare-change classification."""

from __future__ import annotations

import hashlib
import json
import math
import re


def _airport_time(value):
    if not isinstance(value, dict):
        return None, None
    airport = str(value.get("id") or "").strip().upper() or None
    raw_time = str(value.get("time") or "").strip()
    # SerpApi supplies local airport times. Normalize formatting to minute precision.
    match = re.search(r"(\d{4}-\d{2}-\d{2})[ T]+(\d{1,2}:\d{2})", raw_time)
    normalized = f"{match.group(1)}T{match.group(2).zfill(5)}" if match else None
    return airport, normalized


def _flight_segments(fare):
    flight = fare.get("flight") or {}
    result = []
    for segment in flight.get("flights") or []:
        dep_airport, dep_time = _airport_time(segment.get("departure_airport"))
        arr_airport, arr_time = _airport_time(segment.get("arrival_airport"))
        airline = str(segment.get("airline_code") or segment.get("airline") or "").strip().upper() or None
        flight_number = str(segment.get("flight_number") or "").strip().upper() or None
        result.append({"from": dep_airport, "to": arr_airport, "departure": dep_time,
                       "arrival": arr_time, "airline": airline, "flight_number": flight_number})
    return result


def itinerary_identity(itinerary, job):
    """Return a deterministic scope-sensitive identity; skip under-specified data."""
    legs = []
    for key in ("leg1", "leg2"):
        fare = itinerary.get(key) or {}
        segments = _flight_segments(fare)
        if (not segments or any(not segment["from"] or not segment["to"] or
                                not segment["departure"] and not segment["flight_number"] for segment in segments)):
            return None
        if not fare.get("departure_date"):
            return None
        legs.append({"departure_date": fare.get("departure_date"), "segments": segments})
    scope = {"route": [job.get("leg1_origin"), job.get("leg1_destination"), job.get("leg2_origin"), job.get("leg2_destination")],
             "window": [job.get("start_date"), job.get("end_date")], "nights": int(job.get("nights", 0)),
             "currency_context": "INR", "cabin_context": job.get("cabin", "provider-default"),
             "passenger_context": job.get("passengers", "provider-default")}
    identity = {"scope": scope, "legs": legs}
    encoded = json.dumps(identity, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest(), identity


def normalize_run_itineraries(report, job):
    """Deduplicate results by identity; keep the lowest total fare in each run."""
    by_identity = {}
    for itinerary in report.get("itineraries") or []:
        identity = itinerary_identity(itinerary, job)
        try:
            fare = float(itinerary["total_price_inr"])
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
        if not math.isfinite(fare) or fare <= 0:
            continue
        if not identity:
            continue
        key, details = identity
        route = " → ".join([str(job.get("leg1_origin")), str(job.get("leg1_destination")), str(job.get("leg2_destination"))])
        label = describe_identity(details)
        observation = {"identity_key": key, "identity": details, "fare": fare, "currency": "INR",
                       "route": f"{route} · {label}" if label else route,
                       "leg1_date": itinerary["leg1"].get("departure_date"),
                       "leg2_date": itinerary["leg2"].get("departure_date"),
                       "itinerary_label": label, "itinerary": itinerary}
        if key not in by_identity or fare < by_identity[key]["fare"]:
            by_identity[key] = observation
    return list(by_identity.values())


def describe_identity(identity):
    parts = []
    for leg in identity.get("legs", []):
        segments = []
        for segment in leg.get("segments", []):
            number = " ".join(part for part in (segment.get("airline"), segment.get("flight_number")) if part)
            depart = segment.get("departure", "")
            segments.append(f"{number + ' ' if number else ''}{segment.get('from')}→{segment.get('to')} {depart}")
        parts.append(" / ".join(segments))
    return " · ".join(parts)


def classify_fare_changes(current, previous, *, previous_run=None, min_absolute_inr=1000, min_percent=3):
    """Compare each itinerary to its latest successful observation.

    `previous_run` is the immediately preceding successful run and is used
    only for the non-observation label. Missing dates are not fare changes.
    """
    previous_by_key = {item["identity_key"]: item for item in previous}
    missing_baseline = previous if previous_run is None else previous_run
    missing_by_key = {item["identity_key"]: item for item in missing_baseline}
    current_by_key = {item["identity_key"]: item for item in current}
    changes = []
    for key, item in current_by_key.items():
        old = previous_by_key.get(key)
        if not old:
            changes.append({"type": "new_itinerary", **item})
            continue
        if old["currency"] != item["currency"]:
            changes.append({"type": "currency_mismatch", "identity_key": key, "currency": item["currency"],
                            "previous_currency": old["currency"], "itinerary": item["itinerary"],
                            "leg1_date": item["leg1_date"], "leg2_date": item["leg2_date"]})
            continue
        diff = round(item["fare"] - float(old["fare"]), 2)
        pct = round((diff / float(old["fare"])) * 100, 2) if old["fare"] else None
        material = (item["currency"] == "INR" and pct is not None and
                    abs(diff) >= min_absolute_inr and abs(pct) >= min_percent)
        changes.append({"type": ("fare_decreased" if diff < 0 else "fare_increased") if material else "no_material_change",
                        "identity_key": key, "identity": item["identity"], "route": item["route"],
                        "itinerary_label": item.get("itinerary_label"),
                        "leg1_date": item["leg1_date"], "leg2_date": item["leg2_date"],
                        "currency": item["currency"], "previous_fare": float(old["fare"]), "current_fare": item["fare"],
                        "absolute_change": abs(diff), "signed_change": diff, "percentage_change": pct,
                        "previous_observed_at": old["observed_at"], "current_observed_at": item.get("observed_at"),
                        "itinerary": item["itinerary"]})
    for key, old in missing_by_key.items():
        if key not in current_by_key:
            changes.append({"type": "not_observed", "identity_key": key, "identity": old.get("identity"),
                            "route": old.get("route"), "itinerary_label": old.get("itinerary_label"), "leg1_date": old.get("leg1_date"),
                            "leg2_date": old.get("leg2_date"), "previous_fare": float(old["fare"]),
                            "currency": old["currency"], "previous_observed_at": old["observed_at"],
                            "message": "Not returned in this run; this does not establish a price change or loss of availability."})
    return changes
