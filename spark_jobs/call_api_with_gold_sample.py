"""Call the prediction API with a real row from the Gold feature table."""

from __future__ import annotations

import argparse
import json

import requests

from spark_jobs.build_gold_features import NUMERIC_FEATURES
from spark_jobs.common import create_spark_session, load_settings, s3a_uri


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, default=2024)
    parser.add_argument("--month", type=int, choices=range(1, 13))
    parser.add_argument("--api-url", default="http://aviation-api:3000/predict")
    parser.add_argument("--origin")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = load_settings()
    spark = create_spark_session("call-api-with-real-gold-row", settings)
    key = f"gold/training_features/year={args.year}"
    if args.month:
        key = f"{key}/month={args.month:02d}"
    source = s3a_uri(settings.lakehouse_bucket, key)

    try:
        df = spark.read.parquet(source).dropna(subset=NUMERIC_FEATURES)
        if args.origin:
            df = df.filter(df.origin == args.origin.upper())
        row = df.select("flight_date", "origin", "destination", "label", *NUMERIC_FEATURES).limit(1).collect()
        if not row:
            raise RuntimeError(f"No usable Gold row found in {source}")
        record = row[0].asDict()
        features = {name: float(record[name]) for name in NUMERIC_FEATURES}
        response = requests.post(args.api_url, json={"features": features}, timeout=15)
        response.raise_for_status()
        print("Gold source:", source)
        print("Real data context:", json.dumps({k: str(record[k]) for k in ["flight_date", "origin", "destination", "label"]}))
        print("Request features:", json.dumps(features, indent=2))
        print("API response:", json.dumps(response.json(), indent=2))
    finally:
        spark.stop()


if __name__ == "__main__":
    main()

