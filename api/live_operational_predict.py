"""Continuously combine live METAR weather, airport flights, and predictions.

Weather comes from the public AviationWeather.gov METAR API. Airport flight
operations come from AeroDataBox when an API key is configured. The deployed
model is still the historical BTS/ARCO-ERA5 model, so AeroDataBox fields are
logged as live operational context rather than model inputs until the feature
contract is retrained to include flight-status features.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from pyspark.sql import functions as F

from spark_jobs.build_gold_features import NUMERIC_FEATURES
from spark_jobs.common import create_spark_session, load_settings, s3a_uri


AVIATION_WEATHER_METAR_URL = "https://aviationweather.gov/api/data/metar"
AERODATABOX_RAPIDAPI_BASE_URL = "https://aerodatabox.p.rapidapi.com"
AERODATABOX_APIMARKET_BASE_URL = "https://prod.api.market/api/v1/aedbx/aerodatabox"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--airport", default="JFK", help="IATA airport code, for example JFK or ATL.")
    parser.add_argument("--distance-miles", type=float, default=1000.0)
    parser.add_argument("--api-url", default="http://localhost:3000/predict")
    parser.add_argument("--source", default="external_live_operational")
    parser.add_argument("--watch", action="store_true", help="Continuously poll live data until stopped.")
    parser.add_argument("--interval-seconds", type=int, default=300)
    parser.add_argument("--max-iterations", type=int, default=None)
    parser.add_argument("--output-jsonl", default=None)
    parser.add_argument(
        "--flight-window-offset-minutes",
        type=int,
        default=-120,
        help="AeroDataBox relative airport schedule window start.",
    )
    parser.add_argument(
        "--flight-window-duration-minutes",
        type=int,
        default=360,
        help="AeroDataBox relative airport schedule window duration.",
    )
    parser.add_argument(
        "--require-flight-api",
        action="store_true",
        help="Fail if AeroDataBox credentials are not configured.",
    )
    return parser.parse_args()


def airport_metadata(iata_code: str) -> dict[str, Any]:
    settings = load_settings()
    spark = create_spark_session("lookup-airport-live-operational", settings)
    try:
        airports = spark.read.parquet(
            s3a_uri(settings.raw_bucket, "metadata/ourairports/us_airports_selected_with_era5_grid.parquet")
        )
        row = (
            airports.filter(F.upper(F.col("iata_code")) == iata_code.upper())
            .select("name", "iata_code", "icao_code", "gps_code", "ident", "latitude_deg", "longitude_deg")
            .limit(1)
            .collect()
        )
        if not row:
            raise RuntimeError(f"Airport not found in metadata: {iata_code}")
        item = row[0].asDict()
        icao = item.get("icao_code") or item.get("gps_code") or item.get("ident")
        return {
            "iata": str(item["iata_code"]).upper(),
            "icao": str(icao).upper(),
            "name": str(item["name"]),
            "latitude": float(item["latitude_deg"]),
            "longitude": float(item["longitude_deg"]),
        }
    finally:
        spark.stop()


def fetch_metar(icao_code: str) -> dict[str, Any]:
    response = requests.get(
        AVIATION_WEATHER_METAR_URL,
        params={"ids": icao_code.upper(), "format": "json"},
        headers={"User-Agent": "big-data-project-aviation-demo/1.0"},
        timeout=20,
    )
    if response.status_code == 204:
        raise RuntimeError(f"No recent METAR returned for {icao_code}")
    response.raise_for_status()
    data = response.json()
    if not data:
        raise RuntimeError(f"Empty METAR response for {icao_code}")
    return data[0]


def aerodatabox_configured() -> bool:
    return bool(os.getenv("AERODATABOX_API_KEY"))


def aerodatabox_headers() -> dict[str, str]:
    key = os.getenv("AERODATABOX_API_KEY")
    marketplace = os.getenv("AERODATABOX_MARKETPLACE", "rapidapi").lower()
    if not key:
        return {}
    if marketplace == "apimarket":
        return {"x-magicapi-key": key, "Accept": "application/json"}
    return {
        "X-RapidAPI-Key": key,
        "X-RapidAPI-Host": os.getenv("AERODATABOX_RAPIDAPI_HOST", "aerodatabox.p.rapidapi.com"),
        "Accept": "application/json",
    }


def aerodatabox_base_url() -> str:
    configured = os.getenv("AERODATABOX_BASE_URL")
    if configured:
        return configured.rstrip("/")
    if os.getenv("AERODATABOX_MARKETPLACE", "rapidapi").lower() == "apimarket":
        return AERODATABOX_APIMARKET_BASE_URL
    return AERODATABOX_RAPIDAPI_BASE_URL


def fetch_airport_flights(iata_code: str, offset_minutes: int, duration_minutes: int) -> dict[str, Any] | None:
    if not aerodatabox_configured():
        return None
    url = f"{aerodatabox_base_url()}/flights/airports/iata/{iata_code.upper()}"
    response = requests.get(
        url,
        params={
            "offsetMinutes": offset_minutes,
            "durationMinutes": duration_minutes,
            "direction": "Both",
            "withLeg": "true",
            "withCancelled": "true",
            "withCodeshared": "false",
            "withCargo": "false",
            "withPrivate": "false",
            "withLocation": "false",
        },
        headers=aerodatabox_headers(),
        timeout=30,
    )
    if response.status_code == 204:
        return {"arrivals": [], "departures": []}
    response.raise_for_status()
    return response.json()


def parse_iso_time(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def flight_delay_minutes(flight: dict[str, Any]) -> float | None:
    movement = flight.get("movement") or {}
    scheduled = parse_iso_time((movement.get("scheduledTime") or {}).get("local"))
    actual = parse_iso_time((movement.get("actualTime") or {}).get("local"))
    estimated = parse_iso_time((movement.get("revisedTime") or {}).get("local"))
    observed = actual or estimated
    if not scheduled or not observed:
        return None
    return max(0.0, (observed - scheduled).total_seconds() / 60.0)


def summarize_flights(payload: dict[str, Any] | None) -> dict[str, Any]:
    if payload is None:
        return {
            "provider": "AeroDataBox",
            "available": False,
            "reason": "AERODATABOX_API_KEY is not configured",
        }

    departures = payload.get("departures") or []
    arrivals = payload.get("arrivals") or []
    flights = departures + arrivals
    statuses = [str(f.get("status") or "unknown") for f in flights]
    delays = [value for value in (flight_delay_minutes(f) for f in flights) if value is not None]
    cancelled = sum(1 for status in statuses if "cancel" in status.lower())
    diverted = sum(1 for status in statuses if "divert" in status.lower())
    delayed = sum(1 for value in delays if value >= 15.0)
    sample = []
    for flight in flights[:5]:
        movement = flight.get("movement") or {}
        sample.append(
            {
                "number": (flight.get("number") or flight.get("callSign") or "").strip(),
                "status": flight.get("status"),
                "scheduled_local": (movement.get("scheduledTime") or {}).get("local"),
                "actual_local": (movement.get("actualTime") or {}).get("local"),
                "revised_local": (movement.get("revisedTime") or {}).get("local"),
                "airport": (movement.get("airport") or {}).get("iata"),
            }
        )
    return {
        "provider": "AeroDataBox",
        "available": True,
        "departures_count": len(departures),
        "arrivals_count": len(arrivals),
        "total_flights": len(flights),
        "delayed_15min_count": delayed,
        "cancelled_count": cancelled,
        "diverted_count": diverted,
        "average_observed_delay_minutes": round(sum(delays) / len(delays), 2) if delays else None,
        "status_counts": {status: statuses.count(status) for status in sorted(set(statuses))},
        "sample_flights": sample,
    }


def metar_cloud_cover_fraction(metar: dict[str, Any]) -> float:
    cover = str(metar.get("cover") or "").upper()
    mapping = {
        "CLR": 0.0,
        "SKC": 0.0,
        "FEW": 0.2,
        "SCT": 0.4,
        "BKN": 0.75,
        "OVC": 1.0,
        "VV": 1.0,
    }
    return mapping.get(cover, 0.0)


def metar_precipitation_proxy(metar: dict[str, Any]) -> float:
    raw = str(metar.get("rawOb") or "")
    return 1.0 if re.search(r"\\b(-|\\+|VC)?(RA|SN|DZ|PL|GR|GS|TS)\\b", raw) else 0.0


def build_features_from_metar(metar: dict[str, Any], distance_miles: float) -> dict[str, float]:
    report_time = parse_iso_time(metar.get("reportTime")) or datetime.now(timezone.utc)
    features = {
        "scheduled_departure_hour_local": float(report_time.hour),
        "distance_miles": float(distance_miles),
        "day_of_week": float(report_time.isoweekday() % 7 + 1),
        "day_of_month": float(report_time.day),
        "temperature_c_avg": float(metar.get("temp") or 0.0),
        "wind_speed_kts_max": float(metar.get("wspd") or 0.0),
        "wind_gust_kts_max": float(metar.get("wgst") or metar.get("wspd") or 0.0),
        "precipitation_mm_sum": metar_precipitation_proxy(metar),
        "surface_pressure_pa_avg": float(metar.get("altim") or metar.get("slp") or 1013.25) * 100.0,
        "total_cloud_cover_avg": metar_cloud_cover_fraction(metar),
        "cape_j_kg_max": 0.0,
    }
    return {name: features[name] for name in NUMERIC_FEATURES}


def call_prediction_api(api_url: str, features: dict[str, float], source: str) -> dict[str, Any]:
    response = requests.post(api_url, json={"features": features, "source": source}, timeout=15)
    response.raise_for_status()
    return response.json()


def append_jsonl(path: str | None, event: dict[str, Any]) -> Path | None:
    if not path:
        return None
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")
    return output_path


def predict_once(args: argparse.Namespace, airport: dict[str, Any]) -> dict[str, Any]:
    metar = fetch_metar(airport["icao"])
    flights = fetch_airport_flights(
        airport["iata"],
        offset_minutes=args.flight_window_offset_minutes,
        duration_minutes=args.flight_window_duration_minutes,
    )
    features = build_features_from_metar(metar, args.distance_miles)
    prediction = call_prediction_api(args.api_url, features, args.source)
    return {
        "event_time_utc": datetime.now(timezone.utc).isoformat(),
        "airport": airport,
        "aviation_weather_metar": {
            "provider": "AviationWeather.gov",
            "icao": metar.get("icaoId"),
            "report_time": metar.get("reportTime"),
            "flight_category": metar.get("fltCat"),
            "temperature_c": metar.get("temp"),
            "wind_speed_kts": metar.get("wspd"),
            "wind_gust_kts": metar.get("wgst"),
            "altimeter_hpa": metar.get("altim"),
            "cloud_cover": metar.get("cover"),
            "raw": metar.get("rawOb"),
        },
        "aerodatabox_operations": summarize_flights(flights),
        "features": features,
        "api_response": prediction,
    }


def print_event(event: dict[str, Any], iteration: int | None = None) -> None:
    response = event["api_response"]
    metar = event["aviation_weather_metar"]
    ops = event["aerodatabox_operations"]
    compact = {
        "iteration": iteration,
        "event_time_utc": event["event_time_utc"],
        "airport": event["airport"]["iata"],
        "metar_time": metar["report_time"],
        "flight_category": metar["flight_category"],
        "temperature_c": metar["temperature_c"],
        "wind_speed_kts": metar["wind_speed_kts"],
        "aerodatabox_available": ops["available"],
        "live_flights": ops.get("total_flights"),
        "delayed_15min": ops.get("delayed_15min_count"),
        "cancelled": ops.get("cancelled_count"),
        "prediction": response.get("prediction"),
        "disruption_probability": response.get("disruption_probability"),
        "risk_band": response.get("risk_band"),
    }
    print(json.dumps(compact, sort_keys=True), flush=True)


def run(args: argparse.Namespace) -> None:
    if args.output_jsonl:
        args.output_jsonl = str(Path(args.output_jsonl).expanduser().resolve())
    if args.require_flight_api and not aerodatabox_configured():
        raise RuntimeError("AERODATABOX_API_KEY is required when --require-flight-api is set")
    if args.interval_seconds < 1:
        raise ValueError("--interval-seconds must be at least 1")

    airport = airport_metadata(args.airport)
    if args.watch:
        print(
            f"Starting live operational prediction for {airport['iata']} every {args.interval_seconds}s. "
            "Press Ctrl+C to stop.",
            flush=True,
        )
        if args.output_jsonl:
            print(f"Appending events to {args.output_jsonl}", flush=True)
        iteration = 0
        try:
            while args.max_iterations is None or iteration < args.max_iterations:
                iteration += 1
                event = predict_once(args, airport)
                written_path = append_jsonl(args.output_jsonl, event)
                print_event(event, iteration)
                if written_path:
                    print(f"written_jsonl={written_path}", flush=True)
                if args.max_iterations is not None and iteration >= args.max_iterations:
                    break
                time.sleep(args.interval_seconds)
        except KeyboardInterrupt:
            print("\nStopped live operational prediction.", flush=True)
        return

    event = predict_once(args, airport)
    append_jsonl(args.output_jsonl, event)
    print("Airport:", json.dumps(event["airport"], indent=2))
    print("AviationWeather.gov METAR:", json.dumps(event["aviation_weather_metar"], indent=2))
    print("AeroDataBox operations:", json.dumps(event["aerodatabox_operations"], indent=2))
    print("Prediction features:", json.dumps(event["features"], indent=2))
    print("API response:", json.dumps(event["api_response"], indent=2))


def main() -> None:
    run(parse_args())


if __name__ == "__main__":
    main()
