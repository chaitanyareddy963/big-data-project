"""Create cleaned Bronze weather Parquet from original ARCO-ERA5 data."""

from __future__ import annotations

import argparse

from pyspark.sql import functions as F

from spark_jobs.common import create_spark_session, load_settings, normalized_timestamp, s3a_uri
from spark_jobs.validate_raw_weather import REQUIRED_COLUMNS


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--month", type=int, required=True, choices=range(1, 13))
    parser.add_argument("--mode", choices=["overwrite", "append"], default="overwrite")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = load_settings()
    spark = create_spark_session("build-bronze-arco-era5", settings)
    source = s3a_uri(
        settings.raw_bucket,
        f"arco_era5_us_airport_hourly/year={args.year}/month={args.month:02d}",
    )
    destination = s3a_uri(
        settings.lakehouse_bucket,
        f"bronze/weather/year={args.year}/month={args.month:02d}",
    )

    try:
        raw_df = spark.read.parquet(source)
        missing = sorted(set(REQUIRED_COLUMNS) - set(raw_df.columns))
        if missing:
            raise RuntimeError(f"Raw ERA5 schema is missing columns: {missing}")

        bronze_df = (
            raw_df.withColumn("time_utc", normalized_timestamp(raw_df, "time_utc"))
            .withColumn("temperature_c", F.col("2m_temperature") - F.lit(273.15))
            .withColumn(
                "dewpoint_temperature_c",
                F.col("2m_dewpoint_temperature") - F.lit(273.15),
            )
            .withColumn(
                "wind_speed_ms",
                F.sqrt(
                    F.pow(F.col("10m_u_component_of_wind"), 2)
                    + F.pow(F.col("10m_v_component_of_wind"), 2)
                ),
            )
            .withColumn("wind_speed_kts", F.col("wind_speed_ms") * F.lit(1.94384))
            .withColumn(
                "wind_gust_kts",
                F.col("10m_wind_gust_since_previous_post_processing") * F.lit(1.94384),
            )
            .withColumn("precipitation_mm", F.col("total_precipitation") * F.lit(1000.0))
            .select(
                F.col("time_utc").cast("timestamp"),
                F.col("airport_key").cast("int"),
                F.col("day").cast("int"),
                F.col("hour_utc").cast("int"),
                F.col("temperature_c").cast("double"),
                F.col("dewpoint_temperature_c").cast("double"),
                F.col("wind_speed_ms").cast("double"),
                F.col("wind_speed_kts").cast("double"),
                F.col("wind_gust_kts").cast("double"),
                F.col("precipitation_mm").cast("double"),
                F.col("surface_pressure").cast("double").alias("surface_pressure_pa"),
                F.col("mean_sea_level_pressure").cast("double").alias("mean_sea_level_pressure_pa"),
                F.col("total_cloud_cover").cast("double"),
                F.col("convective_available_potential_energy").cast("double").alias("cape_j_kg"),
            )
        )

        bronze_df.write.mode(args.mode).parquet(destination)
        print(f"Wrote Bronze weather Parquet: {destination}")
        print(f"Rows: {bronze_df.count()}")
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
