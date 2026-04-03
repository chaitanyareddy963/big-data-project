from __future__ import annotations

from pyspark.sql import functions as F
from pyspark.sql.types import StringType

from src.common.config import AppConfig
from src.common.contracts import FEATURE_COLUMNS, STREAM_CHECKPOINT_PATH, STREAM_SCORE_PATH
from src.common.logging_utils import configure_logging
from src.common.modeling import load_model_metadata
from src.common.spark import create_spark_session


def build_score_expression(metadata: dict):
    expr = F.lit(float(metadata["intercept"]))
    for feature, coeff in zip(metadata["feature_columns"], metadata["coefficients"], strict=True):
        expr = expr + F.col(feature) * F.lit(float(coeff))
    return 1 / (1 + F.exp(-expr))


def main() -> None:
    configure_logging()
    config = AppConfig()
    metadata = load_model_metadata(config.model_export_uri.rstrip("/"))
    spark = create_spark_session("stream-score")

    raw = (
        spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", config.kafka_bootstrap_servers)
        .option("subscribe", "weather.replay")
        .option("startingOffsets", "earliest")
        .load()
    )

    schema = "event_id STRING, airport_code STRING, event_time STRING, source_type STRING, temperature_c DOUBLE, wind_speed_kts DOUBLE, visibility_miles DOUBLE, precip_mm DOUBLE, pressure_hpa DOUBLE, dep_count INT, arr_count INT, avg_dep_delay_min DOUBLE, avg_arr_delay_min DOUBLE, disruption_label INT, event_hour INT, is_weekend INT, rolling_avg_dep_delay_6h DOUBLE, rolling_avg_arr_delay_6h DOUBLE, rolling_max_wind_6h DOUBLE, rolling_total_precip_6h DOUBLE, delay_pressure_index DOUBLE"

    parsed = raw.select(F.from_json(F.col("value").cast(StringType()), schema).alias("json")).select("json.*")
    scored = (
        parsed.withColumn("risk_score", build_score_expression(metadata))
        .withColumn("risk_label", F.when(F.col("risk_score") >= 0.5, 1).otherwise(0))
        .withColumn("model_version", F.lit(metadata["exported_at"]))
        .withColumn("scored_at", F.current_timestamp())
    )

    kafka_payload = scored.selectExpr(
        "CAST(event_id AS STRING) AS key",
        """to_json(named_struct(
            'event_id', event_id,
            'airport_code', airport_code,
            'event_time', event_time,
            'risk_score', risk_score,
            'risk_label', risk_label,
            'model_version', model_version,
            'scored_at', CAST(scored_at AS STRING)
        )) AS value""",
    )

    kafka_query = (
        kafka_payload.writeStream.format("kafka")
        .option("kafka.bootstrap.servers", config.kafka_bootstrap_servers)
        .option("topic", "disruption.scores")
        .option("checkpointLocation", f"{STREAM_CHECKPOINT_PATH}/kafka")
        .start()
    )

    delta_query = (
        scored.writeStream.format("delta")
        .outputMode("append")
        .option("checkpointLocation", f"{STREAM_CHECKPOINT_PATH}/delta")
        .start(STREAM_SCORE_PATH)
    )

    kafka_query.awaitTermination()
    delta_query.awaitTermination()


if __name__ == "__main__":
    main()
