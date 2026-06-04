"""Build Delta Lake Bronze, Silver, and Gold tables from verified Parquet outputs."""

from __future__ import annotations

import argparse

from spark_jobs.common import create_spark_session, load_settings, s3a_uri


TABLES = [
    ("bronze/weather", "bronze_delta/weather"),
    ("bronze/bts_on_time", "bronze_delta/bts_on_time"),
    ("silver/flight_weather_daily", "silver_delta/flight_weather_daily"),
    ("gold/training_features", "gold_delta/training_features"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--month", type=int, required=True, choices=range(1, 13))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = load_settings()
    spark = create_spark_session("build-delta-lakehouse", settings, with_delta=True)
    partition = f"year={args.year}/month={args.month:02d}"

    try:
        for parquet_prefix, delta_prefix in TABLES:
            source = s3a_uri(settings.lakehouse_bucket, f"{parquet_prefix}/{partition}")
            destination = s3a_uri(settings.lakehouse_bucket, f"{delta_prefix}/{partition}")
            df = spark.read.parquet(source)
            row_count = df.count()
            df.write.format("delta").mode("overwrite").save(destination)
            readback_count = spark.read.format("delta").load(destination).count()
            if readback_count != row_count:
                raise RuntimeError(
                    f"Delta readback mismatch for {destination}: {readback_count} != {row_count}"
                )
            print(f"Wrote Delta table: {destination}")
            print(f"Rows: {readback_count}")
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
