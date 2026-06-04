"""Create model-ready Gold features without post-outcome target leakage."""

from __future__ import annotations

import argparse

from pyspark.sql import functions as F

from spark_jobs.common import create_spark_session, load_settings, s3a_uri


NUMERIC_FEATURES = [
    "scheduled_departure_hour_local",
    "distance_miles",
    "day_of_week",
    "day_of_month",
    "temperature_c_avg",
    "wind_speed_kts_max",
    "wind_gust_kts_max",
    "precipitation_mm_sum",
    "surface_pressure_pa_avg",
    "total_cloud_cover_avg",
    "cape_j_kg_max",
]

CATEGORICAL_FEATURES = [
    "origin",
    "reporting_airline",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--month", type=int, required=True, choices=range(1, 13))
    parser.add_argument("--mode", choices=["overwrite", "append"], default="overwrite")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = load_settings()
    spark = create_spark_session("build-gold-flight-weather-features", settings)
    source = s3a_uri(
        settings.lakehouse_bucket,
        f"silver/flight_weather_daily/year={args.year}/month={args.month:02d}",
    )
    destination = s3a_uri(
        settings.lakehouse_bucket,
        f"gold/training_features/year={args.year}/month={args.month:02d}",
    )

    try:
        silver_df = spark.read.parquet(source)
        gold_df = (
            silver_df.withColumn("day_of_week", F.dayofweek("flight_date").cast("double"))
            .withColumn("day_of_month", F.dayofmonth("flight_date").cast("double"))
            .select(
                "flight_date",
                "origin",
                "destination",
                "reporting_airline",
                *NUMERIC_FEATURES,
                F.col("label").cast("double").alias("label"),
                "label_source",
            )
            .dropna(subset=CATEGORICAL_FEATURES + NUMERIC_FEATURES + ["label"])
        )

        print(f"Silver rows: {silver_df.count()}")
        print(f"Gold rows after required-feature null filtering: {gold_df.count()}")
        gold_df.groupBy("label", "label_source").count().orderBy("label").show()
        gold_df.write.mode(args.mode).parquet(destination)
        print(f"Wrote Gold feature Parquet: {destination}")
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
