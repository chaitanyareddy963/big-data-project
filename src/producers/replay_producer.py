from __future__ import annotations

import argparse
import csv
import json
import time
from collections import deque

from kafka import KafkaProducer

from src.common.config import AppConfig
from src.common.logging_utils import configure_logging


def normalize_types(row: dict) -> dict:
    return {
        "event_id": row["event_id"],
        "airport_code": row["airport_code"],
        "event_time": row["event_time"],
        "source_type": row["source_type"],
        "temperature_c": float(row["temperature_c"]),
        "wind_speed_kts": float(row["wind_speed_kts"]),
        "visibility_miles": float(row["visibility_miles"]),
        "precip_mm": float(row["precip_mm"]),
        "pressure_hpa": float(row["pressure_hpa"]),
        "dep_count": int(row["dep_count"]),
        "arr_count": int(row["arr_count"]),
        "avg_dep_delay_min": float(row["avg_dep_delay_min"]),
        "avg_arr_delay_min": float(row["avg_arr_delay_min"]),
        "disruption_label": int(row["disruption_label"]),
    }


def enrich(row: dict, history: deque) -> dict:
    history.append(row)
    dep = [item["avg_dep_delay_min"] for item in history]
    arr = [item["avg_arr_delay_min"] for item in history]
    wind = [item["wind_speed_kts"] for item in history]
    precip = [item["precip_mm"] for item in history]
    row["event_hour"] = int(row["event_time"][11:13])
    row["is_weekend"] = 0
    row["rolling_avg_dep_delay_6h"] = round(sum(dep) / len(dep), 3)
    row["rolling_avg_arr_delay_6h"] = round(sum(arr) / len(arr), 3)
    row["rolling_max_wind_6h"] = round(max(wind), 3)
    row["rolling_total_precip_6h"] = round(sum(precip), 3)
    row["delay_pressure_index"] = round(
        (row["avg_dep_delay_min"] + row["avg_arr_delay_min"]) / row["pressure_hpa"],
        6,
    )
    return row


def main() -> None:
    configure_logging()
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--topic", default="weather.replay")
    parser.add_argument("--speed", type=float, default=1.0)
    args = parser.parse_args()

    config = AppConfig()
    producer = KafkaProducer(
        bootstrap_servers=config.kafka_bootstrap_servers,
        value_serializer=lambda value: json.dumps(value).encode("utf-8"),
        key_serializer=lambda value: value.encode("utf-8"),
    )

    history_by_airport: dict[str, deque] = {}
    with open(args.input, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            typed_row = normalize_types(row)
            history = history_by_airport.setdefault(typed_row["airport_code"], deque(maxlen=6))
            payload = enrich(typed_row, history)
            producer.send(args.topic, key=typed_row["event_id"], value=payload)
            producer.flush()
            time.sleep(max(0.01, 1.0 / max(args.speed, 1.0)))


if __name__ == "__main__":
    main()
