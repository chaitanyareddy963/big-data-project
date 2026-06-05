"""Fetch live airport weather from Open-Meteo and call the prediction API.

This is an inference-only demo. Training still uses the historical ARCO-ERA5
and BTS lakehouse tables; the live API request shows how current conditions can
be transformed into the deployed model's feature contract.
"""

from __future__ import annotations

import json
import argparse
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from pyspark.sql import functions as F

from spark_jobs.build_gold_features import NUMERIC_FEATURES
from spark_jobs.common import create_spark_session, load_settings, s3a_uri


OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--airport", default="JFK", help="IATA airport code from the metadata table.")
    parser.add_argument("--distance-miles", type=float, default=1000.0)
    parser.add_argument("--api-url", default="http://localhost:3000/predict")
    parser.add_argument("--source", default="external_live_weather")
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Continuously poll live weather and call the prediction API until stopped.",
    )
    parser.add_argument(
        "--interval-seconds",
        type=int,
        default=300,
        help="Polling interval for --watch mode. Open-Meteo current weather usually updates every 15 minutes.",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=None,
        help="Optional cap for --watch mode, useful for notebook or presentation demos.",
    )
    parser.add_argument(
        "--output-jsonl",
        default=None,
        help="Optional local JSONL path where each live prediction event is appended.",
    )
    return parser.parse_args()


def airport_coordinates(iata_code: str) -> tuple[float, float, str]:
    settings = load_settings()
    spark = create_spark_session("lookup-airport-live-weather", settings)
    try:
        airports = spark.read.parquet(
            s3a_uri(settings.raw_bucket, "metadata/ourairports/us_airports_selected_with_era5_grid.parquet")
        )
        row = (
            airports.filter(F.upper(F.col("iata_code")) == iata_code.upper())
            .select("name", "latitude_deg", "longitude_deg")
            .limit(1)
            .collect()
        )
        if not row:
            raise RuntimeError(f"Airport not found in metadata: {iata_code}")
        item = row[0].asDict()
        return float(item["latitude_deg"]), float(item["longitude_deg"]), str(item["name"])
    finally:
        spark.stop()


def fetch_live_weather(latitude: float, longitude: float) -> dict:
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": ",".join(
            [
                "temperature_2m",
                "precipitation",
                "wind_speed_10m",
                "wind_gusts_10m",
                "surface_pressure",
                "cloud_cover",
                "cape",
            ]
        ),
        "wind_speed_unit": "kn",
        "timezone": "auto",
    }
    response = requests.get(OPEN_METEO_URL, params=params, timeout=20)
    response.raise_for_status()
    return response.json()


def build_features(weather: dict, distance_miles: float) -> dict[str, float]:
    current = weather["current"]
    observed = datetime.fromisoformat(current["time"])
    features = {
        "scheduled_departure_hour_local": float(observed.hour),
        "distance_miles": float(distance_miles),
        "day_of_week": float(observed.isoweekday() % 7 + 1),
        "day_of_month": float(observed.day),
        "temperature_c_avg": float(current.get("temperature_2m") or 0.0),
        "wind_speed_kts_max": float(current.get("wind_speed_10m") or 0.0),
        "wind_gust_kts_max": float(current.get("wind_gusts_10m") or current.get("wind_speed_10m") or 0.0),
        "precipitation_mm_sum": float(current.get("precipitation") or 0.0),
        "surface_pressure_pa_avg": float(current.get("surface_pressure") or 1013.25) * 100.0,
        "total_cloud_cover_avg": float(current.get("cloud_cover") or 0.0) / 100.0,
        "cape_j_kg_max": float(current.get("cape") or 0.0),
    }
    return {name: features[name] for name in NUMERIC_FEATURES}


def predict_once(args: argparse.Namespace, latitude: float, longitude: float, airport_name: str) -> dict:
    weather = fetch_live_weather(latitude, longitude)
    features = build_features(weather, args.distance_miles)
    response = requests.post(args.api_url, json={"features": features, "source": args.source}, timeout=15)
    response.raise_for_status()
    return {
        "event_time_utc": datetime.now(timezone.utc).isoformat(),
        "airport": {
            "iata": args.airport.upper(),
            "name": airport_name,
            "latitude": latitude,
            "longitude": longitude,
        },
        "open_meteo_current": weather["current"],
        "features": features,
        "api_response": response.json(),
    }


def append_jsonl(path: str | None, event: dict) -> Path | None:
    if not path:
        return None
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")
    return output_path


def print_event(event: dict) -> None:
    print("Live airport:", json.dumps(event["airport"]))
    print("Open-Meteo current:", json.dumps(event["open_meteo_current"], indent=2))
    print("Prediction features:", json.dumps(event["features"], indent=2))
    print("API response:", json.dumps(event["api_response"], indent=2))


def print_watch_event(iteration: int, event: dict) -> None:
    response = event["api_response"]
    current = event["open_meteo_current"]
    print(
        json.dumps(
            {
                "iteration": iteration,
                "event_time_utc": event["event_time_utc"],
                "airport": event["airport"]["iata"],
                "weather_time": current.get("time"),
                "temperature_c": current.get("temperature_2m"),
                "precipitation_mm": current.get("precipitation"),
                "wind_speed_kts": current.get("wind_speed_10m"),
                "prediction": response.get("prediction"),
                "disruption_probability": response.get("disruption_probability"),
                "risk_band": response.get("risk_band"),
            },
            sort_keys=True,
        ),
        flush=True,
    )


def run_watch(args: argparse.Namespace, latitude: float, longitude: float, airport_name: str) -> None:
    if args.interval_seconds < 1:
        raise ValueError("--interval-seconds must be at least 1")

    iteration = 0
    print(
        f"Starting continuous live prediction for {args.airport.upper()} "
        f"every {args.interval_seconds}s. Press Ctrl+C to stop.",
        flush=True,
    )
    if args.output_jsonl:
        print(f"Appending live prediction events to {args.output_jsonl}", flush=True)
    try:
        while args.max_iterations is None or iteration < args.max_iterations:
            iteration += 1
            event = predict_once(args, latitude, longitude, airport_name)
            written_path = append_jsonl(args.output_jsonl, event)
            print_watch_event(iteration, event)
            if written_path:
                print(f"written_jsonl={written_path.resolve()}", flush=True)

            if args.max_iterations is not None and iteration >= args.max_iterations:
                break
            time.sleep(args.interval_seconds)
    except KeyboardInterrupt:
        print("\nStopped continuous live prediction.", flush=True)


def main() -> None:
    args = parse_args()
    if args.output_jsonl:
        args.output_jsonl = str(Path(args.output_jsonl).expanduser().resolve())
    latitude, longitude, airport_name = airport_coordinates(args.airport)
    if args.watch:
        run_watch(args, latitude, longitude, airport_name)
        return

    event = predict_once(args, latitude, longitude, airport_name)
    append_jsonl(args.output_jsonl, event)
    print_event(event)


if __name__ == "__main__":
    main()
