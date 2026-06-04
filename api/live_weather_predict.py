"""Fetch live airport weather from Open-Meteo and call the prediction API.

This is an inference-only demo. Training still uses the historical ARCO-ERA5
and BTS lakehouse tables; the live API request shows how current conditions can
be transformed into the deployed model's feature contract.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime

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


def main() -> None:
    args = parse_args()
    latitude, longitude, airport_name = airport_coordinates(args.airport)
    weather = fetch_live_weather(latitude, longitude)
    features = build_features(weather, args.distance_miles)
    response = requests.post(args.api_url, json={"features": features}, timeout=15)
    response.raise_for_status()
    print("Live airport:", json.dumps({"iata": args.airport.upper(), "name": airport_name, "latitude": latitude, "longitude": longitude}))
    print("Open-Meteo current:", json.dumps(weather["current"], indent=2))
    print("Prediction features:", json.dumps(features, indent=2))
    print("API response:", json.dumps(response.json(), indent=2))


if __name__ == "__main__":
    main()

