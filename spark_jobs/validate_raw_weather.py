"""Validate a month of original ARCO-ERA5 Parquet data stored in MinIO."""

from __future__ import annotations

import argparse
import json

from pyspark.sql import functions as F

from spark_jobs.common import create_spark_session, load_settings, normalized_timestamp, s3a_uri


REQUIRED_COLUMNS = [
    "time_utc",
    "airport_key",
    "day",
    "hour_utc",
    "2m_temperature",
    "2m_dewpoint_temperature",
    "10m_u_component_of_wind",
    "10m_v_component_of_wind",
    "10m_wind_gust_since_previous_post_processing",
    "surface_pressure",
    "mean_sea_level_pressure",
    "total_precipitation",
    "total_cloud_cover",
    "convective_available_potential_energy",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--month", type=int, required=True, choices=range(1, 13))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = load_settings()
    spark = create_spark_session("validate-raw-arco-era5", settings)
    source = s3a_uri(
        settings.raw_bucket,
        f"arco_era5_us_airport_hourly/year={args.year}/month={args.month:02d}",
    )

    try:
        df = spark.read.parquet(source)
        missing = sorted(set(REQUIRED_COLUMNS) - set(df.columns))
        if missing:
            raise RuntimeError(f"Raw ERA5 schema is missing columns: {missing}")

        validated_df = df.withColumn("_normalized_time_utc", normalized_timestamp(df, "time_utc"))
        summary = (
            validated_df.agg(
                F.count("*").alias("row_count"),
                F.countDistinct("airport_key").alias("airport_count"),
                F.min("_normalized_time_utc").cast("string").alias("min_time_utc"),
                F.max("_normalized_time_utc").cast("string").alias("max_time_utc"),
            )
            .first()
            .asDict()
        )
        summary["source"] = source
        summary["required_columns_present"] = True
        print(json.dumps(summary, indent=2))
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
