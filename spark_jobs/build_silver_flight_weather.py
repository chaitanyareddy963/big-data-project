"""Join BTS flights with daily airport weather and create real disruption labels."""

from __future__ import annotations

import argparse

from pyspark.sql import functions as F

from spark_jobs.common import create_spark_session, load_settings, s3a_uri


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--month", type=int, required=True, choices=range(1, 13))
    parser.add_argument("--mode", choices=["overwrite", "append"], default="overwrite")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = load_settings()
    spark = create_spark_session("build-silver-flight-weather", settings)
    weather_source = s3a_uri(
        settings.lakehouse_bucket,
        f"bronze/weather/year={args.year}/month={args.month:02d}",
    )
    flights_source = s3a_uri(
        settings.lakehouse_bucket,
        f"bronze/bts_on_time/year={args.year}/month={args.month:02d}",
    )
    airports_source = s3a_uri(
        settings.raw_bucket,
        "metadata/ourairports/us_airports_selected_with_era5_grid.parquet",
    )
    destination = s3a_uri(
        settings.lakehouse_bucket,
        f"silver/flight_weather_daily/year={args.year}/month={args.month:02d}",
    )

    try:
        weather_df = spark.read.parquet(weather_source)
        flights_df = spark.read.parquet(flights_source)
        airports_df = spark.read.parquet(airports_source)

        airport_dim = (
            airports_df.filter(F.col("iata_code").isNotNull())
            .groupBy(F.upper("iata_code").alias("origin"))
            .agg(F.min(F.col("airport_key").cast("int")).alias("airport_key"))
        )

        weather_daily = (
            weather_df.withColumn("weather_date", F.to_date("time_utc"))
            .groupBy("airport_key", "weather_date")
            .agg(
                F.avg("temperature_c").alias("temperature_c_avg"),
                F.max("wind_speed_kts").alias("wind_speed_kts_max"),
                F.max("wind_gust_kts").alias("wind_gust_kts_max"),
                F.sum("precipitation_mm").alias("precipitation_mm_sum"),
                F.avg("surface_pressure_pa").alias("surface_pressure_pa_avg"),
                F.avg("total_cloud_cover").alias("total_cloud_cover_avg"),
                F.max("cape_j_kg").alias("cape_j_kg_max"),
            )
        )

        mapped_flights = flights_df.join(F.broadcast(airport_dim), "origin", "left").alias("flights")
        weather_daily = weather_daily.alias("weather")

        joined_df = (
            mapped_flights
            .join(
                weather_daily,
                (F.col("flights.airport_key") == F.col("weather.airport_key"))
                & (F.col("flights.flight_date") == F.col("weather.weather_date")),
                "left",
            )
            .select(
                "flights.*",
                "weather.weather_date",
                "weather.temperature_c_avg",
                "weather.wind_speed_kts_max",
                "weather.wind_gust_kts_max",
                "weather.precipitation_mm_sum",
                "weather.surface_pressure_pa_avg",
                "weather.total_cloud_cover_avg",
                "weather.cape_j_kg_max",
            )
        )

        silver_df = (
            joined_df.filter(F.col("weather_date").isNotNull())
            .withColumn(
                "label",
                F.when(
                    (F.coalesce(F.col("cancelled"), F.lit(0.0)) >= F.lit(1.0))
                    | (F.coalesce(F.col("arrival_delay_minutes"), F.lit(0.0)) >= F.lit(15.0)),
                    F.lit(1.0),
                ).otherwise(F.lit(0.0)),
            )
            .withColumn("label_source", F.lit("BTS_REAL_OUTCOME"))
            .drop("weather_date")
        )

        flight_count = flights_df.count()
        matched_count = silver_df.count()
        print(f"BTS flight rows: {flight_count}")
        print(f"Rows matched to airport weather: {matched_count}")
        print(f"Rows without weather match: {flight_count - matched_count}")
        silver_df.groupBy("label", "label_source").count().orderBy("label").show()

        silver_df.write.mode(args.mode).parquet(destination)
        print(f"Wrote Silver flight-weather Parquet: {destination}")
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
