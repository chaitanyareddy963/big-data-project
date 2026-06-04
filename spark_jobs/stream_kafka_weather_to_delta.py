"""Consume Kafka weather events with Spark Structured Streaming into Delta Lake."""

from __future__ import annotations

import argparse

from pyspark.sql import functions as F
from pyspark.sql.types import DoubleType, IntegerType, StringType, StructField, StructType

from spark_jobs.common import create_spark_session, load_settings, s3a_uri


EVENT_SCHEMA = StructType(
    [
        StructField("airport_key", IntegerType(), False),
        StructField("timestamp_utc", StringType(), False),
        StructField("temperature_c", DoubleType(), True),
        StructField("wind_speed_kts", DoubleType(), True),
        StructField("precipitation_mm", DoubleType(), True),
        StructField("surface_pressure_pa", DoubleType(), True),
    ]
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trigger-once", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = load_settings()
    spark = create_spark_session(
        "stream-kafka-weather-to-delta",
        settings,
        with_delta=True,
        extra_packages=["org.apache.spark:spark-sql-kafka-0-10_2.13:4.0.0"],
    )
    destination = s3a_uri(settings.lakehouse_bucket, "bronze_delta/kafka_weather_events")
    checkpoint = s3a_uri(settings.lakehouse_bucket, "_checkpoints/kafka_weather_events")

    try:
        kafka_df = (
            spark.readStream.format("kafka")
            .option("kafka.bootstrap.servers", "kafka:9092")
            .option("subscribe", "weather.raw")
            .option("startingOffsets", "earliest")
            .load()
        )
        events_df = (
            kafka_df.select(F.from_json(F.col("value").cast("string"), EVENT_SCHEMA).alias("event"))
            .select("event.*")
            .withColumn("timestamp_utc", F.to_timestamp("timestamp_utc"))
            .withColumn("ingested_at_utc", F.current_timestamp())
        )
        writer = (
            events_df.writeStream.format("delta")
            .outputMode("append")
            .option("checkpointLocation", checkpoint)
        )
        if args.trigger_once:
            writer = writer.trigger(availableNow=True)
        query = writer.start(destination)
        print(f"Structured Streaming destination: {destination}")
        query.awaitTermination()
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
