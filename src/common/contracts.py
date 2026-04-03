from __future__ import annotations

RAW_COLUMNS = [
    "event_id",
    "airport_code",
    "event_time",
    "source_type",
    "temperature_c",
    "wind_speed_kts",
    "visibility_miles",
    "precip_mm",
    "pressure_hpa",
    "dep_count",
    "arr_count",
    "avg_dep_delay_min",
    "avg_arr_delay_min",
    "disruption_label",
]

SILVER_COLUMNS = RAW_COLUMNS + [
    "event_date",
    "event_hour",
    "is_weekend",
    "ingest_time",
]

FEATURE_COLUMNS = [
    "temperature_c",
    "wind_speed_kts",
    "visibility_miles",
    "precip_mm",
    "pressure_hpa",
    "dep_count",
    "arr_count",
    "avg_dep_delay_min",
    "avg_arr_delay_min",
    "event_hour",
    "is_weekend",
    "rolling_avg_dep_delay_6h",
    "rolling_avg_arr_delay_6h",
    "rolling_max_wind_6h",
    "rolling_total_precip_6h",
    "delay_pressure_index",
]

GOLD_COLUMNS = [
    "event_id",
    "airport_code",
    "event_time",
    *FEATURE_COLUMNS,
    "disruption_label",
]

SCORE_COLUMNS = [
    "event_id",
    "airport_code",
    "event_time",
    "risk_score",
    "risk_label",
    "model_version",
    "scored_at",
]

MODEL_NAME = "disruption-risk-local"
MODEL_EXPORT_URI = "s3://mlflow/serving/current/"
RAW_BUCKET = "raw"
BRONZE_BUCKET = "bronze"
SILVER_BUCKET = "silver"
GOLD_BUCKET = "gold"
MLFLOW_BUCKET = "mlflow"

BRONZE_TABLE_PATH = "s3a://bronze/aviation_disruptions"
SILVER_TABLE_PATH = "s3a://silver/aviation_disruptions"
GOLD_TABLE_PATH = "s3a://gold/aviation_features"
GOLD_EXPORT_PREFIX = "feature_exports/current"
STREAM_SCORE_PATH = "s3a://gold/stream_scores"
STREAM_CHECKPOINT_PATH = "/workspace/checkpoints/stream_score"

DEFAULT_AIRPORTS = ["ATL", "JFK", "ORD", "DFW", "DEN"]
