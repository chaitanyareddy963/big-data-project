"""Replay historical Gold feature rows as a dataset-only simulation.

This script is for the final demonstration. It proves that held-out or selected
Gold feature rows from the downloaded lakehouse dataset can be used in a
streaming-style test-set replay. Each replay event is published to Kafka for
streaming evidence. The script also calls the deployed API directly for scoring
and logs each prediction to JSONL for auditability. The API does not consume
from Kafka in this demo.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from kafka import KafkaProducer

from spark_jobs.build_gold_features import NUMERIC_FEATURES
from spark_jobs.common import create_spark_session, load_settings, s3a_uri


DEFAULT_TOPIC = "simulation.prediction.requests"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, default=2024)
    parser.add_argument("--month", type=int, default=1)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--delay-seconds", type=float, default=0.1)
    parser.add_argument("--api-url", default="http://aviation-api:3000/predict")
    parser.add_argument("--kafka-bootstrap", default="kafka:9092")
    parser.add_argument("--topic", default=DEFAULT_TOPIC)
    parser.add_argument("--output-jsonl", default=None)
    parser.add_argument("--source", default="dataset_simulation")
    parser.add_argument("--no-kafka", action="store_true", help="Call the API but skip Kafka replay publishing.")
    return parser.parse_args()


def gold_uri(year: int, month: int) -> str:
    settings = load_settings()
    return s3a_uri(settings.lakehouse_bucket, f"gold/training_features/year={year}/month={month:02d}")


def load_rows(year: int, month: int, limit: int) -> list[dict[str, Any]]:
    if limit < 1:
        raise ValueError("--limit must be at least 1")
    settings = load_settings()
    spark = create_spark_session("simulate-gold-stream-predict", settings)
    try:
        path = gold_uri(year, month)
        columns = [
            "flight_date",
            "origin",
            "destination",
            "label",
            *NUMERIC_FEATURES,
        ]
        available = spark.read.parquet(path)
        selected_columns = [column for column in columns if column in available.columns]
        rows = (
            available.select(*selected_columns)
            .orderBy("flight_date", "origin", "destination")
            .limit(limit)
            .collect()
        )
        return [row.asDict(recursive=True) for row in rows]
    finally:
        spark.stop()


def row_features(row: dict[str, Any]) -> dict[str, float]:
    missing = sorted(name for name in NUMERIC_FEATURES if name not in row)
    if missing:
        raise RuntimeError(f"Gold row is missing required features: {missing}")
    return {name: float(row[name] or 0.0) for name in NUMERIC_FEATURES}


def create_producer(bootstrap: str) -> KafkaProducer:
    return KafkaProducer(
        bootstrap_servers=bootstrap,
        value_serializer=lambda value: json.dumps(value, sort_keys=True).encode("utf-8"),
        key_serializer=lambda value: value.encode("utf-8"),
        linger_ms=5,
    )


def append_jsonl(path: str | None, event: dict[str, Any]) -> Path | None:
    if not path:
        return None
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")
    return output_path


def call_api(api_url: str, features: dict[str, float], source: str) -> dict[str, Any]:
    response = requests.post(api_url, json={"features": features, "source": source}, timeout=15)
    response.raise_for_status()
    return response.json()


def compact_print(event: dict[str, Any]) -> None:
    prediction = event["api_response"]
    source = event["source_event"]
    print(
        json.dumps(
            {
                "sequence": event["sequence"],
                "flight_date": source.get("flight_date"),
                "origin": source.get("origin"),
                "destination": source.get("destination"),
                "actual_label": source.get("label"),
                "prediction": prediction.get("prediction"),
                "risk_band": prediction.get("risk_band"),
                "disruption_probability": prediction.get("disruption_probability"),
            },
            sort_keys=True,
        ),
        flush=True,
    )


def main() -> None:
    args = parse_args()
    if args.output_jsonl:
        args.output_jsonl = str(Path(args.output_jsonl).expanduser().resolve())
    rows = load_rows(args.year, args.month, args.limit)
    if not rows:
        raise RuntimeError(f"No Gold rows found for year={args.year}, month={args.month:02d}")

    producer = None if args.no_kafka else create_producer(args.kafka_bootstrap)
    print(
        f"Replaying {len(rows)} historical Gold rows from {gold_uri(args.year, args.month)}. "
        f"Kafka evidence topic={args.topic if producer else '[disabled]'}; "
        f"API scoring endpoint={args.api_url}",
        flush=True,
    )
    if args.output_jsonl:
        print(f"Appending replay events to {args.output_jsonl}", flush=True)

    try:
        for index, row in enumerate(rows, start=1):
            features = row_features(row)
            source_event = {
                "event_time_utc": datetime.now(timezone.utc).isoformat(),
                "stream_type": "gold_feature_replay",
                "dataset_year": args.year,
                "dataset_month": args.month,
                "flight_date": str(row.get("flight_date")),
                "origin": row.get("origin"),
                "destination": row.get("destination"),
                "label": float(row["label"]) if row.get("label") is not None else None,
                "features": features,
            }
            api_response = call_api(args.api_url, features, args.source)
            event = {
                "sequence": index,
                "source": args.source,
                "source_event": source_event,
                "api_response": api_response,
            }
            if producer:
                key = f"{args.year}-{args.month:02d}-{index:06d}"
                producer.send(args.topic, key=key, value=event)
            append_jsonl(args.output_jsonl, event)
            compact_print(event)
            if args.delay_seconds > 0 and index < len(rows):
                time.sleep(args.delay_seconds)
        if producer:
            producer.flush()
    finally:
        if producer:
            producer.close()


if __name__ == "__main__":
    main()
