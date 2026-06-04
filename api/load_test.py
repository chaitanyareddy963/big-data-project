"""Issue concurrent requests to demonstrate 10x API stability."""

from __future__ import annotations

import argparse
import concurrent.futures
import statistics
import time

import requests


SAMPLE = {
    "scheduled_departure_hour_local": 16.0,
    "distance_miles": 1090.0,
    "day_of_week": 2.0,
    "day_of_month": 15.0,
    "temperature_c_avg": 5.5,
    "wind_speed_kts_max": 24.0,
    "wind_gust_kts_max": 31.0,
    "precipitation_mm_sum": 6.0,
    "surface_pressure_pa_avg": 100900.0,
    "total_cloud_cover_avg": 0.75,
    "cape_j_kg_max": 80.0,
}


def invoke(url: str) -> float:
    started = time.perf_counter()
    response = requests.post(url, json={"features": SAMPLE}, timeout=10)
    response.raise_for_status()
    return time.perf_counter() - started


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:3000/predict")
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=10)
    args = parser.parse_args()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        latencies = list(pool.map(lambda _: invoke(args.url), range(args.requests)))
    print(f"Successful requests: {len(latencies)}/{args.requests}")
    print(f"Concurrency: {args.concurrency}x")
    print(f"Mean latency ms: {statistics.mean(latencies) * 1000:.2f}")
    print(f"Max latency ms: {max(latencies) * 1000:.2f}")


if __name__ == "__main__":
    main()
